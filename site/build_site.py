"""データ → 公開サイト（HTML / CSV / JSON）。

依存パッケージなし。第三者が pip install なしで生成物を再現できることを優先する。

レビューを経て確定した設計上の決定:
  - 「欠落」という断定語を公開表示に使わない → 「確認できず」
  - 文字数を原稿用紙換算などで**比例図示しない**。
    英語1字と日本語1字は情報量が同じではないため、面積比較は誇張になる。
    図示するのは言語によらず数えられる量（節数・脚注内の外部参照ドメイン数）だけ。
  - confidence の内部語（medium）を前面に出さず、意味を日本語で書く
  - 「訂正済み」と一括りにしない。判定変更と根拠更新を分けて数える
  - CSV に判定と検証状態を持たない行を作らない（数値だけ引用されるのを防ぐ）

使い方:
    python3 site/build_site.py
"""

from __future__ import annotations

import csv
import html
import json
import pathlib
import re
import tomllib
from datetime import date

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "site" / "public"

SITE_TITLE = "空白図鑑"
SITE_SUB = "暮らし編"
SITE_URL = "https://kuhaku.caprer.co.jp"
BUILD_DATE = "2026-09-11"

# 内部の判定値 → 公開表示。断定語を見出しに使わない。
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
    "該当なし": "今回観測した3つの指標（本文文字数・節の数・脚注内の外部参照ドメイン数）のいずれでも、日本語版が英語版を上回った。総合的な品質を比べたものではない。",
}
CONFIDENCE_PUBLIC = {
    "high": ("根拠を引用できる", "本文を通読し、判断の根拠を具体的に示せる。"),
    "medium": ("探索済み・断定保留", "示した範囲は確認した。範囲外の記事に記述が残っている可能性がある。"),
    "low": ("観測値のみ", "本文の人手確認をしていない。"),
}


def esc(s) -> str:
    return html.escape(str(s if s is not None else ""))


def rich(s: str) -> str:
    """rationale の簡易マークアップを HTML にする。**強調** と改行だけ。"""
    out = esc(s.strip())
    out = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", out, flags=re.S)
    out = re.sub(r"`(.+?)`", r"<code>\1</code>", out)
    paras = [p.strip() for p in out.split("\n\n") if p.strip()]
    return "".join(f"<p>{p.replace(chr(10), '<br>')}</p>" for p in paras)


def num(n) -> str:
    return "—" if n is None else f"{n:,}"


def rev_link(project: str, revid) -> str:
    if not revid:
        return "—"
    url = f"https://{project}.wikipedia.org/w/index.php?oldid={revid}"
    return f'<a class="rev" href="{url}" rel="nofollow">rev.{revid}</a>'


# --------------------------------------------------------------------------
# データ読み込み
# --------------------------------------------------------------------------


def load():
    concepts = tomllib.loads((ROOT / "concepts" / "living.toml").read_text(encoding="utf-8"))
    judg = tomllib.loads((ROOT / "judgments" / "living.toml").read_text(encoding="utf-8"))
    ev = json.loads((ROOT / "data" / "evidence" / "living-latest.json").read_text(encoding="utf-8"))

    events = judg.get("judgment", [])
    superseded = {e["supersedes"] for e in events if e.get("supersedes")}
    current, history = {}, {}
    for e in events:
        history.setdefault(e["concept_id"], []).append(e)
        if e["id"] not in superseded:
            current[e["concept_id"]] = e

    # 訂正の種類を分ける。「訂正済み」と一括りにすると全部が誤判定に見える。
    for cid, ev_now in current.items():
        chain = history.get(cid, [])
        prev = [x for x in chain if x["id"] != ev_now["id"]]
        ev_now["_prev"] = prev[-1] if prev else None
        if not prev:
            ev_now["_change"] = None
        elif prev[-1]["verdict"] != ev_now["verdict"]:
            ev_now["_change"] = "verdict"      # 判定そのものが変わった
        else:
            ev_now["_change"] = "evidence"     # 判定は同じで根拠・信頼度を更新した

    return (
        {c["id"]: c for c in concepts["concept"]},
        current,
        history,
        {c["concept_id"]: c for c in ev["concepts"]},
        ev,
    )


# --------------------------------------------------------------------------
# 部品
# --------------------------------------------------------------------------


def dots(n, cap=60, cls="") -> str:
    """言語によらず数えられる量だけを図示する。節数・脚注ドメイン数。"""
    if n is None:
        return '<span class="dots none">—</span>'
    if n == 0:
        return '<span class="dots zero" title="0">なし</span>'
    shown = min(n, cap)
    body = "".join(f'<i class="{cls}"></i>' for _ in range(shown))
    more = "…" if n > cap else ""
    return f'<span class="dots">{body}{more}</span>'


