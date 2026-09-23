#!/usr/bin/env python3
"""描画に必要なものを1つの JSON にまとめる。表示層との唯一の契約。

これまで表示コード（site/build_site.py）が concepts / judgments / evidence の
3つを直接読み、そこで公開ラベルへの言い換え・欠測と0の区別・訂正種別の判定を
していた。表示を SvelteKit に移すと、**その意味づけが Python と JS に二重化する**。
二重化した意味は必ずずれる。だから意味は全部ここで確定させ、
表示層は解釈せずに並べるだけにする。

  python3 -m pipeline.viewmodel        data/viewmodel.json を書き出す

**null と 0 は違う。** null は「照合する候補がそもそも無かった」であり、
「0字の記事がある」ではない。JSON の null と 0 を取り違えないこと。
"""

from __future__ import annotations

import json
import pathlib
import sys
import tomllib

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "viewmodel.json"
SCHEMA_VERSION = "1.0.0"

# 内部の判定語をそのまま見出しに出さない。「欠落」は不在の断定に読めるため。
VERDICT_PUBLIC = {
    "欠落": "確認できず",
    "薄い": "論点に差がある",
    "実質包含": "別記事の中にある",
    "判定不能": "比較できない",
    "該当なし": "日本語版が上回る",
}
VERDICT_ORDER = ["欠落", "実質包含", "薄い", "判定不能", "該当なし"]
VERDICT_DEF = {
    "欠落": "独立した記事も、上位・隣接記事の中の実質的な説明も、下記の探索範囲では確認できなかった。"
            "「日本語に情報が存在しない」という意味ではない。",
    "実質包含": "独立した記事は無いが、別の記事の中に概念の定義がある。単独の記事が定義している場合に限る。",
    "薄い": "独立した記事はある。その上で、英語版で扱われている論点のうち、日本語版の記事では"
            "確認できないものを人手で特定した。文字数が少ないことだけを理由にはしていない。"
            "英語版が正しい基準だという意味ではない。",
    "判定不能": "日本語版と英語版で扱っている概念の粒度が違うなど、比較が成立しない。",
    "該当なし": "今回観測した3つの指標（本文文字数・節の数・脚注内の外部参照ドメイン数）のいずれでも、"
              "日本語版が英語版を上回った。総合的な品質を比べたものではない。",
}
# 採用基準。なぜこの概念を対象に選んだかの説明で、判定とは別の軸。
ELIGIBILITY_TEXT = {
    "a": "国に依存しない概念",
    "b": "国内での発生・利用を日本語資料で確認",
    "c": "海外制度だが国内の生活に影響",
}
CONFIDENCE_PUBLIC = {
    "high": {"label": "根拠を引用できる", "note": "本文を通読し、判断の根拠を具体的に示せる。"},
    "medium": {"label": "探索済み・断定保留",
               "note": "示した範囲は確認した。範囲外の記事に記述が残っている可能性がある。"},
    "low": {"label": "観測値のみ", "note": "本文の人手確認をしていない。"},
}


# 候補の出どころ。内部語をそのまま出さない。
SOURCE_LABEL = {
    "wikidata_sitelink": "sitelink",
    "wikidata_label": "ラベル",
    "wikidata_alias": "別名",
    "manual": "人手",
}


def rev_url(project: str, revid) -> str | None:
    """改訂IDから permalink を作る。第三者が測定した版そのものを開けるように。"""
    return f"https://{project}.wikipedia.org/w/index.php?oldid={revid}" if revid else None


def load() -> tuple[dict, list, dict, dict, dict]:
    concepts = tomllib.loads((ROOT / "concepts" / "living.toml").read_text(encoding="utf-8"))
    judg = tomllib.loads((ROOT / "judgments" / "living.toml").read_text(encoding="utf-8"))
    ev = json.loads((ROOT / "data" / "evidence" / "living-latest.json").read_text(encoding="utf-8"))
    return (
        {c["id"]: c for c in concepts["concept"]},
        judg.get("judgment", []),
        ev,
        {c["concept_id"]: c for c in ev["concepts"]},
        judg,
    )


