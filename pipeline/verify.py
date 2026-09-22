"""公開した数字を、保存してある生データから作り直して照合する。

このリポジトリは「第三者が同じ結果に到達できる」と主張し、改訂IDと応答のSHA-256を
公開している。しかし**それを検算する手段を出していなかった**。主張だけあって道具が無い
状態は、このプロジェクトが批判している「差分は出せるが検証はしない」と同じである。

2つの検査をする。

  完全性 (--offline, 既定)
    ネットワークを使わない。data/raw に保存した応答から観測値を作り直し、
    公開した数字と一致するかを見る。一致すれば「公開値は保存された証拠から
    導ける」ことが確かめられる。

  乖離 (--drift)
    Wikipedia に現在の改訂IDだけを問い合わせ、測定時から記事が変わっていないかを見る。
    変わっていること自体は誤りではない。**いつの時点の数字かを読者に示すため**に測る。

使い方:
    python3 -m pipeline.verify              # 完全性のみ（ネットワーク不要）
    python3 -m pipeline.verify --drift      # 乖離もあわせて見る
終了コード 1 で不一致あり。
"""

from __future__ import annotations

import gzip
import hashlib
import json
import pathlib
import sys
import tomllib

from . import metrics

ROOT = pathlib.Path(__file__).resolve().parent.parent


def load_bundle() -> dict:
    p = ROOT / "data" / "evidence" / "living-latest.json"
    return json.loads(p.read_text(encoding="utf-8"))


def raw_path(run_id: str, sha: str) -> pathlib.Path:
    return ROOT / "data" / "raw" / run_id / f"{sha}.json.gz"


def read_raw(run_id: str, sha: str) -> str | None:
    p = raw_path(run_id, sha)
    if not p.exists():
        return None
    with gzip.open(p, "rt", encoding="utf-8") as f:
        return f.read()


# --------------------------------------------------------------------------
# 完全性: 保存した応答から観測値を作り直す
# --------------------------------------------------------------------------


def page_from_response(body: str) -> dict | None:
    """保存した応答から、ページ1件分の wikitext と平文を取り出す。"""
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return None
    pages = (data.get("query") or {}).get("pages") or []
    if not pages or pages[0].get("missing"):
        return None
    page = pages[0]
    revs = page.get("revisions") or []
    wikitext = ""
    if revs:
        wikitext = (revs[0].get("slots", {}).get("main", {}) or {}).get("content", "") or ""
    return {
        "revid": revs[0].get("revid") if revs else None,
        "wikitext": wikitext,
        "plaintext": page.get("extract"),
    }


