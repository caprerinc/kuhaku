"""言語間リンクの欠落だけで「無い」とした判定が、人手確認でどれだけ反証されたかを数える。

このリポジトリは「素朴に差分を取ったデータはそのままでは使えない」と主張している。
その主張の根拠になる数字は、**このリポジトリのデータから計算できなければならない**。

当初は別サンプル（学問分野25件・生活分野11件）で測った55%という数字を使っていたが、
その調査は本データセットに含まれておらず、第三者が検算できない。
主張の根拠に検算できない数字を使うのは、この調査が批判していることそのものなので、
ここで計算し直す。

素朴な判定 = 「Wikidata に日本語版への言語間リンクが無い → 日本語版に無い」

**これは精度評価ではない。** 対象20件は手選びで、無作為抽出ではない。
また「人手確認でも見つからなかった」ことは、その判定が正しかったことの証明にもならない。
だから「正解」「誤り率」とは呼ばず、**反証されたかどうか**だけを数える。

使い方:
    python3 -m pipeline.stats
"""

from __future__ import annotations

import json
import pathlib
import tomllib
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parent.parent


def load() -> tuple[dict, dict]:
    ev = json.loads((ROOT / "data" / "evidence" / "living-latest.json").read_text(encoding="utf-8"))
    js = tomllib.loads((ROOT / "judgments" / "living.toml").read_text(encoding="utf-8"))["judgment"]
    superseded = {j["supersedes"] for j in js if j.get("supersedes")}
    current = {j["concept_id"]: j for j in js if j["id"] not in superseded}
    return {c["concept_id"]: c for c in ev["concepts"]}, current


def naive_scorecard() -> dict:
    """欠落フラグが人手確認で反証されたかを数える。成績表ではない。

    contradicted     … 人手確認で、別の記事の中に定義が見つかった（フラグは反証された）
    not_contradicted … 人手確認でも見つからなかった。**正しかったという意味ではない。**
                       たとえばスクリーンタイムは、同名で別概念の記事が日本語版に実在するが、
                       言語間リンクが無いというだけでフラグが立っている。結論は反証されて
                       いないが、この規則が同名別概念を見分けられたわけではない。
    """
    ev, cur = load()
    flagged, not_contradicted, contradicted = [], [], []
    for cid, j in cur.items():
        comp = ev[cid].get("comparison") or {}
        if comp.get("ja_sitelink_exists"):
            continue
        flagged.append(cid)
        tgt = contradicted if j["verdict"] == "実質包含" else not_contradicted
        tgt.append((cid, j["verdict"], j["id"]))

    have = [(cid, j["verdict"]) for cid, j in cur.items()
            if (ev[cid].get("comparison") or {}).get("ja_sitelink_exists")]

    return {
        "judged": len(cur),
        "flagged_missing": len(flagged),
        "contradicted": [c for c, _, _ in contradicted],
        "not_contradicted": [c for c, _, _ in not_contradicted],
        "rows": _rows(ev, cur),
        "sitelink_present": len(have),
        "sitelink_present_verdicts": dict(Counter(v for _, v in have)),
        "caveat": "対象20件は手選びで無作為抽出ではない。精度評価としては使えない。"
                  "「反証されなかった」ことは、その判定が正しかったことを意味しない。",
    }


def _rows(ev: dict, cur: dict) -> list[dict]:
    """第三者が集計そのものを監査できるよう、1概念1行の表を作る。"""
    out = []
    for cid, j in sorted(cur.items()):
        comp = ev[cid].get("comparison") or {}
        has = bool(comp.get("ja_sitelink_exists"))
        flagged = not has
        out.append({
            "concept_id": cid,
            "ja_sitelink": "あり" if has else "なし",
            "naive_flag": "「日本語版に無い」と出る" if flagged else "フラグ立たず",
            "human_verdict": j["verdict"],
            "outcome": ("contradicted" if flagged and j["verdict"] == "実質包含"
                        else "not_contradicted" if flagged else "not_flagged"),
            "judgment_id": j["id"],
            "included_because": "人手検証を完了した概念すべてを対象にしている",
        })
    return out


def write_audit_csv() -> pathlib.Path:
    """集計の元になる表を公開する。集計値だけでなく行が見えないと監査できない。"""
    import csv
    s = naive_scorecard()
    path = ROOT / "site" / "public" / "naive-check.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(s["rows"][0].keys()))
        w.writeheader()
        w.writerows(s["rows"])
    return path


def main() -> int:
    s = naive_scorecard()
    print("言語間リンクの欠落だけで立てた「無い」フラグが、人手確認で反証されたか")
    print("  規則: Wikidata に日本語版への言語間リンクが無い → 「日本語版に無い」\n")
    print(f"  人手検証した概念        : {s['judged']}件（手選び。無作為抽出ではない）")
    print(f"  フラグが立った          : {s['flagged_missing']}件")
    print(f"  人手確認で反証された    : {len(s['contradicted'])}件"
          f"（別の記事の中に定義があった）")
    for c in s["contradicted"]:
        print(f"     ✗ {c}")
    print(f"  反証されなかった        : {len(s['not_contradicted'])}件"
          f"（正しかったという意味ではない）")
    for c in s["not_contradicted"]:
        print(f"     ・{c}")
    print(f"\n  言語間リンクがあるもの  : {s['sitelink_present']}件 → {s['sitelink_present_verdicts']}")
    print(f"\n  {s['caveat']}")
    p = write_audit_csv()
    print(f"\n  集計の元表: {p.relative_to(ROOT)}（{len(s['rows'])}行）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