def resolve_judgments(events: list) -> tuple[dict, dict]:
    """現行の判定と、概念ごとの全履歴。訂正は上書きせず追記されている。"""
    superseded = {e["supersedes"] for e in events if e.get("supersedes")}
    current, history = {}, {}
    for e in events:
        history.setdefault(e["concept_id"], []).append(e)
        if e["id"] not in superseded:
            current[e["concept_id"]] = e
    return current, history


def change_kind(now: dict, chain: list) -> tuple[str | None, dict | None]:
    """訂正の種類。「訂正済み」と一括りにすると全部が誤判定に見えるので分ける。"""
    prev = [x for x in chain if x["id"] != now["id"]]
    if not prev:
        return None, None
    p = prev[-1]
    return ("verdict" if p["verdict"] != now["verdict"] else "evidence"), p


def candidates(c_ev: dict) -> list[dict]:
    """照会した候補タイトル。全文検索で拾っただけのものは探索記録に出さない
    （候補を思いつくためだけに使い、比較対象には選ばない規則）。"""
    out = []
    for r in c_ev.get("ja_candidates", []):
        if r.get("candidate_source") == "ja_search_candidate":
            continue
        out.append({
            "title": r.get("candidate"),
            "source": r.get("candidate_source"),
            "source_label": SOURCE_LABEL.get(r.get("candidate_source"), r.get("candidate_source")),
            "exists": bool(r.get("exists")),
            "redirected": bool(r.get("redirected")),
            "resolved_title": r.get("resolved_title"),
            "revid": r.get("revid"),
            "rev_url": rev_url("ja", r.get("revid")),
            "body_chars": r.get("body_chars"),
        })
    return out


def observation_notes(c_ev: dict, j: dict) -> list[list[dict]]:
    """観測表に添える注記。**文言はここで決める**。

    表示層には解釈を持たせないので、リンクを含む文を「断片の配列」で渡す。
    断片は {"text":...} か {"text":..., "href":...}。表示層はそれを並べるだけ。
    """
    notes: list[list[dict]] = []
    en = c_ev.get("en") or {}

    # 候補が実在するのに日本語版の列が空欄だと、探索記録と矛盾して見える。
    # 「見つかったが比較対象にしなかった」理由を必ず書く。
    if not c_ev.get("ja_selected"):
        found = [r for r in candidates(c_ev) if r["exists"]]
        if found:
            seg = [{"text": "日本語版に同じ名前の記事 "}]
            for i, r in enumerate(found):
                if i:
                    seg.append({"text": "、"})
                seg.append({"text": f"「{r['title']}」("})
                seg.append({"text": f"rev.{r['revid']}", "href": r["rev_url"]})
                chars = r["body_chars"]
                seg.append({"text": f"、{chars:,}字)" if chars is not None else ")"})
            seg.append({"text": " はあるが、扱っている概念が異なるため比較の対象にしていない。"
                                "そのため日本語版の列は空欄にしてある。"})
            notes.append(seg)
        else:
            notes.append([{"text": "照会した候補がいずれも存在しなかったため、"
                                   "日本語版の列は空欄にしてある。0字の記事があるという意味ではない。"}])

    # 判定時に読んだ版が観測時と違う場合は隠さず併記する。
    jrev = j.get("en_revid")
    if jrev and en.get("revid") and jrev != en.get("revid"):
        notes.append([
            {"text": "判定時に読んだ英語版は "},
            {"text": f"rev.{jrev}", "href": rev_url("en", jrev)},
            {"text": "。観測はその前の版で行った。"},
        ])
    return notes


