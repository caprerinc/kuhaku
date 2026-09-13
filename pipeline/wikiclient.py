"""Wikipedia / Wikidata の読み取りクライアント。

設計方針:
  - 標準ライブラリのみ。第三者が pip install なしで再現できることを最優先する。
  - すべてのリクエストURLと、応答本文の SHA-256 を記録する。
    「いつ取得したか」だけでは再現も反証もできないため（revision ID と応答ハッシュが再現性の核）。
  - このモジュールは判定をしない。事実の収集だけを行う。
"""

from __future__ import annotations

import gzip
import hashlib
import json
import pathlib
import time
import urllib.error
import urllib.parse
import urllib.request

USER_AGENT = "kuhaku-zukan/0.1 (https://kuhaku.caprer.co.jp)"

# 連続リクエストの間隔。Wikimedia の利用規約に沿って控えめにする。
REQUEST_INTERVAL_SEC = 0.2

_last_request_at = 0.0

# API応答の生データを保存する先。ハッシュだけでは第三者が再現・反証できないため、
# 応答そのものを残す。ファイル名は応答の SHA-256 なので重複は自動的に排除される。
_raw_dir: pathlib.Path | None = None


def set_raw_dir(path: pathlib.Path | None) -> None:
    global _raw_dir
    _raw_dir = path
    if path is not None:
        path.mkdir(parents=True, exist_ok=True)


def _persist(body: str, sha: str) -> None:
    if _raw_dir is None or not body:
        return
    dest = _raw_dir / f"{sha}.json.gz"
    if dest.exists():
        return
    with gzip.open(dest, "wt", encoding="utf-8") as f:
        f.write(body)


class FetchResult:
    """1回のAPI呼び出しの記録。証拠バンドルにそのまま埋め込める形にしておく。"""

    def __init__(self, url: str, status: int, body: str, error: str | None = None):
        self.url = url
        self.status = status
        self.body = body
        self.error = error
        self.sha256 = hashlib.sha256(body.encode("utf-8")).hexdigest() if body else None

    def json(self):
        return json.loads(self.body)

    def as_record(self) -> dict:
        """証拠バンドル用。応答本文そのものは持たせない（巨大になるため）。"""
        return {
            "url": self.url,
            "http_status": self.status,
            "response_sha256": self.sha256,
            "error": self.error,
        }


def _throttle() -> None:
    global _last_request_at
    wait = REQUEST_INTERVAL_SEC - (time.monotonic() - _last_request_at)
    if wait > 0:
        time.sleep(wait)
    _last_request_at = time.monotonic()


def fetch(url: str, *, retries: int = 3) -> FetchResult:
    """GET して FetchResult を返す。失敗は例外にせず記録として残す。

    失敗を握りつぶさないのは、「取得できなかった」ことも証拠の一部だから。
    取得失敗を「記事が無い」と取り違えるのが、このプロジェクトが最も避けたい誤りにあたる。
    """
    last_error = None
    for attempt in range(retries):
        _throttle()
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = resp.read().decode("utf-8")
                result = FetchResult(url, resp.status, body)
                _persist(body, result.sha256)
                return result
        except urllib.error.HTTPError as e:
            last_error = f"HTTP {e.code}"
            if e.code < 500:
                return FetchResult(url, e.code, "", last_error)
        except Exception as e:  # noqa: BLE001 - ネットワーク例外は種類を問わず記録する
            last_error = f"{type(e).__name__}: {e}"
        time.sleep(1.5 * (attempt + 1))
    return FetchResult(url, 0, "", last_error)


def api(project: str, params: dict) -> str:
    """action=api のURLを組み立てる。project は 'en' / 'ja'。"""
    p = {"format": "json", "formatversion": "2", **params}
    return f"https://{project}.wikipedia.org/w/api.php?" + urllib.parse.urlencode(p)


def wikidata_api(params: dict) -> str:
    p = {"format": "json", "formatversion": "2", **params}
    return "https://www.wikidata.org/w/api.php?" + urllib.parse.urlencode(p)


# --------------------------------------------------------------------------
# 取得関数
# --------------------------------------------------------------------------


