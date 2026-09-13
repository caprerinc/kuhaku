"""公開文面のチェッカー。

このプロジェクトは「主張範囲を超えないこと」で成り立っている。
その自己規律を目視に頼ると必ず漏れる。実際、公開直前のレビューで
13件の違反が見つかり、うち1件は**同じカードの中で数字が矛盾する事実誤認**だった。

だから規律そのものをコードにする。

使い方:
    python3 site/lint_copy.py          # 生成済み HTML を検査
    python3 site/lint_copy.py --sources  # 元データ（concepts / judgments）も検査
終了コード 1 で違反あり。
"""

from __future__ import annotations

import html
import json
import pathlib
import re
import sys
import tomllib

ROOT = pathlib.Path(__file__).resolve().parent.parent
HTML = ROOT / "site" / "public" / "index.html"

# --------------------------------------------------------------------------
# 禁止表現。(正規表現, 説明, 例外パターン)
# --------------------------------------------------------------------------
FORBIDDEN = [
    (r"情報量",
     "文字数・節数・出典数を統合して「情報量」と呼ばない",
     r"情報量(は|が)同じでは|「情報量」とは呼びません|情報量とは呼ばない"),
    (r"充実度|明確に充実|充実している|充実していない",
     "観測値から「充実」を結論づけない（総合品質の判定に読める）", None),
    (r"(質|品質)が(低|悪)", "日本語版Wikipediaの品質を評価しない", None),
    (r"遅れている", "「日本は遅れている」型の文明論を書かない",
     r"遅れているということではありません|遅れているわけではない"),
    (r"日本語に(は)?(この)?情報が(存在し)?ない", "主張範囲はWikipedia日本語版に限る",
     r"という意味ではない|ことは主張していません|わけではありません|ものではありません"),
    (r"どこにも(実質的に)?(書かれて|存在し|記述が)",
     "探索範囲を超えた全称否定を書かない（「確認した◯記事では」と限定する）", None),
    (r"(埋める|加筆す|書かれる|改善す)べき", "Wikipedia編集者への宿題化を書かない", None),
    (r"(リダイレクト|転送|統合)(は|が).{0,6}(誤り|間違|不適切)",
     "独立記事にしない編集判断を誤りとしない", None),
    (r"検証済みだから", "「検証済みだから正しい」と書かない", None),
    (r"英語版(の方|のほう)が(正し|完全|優れ)", "英語版を正解の基準にしない", None),
    (r"(短い|少ない)から(質|価値)", "分量と品質を混同しない", None),
    # 出典のない量的主張。観測値の表以外で割合を書かない。
    (r"[0-9０-９]+\s*割(の|に)|[0-9０-９]+\s*[%％]の(人|方|患者|女性|親)",
     "出典のない頻度・割合の主張を書かない", None),
]

# 必ず含まれていなければならない文言
REQUIRED = [
    (r"Wikipedia日本語版に対応する記事を確認できたか", "主張範囲の限定が冒頭にない"),
    (r"日本語で情報が手に入るかどうかを調べたものではありません", "調査範囲の否認文がない"),
    (r"編集上の(欠陥|不備)", "「空白＝編集上の欠陥ではない」の明記がない"),
    (r"英語版が正しい基準", "「英語版を基準としない」の明記がない"),
]


def strip_html(s: str) -> str:
    s = re.sub(r"<style.*?</style>", " ", s, flags=re.S)
    s = re.sub(r"<script.*?</script>", " ", s, flags=re.S)
    s = re.sub(r"<[^>]+>", " ", s)
    return html.unescape(s)


# 禁止事項そのものを列挙している文（注意書き・定義・否認文）は違反ではない。
NEGATION_GUARD = re.compile(
    r"と読める書き方をしない|と書かない|書いてはいけない|してはいけない|"
    r"という意味ではない|わけではありません|ものではありません|とは呼びません|"
    r"ことは主張していません|と断じない|としない。|は違反")


def check_text(text: str, label: str) -> list[str]:
    out = []
    for pat, why, exc in FORBIDDEN:
        for m in re.finditer(pat, text):
            ctx = text[max(0, m.start() - 45): m.start() + 45].replace("\n", " ").strip()
            if exc and re.search(exc, ctx):
                continue
            if NEGATION_GUARD.search(ctx):
                continue
            out.append(f"[{label}] {why}\n      … {ctx} …")
    return out


def check_numbers() -> list[str]:
    """**記事全体の分量**として書かれた「N字」が、観測値と食い違っていないか。

    公開直前に「産後うつ病の本文は2,148字、英語版は67,816字」と書いたまま
    残っていたのを見逃した（実測は 2,118字 / 57,735字）。同じカードの中で
    数字が矛盾していた。人の目では捕まえられないので機械で照合する。

    節単位の文字数（「英語版 History 4,005字」など）や隣接記事の文字数は
    正当な記述なので対象にしない。記事全体を指す言い回しだけを見る。
    """
    ev = json.loads((ROOT / "data" / "evidence" / "living-latest.json").read_text(encoding="utf-8"))
    concepts = {c["id"]: c for c in tomllib.loads(
        (ROOT / "concepts" / "living.toml").read_text(encoding="utf-8"))["concept"]}
    judg = tomllib.loads((ROOT / "judgments" / "living.toml").read_text(encoding="utf-8"))["judgment"]
    superseded = {e["supersedes"] for e in judg if e.get("supersedes")}
    current = {e["concept_id"]: e for e in judg if e["id"] not in superseded}

    # 「記事全体の分量」を主張している言い回し
    WHOLE = [
        (r"(?:本文|日本語版の本文|日本語版は|日本語版が)\s*([0-9][0-9,]*)\s*字", "ja"),
        (r"英語版は\s*([0-9][0-9,]*)\s*字", "en"),
        (r"en\s*([0-9][0-9,]*)\s*字", "en"),
        (r"ja\s*([0-9][0-9,]*)\s*字", "ja"),
    ]
    out = []
    for c in ev["concepts"]:
        cid = c["concept_id"]
        if cid not in current:
            continue
        comp = c.get("comparison") or {}
        truth = {"en": comp.get("en_body_chars"), "ja": comp.get("ja_body_chars")}
        text = (current[cid].get("rationale") or "") + "\n" + (concepts[cid].get("why") or "")
        for pat, side in WHOLE:
            for m in re.finditer(pat, text):
                v = int(m.group(1).replace(",", ""))
                exp = truth[side]
                if exp is None or v == exp:
                    continue
                ctx = text[max(0, m.start() - 40): m.start() + 40].replace("\n", " ")
                out.append(f"[{cid}] {side} の分量として {v:,}字 と書いているが、観測値は {exp:,}字\n      … {ctx} …")
    return out