def observations(c_ev: dict) -> dict:
    """観測値。3つの量を**別々に**並べる。合算して単一スコアにしない。

    値が null なのは「照合する候補が無かった」の意。0 とは違う。
    """
    comp = c_ev.get("comparison") or {}
    en = c_ev.get("en") or {}
    ja = None
    for cand in c_ev.get("ja_candidates", []):
        if cand.get("resolved_title") == c_ev.get("ja_selected"):
            ja = cand
            break

    def side(revid, chars, sections, domains, modified, project):
        return {
            "revid": revid,
            "rev_url": rev_url(project, revid),
            "body_chars": chars,
            "sections": sections,
            "ref_domains": domains,
            "last_modified": modified,
        }

    return {
        "invalid": bool(comp.get("invalid")),
        "en": side(en.get("revid"), comp.get("en_body_chars"),
                   comp.get("en_top_level_sections"), comp.get("en_direct_ref_domains"),
                   comp.get("en_last_modified"), "en"),
        "ja": side((ja or {}).get("revid"), comp.get("ja_body_chars"),
                   comp.get("ja_top_level_sections"), comp.get("ja_direct_ref_domains"),
                   comp.get("ja_last_modified"), "ja"),
        "body_char_ratio": comp.get("body_char_ratio"),
        # 表示側が「0字の記事がある」と読み違えないための明示。
        "ja_candidate_missing": c_ev.get("ja_selected") is None,
    }