def obs_table(c_ev, j) -> str:
    """観測値。それぞれ別の量として並べる。統合スコアは作らない。"""
    comp = c_ev.get("comparison") or {}
    en, ja = c_ev.get("en") or {}, None
    for r in c_ev.get("ja_candidates", []):
        if r["candidate"] == c_ev.get("ja_selected"):
            ja = r
            break
    ja = ja or {}

    def row(label, ja_v, en_v, viz=None, note=""):
        v_ja = dots(ja_v, cls=viz) if viz else f'<span class="n">{num(ja_v)}</span>'
        v_en = dots(en_v, cls=viz) if viz else f'<span class="n">{num(en_v)}</span>'
        return (f"<tr><th>{esc(label)}</th><td>{v_ja}</td><td>{v_en}</td>"
                f"<td class='note'>{esc(note)}</td></tr>")

    rows = [
        row("本文文字数", comp.get("ja_body_chars"), comp.get("en_body_chars"),
            note="言語間で1字あたりの情報量は同じではない。比較の目安にとどまる"),
        row("節の数", comp.get("ja_top_level_sections"), comp.get("en_top_level_sections"), viz="sq"),
        row("脚注内の外部参照ドメイン数", comp.get("ja_direct_ref_domains"),
            comp.get("en_direct_ref_domains"), viz="ci"),
    ]
    lm_ja = (comp.get("ja_last_modified") or "")[:10] or "—"
    lm_en = (comp.get("en_last_modified") or "")[:10] or "—"
    rows.append(f"<tr><th>最終更新</th><td><span class='n'>{esc(lm_ja)}</span></td>"
                f"<td><span class='n'>{esc(lm_en)}</span></td><td class='note'></td></tr>")

    ja_rev = rev_link("ja", ja.get("revid"))
    en_rev = rev_link("en", en.get("revid"))
    notes = []

    # 候補が実在するのに日本語版の列が空欄だと、探索記録と矛盾して見える。
    # 「見つかったが比較対象にしなかった」理由を必ず書く。
    if not c_ev.get("ja_selected"):
        found = [r for r in c_ev.get("ja_candidates", [])
                 if r["exists"] and r["candidate_source"] != "ja_search_candidate"]
        if found:
            lst = "、".join(
                f'「{esc(r["candidate"])}」({rev_link("ja", r.get("revid"))}、{num(r.get("body_chars"))}字)'
                for r in found)
            notes.append(
                f'日本語版に同じ名前の記事 {lst} はあるが、扱っている概念が異なるため'
                '比較の対象にしていない。そのため日本語版の列は空欄にしてある。')
        else:
            notes.append('照会した候補がいずれも存在しなかったため、日本語版の列は空欄にしてある。'
                         '0字の記事があるという意味ではない。')

    # 判定時に読んだ版が観測時と違う場合は隠さず併記する
    jrev = j.get("en_revid")
    if jrev and en.get("revid") and jrev != en.get("revid"):
        notes.append(f'判定時に読んだ英語版は {rev_link("en", jrev)}。観測はその前の版で行った。')
    extra = "".join(f'<p class="tiny">{n}</p>' for n in notes)

    return f"""<table class="obs">
<thead><tr><th></th><th>日本語版<br><span class="revcell">{ja_rev}</span></th>
<th>英語版<br><span class="revcell">{en_rev}</span></th><th></th></tr></thead>
<tbody>{''.join(rows)}</tbody></table>{extra}"""


def trail(c_ev, j) -> str:
    """探索記録。**このサイトの中身はここ。**

    「どれだけ探して見つからなかったか」を、第三者が同じ手順を踏める形で残す。
    """
    cands = [r for r in c_ev.get("ja_candidates", []) if r["candidate_source"] != "ja_search_candidate"]
    lines = []

    lines.append('<div class="trail-sec"><span class="tl">候補タイトル</span>'
                 f'<span class="tn">{len(cands)}件を完全一致で照会</span></div>')
    items = []
    for r in cands:
        mark = "○" if r["exists"] else "✗"
        cls = "hit" if r["exists"] else "miss"
        red = f' <span class="red">→「{esc(r.get("resolved_title"))}」に転送</span>' if r.get("redirected") else ""
        src = {"wikidata_sitelink": "sitelink", "wikidata_label": "ラベル",
               "wikidata_alias": "別名", "manual": "人手"}.get(r["candidate_source"], r["candidate_source"])
        items.append(f'<li class="{cls}"><span class="mk">{mark}</span>'
                     f'<span class="ttl">{esc(r["candidate"])}</span>'
                     f'<span class="src">{esc(src)}</span>{red}</li>')
    lines.append(f'<ul class="cands">{"".join(items)}</ul>')

    conts = j.get("checked_containers") or []
    if conts:
        lines.append('<div class="trail-sec"><span class="tl">上位・隣接記事</span>'
                     f'<span class="tn">{len(conts)}件を通読</span></div>')
        lines.append('<ul class="conts">' + "".join(
            f'<li>{esc(c)}</li>' for c in conts) + "</ul>")

    terms = j.get("search_terms") or []
    if terms:
        lines.append('<div class="trail-sec"><span class="tl">検索語</span>'
                     f'<span class="tn">{len(terms)}語</span></div>')
        lines.append('<p class="terms">' + " ".join(
            f'<span>{esc(t)}</span>' for t in terms) + "</p>")

    return f'<div class="trail"><div class="trail-head">探索記録　{esc(j.get("judged_at"))}</div>{"".join(lines)}</div>'


