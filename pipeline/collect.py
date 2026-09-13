"""概念リスト → 証拠バンドル。

このスクリプトは **判定をしない**。事実を集めて並べるだけ。
4値判定（欠落／薄い／実質包含／判定不能）は人間が judgments/ に書く。

自動判定を信じないのは、実測で偽陽性が55%あったから（計画書 §2 F2, F6）。
機械にできるのは「何を調べて、何が見つからなかったか」を漏れなく残すところまで。

使い方:
    python3 -m pipeline.collect concepts/living.toml
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import sys
import tomllib
from datetime import datetime, timezone

from . import metrics, wikiclient

TOOL_VERSION = "0.1.0"
ROOT = pathlib.Path(__file__).resolve().parent.parent

# 機械が自動で比較対象に選んでよい候補の出どころ。**sitelink だけ**。
#
# Wikidata の ja ラベルや別名、人手で書いた候補タイトルは「典拠」ではない。
# 同名異義語・曖昧さ回避・別概念へのリダイレクトを引くため。実測（2026-09-08）:
#   satiety-value      → 「満腹感」（「食」へ転送）を採用 → 文字比 7.72
#   food-fortification → 「栄養補助食品」を採用（栄養強化とは別概念）
#   damp-structural    → 「雨漏り」を採用（建物の湿気とは別概念）
# これらは人間が「同一概念だ」と確認してはじめて比較対象になる。
AUTO_SELECTABLE_SOURCES = {"wikidata_sitelink"}

# 候補として存在確認まではする出どころ（比較対象の自動選定には使わない）
CHECKED_SOURCES = {"wikidata_sitelink", "wikidata_label", "wikidata_alias", "manual"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def page_observation(project: str, title: str) -> dict:
    """1ページ分の観測。存在しない場合も、取得に失敗した場合もそのまま記録する。

    「存在しない」と「取得できなかった」を混同しない。混同すると、
    ネットワークの不調が「日本語版に記事が無い」という主張に化ける。
    """
    page = wikiclient.fetch_page(project, title)
    obs = {k: v for k, v in page.items() if not k.startswith("_")}
    if page["fetch_failed"] or not page["exists"]:
        return obs

    if page["_plaintext"] is not None:
        obs.update(metrics.body_metrics(page["_plaintext"]))
    else:
        # 平文が取れなかった。文字数は「0」ではなく「不明」にする。
        obs["body_chars"] = None
        obs["plaintext_missing"] = True
    obs.update(metrics.footnote_metrics(page["_wikitext"] or ""))
    return obs


def collect_concept(c: dict) -> dict:
    """1概念分の証拠バンドルを組み立てる。"""
    started = now_iso()
    record: dict = {
        "concept_id": c["id"],
        "theme": c["theme"],
        "why": c.get("why"),
        "eligibility": {
            "criterion": c.get("eligibility"),
            "status": c.get("eligibility_status"),
            "note": c.get("eligibility_note"),
            # 「日本語資料2件」の実URLは人間が judgments 側に記録する。
            "japanese_sources": [],
        },
        "collected_at_start": started,
        "en": None,
        "wikidata": None,
        "ja_candidates": [],
        "ja_selected": None,
        "comparison": None,
    }

    # --- 英語版 ---------------------------------------------------------
    en = page_observation("en", c["en_title"])
    record["en"] = en

    # --- Wikidata（jaラベル・別名・ja sitelink） -------------------------
    qid = en.get("wikidata_qid")
    wd = None
    if qid:
        wd = wikiclient.fetch_wikidata_entity(qid)
        record["wikidata"] = wd

    # --- 日本語版の候補タイトルを集める ---------------------------------
    # 候補ごとに「どこから来た候補か」を必ず残す。
    # 後から第三者が「探し方が甘かったのでは」を検証できるようにするため。
    candidates: list[dict] = []
    seen: set[str] = set()

    def add(title: str | None, source: str) -> None:
        if not title:
            return
        key = title.strip()
        if not key or key in seen:
            return
        seen.add(key)
        candidates.append({"title": key, "source": source})

    if wd:
        add(wd.get("ja_sitelink"), "wikidata_sitelink")
        add(wd.get("ja_label"), "wikidata_label")
        for a in wd.get("ja_aliases", []):
            add(a, "wikidata_alias")
    for t in c.get("ja_candidates", []):
        add(t, "manual")

    # --- 候補を1件ずつ完全一致で存在確認 --------------------------------
    resolved: list[dict] = []
    for cand in candidates:
        obs = page_observation("ja", cand["title"])
        resolved.append({"candidate": cand["title"], "candidate_source": cand["source"], **obs})
    record["ja_candidates"] = resolved

    # --- 全文検索は「人間が実質包含を探すための材料」としてのみ集める -----
    #
    # ここで得たページは **絶対に比較対象に選ばない**。
    # 実測（2026-09-08）で、検索結果を選定に混ぜたところ
    #   パラソーシャル関係 → 「バーチャルYouTuber」を採用（文字比 0.73）
    #   スクリーンタイム   → 「24時間テレビ」を採用（文字比 2.75）
    # という誤りが出た。全文検索は語の一部が一致しただけのページを返す。
    # 上位・隣接記事に記述が含まれている（＝実質包含）かどうかは、
    # 人間がこれらのページを読んで判定する。
    search_records = []
    for q in c.get("ja_candidates", [])[:2]:
        s = wikiclient.search("ja", q, limit=3)
        search_records.append({"query": s["query"], "hits": s["hits"], "request": s["request"]})
    record["ja_search_context"] = search_records

    # --- 比較対象に使う日本語ページを選ぶ -------------------------------
    # 自動選定は「Wikidata の ja sitelink が実在する場合」だけ。
    # それ以外は選ばず、人間が judgments 側で候補を昇格させる。
    selected = None
    sitelink = (wd or {}).get("ja_sitelink")
    for r in resolved:
        if (
            r["candidate_source"] in AUTO_SELECTABLE_SOURCES
            and sitelink
            and r["candidate"] == sitelink
            and r["exists"]
        ):
            selected = r
            break
    record["ja_selected"] = selected["candidate"] if selected else None
    record["ja_selected_source"] = selected["candidate_source"] if selected else None

    # 人間が「同一概念か」を確認して昇格させる候補。存在するものだけ挙げる。
    record["ja_promotable_candidates"] = [
        {
            "candidate": r["candidate"],
            "source": r["candidate_source"],
            "resolved_title": r.get("resolved_title"),
            "redirected": r.get("redirected"),
            "body_chars": r.get("body_chars"),
        }
        for r in resolved
        if r["exists"] and r["candidate_source"] in CHECKED_SOURCES and r is not selected
    ]
    record["requires_human_selection"] = selected is None and bool(record["ja_promotable_candidates"])

    # --- 観測値の比較 ---------------------------------------------------
    # 取得に失敗した候補が1件でもあれば、比較全体を無効にする。
    # 「取得できなかった」を「記事が無い」として集計しないため。
    failures = [r["candidate"] for r in resolved if r.get("fetch_failed")]
    if en.get("fetch_failed"):
        failures.append(f"en:{c['en_title']}")
    if (wd or {}).get("fetch_failed"):
        failures.append(f"wikidata:{qid}")

    if failures:
        record["comparison"] = {"invalid": True, "reason": "fetch_failed", "failed_targets": failures}
    elif en.get("exists"):
        en_chars = en.get("body_chars")
        ja_chars = (selected or {}).get("body_chars")
        ratio = None
        if en_chars and ja_chars is not None:
            ratio = round(ja_chars / en_chars, 4)
        record["comparison"] = {
            "invalid": False,
            "en_body_chars": en_chars,
            "ja_body_chars": ja_chars,
            # 「情報量の比率」ではない。本文文字数の比でしかない。
            "body_char_ratio": ratio,
            "en_top_level_sections": en.get("top_level_sections"),
            "ja_top_level_sections": (selected or {}).get("top_level_sections"),
            "en_direct_ref_domains": en.get("external_ref_domains"),
            "ja_direct_ref_domains": (selected or {}).get("external_ref_domains"),
            "en_last_modified": en.get("revision_timestamp"),
            "ja_last_modified": (selected or {}).get("revision_timestamp"),
            "ja_checked_candidate_exists": any(
                r["exists"] for r in resolved if r["candidate_source"] in CHECKED_SOURCES
            ),
            "ja_sitelink_exists": selected is not None,
            "ja_selected_is_redirect_target": bool((selected or {}).get("redirected")),
        }
    else:
        record["comparison"] = {"invalid": True, "reason": "en_article_not_found"}

    record["collected_at_end"] = now_iso()
    return record


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    src = pathlib.Path(argv[1])
    if not src.is_absolute():
        src = ROOT / src
    raw_bytes = src.read_bytes()
    cfg = tomllib.loads(raw_bytes.decode("utf-8"))
    input_sha256 = hashlib.sha256(raw_bytes).hexdigest()

    concepts = cfg.get("concept", [])
    run_started = now_iso()
    run_id = "run-" + run_started.replace(":", "").replace("-", "").replace("+0000", "Z")

    # API応答の生データを残す。ハッシュだけでは第三者が再現・反証できない。
    wikiclient.set_raw_dir(ROOT / "data" / "raw" / run_id)

    bundles = []
    for i, c in enumerate(concepts, 1):
        print(f"[{i:>2}/{len(concepts)}] {c['id']} … ", end="", flush=True)
        b = collect_concept(c)
        bundles.append(b)
        comp = b.get("comparison") or {}
        if comp.get("invalid"):
            state = f"⚠ 比較無効（{comp.get('reason')}）"
        elif comp.get("ja_sitelink_exists"):
            state = f"「{b['ja_selected']}」 文字比 {comp.get('body_char_ratio')}"
        elif b.get("requires_human_selection"):
            n = len(b.get("ja_promotable_candidates") or [])
            state = f"ja sitelink 無し / 要人手選定（候補{n}件）"
        else:
            state = "ja sitelink・候補ともに不在（欠落の候補）"
        print(state)

    out = {
        "schema_version": "1.0.0",
        "run_id": run_id,
        "edition": cfg.get("edition"),
        "tool_version": TOOL_VERSION,
        "calc_version": metrics.CALC_VERSION,
        "python_version": sys.version.split()[0],
        "input_file": str(src.relative_to(ROOT)) if src.is_relative_to(ROOT) else str(src),
        "input_sha256": input_sha256,
        "raw_response_dir": f"data/raw/{run_id}",
        "user_agent": wikiclient.USER_AGENT,
        "run_started_at": run_started,
        "run_finished_at": now_iso(),
        "concept_count": len(bundles),
        "notes": [
            "このファイルは観測記録であり、判定ではない。4値判定は judgments/ にある。",
            "各ページの本文・wikitext・改訂IDは1リクエストで取得しており、同一 revision に固定されている。",
            "body_chars は附録節（脚注/出典/関連項目/外部リンク/References/Further reading 等）を、その子節ごと除外した本文の文字数（空白を除く）。",
            "external_ref_domains は wikitext に直接書かれた <ref>...</ref> 内のURLのみを対象とし、"
            "Wikimedia・短縮URL・SNS・識別子リゾルバを除いた eTLD+1 のユニーク数。"
            "{{sfn}}/{{harvnb}}/{{efn}}/{{reflist|refs=}} 形式の脚注は拾えないため系統的に過少計上になる。"
            "その度合いは template_footnote_markers で確認できる。",
            "eTLD+1 は同梱の簡易サフィックス表で求めている。完全な Public Suffix List ではないため、"
            "github.io や blogspot.com のようなホスティングは1発行元に潰れる。",
            "ja_selected は Wikidata の ja sitelink が実在する場合にのみ自動で決まる。"
            "ラベル・別名・人手候補は同名異義語を引くため自動選定に使わない（要人手選定）。",
            "API応答の生データは raw_response_dir に応答の SHA-256 をファイル名として gzip 保存してある。",
        ],
        "concepts": bundles,
    }

    outdir = ROOT / "data" / "evidence"
    outdir.mkdir(parents=True, exist_ok=True)
    path = outdir / f"{cfg.get('edition','edition')}-{run_id}.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    latest = outdir / f"{cfg.get('edition','edition')}-latest.json"
    latest.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n証拠バンドル: {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
