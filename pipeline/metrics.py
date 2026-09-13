"""記事の観測値を算出する。

**重要**: ここで出す数値はすべて「観測値」であって品質評価ではない。
文字数・節数・脚注ドメイン数は別々の量であり、統合して「情報量」と呼んではいけない。
公開時の表記も「本文文字数は英語版の◯%」に限定すること。

算出規則を変えたら CALC_VERSION を上げる。証拠バンドルに版が記録されるので、
後から「どの規則で出した数字か」を第三者が特定できる。
"""

from __future__ import annotations

import re
from urllib.parse import unquote, urlsplit

CALC_VERSION = "1.1.0"
# 1.1.0: 附録節の子節も除外する / hostname を使う / アーカイブ展開の成否を数える /
#        JSTOR・arXiv を識別子リゾルバから外す（実体の発行元・リポジトリであるため）

# 附録節。本文文字数から除外する。
# 英語版は Further reading / External links が長く、除外しないと格差を
# 過大に見せる方向へ偏る（実測で en 記事の3〜9%を占めた）。
APPENDIX_HEADINGS = {
    # en
    "references", "external links", "see also", "notes", "further reading",
    "bibliography", "citations", "sources", "footnotes", "works cited",
    # ja
    "脚注", "出典", "注釈", "参考文献", "関連項目", "外部リンク", "参照",
    "文献", "註", "註釈", "参考", "関連文献",
}

# eTLD+1 を求めるための複合サフィックス。完全な Public Suffix List ではない。
# 依存パッケージを増やさないための割り切りであり、この限界は公開ページに明記する。
MULTI_LABEL_SUFFIXES = {
    "co.jp", "ne.jp", "or.jp", "ac.jp", "go.jp", "ed.jp", "gr.jp", "lg.jp", "ad.jp",
    "co.uk", "org.uk", "ac.uk", "gov.uk", "me.uk", "nhs.uk", "sch.uk",
    "com.au", "net.au", "org.au", "edu.au", "gov.au",
    "co.nz", "org.nz", "govt.nz", "ac.nz",
    "co.kr", "or.kr", "go.kr", "ac.kr", "re.kr",
    "com.cn", "edu.cn", "gov.cn", "net.cn", "org.cn", "ac.cn",
    "com.tw", "org.tw", "gov.tw", "edu.tw",
    "com.br", "gov.br", "org.br", "edu.br",
    "com.in", "org.in", "net.in", "gov.in", "ac.in", "nic.in",
    "com.sg", "gov.sg", "edu.sg", "com.hk", "gov.hk", "edu.hk",
    "com.my", "com.mx", "gob.mx", "com.ar", "gob.es", "com.tr", "gov.tr",
    "co.za", "org.za", "com.ua", "com.pl", "gov.pl",
}

WIKIMEDIA_DOMAINS = {
    "wikipedia.org", "wikimedia.org", "wikidata.org", "wiktionary.org",
    "wikisource.org", "wikibooks.org", "wikiquote.org", "wikiversity.org",
    "wikinews.org", "mediawiki.org", "wmflabs.org", "toolforge.org", "wikivoyage.org",
}

SHORTENER_DOMAINS = {
    "bit.ly", "tinyurl.com", "goo.gl", "t.co", "ow.ly", "is.gd",
    "buff.ly", "dlvr.it", "amzn.to", "j.mp", "rb.gy", "cutt.ly",
}

SOCIAL_DOMAINS = {
    "twitter.com", "x.com", "facebook.com", "instagram.com", "youtube.com",
    "youtu.be", "tiktok.com", "reddit.com", "linkedin.com", "threads.net",
    "pinterest.com", "tumblr.com", "note.com", "ameblo.jp", "medium.com",
}

# 識別子リゾルバ。実体の発行元ではないので、発行元ドメインとしては数えない。
# doi.org を1ドメインとして数えると、数百件の学術引用が「1発行元」に潰れてしまう。
#
# JSTOR・arXiv・Semantic Scholar はここに入れない。単なるリゾルバではなく
# 実体を持つリポジトリ／提供元であり、除外すると過少計上になる。
IDENTIFIER_RESOLVERS = {
    "doi.org", "dx.doi.org", "handle.net", "hdl.handle.net",
    "worldcat.org", "crossref.org",
}

