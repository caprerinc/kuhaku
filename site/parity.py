#!/usr/bin/env python3
"""公開物から「主張の指紋」を採り、移行前後で同じかを比べる。

SvelteKit への移行は**表示だけを作り直し、主張は一字も変えない**作業である。
だが 846 行の生成器を部品に割ると、公開ラベルの対応・欠測と0の区別・
訂正種別・改訂IDリンク・探索記録といった意味が、静かに落ちる。
目視では捕まらないので機械で押さえる。

  python3 site/parity.py --baseline            いまの公開物を基準として保存
  python3 site/parity.py --check <html>        基準と比べる（差があれば終了コード1）

比べるのは「何を主張しているか」であって、見た目ではない。
版面・色・字形を直すのが移行の目的なので、体裁の差分で落ちては意味がない。
"""

from __future__ import annotations

import hashlib
import html as htmllib
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
BASELINE = ROOT / "site" / "parity-baseline.json"

# 主張に関わる必須文言。移行で落ちたら致命的なもの。
# 表記ゆれで空振りしないよう正規表現で持つ。文字列一致で照合して
# 「必須文言が無い」と誤検知した経緯がある（このプロジェクトが批判している誤りと同じ形）。
REQUIRED_PHRASES = {
    "不在断定の否認": r"日本語に情報が存在しない",
    "英語版を規範としない": r"英語版が正しい基準",
    "指標を合算しない": r"情報量.{0,6}(呼びません|ではありません)",
    "標本の限界": r"無作為に抽出したもの(ではありません|でもない)|手選び",
    "確認できずは不在の証明ではない": r"(欠けている|存在しない)ことを意味しない|正しかったことを意味しません",
}


def strip_html(s: str) -> str:
    s = re.sub(r"<style.*?</style>", " ", s, flags=re.S)
    s = re.sub(r"<script.*?</script>", " ", s, flags=re.S)
    s = re.sub(r"<[^>]+>", " ", s)
    return htmllib.unescape(s)


def norm_text(s: str) -> str:
    """体裁の差を無視して中身だけ残す。空白の量や改行位置では落とさない。"""
    return re.sub(r"\s+", "", strip_html(s))


def numbers(s: str) -> list[str]:
    """本文に出る数値。カンマ区切りは正規化して拾う。"""
    txt = strip_html(s)
    return sorted({n.replace(",", "") for n in re.findall(r"\d[\d,]*", txt)})


def cards(doc: str) -> dict[str, str]:
    """概念カードを id ごとに切り出す。"""
    out = {}
    for m in re.finditer(r'<article[^>]*\bid="([^"]+)"[^>]*>', doc):
        start = m.start()
        end = doc.find("</article>", start)
        out[m.group(1)] = doc[start: end if end != -1 else len(doc)]
    return out


def verdict_class(card: str) -> str | None:
    m = re.search(r'class="[^"]*\bv-(\d+)\b', card)
    return m.group(1) if m else None


def fingerprint(doc: str) -> dict:
    cs = cards(doc)
    body = strip_html(doc)
    return {
        "concept_count": len(cs),
        "concepts": {
            cid: {
                "verdict": verdict_class(c),
                "numbers": numbers(c),
                "revids": sorted(set(re.findall(r"oldid=(\d+)", c))),
                # 体裁を除いた本文の同一性。文言が変わればここが動く。
                "text_sha": hashlib.sha256(norm_text(c).encode()).hexdigest()[:16],
            }
            for cid, c in sorted(cs.items())
        },
        # カード外（前書き・凡例・訂正表・注記）の主張。
        "outside_cards": {
            "revids": sorted(set(re.findall(r"oldid=(\d+)", doc))),
            "required_phrases": {k: bool(re.search(v, body)) for k, v in REQUIRED_PHRASES.items()},
            "external_links": sorted({
                u for u in re.findall(r'href="(https?://[^"]+)"', doc)
            }),
        },
    }