def fetch_page(project: str, title: str) -> dict:
    """タイトルを解決し、リビジョン・wikitext・平文を **1リクエストで** 取得する。

    平文（extracts）を別リクエストにすると、記録した revision と本文文字数が
    別の版になりうる。同一リクエストにすることで、すべての観測値が
    ひとつの revision に固定される。

    返り値には「見つからなかった」ことも「取得に失敗した」ことも明示的に入る。
    取得失敗を「記事が無い」と取り違えるのが、このプロジェクトが最も避けたい誤り。
    """
    url = api(
        project,
        {
            "action": "query",
            "prop": "revisions|extracts|pageprops",
            "rvprop": "ids|timestamp|size|sha1|content",
            "rvslots": "main",
            "explaintext": "1",
            "exsectionformat": "wiki",
            "redirects": "1",
            "titles": title,
        },
    )
    res = fetch(url)
    out = {
        "requested_title": title,
        "project": project,
        "fetch_failed": False,
        "exists": False,
        "resolved_title": None,
        "redirected": False,
        "redirect_chain": [],
        "is_redirect_page": False,
        "revid": None,
        "revision_timestamp": None,
        "revision_sha1": None,
        "wikitext_bytes": None,
        "wikitext_sha256": None,
        "plaintext_sha256": None,
        "wikidata_qid": None,
        "request": res.as_record(),
        "_wikitext": None,  # 証拠バンドルには書き出さない作業用フィールド
        "_plaintext": None,
    }
    if res.status != 200 or not res.body:
        out["fetch_failed"] = True
        return out

    data = res.json()
    q = data.get("query", {})
    chain = [(r["from"], r["to"]) for r in q.get("redirects", [])]
    out["redirect_chain"] = [{"from": a, "to": b} for a, b in chain]
    out["redirected"] = bool(chain)

    pages = q.get("pages", [])
    if not pages:
        return out
    page = pages[0]
    if page.get("missing"):
        return out

    out["exists"] = True
    out["resolved_title"] = page.get("title")
    out["wikidata_qid"] = (page.get("pageprops") or {}).get("wikibase_item")

    plaintext = page.get("extract")
    if plaintext is not None:
        out["_plaintext"] = plaintext
        out["plaintext_sha256"] = hashlib.sha256(plaintext.encode("utf-8")).hexdigest()

    revs = page.get("revisions") or []
    if revs:
        rev = revs[0]
        wikitext = (rev.get("slots", {}).get("main", {}) or {}).get("content", "")
        out["revid"] = rev.get("revid")
        out["revision_timestamp"] = rev.get("timestamp")
        out["revision_sha1"] = rev.get("sha1")
        out["wikitext_bytes"] = rev.get("size")
        out["wikitext_sha256"] = hashlib.sha256(wikitext.encode("utf-8")).hexdigest()
        out["_wikitext"] = wikitext
        # リダイレクト「ページ」を実体と取り違えないための明示チェック。
        # redirects=1 で解決済みのはずだが、二重リダイレクト等の取りこぼしを検出する。
        stripped = wikitext.lstrip()
        out["is_redirect_page"] = stripped[:9].upper().startswith("#REDIRECT") or stripped.startswith("#転送")
    return out


def fetch_wikidata_entity(qid: str) -> dict:
    """Wikidata から ja ラベル・別名・各言語版へのリンクを取得する。"""
    url = wikidata_api(
        {
            "action": "wbgetentities",
            "ids": qid,
            "props": "labels|aliases|sitelinks",
            "languages": "ja|en",
        }
    )
    res = fetch(url)
    out = {
        "qid": qid,
        "entity_lastrevid": None,
        "fetch_failed": False,
        "ja_label": None,
        "en_label": None,
        "ja_aliases": [],
        "ja_sitelink": None,
        "sitelink_count": None,
        "request": res.as_record(),
    }
    if res.status != 200 or not res.body:
        out["fetch_failed"] = True
        return out
    ent = (res.json().get("entities") or {}).get(qid)
    if not ent:
        out["fetch_failed"] = True
        return out
    out["entity_lastrevid"] = ent.get("lastrevid")
    labels = ent.get("labels") or {}
    out["ja_label"] = (labels.get("ja") or {}).get("value")
    out["en_label"] = (labels.get("en") or {}).get("value")
    out["ja_aliases"] = [a["value"] for a in (ent.get("aliases") or {}).get("ja", [])]
    sitelinks = ent.get("sitelinks") or {}
    out["ja_sitelink"] = (sitelinks.get("jawiki") or {}).get("title")
    out["sitelink_count"] = len(sitelinks)
    return out


def search(project: str, query: str, limit: int = 5) -> dict:
    """全文検索。**候補の生成にのみ使う。存在判定には使わない。**

    実測（2026-09-08）で、部分一致は「親の燃え尽き」→「あしたのジョー」のような
    誤爆を起こした。ここで得た候補は必ず完全一致チェックに通すこと。
    """
    url = api(
        project,
        {"action": "query", "list": "search", "srsearch": query, "srlimit": limit, "srprop": "size"},
    )
    res = fetch(url)
    out = {"query": query, "hits": [], "request": res.as_record()}
    if res.status == 200 and res.body:
        out["hits"] = [
            {"title": h["title"], "wikitext_bytes": h.get("size")}
            for h in res.json().get("query", {}).get("search", [])
        ]
    return out