ARCHIVE_DOMAINS = {"web.archive.org", "archive.org", "archive.today", "archive.ph", "archive.is", "archive.fo"}

_HEADING_RE = re.compile(r"^(={2,6})\s*(.+?)\s*\1\s*$", re.MULTILINE)
_REF_RE = re.compile(r"<ref\b[^>]*?(?<!/)>(.*?)</ref\s*>", re.IGNORECASE | re.DOTALL)
_URL_RE = re.compile(r"https?://[^\s\|\]\}<>\"']+")
_IDENTIFIER_PARAM_RE = re.compile(r"\|\s*(doi|pmid|pmc|isbn|issn|jstor|bibcode|arxiv)\s*=\s*[^\|\}\s]", re.IGNORECASE)


# --------------------------------------------------------------------------
# 本文
# --------------------------------------------------------------------------


def split_sections(plaintext: str) -> list[tuple[str | None, int, str]]:
    """平文を (見出し, レベル, 本文) に分解する。導入部の見出しは None。"""
    if not plaintext:
        return []
    sections: list[tuple[str | None, int, str]] = []
    matches = list(_HEADING_RE.finditer(plaintext))
    lead_end = matches[0].start() if matches else len(plaintext)
    sections.append((None, 0, plaintext[:lead_end]))
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(plaintext)
        sections.append((m.group(2).strip(), len(m.group(1)), plaintext[start:end]))
    return sections


def is_appendix(heading: str | None) -> bool:
    if heading is None:
        return False
    return heading.strip().lower().strip("＝= 　") in APPENDIX_HEADINGS


def body_metrics(plaintext: str) -> dict:
    """本文文字数と節数。附録節は**その子節ごと**除外する。空白文字は数えない。

    子節まで落とすのは、`== References ==` の下にある `=== Notes ===` のような
    見出しが、名前が附録一覧に無いだけで本文に戻ってしまうため。
    """
    sections = split_sections(plaintext)
    body_chars = 0
    dropped_chars = 0
    top_sections: list[str] = []
    dropped_sections: list[str] = []
    skip_until_level: int | None = None

    for heading, level, content in sections:
        text = re.sub(r"\s+", "", content)
        # 附録節の内側にいる間（＝より深い見出しが続く間）は落とし続ける
        if skip_until_level is not None:
            if heading is not None and level > skip_until_level:
                dropped_chars += len(text)
                dropped_sections.append(heading)
                continue
            skip_until_level = None
        if is_appendix(heading):
            skip_until_level = level
            dropped_chars += len(text)
            dropped_sections.append(heading)
            continue
        body_chars += len(text)
        if level == 2 and heading:
            top_sections.append(heading)
    return {
        "body_chars": body_chars,
        "appendix_chars_excluded": dropped_chars,
        "top_level_sections": len(top_sections),
        "top_level_section_titles": top_sections,
        "excluded_appendix_sections": dropped_sections,
    }


# --------------------------------------------------------------------------
# 脚注
# --------------------------------------------------------------------------


def registrable_domain(host: str) -> str:
    host = _strip_www(host.lower().strip("."))
    parts = host.split(".")
    if len(parts) <= 2:
        return host
    last_two = ".".join(parts[-2:])
    if last_two in MULTI_LABEL_SUFFIXES:
        return ".".join(parts[-3:])
    return last_two


def _strip_www(host: str) -> str:
    """先頭の 'www.' だけを外す。lstrip('www.') は文字集合を剥がすので使えない
    （'wiki.example.com' が 'ki.example.com' になる）。"""
    return host[4:] if host.lower().startswith("www.") else host