def check_offline(bundle: dict) -> tuple[list[str], dict, dict]:
    """証拠バンドルの観測値を、保存した応答から作り直して照合する。

    返り値の3つ目は、再計算した値（概念ID → 項目）。公開物の照合に使う。

    **この検査が示すこと**: 同梱の応答から、証拠バンドルの観測値を再計算できる。
    **示さないこと**: その応答が本当に Wikipedia から取得されたものであること、
    算出規則そのものの妥当性、人手判定の妥当性。
    """
    run_id = bundle["run_id"]
    problems: list[str] = []
    st = {"obs": 0, "pages": set(), "recomputed": 0, "no_plaintext": 0,
          "absent_checked": 0, "hash_ok": 0, "raw_unreferenced": 0}
    recomputed: dict[str, dict] = {}

    raw_dir = ROOT / "data" / "raw" / run_id
    on_disk: set[str] = set()
    if raw_dir.exists():
        for f in sorted(raw_dir.glob("*.json.gz")):
            with gzip.open(f, "rt", encoding="utf-8") as fh:
                body = fh.read()
            name = f.name.removesuffix(".json.gz")
            on_disk.add(name)
            if hashlib.sha256(body.encode("utf-8")).hexdigest() != name:
                problems.append(f"[生データ] {f.name} の中身がファイル名のハッシュと一致しない")
            else:
                st["hash_ok"] += 1
    else:
        problems.append(f"[生データ] {raw_dir} が無い")

    referenced: set[str] = set()

    def note_req(req: dict | None) -> str | None:
        sha = (req or {}).get("response_sha256")
        if sha:
            referenced.add(sha)
        return sha

    def recheck(obs: dict, label: str) -> dict | None:
        """1観測を保存応答から作り直す。取りこぼしは成功として数えない。"""
        if not obs:
            return None
        st["obs"] += 1
        sha = note_req(obs.get("request"))
        if not sha:
            problems.append(f"[{label}] 応答のハッシュが記録されていない")
            return None
        body = read_raw(run_id, sha)
        if body is None:
            problems.append(f"[{label}] 記録されたハッシュ {sha[:12]}… の生データが無い")
            return None
        page = page_from_response(body)

        if not obs.get("exists"):
            # 「無い」と記録したものが、応答でも本当に無いかを確かめる
            if page is not None:
                problems.append(f"[{label}] 不在と記録しているが、応答にはページがある")
            else:
                st["absent_checked"] += 1
            return None

        if page is None:
            problems.append(f"[{label}] 実在と記録しているが、応答からページを取り出せない")
            return None

        st["pages"].add((obs.get("project"), page["revid"]))
        if page["revid"] != obs.get("revid"):
            problems.append(f"[{label}] 改訂ID 記録={obs.get('revid')} / 再現={page['revid']}")

        out = {"revid": page["revid"]}
        if page["plaintext"] is None:
            st["no_plaintext"] += 1
            problems.append(f"[{label}] 保存応答に平文が無く、本文文字数・節数を再計算できない")
        else:
            bm = metrics.body_metrics(page["plaintext"])
            out["body_chars"] = bm["body_chars"]
            out["top_level_sections"] = bm["top_level_sections"]
            for k, jp in (("body_chars", "本文文字数"), ("top_level_sections", "節数")):
                if bm[k] != obs.get(k):
                    problems.append(f"[{label}] {jp} バンドル={obs.get(k)} / 再現={bm[k]}")
        fm = metrics.footnote_metrics(page["wikitext"])
        out["external_ref_domains"] = fm["external_ref_domains"]
        if fm["external_ref_domains"] != obs.get("external_ref_domains"):
            problems.append(f"[{label}] 脚注ドメイン数 バンドル={obs.get('external_ref_domains')} "
                            f"/ 再現={fm['external_ref_domains']}")
        st["recomputed"] += 1
        return out

    for c in bundle["concepts"]:
        cid = c["concept_id"]
        rec = {"en": recheck(c.get("en"), f"{cid}/en"), "ja": None}
        for r in c.get("ja_candidates", []):
            got = recheck(r, f"{cid}/ja:{r['candidate']}")
            if r["candidate"] == c.get("ja_selected"):
                rec["ja"] = got
        note_req((c.get("wikidata") or {}).get("request"))
        for sr in c.get("ja_search_context", []):
            note_req(sr.get("request"))
        recomputed[cid] = rec

    # raw の集合とバンドルが参照する集合を双方向で突き合わせる
    missing = referenced - on_disk
    extra = on_disk - referenced
    for m in sorted(missing):
        problems.append(f"[生データ] バンドルが参照する {m[:12]}… がディスクに無い")
    st["raw_unreferenced"] = len(extra)
    if extra:
        problems.append(f"[生データ] バンドルから参照されないファイルが {len(extra)}件ある")

    return problems, st, recomputed


def check_published(recomputed: dict) -> list[str]:
    """**公開した CSV の数字**が、保存応答からの再計算値と一致するか。

    証拠バンドルまでの照合では「公開した数字を検算した」ことにならない。
    読者が手にするのは site/public のファイルなので、そこまで突き合わせる。
    """
    import csv as _csv
    path = ROOT / "site" / "public" / "kuhaku-zukan.csv"
    if not path.exists():
        return ["[公開物] kuhaku-zukan.csv が無い"]
    problems: list[str] = []
    n = 0
    with path.open(encoding="utf-8-sig") as f:
        for row in _csv.DictReader(f):
            cid = row["concept_id"]
            rec = recomputed.get(cid)
            if not rec:
                problems.append(f"[公開物] {cid} が証拠バンドルに無い")
                continue
            for side, cols in (("en", (("en_body_chars", "body_chars"),
                                       ("en_sections", "top_level_sections"),
                                       ("en_footnote_ref_domains", "external_ref_domains"),
                                       ("en_revid", "revid"))),
                               ("ja", (("ja_body_chars", "body_chars"),
                                       ("ja_sections", "top_level_sections"),
                                       ("ja_footnote_ref_domains", "external_ref_domains"),
                                       ("ja_revid", "revid")))):
                src = rec.get(side)
                for col, key in cols:
                    pub = row.get(col, "")
                    exp = (src or {}).get(key)
                    if pub == "":
                        if exp is not None and side == "en":
                            problems.append(f"[公開物] {cid}.{col} が空欄だが再計算値は {exp}")
                        continue
                    if exp is None:
                        problems.append(f"[公開物] {cid}.{col}={pub} だが再計算できていない")
                    elif str(exp) != pub:
                        problems.append(f"[公開物] {cid}.{col} 公開={pub} / 再現={exp}")
            n += 1
    if not problems:
        problems.append(f"__OK__{n}")
    return problems