def check_contract(doc: str) -> list[str]:
    """公開物の主張が、描画契約(viewmodel.json)だけから導けるか。

    表示層を SvelteKit に移すと、Svelte は viewmodel.json しか読まない。
    そこに無い値がいま公開されているなら、移行で**黙って消える**。
    build_site.py を捨てる前に、これが通ることが条件。
    """
    vmp = ROOT / "data" / "viewmodel.json"
    if not vmp.exists():
        return ["描画契約が無い。先に python3 -m pipeline.viewmodel を実行すること"]
    vm = vmp.read_text(encoding="utf-8")
    flat = vm.replace(",", "")
    body = strip_html(doc)
    problems = []

    nums = set(re.findall(r"(?<![\d,])\d{1,3}(?:,\d{3})+(?![\d,])|(?<![\d,])\d{3,}(?![\d,])", body))
    missing = sorted(n for n in nums if n.replace(",", "") not in flat)
    if missing:
        problems.append(f"契約から引けない数値 {len(missing)}種: {missing[:10]}")

    # 改訂IDは**構造化されたフィールドから**集める。JSON 文字列全体への
    # 文字列一致だと、判定文の散文にたまたま同じ数字があるだけで通ってしまう。
    # 実際そうなっていて、契約に候補の構造が無いことを見逃した。
    def structured_revids(o, key=None):
        if isinstance(o, dict):
            for k, v in o.items():
                yield from structured_revids(v, k)
        elif isinstance(o, list):
            for v in o:
                yield from structured_revids(v, key)
        elif isinstance(o, int) and key in ("revid", "en_revid", "judged_en_revid"):
            yield str(o)
        elif isinstance(o, int) and key == "ja_revids":
            yield str(o)
        elif isinstance(o, str) and key in ("rev_url", "judged_en_rev_url"):
            m = re.search(r"oldid=(\d+)", o)
            if m:
                yield m.group(1)

    doc_obj = json.loads(vm)
    have = set(structured_revids(doc_obj))
    revs = {a or b for a, b in re.findall(r"oldid=(\d+)|rev\.(\d+)", doc)}
    lost = sorted(r for r in revs if r not in have)
    if lost:
        problems.append(f"契約の構造化フィールドに無い改訂ID: {lost}")

    # 文字列一致だと、訂正一覧に id が残っているだけで通ってしまう。
    # 描画対象の items に居ることを厳密に見る。
    listed = {i["concept_id"] for i in json.loads(vm).get("items", [])}
    for cid in cards(doc):
        if cid not in listed:
            problems.append(f"契約の items に無い概念: {cid}")
    return problems


# 配信物に混ざってはいけないもの。`.assetsignore` は許可リストではなく、
# adapter-cloudflare は自前の `.assetsignore`（_worker.js 等の4項目だけ）で
# 上書きする。だから除外設定ではなく**一覧そのもの**を見る。
FORBIDDEN_NAMES = re.compile(
    r"(^|/)\.(claude|git|env|aws|ssh|vscode|idea)(/|$)|"
    r"(^|/)(secrets?|\.env\..*|.*\.pem|.*\.key|id_rsa.*|\.DS_Store)$",
    re.I)
# 先頭が . のものはこれだけ許す。増やすときは理由を書くこと。
ALLOWED_DOTFILES = {".assetsignore"}


def check_inventory(root: pathlib.Path) -> list[str]:
    """配信されるファイルの一覧を検査する。

    配信ルートに何が入るかは、除外設定を読んでも分からない。実際に並んだものを見る。
    ディレクトリURLが404でも、その下の個別ファイルが配信されていることはある。
    """
    if not root.exists():
        return [f"配信物が無い: {root}"]
    problems = []
    files = sorted(f.relative_to(root).as_posix() for f in root.rglob("*") if f.is_file())
    if not files:
        return [f"配信物が空: {root}"]
    for rel in files:
        if FORBIDDEN_NAMES.search("/" + rel):
            problems.append(f"配信物に含めてはいけない: {rel}")
            continue
        for seg in rel.split("/"):
            if seg.startswith(".") and seg not in ALLOWED_DOTFILES:
                problems.append(f"想定外のドットファイル: {rel}")
                break
    if not any(f == "index.html" for f in files):
        problems.append("index.html が無い")
    # 404 は「ファイルがあるか」ではなく「実際に 404 が返るか」で見る。
    # 現行構成は 404.html を持たず Cloudflare 側が返しており、それで正しい。
    # 配信後の HTTP 確認（run.sh deploy / deploy.yml）が本来の担保。
    return problems


