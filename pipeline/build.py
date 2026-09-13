"""証拠バンドル + 判定記録 → 公開用データセット。

判定が無い概念は「未判定」として出す。観測値だけで判定を代用しない。
観測値（文字比）は判定ではない。文字比が低いことは「薄い」の証拠のひとつに過ぎず、
主要論点の欠落を人手で確認してはじめて「薄い」と言える。

使い方:
    python3 -m pipeline.build            # 最新の証拠バンドルを使う
    python3 -m pipeline.build data/evidence/living-run-....json
"""

from __future__ import annotations

import csv
import json
import pathlib
import sys
import tomllib

ROOT = pathlib.Path(__file__).resolve().parent.parent
VERDICTS = ["欠落", "薄い", "実質包含", "該当なし", "判定不能"]


def load_judgments(edition: str) -> dict[str, dict]:
    """追記型の判定イベントから、概念ごとの「現在の判定」を組み立てる。

    supersedes で古い判定を上書きする。イベント自体は消さない。
    """
    path = ROOT / "judgments" / f"{edition}.toml"
    if not path.exists():
        return {}
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    events = data.get("judgment", [])

    superseded = {e["supersedes"] for e in events if e.get("supersedes")}
    current: dict[str, dict] = {}
    history: dict[str, list] = {}
    for e in events:
        history.setdefault(e["concept_id"], []).append(e)
        if e.get("id") in superseded:
            continue
        current[e["concept_id"]] = e
    for cid, ev in current.items():
        ev["_history_count"] = len(history.get(cid, []))
        ev["_was_corrected"] = len(history.get(cid, [])) > 1
    return current


def main(argv: list[str]) -> int:
    if len(argv) > 1:
        ev_path = pathlib.Path(argv[1])
        if not ev_path.is_absolute():
            ev_path = ROOT / ev_path
    else:
        candidates = sorted((ROOT / "data" / "evidence").glob("*-latest.json"))
        if not candidates:
            print("証拠バンドルが見つかりません。先に pipeline.collect を実行してください。")
            return 1
        ev_path = candidates[0]

    ev = json.loads(ev_path.read_text(encoding="utf-8"))
    judgments = load_judgments(ev.get("edition", "living"))

    rows = []
    for c in ev["concepts"]:
        comp = c.get("comparison") or {}
        j = judgments.get(c["concept_id"])
        rows.append(
            {
                "concept_id": c["concept_id"],
                "theme": c["theme"],
                "en_title": (c.get("en") or {}).get("resolved_title"),
                "ja_selected": c.get("ja_selected"),
                "verdict": (j or {}).get("verdict", "未判定"),
                "confidence": (j or {}).get("confidence", ""),
                "corrected": "yes" if (j or {}).get("_was_corrected") else "",
                "en_body_chars": comp.get("en_body_chars"),
                "ja_body_chars": comp.get("ja_body_chars"),
                "body_char_ratio": comp.get("body_char_ratio"),
                "en_sections": comp.get("en_top_level_sections"),
                "ja_sections": comp.get("ja_top_level_sections"),
                "en_ref_domains": comp.get("en_direct_ref_domains"),
                "ja_ref_domains": comp.get("ja_direct_ref_domains"),
                "en_revid": (c.get("en") or {}).get("revid"),
                "ja_sitelink_exists": comp.get("ja_sitelink_exists"),
                "requires_human_selection": c.get("requires_human_selection"),
                "comparison_invalid": comp.get("invalid", False),
                "eligibility": (c.get("eligibility") or {}).get("criterion"),
                "eligibility_status": (c.get("eligibility") or {}).get("status"),
                "judged_at": (j or {}).get("judged_at", ""),
            }
        )

    out = {
        "schema_version": "1.0.0",
        "edition": ev.get("edition"),
        "source_evidence_run_id": ev.get("run_id"),
        "calc_version": ev.get("calc_version"),
        "generated_from": ev_path.name,
        "disclaimer": (
            "本文文字数・節数・脚注ドメイン数はいずれも観測値であり、品質評価ではない。"
            "「未判定」は人手検証をまだ行っていないことを意味し、欠落を意味しない。"
        ),
        "items": rows,
    }
    (ROOT / "data" / "dataset.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with (ROOT / "data" / "dataset.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # ---- 画面向けサマリ ----
    print(f"証拠: {ev_path.name}  (run={ev.get('run_id')}, calc={ev.get('calc_version')})")
    print(f"判定済み: {sum(1 for r in rows if r['verdict'] != '未判定')} / {len(rows)}\n")

    themes: dict[str, list] = {}
    for r in rows:
        themes.setdefault(r["theme"], []).append(r)

    print(f"{'テーマ':<12}{'件数':>4}{'sitelink無':>10}{'要人手選定':>10}{'文字比中央値':>12}  最も低い概念")
    print("-" * 84)
    for theme, rs in themes.items():
        ratios = sorted(r["body_char_ratio"] for r in rs if r["body_char_ratio"] is not None)
        med = ratios[len(ratios) // 2] if ratios else None
        no_sitelink = sum(1 for r in rs if not r["ja_sitelink_exists"])
        need_human = sum(1 for r in rs if r["requires_human_selection"])
        lowest = min((r for r in rs if r["body_char_ratio"] is not None),
                     key=lambda r: r["body_char_ratio"], default=None)
        low_s = f"{lowest['concept_id']} {lowest['body_char_ratio']:.3f}" if lowest else "-"
        print(f"{theme:<12}{len(rs):>4}{no_sitelink:>10}{need_human:>10}{(f'{med:.3f}' if med is not None else '-'):>12}  {low_s}")

    print("\n■ ja sitelink が存在しない概念（観測値。判定は verdict 列を見ること）")
    for r in rows:
        if not r["ja_sitelink_exists"]:
            n = "要人手選定" if r["requires_human_selection"] else "候補も不在"
            print(f"   {r['concept_id']:<32} en {r['en_body_chars']:>7}字  {n:<10} 判定: {r['verdict']}")

    print("\n■ 日本語版のほうが本文が長い概念（反例）")
    for r in sorted((x for x in rows if (x['body_char_ratio'] or 0) >= 1.0),
                    key=lambda x: -x["body_char_ratio"]):
        print(f"   {r['concept_id']:<32} 文字比 {r['body_char_ratio']:.3f}  (ja {r['ja_body_chars']} / en {r['en_body_chars']})")

    invalid = [r for r in rows if r["comparison_invalid"]]
    if invalid:
        print("\n⚠ 比較が無効な概念（取得失敗等）")
        for r in invalid:
            print(f"   {r['concept_id']}")

    print(f"\n出力: data/dataset.json, data/dataset.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