def card(i, cid, con, j, c_ev) -> str:
    v = j["verdict"]
    pub = VERDICT_PUBLIC[v]
    cname, cdesc = CONFIDENCE_PUBLIC.get(j.get("confidence", "medium"))
    en_title = (c_ev.get("en") or {}).get("resolved_title") or con["en_title"]
    ja_name = con["ja_candidates"][0] if con.get("ja_candidates") else cid

    change = ""
    if j.get("_change"):
        p = j["_prev"]
        reason = esc(j.get("correction_reason") or "")
        if j["_change"] == "verdict":
            label = "判定を変更"
            body = (f'初回 <b>{esc(VERDICT_PUBLIC[p["verdict"]])}</b> → '
                    f'現在 <b>{esc(pub)}</b>。{reason}')
        else:
            # 判定が変わっていないのに「初回X → 現在X」と出すと意味が伝わらない。
            # 変わったのは確からしさと根拠なので、そこだけを書く。
            label = "根拠を更新"
            prev_c = CONFIDENCE_PUBLIC.get(p.get("confidence", "medium"))[0]
            shift = (f'確からしさ <b>{esc(prev_c)}</b> → <b>{esc(cname)}</b>。'
                     if prev_c != cname else "")
            body = f'判定は「{esc(pub)}」のまま。{shift}{reason}'
        change = (f'<div class="change"><span class="cbadge {j["_change"]}">{label}</span>'
                  f'<span>{body}</span></div>')

    elig = con.get("eligibility")
    elig_txt = {"a": "国に依存しない概念", "b": "国内での発生・利用を日本語資料で確認",
                "c": "海外制度だが国内の生活に影響"}.get(elig, "")

    return f"""<article class="card v-{VERDICT_ORDER.index(v)}" id="{esc(cid)}">
  <header>
    <div class="cno">{i:02d}</div>
    <div class="ctitles">
      <h3>{esc(ja_name)}</h3>
      <p class="en">{esc(en_title)}</p>
    </div>
    <div class="verdict">
      <span class="vlabel">{esc(pub)}</span>
      <span class="conf" title="{esc(cdesc)}">{esc(cname)}</span>
    </div>
  </header>
  <p class="why">{esc(con.get('why','').replace('★看板', '').replace('★反例候補。','').strip())}</p>
  {change}
  {obs_table(c_ev, j)}
  {trail(c_ev, j)}
  <details class="reason"><summary>判定の根拠を読む</summary>{rich(j['rationale'])}
    <p class="meta">判定 {esc(j['id'])}・確認日 {esc(j['judged_at'])}・
    対象 {esc(con['theme'])}・採用基準 {esc(elig)}（{esc(elig_txt)}）・
    <a href="#{esc(cid)}">この項目のURL</a></p>
  </details>
</article>"""


# --------------------------------------------------------------------------
# 出力
# --------------------------------------------------------------------------


def build():
    concepts, current, history, evmap, ev = load()
    judged = [(cid, j) for cid, j in current.items()]
    judged.sort(key=lambda t: (VERDICT_ORDER.index(t[1]["verdict"]),
                               -((evmap[t[0]].get("comparison") or {}).get("en_body_chars") or 0)))

    from collections import Counter
    vc = Counter(j["verdict"] for _, j in judged)
    breakdown = (
        f'{len(judged)}件のうち、日本語版に記事はあるが英語版で扱われる論点を確認できなかったのが'
        f'<strong>{vc.get("薄い", 0)}件</strong>。残りは、'
        f'記事を確認できないもの{vc.get("欠落", 0)}件、'
        f'別の記事の中に定義があるもの{vc.get("実質包含", 0)}件、'
        f'扱う範囲が違って比較できないもの{vc.get("判定不能", 0)}件、'
        f'観測した指標では日本語版が上回るもの{vc.get("該当なし", 0)}件に分かれました。'
        f'<strong>短いことと、無いことは別です。</strong>'
    )
    n_verdict_changed = sum(1 for _, j in judged if j.get("_change") == "verdict")
    n_evidence_updated = sum(1 for _, j in judged if j.get("_change") == "evidence")
    unjudged = [c for c in ev["concepts"] if c["concept_id"] not in current]

    cards, i = [], 0
    last_v = None
    for cid, j in judged:
        if j["verdict"] != last_v:
            last_v = j["verdict"]
            cards.append(
                f'<div class="vgroup"><h2>{esc(VERDICT_PUBLIC[last_v])}</h2>'
                f'<p>{esc(VERDICT_DEF[last_v])}</p></div>')
            if last_v == "実質包含":
                cards.append(
                    '<blockquote class="quote"><p>養育スタイル（en:parenting styles）について研究し、'
                    'スタイルを「消極・受け身型」「独裁・支配型」「民主型」「無関心型」の4つに分類した。</p>'
                    '<cite>日本語版Wikipedia「ダイアナ・バウムリンド」'
                    '<a class="rev" href="https://ja.wikipedia.org/w/index.php?oldid=103834617" rel="nofollow">rev.103834617</a>'
                    '（記事全体で354字）</cite></blockquote>'
                    '<p class="sec-note">英語版で48,396字ある「育児スタイル」を、日本語版で確認できたのはこの一文です。'
                    'ここに並ぶ類型は研究史上の分類を説明したものであり、'
                    '<strong>親を評価するものではありません</strong>。</p>')
        i += 1
        cards.append(card(i, cid, concepts[cid], j, evmap[cid]))

    # ---- 未検証の一覧（数値だけを切り出せないよう、必ず「未検証」を各行に持たせる）
    un_rows = "".join(
        f"<tr><td>{esc(c['theme'])}</td><td>{esc((c.get('en') or {}).get('resolved_title'))}</td>"
        f"<td class='n'>{num((c.get('comparison') or {}).get('en_body_chars'))}</td>"
        f"<td class='n'>{num((c.get('comparison') or {}).get('ja_body_chars'))}</td>"
        f"<td class='un'>未検証</td></tr>"
        for c in sorted(unjudged, key=lambda x: x["theme"]))

    # ---- 訂正履歴
    corr_rows = []
    for cid, j in judged:
        if not j.get("_change"):
            continue
        p = j["_prev"]
        corr_rows.append(
            f"<tr><td>{esc(concepts[cid]['ja_candidates'][0])}</td>"
            f"<td>{esc(VERDICT_PUBLIC[p['verdict']])}<span class='arw'>→</span>"
            f"{esc(VERDICT_PUBLIC[j['verdict']])}</td>"
            f"<td>{'判定を変更' if j['_change']=='verdict' else '根拠を更新'}</td>"
            f"<td>{esc(j.get('correction_reason'))}</td>"
            f"<td class='n'>{esc(j['judged_at'])}</td></tr>")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "index.html").write_text(
        page(cards, un_rows, corr_rows, len(ev["concepts"]), len(judged),
             n_verdict_changed, n_evidence_updated, ev, breakdown),
        encoding="utf-8")

    write_data(concepts, current, evmap, ev, unjudged)
    print(f"生成: {OUT/'index.html'}")
    print(f"      {OUT/'kuhaku-zukan.csv'}")
    print(f"      {OUT/'kuhaku-zukan.json'}")
    print(f"検証済み {len(judged)}件 / 全{len(ev['concepts'])}件・判定変更 {n_verdict_changed}件・根拠更新 {n_evidence_updated}件")


