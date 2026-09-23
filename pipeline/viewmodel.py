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
    concepts, events, ev, evmap, _ = load()
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
                "theme": c_ev.get("theme"),
                "en_title": (c_ev.get("en") or {}).get("resolved_title") or c.get("en_title"),
                "why": c_ev.get("why"),
                "observations": observations(c_ev),
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
            "theme": c_ev.get("theme"),
            # concepts 側は "a"/"b"/"c" の文字列、evidence 側は辞書。
            # 現行の表示は concepts 側の文字列を使っているので合わせる。
            "eligibility": c.get("eligibility"),
            "eligibility_text": ELIGIBILITY_TEXT.get(c.get("eligibility"), ""),
            "eligibility_detail": c_ev.get("eligibility"),
            "en_title": (c_ev.get("en") or {}).get("resolved_title") or c.get("en_title"),
            "ja_selected": c_ev.get("ja_selected"),
            "why": c_ev.get("why"),
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
            "correction": None,
        }
        if kind:
            item["correction"] = {
                "kind": kind,                      # verdict = 判定が変わった / evidence = 根拠を更新
                "prev_verdict": prev["verdict"],
                "prev_verdict_public": VERDICT_PUBLIC[prev["verdict"]],
                "prev_judged_at": prev.get("judged_at"),
                "reason": j.get("correction_reason", ""),
                "supersedes": j.get("supersedes"),
            }
            corrections.append({"concept_id": cid, **item["correction"],
                                "verdict_public": item["verdict"]["public"]})
        items.append(item)

    items.sort(key=lambda x: (x["verdict"]["order"], x["concept_id"]))
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
        },
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


def main() -> int:
    vm = build()
    OUT.write_text(json.dumps(vm, ensure_ascii=False, indent=2), encoding="utf-8")
    c = vm["counts"]
    print(f"描画契約を書き出した: {OUT.relative_to(ROOT)}")
    print(f"  全{c['concepts_total']}件 / 判定済み {c['judged']}件 / 未検証 {c['unjudged']}件")
    print(f"  訂正: 判定変更 {c['verdict_changed']}件・根拠更新 {c['evidence_updated']}件")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