# 不在を言う表現。これらは必ず探索範囲の限定と同じ文脈に置く。
ABSENCE = re.compile(r"見当たらない|記述されていない|扱われていない|存在しない|痕跡が(無|な)い|"
                     r"言及が(無|な)い|記載が(無|な)い|書かれていない")
# 探索範囲を示す語。これが近くにあれば限定されているとみなす。
SCOPE = re.compile(r"確認した|照会した|探索|範囲では|本文では|本文に|記事では|記事に|"
                   r"候補|通読|調べた|今回|検索語|上位・隣接|限定|隣接記事|"
                   r"「[^」]{2,24}」|[0-9][0-9,]*\s*字|英語版\s*[A-Za-z]")


def check_absence_claims(text: str, label: str) -> list[str]:
    """不在の断定に、探索範囲の限定が添えられているか。

    「どこにも書かれていない」は規則で弾けるが、「見当たらない」「扱われていない」
    のような言い換えはすり抜ける。不在は完全証明できないので、
    これらの表現には必ず「何を調べた範囲での話か」を同じ文脈に置く。
    """
    out = []
    for m in ABSENCE.finditer(text):
        ctx = text[max(0, m.start() - 170): m.start() + 40].replace("\n", " ")
        if SCOPE.search(ctx) or NEGATION_GUARD.search(ctx):
            continue
        out.append(f"[{label}] 不在の断定に探索範囲の限定が無い（「確認した◯記事では」等を添える）"
                   f"\n      … {ctx.strip()} …")
    return out


def check_structure() -> list[str]:
    """判定と確からしさの組み合わせが規則に反していないか。"""
    judg = tomllib.loads((ROOT / "judgments" / "living.toml").read_text(encoding="utf-8"))["judgment"]
    superseded = {e["supersedes"] for e in judg if e.get("supersedes")}
    out = []
    for e in judg:
        if e["id"] in superseded:
            continue
        if e["verdict"] == "欠落" and e.get("confidence") == "high":
            out.append(f"[{e['concept_id']}] 「確認できず」に confidence: high が付いている。"
                       "不在は完全証明できないため最大 medium とする規則に反する")
        if e["verdict"] == "欠落" and not e.get("checked_containers"):
            out.append(f"[{e['concept_id']}] 「確認できず」なのに確認した隣接記事の記録が無い")
        if e["verdict"] == "欠落" and not e.get("search_terms"):
            out.append(f"[{e['concept_id']}] 「確認できず」なのに使った検索語の記録が無い")
    return out


def main() -> int:
    problems: list[str] = []

    # --file が指定されたら、そのファイルだけを検査する（note記事・X投稿案など）
    files = [a for a in sys.argv[1:] if not a.startswith("--")]
    if files:
        for f in files:
            path = pathlib.Path(f)
            problems += check_text(path.read_text(encoding="utf-8"), path.name)
            problems += check_absence_claims(path.read_text(encoding="utf-8"), path.name)
        if not problems:
            print(f"文面チェック（{', '.join(files)}）: 違反なし")
            return 0
        print(f"文面チェック: {len(problems)}件の違反\n")
        for pr in problems:
            print("  ✗ " + pr)
        return 1

    if HTML.exists():
        text = strip_html(HTML.read_text(encoding="utf-8"))
        problems += check_text(text, "公開HTML")
        problems += check_absence_claims(text, "公開HTML")
        for pat, why in REQUIRED:
            if not re.search(pat, text):
                problems.append(f"[公開HTML] 必須文言が無い: {why}")
    else:
        problems.append("生成物が無い。先に build_site.py を実行すること")

    if "--sources" in sys.argv:
        problems += check_text((ROOT / "concepts" / "living.toml").read_text(encoding="utf-8"),
                               "concepts/living.toml")
        # 判定記録は「現行イベント」だけを見る。訂正で無効化された過去イベントは
        # 当時そう書いたという歴史そのものなので、書き換えてはいけない。
        judg = tomllib.loads((ROOT / "judgments" / "living.toml").read_text(encoding="utf-8"))["judgment"]
        superseded = {e["supersedes"] for e in judg if e.get("supersedes")}
        for e in judg:
            if e["id"] in superseded:
                continue
            problems += check_text(e.get("rationale", "") + "\n" + e.get("correction_reason", ""),
                                   f"judgments/{e['id']} ({e['concept_id']})")

    problems += check_numbers()
    problems += check_structure()

    if not problems:
        print("文面チェック: 違反なし")
        return 0
    print(f"文面チェック: {len(problems)}件の違反\n")
    for p in problems:
        print("  ✗ " + p)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