def write_data(concepts, current, evmap, ev, unjudged):
    """CSV/JSON。**全行に判定と検証状態を持たせる。** 数値だけの表は作らない。"""
    rows = []
    for c in ev["concepts"]:
        cid = c["concept_id"]
        j = current.get(cid)
        comp = c.get("comparison") or {}
        con = concepts[cid]
        rows.append({
            "concept_id": cid,
            "theme": con["theme"],
            "en_title": (c.get("en") or {}).get("resolved_title"),
            "ja_article": c.get("ja_selected"),
            "verification_status": "人手確認済み" if j else "未確認",
            "verdict": VERDICT_PUBLIC[j["verdict"]] if j else "未検証",
            "verdict_internal": j["verdict"] if j else "",
            "verdict_definition": VERDICT_DEF[j["verdict"]] if j else "人手確認をしていない",
            "confidence": CONFIDENCE_PUBLIC[j["confidence"]][0] if j else "",
            "confidence_meaning": CONFIDENCE_PUBLIC[j["confidence"]][1] if j else "",
            "judgment_id": j["id"] if j else "",
            "supersedes": (j.get("supersedes") or "") if j else "",
            "judged_at": j.get("judged_at") if j else "",
            "en_revid": (c.get("en") or {}).get("revid"),
            "ja_revid": next((r.get("revid") for r in c.get("ja_candidates", [])
                              if r["candidate"] == c.get("ja_selected")), None),
            # 不在は 0 ではなく空欄にする。0字の記事があると誤読されるため。
            "en_body_chars": comp.get("en_body_chars"),
            "ja_body_chars": comp.get("ja_body_chars"),
            "en_sections": comp.get("en_top_level_sections"),
            "ja_sections": comp.get("ja_top_level_sections"),
            "en_footnote_ref_domains": comp.get("en_direct_ref_domains"),
            "ja_footnote_ref_domains": comp.get("ja_direct_ref_domains"),
            "comparison_valid": not comp.get("invalid", False),
            "ja_relation": ("同一概念として比較" if c.get("ja_selected")
                            else ("未選定" if not c.get("requires_human_selection") else "人手選定待ち")),
            "eligibility_criterion": (c.get("eligibility") or {}).get("criterion"),
            "eligibility_status": (c.get("eligibility") or {}).get("status"),
            "evidence_run_id": ev["run_id"],
            "calc_version": ev["calc_version"],
            "scope": "Wikipedia日本語版に限定した調査。日本語に情報が存在しないことを意味しない",
            "permalink": f"{SITE_URL}/#{cid}",
            "source_license": "Wikipedia由来のデータは CC BY-SA 4.0",
        })

    with (OUT / "kuhaku-zukan.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    (OUT / "kuhaku-zukan.json").write_text(json.dumps({
        "title": f"{SITE_TITLE} {SITE_SUB}",
        "url": SITE_URL,
        "built_at": BUILD_DATE,
        "scope": "Wikipedia日本語版に対応する記事が確認できるかを調べたもの。"
                 "日本語で情報が入手できるかを調べたものではない。",
        "license": "Wikipedia由来のデータは CC BY-SA 4.0。帰属表示のうえ利用できる。",
        "notes": ev["notes"],
        "verdict_definitions": {VERDICT_PUBLIC[k]: v for k, v in VERDICT_DEF.items()},
        "confidence_definitions": {v[0]: v[1] for v in CONFIDENCE_PUBLIC.values()},
        "items": rows,
        "judgments": tomllib.loads((ROOT / "judgments" / "living.toml").read_text(encoding="utf-8"))["judgment"],
        "evidence": ev["concepts"],
    }, ensure_ascii=False, indent=2), encoding="utf-8")