def diff(old: dict, new: dict) -> list[str]:
    problems: list[str] = []

    if old["concept_count"] != new["concept_count"]:
        problems.append(
            f"概念カードの数が違う: {old['concept_count']} → {new['concept_count']}")

    o, n = old["concepts"], new["concepts"]
    for cid in sorted(set(o) - set(n)):
        problems.append(f"概念が消えた: {cid}")
    for cid in sorted(set(n) - set(o)):
        problems.append(f"概念が増えた: {cid}")

    for cid in sorted(set(o) & set(n)):
        a, b = o[cid], n[cid]
        if a["verdict"] != b["verdict"]:
            problems.append(f"{cid}: 判定が違う v-{a['verdict']} → v-{b['verdict']}")
        if a["numbers"] != b["numbers"]:
            lost = sorted(set(a["numbers"]) - set(b["numbers"]))
            gained = sorted(set(b["numbers"]) - set(a["numbers"]))
            problems.append(
                f"{cid}: 数値が違う"
                + (f" 消えた={lost}" if lost else "")
                + (f" 増えた={gained}" if gained else ""))
        if a["revids"] != b["revids"]:
            problems.append(f"{cid}: 改訂IDが違う {a['revids']} → {b['revids']}")
        if a["text_sha"] != b["text_sha"]:
            problems.append(f"{cid}: 文言が変わっている（体裁を除いて比較）")

    oa, nb = old["outside_cards"], new["outside_cards"]
    if oa["revids"] != nb["revids"]:
        lost = sorted(set(oa["revids"]) - set(nb["revids"]))
        if lost:
            problems.append(f"ページ全体から改訂IDが消えた: {lost}")
    for p, had in oa["required_phrases"].items():
        if had and not nb["required_phrases"].get(p):
            problems.append(f"必須文言が消えた: 「{p}」")
    lost_links = sorted(set(oa["external_links"]) - set(nb["external_links"]))
    if lost_links:
        problems.append(f"外部リンクが消えた: {lost_links}")

    return problems


def main(argv: list[str]) -> int:
    if "--baseline" in argv:
        src = ROOT / "site" / "public" / "index.html"
        if not src.exists():
            print("公開物が無い。先に ./run.sh build を実行すること", file=sys.stderr)
            return 2
        fp = fingerprint(src.read_text(encoding="utf-8"))
        BASELINE.write_text(json.dumps(fp, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"基準を保存: {BASELINE.relative_to(ROOT)}")
        print(f"  概念 {fp['concept_count']}件 / 改訂ID {len(fp['outside_cards']['revids'])}件 / "
              f"外部リンク {len(fp['outside_cards']['external_links'])}件")
        missing = [p for p, v in fp["outside_cards"]["required_phrases"].items() if not v]
        if missing:
            print(f"  ※ 基準時点で見つからない必須文言: {missing}")
        return 0

    if "--check" in argv:
        i = argv.index("--check")
        if i + 1 >= len(argv):
            print("--check にHTMLのパスが要る", file=sys.stderr)
            return 2
        target = pathlib.Path(argv[i + 1])
        if not BASELINE.exists():
            print("基準が無い。先に --baseline を実行すること", file=sys.stderr)
            return 2
        old = json.loads(BASELINE.read_text(encoding="utf-8"))
        new = fingerprint(target.read_text(encoding="utf-8"))
        problems = diff(old, new)
        if not problems:
            print(f"主張の同一性: 基準と一致（概念{new['concept_count']}件）")
            return 0
        print(f"主張の同一性: {len(problems)}件の差\n")
        for p in problems:
            print("  ✗ " + p)
        print("\n  体裁の変更は差分に出ない。ここに出るのは主張が変わった箇所だけ。")
        return 1

    if "--inventory" in argv:
        i = argv.index("--inventory")
        root = pathlib.Path(argv[i + 1]) if i + 1 < len(argv) else ROOT / "site" / "public"
        problems = check_inventory(root)
        n = sum(1 for f in root.rglob("*") if f.is_file()) if root.exists() else 0
        if not problems:
            print(f"配信物の一覧: {n}件。含めてはいけないものは無い（{root}）")
            return 0
        print(f"配信物の一覧: {len(problems)}件の問題\n")
        for p in problems:
            print("  ✗ " + p)
        return 1

    if "--contract" in argv:
        src = ROOT / "site" / "public" / "index.html"
        problems = check_contract(src.read_text(encoding="utf-8"))
        if not problems:
            print("描画契約: 公開物の数値・改訂ID・概念はすべて viewmodel.json から導ける")
            return 0
        print(f"描画契約: {len(problems)}件の不足\n")
        for p in problems:
            print("  ✗ " + p)
        return 1

    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