def build() -> dict:
    from . import stats as _stats
    from . import verify as _verify

    concepts, events, ev, evmap, _ = load()
    sc = _stats.naive_scorecard()
    dr = _verify.latest_drift()
    # 検算をその場で走らせて結果を持つ。ネットワークは使わない。
    bundle = _verify.load_bundle()
    vproblems, vstats, vrecomputed = _verify.check_offline(bundle)
    vpub = _verify.check_published(vrecomputed)
    published_rows = int(vpub[0].removeprefix("__OK__")) if (
        len(vpub) == 1 and vpub[0].startswith("__OK__")) else 0
    vproblems = vproblems + ([] if published_rows else vpub)
    current, history = resolve_judgments(events)

    items, corrections, unjudged = [], [], []
    for cid, c in concepts.items():
        c_ev = evmap.get(cid)
        j = current.get(cid)
        if not c_ev:
            continue
        if not j:
            unjudged.append({
                "concept_id": cid,
                "theme": c.get("theme") or c_ev.get("theme"),
                "en_title": (c_ev.get("en") or {}).get("resolved_title") or c.get("en_title"),
                "why": (c.get("why") or "").strip(),
                "observations": observations(c_ev),
                "candidates": candidates(c_ev),
                # 未検証は「欠けている」ことを意味しない。
                "note": "観測値は取得したが、人手での確認をしていない。欠けていることを意味しない。",
            })
            continue

        kind, prev = change_kind(j, history.get(cid, []))
        conf = CONFIDENCE_PUBLIC.get(j.get("confidence"), CONFIDENCE_PUBLIC["low"])
        item = {
            "concept_id": cid,
            # 判定イベントの識別子。訂正履歴を追うときの鍵なので表示にも出す。
            "judgment_id": j["id"],
            "theme": c.get("theme") or c_ev.get("theme"),
            # concepts 側は "a"/"b"/"c" の文字列、evidence 側は辞書。
            # 現行の表示は concepts 側の文字列を使っているので合わせる。
            "eligibility": c.get("eligibility"),
            "eligibility_text": ELIGIBILITY_TEXT.get(c.get("eligibility"), ""),
            "eligibility_detail": c_ev.get("eligibility"),
            "en_title": (c_ev.get("en") or {}).get("resolved_title") or c.get("en_title"),
            # 見出しに出す日本語名。概念側の第一候補で、実際に採用した記事名とは別。
            "display_name": (c.get("ja_candidates") or [cid])[0],
            "ja_selected": c_ev.get("ja_selected"),
            # **説明文は concepts 側**。evidence 側の why は収集時点の内部メモで、
            # ★誤判定事例 のような編集用の目印が残っており、文面も古い。
            "why": (c.get("why") or "").strip(),
            "verdict": {
                "internal": j["verdict"],
                "public": VERDICT_PUBLIC[j["verdict"]],
                "order": VERDICT_ORDER.index(j["verdict"]),
            },
            "confidence": {"internal": j.get("confidence"), **conf},
            "judged_at": j.get("judged_at"),
            "rationale": j.get("rationale", "").strip(),
            "search_terms": j.get("search_terms") or [],
            "checked_containers": j.get("checked_containers") or [],
            "ja_revids": j.get("ja_revids") or [],
            # 判定時に読んだ英語版。観測した版と違うことがあるので別に持つ。
            # 「観測はその前の版で行った」という注記の根拠がこれ。
            "judged_en_revid": j.get("en_revid"),
            "judged_en_rev_url": rev_url("en", j.get("en_revid")),
            "observations": observations(c_ev),
            "candidates": candidates(c_ev),
            "observation_notes": observation_notes(c_ev, j),
            "correction": None,
        }
        if kind:
            item["correction"] = {
                "kind": kind,   # verdict = 判定が変わった / evidence = 根拠を更新
                "prev_verdict": prev["verdict"],
                "prev_verdict_public": VERDICT_PUBLIC[prev["verdict"]],
                "prev_judged_at": prev.get("judged_at"),
                "reason": j.get("correction_reason", ""),
                "supersedes": j.get("supersedes"),
                # 見出しと本文の文言はここで決める。表示層に解釈を持たせない。
                # 判定が変わっていないのに「初回X → 現在X」と出すと意味が伝わらないので、
                # 根拠更新のときは確からしさの変化だけを書く。
                "label": "判定を変更" if kind == "verdict" else "根拠を更新",
                "body": (
                    f'初回 **{VERDICT_PUBLIC[prev["verdict"]]}** → '
                    f'現在 **{VERDICT_PUBLIC[j["verdict"]]}**。{j.get("correction_reason", "")}'
                    if kind == "verdict" else
                    f'判定は「{VERDICT_PUBLIC[j["verdict"]]}」のまま。'
                    + (f'確からしさ **{CONFIDENCE_PUBLIC.get(prev.get("confidence"), CONFIDENCE_PUBLIC["low"])["label"]}**'
                       f' → **{CONFIDENCE_PUBLIC.get(j.get("confidence"), CONFIDENCE_PUBLIC["low"])["label"]}**。'
                       if CONFIDENCE_PUBLIC.get(prev.get("confidence"), CONFIDENCE_PUBLIC["low"])["label"]
                          != CONFIDENCE_PUBLIC.get(j.get("confidence"), CONFIDENCE_PUBLIC["low"])["label"]
                       else "")
                    + j.get("correction_reason", "")
                ),
            }
            corrections.append({"concept_id": cid, **item["correction"],
                                "verdict_public": item["verdict"]["public"]})
        items.append(item)

    # 判定の種類ごとに並べ、その中は英語版の本文文字数の降順。
    # 並び順も表示の意味なので契約側で決める（通し番号がこれで決まる）。
    # 「無い」と判断したものが別の記事の中にあった件数。
    # ヒーローの数字は直書きで、判定ログから導けなかった（fix⑧）。
    # 導出できるのは「欠落 → 実質包含」の遷移だけ。看板の語り（代表例を2回続けて
    # 外した話）には、記録前に見つけて最初から実質包含で記録したものが含まれる。
    # **数えられるものと語りを混ぜない。**
    found_in_other = sum(
        1 for c in corrections
        if c["kind"] == "verdict" and c["prev_verdict"] == "欠落"
        and c["verdict_public"] == VERDICT_PUBLIC["実質包含"])

    # 看板の引用。旧版はカード生成ループに直書きされていた。
    # 一箇所に集めて実データと突き合わせられるようにする。
    ps = next((i for i in items if i["concept_id"] == "parenting-styles"), None)
    flagship = None
    if ps:
        flagship = {
            "concept_id": ps["concept_id"],
            "text": "養育スタイル（en:parenting styles）について研究し、"
                    "スタイルを「消極・受け身型」「独裁・支配型」「民主型」「無関心型」の4つに分類した。",
            "source_title": "ダイアナ・バウムリンド",
            "source_revid": ps["ja_revids"][0] if ps["ja_revids"] else None,
            "source_rev_url": rev_url("ja", ps["ja_revids"][0]) if ps["ja_revids"] else None,
            "source_body_chars": 354,
            "en_body_chars": ps["observations"]["en"]["body_chars"],
        }
        # 引用の出典が判定の包含先と一致していること。ずれたら公開しない。
        if not flagship["source_revid"]:
            raise SystemExit("看板の引用に出典の改訂IDが無い")
        if not any(str(flagship["source_revid"]) in c for c in ps["checked_containers"]):
            raise SystemExit(
                f'看板の引用の出典 revid {flagship["source_revid"]} が探索記録に無い')

    items.sort(key=lambda x: (x["verdict"]["order"],
                              -(x["observations"]["en"]["body_chars"] or 0)))
    return {
        "schema_version": SCHEMA_VERSION,
        "edition": ev.get("edition"),
        "evidence_run_id": ev.get("run_id"),
        "calc_version": ev.get("calc_version"),
        "labels": {
            "verdict_public": VERDICT_PUBLIC,
            "verdict_order": VERDICT_ORDER,
            "verdict_def": VERDICT_DEF,
            "confidence_public": CONFIDENCE_PUBLIC,
        },
        "counts": {
            "concepts_total": len(evmap),
            "judged": len(items),
            "unjudged": len(unjudged),
            "verdict_changed": sum(1 for c in corrections if c["kind"] == "verdict"),
            "evidence_updated": sum(1 for c in corrections if c["kind"] == "evidence"),
            "found_in_other_article": found_in_other,
            "by_verdict": {v: sum(1 for i in items if i["verdict"]["internal"] == v)
                           for v in VERDICT_ORDER},
        },
        # 素朴な自動判定と人手検証の突き合わせ。割合は出さない
        # （手選びで無作為抽出ではないため精度評価にならない）。
        "scorecard": {
            "judged": sc["judged"],
            "flagged_missing": sc["flagged_missing"],
            "contradicted": sc["contradicted"],
            "not_contradicted": sc["not_contradicted"],
        },
        # 検算の結果。旧版は「2026-09-14 に実行した結果です」と日付を直書きしていて
        # 古くなっていた（鮮度表示と同じ問題）。作り直して数字ごと持たせる。
        "verification": {
            "raw_hash_ok": vstats["hash_ok"],
            "recomputed": vstats["recomputed"],
            "observations": vstats["obs"],
            "pages": len(vstats["pages"]),
            "absent_checked": vstats["absent_checked"],
            "published_rows": published_rows,
            "mismatches": len(vproblems),
        },
        "drift": dr,
        "flagship_quote": flagship,
        "items": items,
        "unjudged": unjudged,
        "corrections": corrections,
        "disclaimer": {
            "scope": "調べたのは Wikipedia 日本語版だけ。辞典・論文・書籍は調べていない。",
            "sampling": "20件は手選びで、無作為に抽出したものではない。精度の評価ではない。",
            "metrics": "本文文字数・節の数・脚注内の外部参照ドメイン数は別々の量であり、"
                       "足し合わせて「情報量」とは呼ばない。",
            "null_vs_zero": "観測値が null なのは照合する候補が無かったという意味で、0字ではない。",
        },
    }


def check_internal_markers(vm: dict) -> list[str]:
    """編集用の目印が公開側に混ざっていないか。黙って消すと出どころの誤りに気づけない。"""
    bad = []
    for item in vm["items"] + vm["unjudged"]:
        for field in ("why", "display_name"):
            v = item.get(field) or ""
            if "★" in v:
                bad.append(f'{item["concept_id"]}.{field} に編集用の目印: {v[:40]}')
    return bad


def main() -> int:
    vm = build()
    problems = check_internal_markers(vm)
    if problems:
        print("編集用の目印が公開側に混ざっている:", file=sys.stderr)
        for p in problems:
            print("  ✗ " + p, file=sys.stderr)
        return 1
    OUT.write_text(json.dumps(vm, ensure_ascii=False, indent=2), encoding="utf-8")
    c = vm["counts"]
    print(f"描画契約を書き出した: {OUT.relative_to(ROOT)}")
    print(f"  全{c['concepts_total']}件 / 判定済み {c['judged']}件 / 未検証 {c['unjudged']}件")
    print(f"  訂正: 判定変更 {c['verdict_changed']}件・根拠更新 {c['evidence_updated']}件")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