CSS = """
:root{
  --paper:#FBFAF7; --ink:#16161A; --ai:#1C3A5E; --shu:#A63A2A;
  --sumi:#6E6E75; --kei:#DEDCD5; --kuu:#EFEDE7;
  --mincho:"Hiragino Mincho ProN","Yu Mincho",YuMincho,"Noto Serif JP",serif;
  --gothic:"Hiragino Sans","Yu Gothic",YuGothic,"Noto Sans JP",sans-serif;
  --mono:ui-monospace,SFMono-Regular,"SF Mono",Menlo,monospace;
}
@media (prefers-color-scheme:dark){
  :root{--paper:#141416;--ink:#E8E6E0;--ai:#8FB3D9;--shu:#E0776A;
        --sumi:#9A9AA2;--kei:#33333A;--kuu:#1E1E22;}
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--paper);color:var(--ink);
  font-family:var(--gothic);font-size:16px;line-height:1.85;
  font-feature-settings:"palt";}
.wrap{max-width:50rem;margin:0 auto;padding:0 1.25rem}
a{color:inherit;text-underline-offset:.2em;text-decoration-thickness:.5px}
a:focus-visible,summary:focus-visible{outline:2px solid var(--ai);outline-offset:3px}
h1,h2,h3{font-family:var(--mincho);font-weight:600;line-height:1.4;letter-spacing:.02em}
code{font-family:var(--mono);font-size:.9em}
.n,.rev,.revcell{font-family:var(--mono);font-variant-numeric:tabular-nums}

/* ── 表紙 ───────────────────────────── */
.cover{padding:4.5rem 0 2.5rem;border-bottom:1px solid var(--kei)}
.brand{font-family:var(--mincho);font-size:2.6rem;letter-spacing:.28em;margin:0 0 .2rem}
.brand-sub{font-family:var(--mincho);font-size:.95rem;letter-spacing:.4em;color:var(--sumi);margin:0}
.thesis{margin:3rem 0 0;font-family:var(--mincho);font-size:1.32rem;line-height:1.95}
.thesis2{margin:1.4rem 0 0;font-family:var(--mincho);font-size:1.05rem;color:var(--ai)}
.breakdown{margin:1.8rem 0 0;padding:1rem 1.1rem;border:1px solid var(--kei);background:var(--kuu);font-size:.92rem;line-height:1.9}
.quote{margin:1.6rem 0 0;padding:1.3rem 1.4rem;background:var(--kuu);border-left:2px solid var(--ai)}
.quote p{margin:0;font-family:var(--mincho);font-size:1.05rem}
.quote cite{display:block;margin-top:.7rem;font-style:normal;font-size:.8rem;color:var(--sumi);font-family:var(--gothic)}
.lede{margin:2.4rem 0 0;color:var(--sumi);font-size:.95rem}
.lede strong{color:var(--ink)}

/* ── 節 ────────────────────────────── */
section{padding:3rem 0;border-bottom:1px solid var(--kei)}
section>h2{font-size:1.25rem;margin:0 0 1rem;color:var(--ai)}
section>h2::before{content:"";display:inline-block;width:1.6rem;height:1px;
  background:var(--ai);vertical-align:.35em;margin-right:.7rem}
.sec-note{color:var(--sumi);font-size:.9rem}

/* ── 訂正方針 ───────────────────────── */
.corr-policy{background:var(--kuu);padding:1.2rem 1.3rem;border-top:2px solid var(--shu)}
.corr-policy h2{color:var(--shu);font-size:1.05rem;margin:0 0 .5rem}
.corr-policy p{margin:.3rem 0;font-size:.92rem}
.corr-policy .n{color:var(--shu);font-weight:700}

/* ── 判定の定義 ─────────────────────── */
.defs{list-style:none;padding:0;margin:0}
.defs li{display:grid;grid-template-columns:11rem 1fr;gap:1rem;
  padding:.85rem 0;border-top:1px solid var(--kei);align-items:start}
.defs li:last-child{border-bottom:1px solid var(--kei)}
.defs .d{font-size:.9rem;color:var(--sumi)}

/* 判定ラベル: 塗りの量で分類そのものを表す（色だけに頼らない） */
.vlabel{display:inline-block;font-size:.78rem;font-family:var(--gothic);
  padding:.22rem .6rem;border:1px solid var(--ai);color:var(--ai);
  white-space:nowrap;line-height:1.5}
.v-0 .vlabel,.dl-0{background:transparent}
.v-1 .vlabel,.dl-1{background:color-mix(in srgb,var(--ai) 12%,transparent)}
.v-2 .vlabel,.dl-2{background:color-mix(in srgb,var(--ai) 26%,transparent)}
.v-3 .vlabel,.dl-3{background:repeating-linear-gradient(-45deg,
  transparent 0 4px,color-mix(in srgb,var(--ai) 22%,transparent) 4px 8px)}
.v-4 .vlabel,.dl-4{background:var(--ai);color:var(--paper);border-color:var(--ai)}

/* ── カード ─────────────────────────── */
.vgroup{margin:3rem 0 1.2rem;padding-top:1.5rem;border-top:2px solid var(--ai)}
.vgroup h2{font-size:1.35rem;margin:0 0 .35rem;color:var(--ai)}
.vgroup p{margin:0;font-size:.88rem;color:var(--sumi)}
.card{padding:2rem 0;border-top:1px solid var(--kei)}
.card>header{display:grid;grid-template-columns:2.6rem 1fr auto;gap:.9rem;align-items:start}
.cno{font-family:var(--mono);font-size:.85rem;color:var(--sumi);padding-top:.35rem}
.ctitles h3{margin:0;font-size:1.35rem}
.ctitles .en{margin:.15rem 0 0;font-size:.8rem;color:var(--sumi);font-family:var(--mono)}
.verdict{text-align:right}
.conf{display:block;margin-top:.35rem;font-size:.72rem;color:var(--sumi)}
.why{margin:.9rem 0 0 3.5rem;font-size:.95rem}
@media(max-width:38rem){.card>header{grid-template-columns:2.2rem 1fr}
  .verdict{grid-column:2;text-align:left;margin-top:.4rem}.why{margin-left:0}}

.change{margin:1rem 0 0;padding:.7rem .9rem;border-left:2px solid var(--shu);
  background:color-mix(in srgb,var(--shu) 6%,transparent);font-size:.86rem}
.cbadge{display:inline-block;margin-right:.6rem;padding:.1rem .5rem;
  font-size:.72rem;border:1px solid var(--shu);color:var(--shu)}
.cbadge.evidence{border-style:dashed}

/* 観測値 */
.obs{width:100%;border-collapse:collapse;margin:1.4rem 0 0;font-size:.86rem}
.obs th,.obs td{text-align:left;padding:.5rem .6rem;border-bottom:1px solid var(--kei);vertical-align:top}
.obs thead th{font-weight:400;font-size:.78rem;color:var(--sumi);border-bottom:1px solid var(--ai);white-space:nowrap}
.obs thead th:nth-child(2),.obs thead th:nth-child(3){width:9rem}
.obs tbody th{font-weight:400;color:var(--sumi);width:11rem}
.obs .note{color:var(--sumi);font-size:.72rem;line-height:1.6}
.revcell a{color:var(--ai);font-size:.72rem}
.dots{display:inline-flex;flex-wrap:wrap;gap:2px;max-width:14rem;align-items:center}
.dots i{width:6px;height:6px;background:var(--ai);display:block}
.dots i.ci{border-radius:50%}
.dots.zero{color:var(--sumi);font-size:.8rem;font-family:var(--gothic)}
.tiny{font-size:.75rem;color:var(--sumi);margin:.5rem 0 0}

/* 探索記録 ── この頁の中心 */
.trail{margin:1.6rem 0 0;border:1px solid var(--kei);border-left:3px solid var(--ai);
  background:var(--kuu);padding:1rem 1.1rem;font-family:var(--mono);font-size:.78rem;line-height:1.75}
.trail-head{color:var(--ai);letter-spacing:.14em;padding-bottom:.5rem;
  border-bottom:1px dashed var(--kei);margin-bottom:.7rem}
.trail-sec{display:flex;gap:.7rem;align-items:baseline;margin:.7rem 0 .2rem}
.trail-sec .tl{color:var(--ai)}
.trail-sec .tn{color:var(--sumi);font-size:.72rem}
.cands,.conts{list-style:none;margin:0;padding:0}
.cands li,.conts li{padding:.1rem 0}
.cands .mk{display:inline-block;width:1.2em;color:var(--sumi)}
.cands li.hit .mk{color:var(--ai)}
.cands .src{color:var(--sumi);font-size:.7rem;margin-left:.6rem}
.cands .red{color:var(--shu)}
.conts li{padding-left:1.2em;text-indent:-1.2em}
.conts li::before{content:"・";color:var(--sumi)}
.terms{margin:.2rem 0 0}
.terms span{display:inline-block;margin:0 .5rem .2rem 0;padding:0 .35rem;
  background:var(--paper);border:1px solid var(--kei)}

.reason{margin:1.2rem 0 0;font-size:.9rem}
.reason summary{cursor:pointer;color:var(--ai);font-size:.85rem}
.reason p{margin:.8rem 0}
.reason .meta{font-size:.75rem;color:var(--sumi);border-top:1px solid var(--kei);padding-top:.6rem}

/* ── 表 ────────────────────────────── */
.tblwrap{overflow-x:auto}
table.plain{width:100%;border-collapse:collapse;font-size:.84rem;min-width:34rem}
table.plain th,table.plain td{text-align:left;padding:.45rem .6rem;border-bottom:1px solid var(--kei)}
table.plain thead th{font-weight:400;color:var(--sumi);border-bottom:1px solid var(--ai)}
table.plain td.n{font-family:var(--mono);font-variant-numeric:tabular-nums}
td.un{color:var(--sumi);font-size:.78rem}
.arw{color:var(--shu);padding:0 .4rem}

.limits li,.method li{margin:.5rem 0}
.dl{display:flex;gap:.8rem;flex-wrap:wrap;margin:1rem 0 0}
.dl a{display:inline-block;padding:.5rem 1rem;border:1px solid var(--ai);color:var(--ai);
  text-decoration:none;font-size:.88rem}
.dl a:hover{background:var(--ai);color:var(--paper)}
.cmd{font-family:var(--mono);font-size:.8rem;background:var(--kuu);border:1px solid var(--kei);padding:.8rem 1rem;overflow-x:auto;line-height:1.8;margin:.8rem 0}
footer{padding:3rem 0 5rem;color:var(--sumi);font-size:.82rem}
.flinks{display:flex;gap:1.4rem;flex-wrap:wrap;padding-bottom:1.2rem;margin-bottom:1.2rem;border-bottom:1px solid var(--kei)}
.flinks a{color:var(--ai);font-size:.9rem}
.cta{border:1px solid var(--kei);padding:1.3rem;margin:1rem 0 0;background:var(--kuu)}
.cta h2{margin:0 0 .4rem;font-size:1.05rem}
@media (prefers-reduced-motion:no-preference){
  .card{animation:fade .5s ease both}
  @keyframes fade{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
}
"""