# --------------------------------------------------------------------------
# 乖離: 測定時から記事が変わっていないか
# --------------------------------------------------------------------------


def write_drift(bundle: dict, changed: list[str], dstats: dict) -> pathlib.Path:
    """drift の結果を日付つきで残す。

    サイトの鮮度表示はこれを読む。手で日付と件数を書くと必ず腐る
    （実際、2026-09-14 の数字を9日間そのまま載せていた）。
    """
    import datetime
    today = datetime.date.today().isoformat()
    d = ROOT / "data" / "drift"
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{today}.json"
    path.write_text(json.dumps({
        "measured_at": today,
        "against_run_id": bundle["run_id"],
        "targets": dstats["targets"],
        "unchanged": dstats["unchanged"],
        "changed": len(changed),
        "fetch_failed": dstats["fetch_failed"],
        "changed_by_language": dstats.get("changed_by_language", {}),
        "targets_by_language": dstats.get("targets_by_language", {}),
        "DO_NOT_USE_FOR": "言語間の更新頻度の比較。対象記事の集合が日英で違い、期間も短い。"
                          "この数値からどちらの言語版がよく更新されているかは言えない。",
        "why_measured": "公開した観測値が「いつの時点のものか」を示すため。"
                        "記事が変わっていること自体は誤りではない。",
        "how_to_reproduce": "./run.sh drift",
        "details": changed,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def latest_drift() -> dict | None:
    """サイトが読む用。いちばん新しい drift の結果を返す。"""
    d = ROOT / "data" / "drift"
    files = sorted(d.glob("*.json")) if d.exists() else []
    if not files:
        return None
    return json.loads(files[-1].read_text(encoding="utf-8"))


def check_drift(bundle: dict) -> tuple[list[str], dict]:
    from . import wikiclient

    targets: dict[tuple[str, str], int] = {}
    for c in bundle["concepts"]:
        en = c.get("en") or {}
        if en.get("exists") and en.get("resolved_title"):
            targets[("en", en["resolved_title"])] = en["revid"]
        sel = c.get("ja_selected")
        for r in c.get("ja_candidates", []):
            if r["exists"] and r["candidate"] == sel and r.get("resolved_title"):
                targets[("ja", r["resolved_title"])] = r["revid"]

    changed, same, failed = [], 0, 0
    by_lang = {"en": 0, "ja": 0}
    tgt_lang = {"en": 0, "ja": 0}
    for (proj, _t) in targets:
        tgt_lang[proj] = tgt_lang.get(proj, 0) + 1
    for (proj, title), recorded in sorted(targets.items()):
        url = wikiclient.api(proj, {"action": "query", "prop": "revisions",
                                    "rvprop": "ids|timestamp", "redirects": "1", "titles": title})
        res = wikiclient.fetch(url)
        if res.status != 200 or not res.body:
            failed += 1
            continue
        pages = (res.json().get("query") or {}).get("pages") or []
        if not pages or pages[0].get("missing"):
            changed.append(f"[{proj}] 「{title}」は現在見つからない（記録 rev.{recorded}）")
            by_lang[proj] = by_lang.get(proj, 0) + 1
            continue
        cur = (pages[0].get("revisions") or [{}])[0].get("revid")
        if cur != recorded:
            changed.append(f"[{proj}] 「{title}」 rev.{recorded} → rev.{cur}")
            by_lang[proj] = by_lang.get(proj, 0) + 1
        else:
            same += 1
    return changed, {"targets": len(targets), "unchanged": same, "fetch_failed": failed,
                     "changed_by_language": by_lang, "targets_by_language": tgt_lang}


def revids_in_raw() -> set[int]:
    """バンドルに本文つきで入っているページの改訂IDを集める。"""
    found: set[int] = set()
    for f in (ROOT / "data" / "raw").rglob("*.json.gz"):
        try:
            body = gzip.open(f, "rt", encoding="utf-8").read()
            pages = ((json.loads(body).get("query") or {}).get("pages")) or []
        except Exception:
            continue
        if isinstance(pages, dict):
            pages = list(pages.values())
        for pg in pages:
            if isinstance(pg, dict) and pg.get("revisions"):
                rid = (pg["revisions"][0] or {}).get("revid")
                if rid:
                    found.add(int(rid))
    return found


def check_containers() -> tuple[list[str], int]:
    """「実質包含」の包含先が、改訂ID付きでバンドルに入っているか。

    包含先の本文はこの判定の根拠そのものなので、バンドルに無いと
    第三者が反証できない。改訂IDを記録しなかった判定が実際にあり、
    公開した文字数を後から再現できなくなった（j-0002 → j-0028）。
    """
    doc = tomllib.loads((ROOT / "judgments" / "living.toml").read_text(encoding="utf-8"))
    events = doc.get("judgment") or []
    superseded = {e["supersedes"] for e in events if e.get("supersedes")}
    current = [e for e in events if e["id"] not in superseded]

    have = revids_in_raw()
    problems, checked = [], 0
    for e in current:
        if e.get("verdict") != "実質包含":
            continue
        checked += 1
        revids = e.get("ja_revids") or []
        if not revids:
            problems.append(f"{e['id']}（{e['concept_id']}）包含先の改訂IDが記録されていない")
            continue
        for rid in revids:
            if int(rid) not in have:
                problems.append(
                    f"{e['id']}（{e['concept_id']}）包含先 revid {rid} の本文がバンドルに無い")
    return problems, checked


def main(argv: list[str]) -> int:
    bundle = load_bundle()
    print(f"証拠バンドル: {bundle['run_id']}（算出規則 {bundle['calc_version']}）\n")

    problems, st, recomputed = check_offline(bundle)
    print("■ 完全性 — 保存した応答から観測値を作り直して照合")
    print(f"   生データのハッシュ一致   : {st['hash_ok']}件")
    print(f"   再計算した観測           : {st['recomputed']} / {st['obs']}件"
          f"（実ページ {len(st['pages'])}件・不在の確認 {st['absent_checked']}件）")
    if st["no_plaintext"]:
        print(f"   平文が無く再計算不可     : {st['no_plaintext']}件")
    if st["raw_unreferenced"]:
        print(f"   バンドル未参照の生データ : {st['raw_unreferenced']}件")

    cprob, cn = check_containers()
    print("\n■ 根拠 — 「実質包含」の包含先が改訂ID付きでバンドルにあるか")
    if cprob:
        print(f"   {cn}件中 {len(cprob)}件が欠けている。")
        problems += cprob
    else:
        print(f"   {cn}件すべて、包含先の本文を同梱している。")

    pub = check_published(recomputed)
    ok_pub = len(pub) == 1 and pub[0].startswith("__OK__")
    print("\n■ 公開物 — 公開した CSV の数字を再計算値と照合")
    if ok_pub:
        print(f"   {pub[0].removeprefix('__OK__')}行すべて一致。")
    else:
        problems += pub

    if problems:
        print(f"\n**不一致 {len(problems)}件**")
        for p in problems[:25]:
            print("   ✗ " + p)
        if len(problems) > 25:
            print(f"   … 他 {len(problems)-25}件")
    else:
        print("\n不一致なし。同梱の応答から、証拠バンドルと公開CSVの数字を作り直せる。")
    print("\n   この検査が示すのは「同梱の応答から観測値を再計算できる」ことだけ。"
          "\n   応答が本当に Wikipedia から取得されたこと、算出規則の妥当性、"
          "\n   人手判定の妥当性は示さない。")

    rc = 1 if problems else 0

    if "--drift" in argv:
        print("\n■ 乖離 — 測定時から記事が変わっていないか")
        changed, dstats = check_drift(bundle)
        print(f"   対象 {dstats['targets']}件 / 変化なし {dstats['unchanged']}件 / "
              f"変化あり {len(changed)}件 / 取得失敗 {dstats['fetch_failed']}件")
        for c in changed:
            print("     ・" + c)
        print(f"\n   結果を保存: {write_drift(bundle, changed, dstats).relative_to(ROOT)}")
        print("\n   記事が変わっていること自体は誤りではない。"
              "公開した数字が「いつの時点のものか」を示すために測っている。"
              "\n   **言語別の内訳を更新頻度の比較に使ってはいけない。対象記事の集合が日英で違う。**")

    return rc



if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