def unwrap_archive(url: str) -> tuple[str, str]:
    """アーカイブURLから元URLを復元する。

    返り値は (URL, 状態)。状態は "not_archive" / "unwrapped" / "unwrap_failed"。
    復元できたか失敗したかを数えられるようにしてある（成功率を公開するため）。
    """
    try:
        parts = urlsplit(url)
    except ValueError:
        return url, "not_archive"
    host = _strip_www(parts.netloc.lower())
    if host not in ARCHIVE_DOMAINS and parts.netloc.lower() not in ARCHIVE_DOMAINS:
        return url, "not_archive"
    tail = parts.path + (("?" + parts.query) if parts.query else "")
    m = re.search(r"(https?)(://|%3A%2F%2F|:/)(.+)$", tail, re.IGNORECASE)
    if m:
        inner = unquote(m.group(0))
        inner = re.sub(r"^(https?):/(?!/)", r"\1://", inner)
        return inner, "unwrapped"
    return url, "unwrap_failed"


def footnote_metrics(wikitext: str) -> dict:
    """**wikitext に直接書かれた `<ref>...</ref>` の中のURL** だけを数える。

    prop=extlinks は使わない。公式サイトや「外部リンク」節が混ざり、
    「検証可能性の指標」という名前に耐えないため。

    既知の限界（公開ページに明記すること）:
      - `{{sfn}}` `{{harvnb}}` `{{efn}}` `{{reflist|refs=...}}` は拾わない。
        これらを多用する記事では系統的に**過少計上**になる。
      - 自己閉じの `<ref name=x />` は数えない（ユニークドメイン数には通常影響しない）。
      - 入れ子の ref は正しく解析できない。
    したがって公開時の指標名は「情報源の数」ではなく
    **「脚注に直接書かれた外部URLのドメイン数」** とすること。
    """
    empty = {
        "ref_count": 0, "refs_with_url": 0, "refs_without_url": 0,
        "refs_with_identifier": 0, "external_ref_domains": 0,
        "external_ref_domain_list": [], "excluded_domain_counts": {},
        "archive_unwrapped": 0, "archive_unwrap_failed": 0,
        "template_footnote_markers": 0,
    }
    if not wikitext:
        return empty

    refs = _REF_RE.findall(wikitext)
    domains: set[str] = set()
    excluded: dict[str, int] = {}
    with_url = 0
    without_url = 0
    with_identifier = 0
    unwrapped = 0
    unwrap_failed = 0

    for ref in refs:
        urls = _URL_RE.findall(ref)
        has_identifier = bool(_IDENTIFIER_PARAM_RE.search(ref))
        if has_identifier:
            with_identifier += 1
        if not urls:
            without_url += 1
            continue
        with_url += 1
        for raw in urls:
            url, state = unwrap_archive(raw.rstrip(".,;)"))
            if state == "unwrapped":
                unwrapped += 1
            elif state == "unwrap_failed":
                unwrap_failed += 1
            try:
                host = urlsplit(url).hostname  # netloc だとポート・userinfo で壊れる
            except ValueError:
                continue
            if not host:
                continue
            dom = registrable_domain(host)
            if dom in WIKIMEDIA_DOMAINS:
                excluded["wikimedia"] = excluded.get("wikimedia", 0) + 1
            elif dom in SHORTENER_DOMAINS:
                excluded["shortener"] = excluded.get("shortener", 0) + 1
            elif dom in SOCIAL_DOMAINS:
                excluded["social"] = excluded.get("social", 0) + 1
            elif dom in IDENTIFIER_RESOLVERS:
                excluded["identifier_resolver"] = excluded.get("identifier_resolver", 0) + 1
            elif dom in ARCHIVE_DOMAINS:
                excluded["unresolved_archive"] = excluded.get("unresolved_archive", 0) + 1
            else:
                domains.add(dom)

    # テンプレート形式の脚注がどれだけあるか。過少計上の度合いを読者が測れるように残す。
    template_markers = len(re.findall(r"\{\{\s*(sfn|harvnb|harv|efn|r)\b", wikitext, re.IGNORECASE))

    return {
        "ref_count": len(refs),
        "refs_with_url": with_url,
        "refs_without_url": without_url,
        "refs_with_identifier": with_identifier,
        "external_ref_domains": len(domains),
        "external_ref_domain_list": sorted(domains),
        "excluded_domain_counts": excluded,
        "archive_unwrapped": unwrapped,
        "archive_unwrap_failed": unwrap_failed,
        "template_footnote_markers": template_markers,
    }