def page(cards, un_rows, corr_rows, total, judged_n, n_v, n_e, ev, breakdown) -> str:
    corr_tbl = ("<div class='tblwrap'><table class='plain'><thead><tr><th>概念</th><th>初回 → 現在</th>"
                "<th>種類</th><th>理由</th><th>日付</th></tr></thead><tbody>"
                + "".join(corr_rows) + "</tbody></table></div>")
    defs = "".join(
        f'<li><span class="vlabel dl-{i}">{esc(VERDICT_PUBLIC[v])}</span>'
        f'<span class="d">{esc(VERDICT_DEF[v])}</span></li>'
        for i, v in enumerate(VERDICT_ORDER)) + \
        '<li><span class="vlabel dl-0" style="border-style:dashed">未検証</span>' \
        '<span class="d">観測値は取得したが、人手での確認をしていない。' \
        '欠けていることを意味しない。</span></li>'

    return f"""<!doctype html>
<html lang="ja"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{SITE_TITLE} {SITE_SUB} — 日本語版Wikipediaの空白を、探索記録つきで</title>
<meta name="description" content="暮らしに関わる{total}の概念について、日本語版Wikipediaに対応する記事があるかを調べ、{judged_n}件を人手で検証した記録。判定手順・誤り・訂正履歴をすべて公開しています。">
<meta property="og:title" content="{SITE_TITLE} {SITE_SUB}">
<meta property="og:description" content="日本語版Wikipediaに対応する記事があるかを{total}概念で調べ、{judged_n}件を人手検証した記録。">
<meta property="og:type" content="article">
<style>{CSS}</style>
</head><body>
<div class="wrap">

<header class="cover">
  <h1 class="brand">{SITE_TITLE}</h1>
  <p class="brand-sub">{SITE_SUB}</p>

  <p class="thesis">英語版にある概念が、日本語版に見当たらない。<br>
  そう判断したもののうち2件は、探索範囲を広げると<br>
  別の記事の中に書かれていました。</p>

  <p class="thesis2">差分を取るだけでは、あるとも無いとも言えない。これはその記録です。</p>

  <p class="lede">暮らしに関わる<strong>{total}の概念</strong>について、日本語版Wikipediaに対応する記事があるかを調べ、
  <strong>{judged_n}件</strong>を人手で検証しました。分かったのは、日本語の知識が全体的に遅れているということではありません。
  <strong>抜けかたが一様ではない</strong>ということです。独立した記事が無くても、別の記事の一文として存在していることがある。
  記事があっても、同じ名前の別の概念だったりする。観測した指標では日本語版が上回る概念もある。<br><br>
  ここで言えるのは<strong>「Wikipedia日本語版に対応する記事を確認できたか」だけ</strong>です。
  日本語で情報が手に入るかどうかを調べたものではありません。<br>また、独立した記事が無いことは、<strong>編集上の欠陥や、独立記事にすべきだということを意味しません</strong>。上位の記事にまとめるのは、多くの場合それ自体が妥当な編集判断です。</p>

  <p class="breakdown">{breakdown}</p>
</header>

<section class="corr-policy">
  <h2>先に、間違いについて</h2>
  <p>この調査では、<span class="n">{judged_n}</span>件のうち<span class="n">{n_v}</span>件で<strong>判定そのものを後から変更</strong>し、
  <span class="n">{n_e}</span>件で根拠と確からしさを更新しました。</p>
  <p>最初に代表例として選んだ事例が、2回続けて誤りでした。どちらも「日本語版に無い」と判断したものが、
  探索範囲を広げると別の記事の中にあった、というものです。公開後に6件を追加で検証したときにも、
  同じことが2回起きました。</p>
  <p class="sec-note">訂正は上書きせず、すべて履歴として残しています。→ <a href="#corrections">訂正の記録</a></p>
</section>

<section>
  <h2>判定の種類</h2>
  <p class="sec-note">先に定義を示します。塗りの濃さは「日本語版にどれだけ記述があるか」の分類を表しています。</p>
  <ul class="defs">{defs}</ul>
</section>

<section>
  <h2>図鑑</h2>
  <p class="sec-note">{judged_n}件。判定の種類ごとに並べ、各項目に探索記録を付けました。
  数字はすべて観測値です。文字数・節数・脚注の数はそれぞれ別の量であり、足し合わせて「情報量」とは呼びません。</p>
  {''.join(cards)}
</section>

<section id="corrections">
  <h2>訂正の記録</h2>
  <p class="sec-note">判定を変更したもの（{n_v}件）と、判定は変えずに根拠・確からしさを更新したもの（{n_e}件）。
  過去の判定は消していません。</p>
  {corr_tbl}
  <h3 style="font-size:1rem;margin:2rem 0 .5rem">収集手順そのものの訂正</h3>
  <ul class="limits sec-note">
    <li><strong>全文検索の結果を比較対象に選んでいた。</strong>「パラソーシャル関係」が「バーチャルYouTuber」と比較され、文字数比 0.73 と出た。検索は候補を集めるためだけに使い、比較対象には選ばないよう直した。</li>
    <li><strong>Wikidataのラベル・別名を典拠として自動選定していた。</strong>「満腹感」が「食」への転送を掴んで比 7.72、「栄養強化」に「栄養補助食品」を採用した。自動選定は Wikidata の言語間リンクがある場合だけに限った。</li>
    <li><strong>バイト数で比較していた。</strong>日本語はUTF-8で1文字が約3バイトになるため、日本語版と英語版の分量比を約3倍過大に算出していた。文字数での比較に直した。</li>
    <li><strong>キーワード検査でナビゲーション用テンプレートのリンクを「記述あり」と数えていた。</strong>本文114字の「快適性評価」でPMVや作用温度が「ある」と出た。本文だけを対象に直した。</li>
    <li><strong>本文と改訂IDを別々に取得していた。</strong>記録した版と測った本文が別の版になりうるため、1回のリクエストにまとめた。</li>
  </ul>
</section>

<section>
  <h2>調べかた</h2>
  <ol class="method sec-note">
    <li>英語版の記事から Wikidata の項目を特定し、日本語版への言語間リンク・日本語ラベル・別名を集める。</li>
    <li>人手で用意した候補も加え、<strong>すべて完全一致で</strong>日本語版に存在するか照会する。転送は追跡し、転送先を実体として扱う。</li>
    <li>全文検索は<strong>候補を思いつくためだけ</strong>に使う。語の一部が一致しただけの記事を掴むため、比較対象には選ばない。</li>
    <li>本文（レンダリング後の平文から、脚注・出典・関連項目・外部リンクなどの附録節をその子節ごと除いたもの）の文字数、節の数、脚注に直接書かれた外部URLのドメイン数、最終更新を記録する。</li>
    <li>人手で英語版と日本語版を読み比べ、上位・隣接記事も通読したうえで判定する。<strong>文字数が少ないというだけでは「論点に差がある」とはしない。</strong>英語版で扱われていて日本語版の記事では確認できない論点を、具体的に特定できた場合だけそう判定する。</li>
    <li>「確認できず」と判断する場合も、<strong>確からしさは「断定保留」までにとどめる</strong>。不在は原理的に完全には証明できないため、確認した記事とその改訂ID、使った検索語をすべて公開する。</li>
  </ol>
  <p class="sec-note">取得はすべて Python の標準ライブラリだけで行っています。第三者が追加インストールなしに同じ手順を再現できることを優先しました。</p>
</section>

<section>
  <h2>この調査の限界</h2>
  <ul class="limits sec-note">
    <li><strong>調べたのは Wikipedia 日本語版だけです。</strong>辞典、論文、書籍、記事など日本語の情報源全体を調べたものではありません。「日本語に情報が無い」ことは主張していません。</li>
    <li><strong>「確認できず」は不在の証明ではありません。</strong>示した別名と隣接記事の範囲で見つからなかった、という意味です。範囲外に記述がある可能性は常に残ります。見つけた方はご指摘ください。</li>
    <li><strong>文字数の比較には限界があります。</strong>英語1文字と日本語1文字は情報量が同じではありません。文字数は内容の量そのものを表しません。</li>
    <li><strong>脚注の数え方に取りこぼしがあります。</strong>本文に直接書かれた <code>&lt;ref&gt;</code> の中のURLだけを数えており、<code>{{{{sfn}}}}</code> などのテンプレート形式の脚注は拾えません。この形式を多用する記事では実際より少なく出ます。</li>
    <li><strong>ドメイン数は発行元の独立性を保証しません。</strong>同じ発行元が複数のドメインを持つこともあります。名称も「脚注内の外部参照ドメイン数」であり、「出典の数」ではありません。</li>
    <li><strong>英語版が正しい基準だとは考えていません。</strong>記述が長いことと正確であることは別です。日本語版が独立記事を作らず上位記事に統合しているのは、多くの場合それ自体が妥当な編集判断です。</li>
    <li><strong>記述内容の正確性は評価していません。</strong>調べたのは、どの論点が扱われているかだけです。</li>
  </ul>
</section>

<section>
  <h2>データ</h2>
  <p class="sec-note">全{total}件分を配布します。人手検証をしていない{total - judged_n}件も、
  <strong>必ず「未検証」と記録した上で</strong>含めています。数値だけを取り出せる表は作っていません。
  引用の際は判定と確からしさも併せてご利用ください。</p>
  <div class="dl">
    <a href="/kuhaku-zukan.csv" download>CSV をダウンロード</a>
    <a href="/kuhaku-zukan.json" download>JSON をダウンロード（探索記録・訂正履歴つき）</a>
  </div>
  <div class="dl"><a href="https://github.com/caprerinc/kuhaku">ソースコードと生データ（GitHub）</a></div>
  <p class="sec-note" style="margin-top:1rem">観測の実行ID <code>{esc(ev['run_id'])}</code>／算出規則 <code>{esc(ev['calc_version'])}</code>。
  各項目の改訂IDから、測定した版そのものを開けます。</p>

  <h3 style="font-size:1rem;margin:2.2rem 0 .5rem">この数字を検算する</h3>
  <p class="sec-note">「再現できます」と書くだけでは足りないので、検算するコマンドを用意しました。
  取得したAPI応答は1件ずつ保存してあり（344件）、そこから観測値を作り直して、
  <strong>上で配布しているCSVの数字</strong>に突き合わせます。<strong>ネットワークは使いません。</strong></p>
  <pre class="cmd">git clone https://github.com/caprerinc/kuhaku
cd kuhaku &amp;&amp; ./run.sh verify</pre>
  <p class="sec-note">2026-09-14 に実行した結果です。保存した生データ344件はすべてファイル名のハッシュと一致。
  観測128件（実ページ95件）を作り直し、記事が無いと記録した85件も応答で確認しました。
  <strong>公開しているCSVの47行すべてが再計算値と一致</strong>し、不一致はありません。</p>
  <p class="sec-note">この検査が示すのは<strong>「同梱の応答から公開値を作り直せる」ことだけ</strong>です。
  その応答が本当にWikipediaから取得されたものであること、算出規則そのものの妥当性、
  人手判定の妥当性は示しません。</p>

  <h3 style="font-size:1rem;margin:2.2rem 0 .5rem">この数字はいつのものか</h3>
  <p class="sec-note">記事は日々書き換わるので、ここの数字は測定した版のものです。
  <code>./run.sh drift</code> で、現在の版と比べて何が変わったかを確認できます。</p>
  <p class="sec-note">2026-09-14 に実行したところ、対象81ページのうち<strong>16ページ</strong>で
  改訂IDが変わっていました。記事が変わること自体は当たり前で、誤りではありません。
  ここで言えるのは、公開した数字は時間とともに古くなる、ということだけです。
  実行結果は <code>data/drift/</code> に日付つきで残してあります。</p>
</section>

<section>
  <div class="cta">
    <h2>この調査をやった人</h2>
    <p class="sec-note">株式会社Caprer が作りました。素朴に差分を取ると誤判定が出る領域で、
    検証手順と誤り率を公開できる形に整えるのが仕事です。
    日本語データの品質調査や、AI・RAG の評価系の構築をお手伝いしています。</p>
    <p class="sec-note"><a href="https://caprer.co.jp">caprer.co.jp</a></p>
  </div>
</section>

<section>
  <h2>人手検証をしていない{total - judged_n}件</h2>
  <p class="sec-note">観測値だけを取得したものです。<strong>欠けていることを意味しません。</strong>
  同じ手順で人手検証をするまでは判定を出しません。</p>
  <div class="tblwrap"><table class="plain"><thead><tr>
    <th>テーマ</th><th>英語版の記事</th><th>英語版 本文文字数</th><th>日本語版 本文文字数</th><th>状態</th>
  </tr></thead><tbody>{un_rows}</tbody></table></div>
</section>

<footer>
  <p class="flinks">
    <a href="https://github.com/caprerinc/kuhaku">ソースコードとデータ</a>
    <a href="https://github.com/caprerinc/kuhaku/issues/new?template=correction.yml">誤りを報告する</a>
    <a href="#corrections">訂正の記録</a>
  </p>
  <p>{SITE_TITLE} {SITE_SUB}　{BUILD_DATE} 版</p>
  <p>Wikipedia 由来のデータは <a href="https://creativecommons.org/licenses/by-sa/4.0/deed.ja" rel="license">CC BY-SA 4.0</a> です。
  本文の引用および観測値は、日本語版・英語版Wikipedia の各改訂版に基づきます。</p>
  <p>誤りを見つけたら<a href="https://github.com/caprerinc/kuhaku/issues/new?template=correction.yml">Issue</a>で教えてください。訂正は上書きせず、履歴として公開します。</p>
</footer>

</div></body></html>"""


if __name__ == "__main__":
    build()
