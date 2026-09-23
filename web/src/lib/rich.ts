/**
 * 判定文の簡易マークアップを HTML にする。**強調** と `コード` と段落だけ。
 *
 * **必ず先にエスケープしてからマークアップを適用する。** 逆にすると、
 * 本文に < が含まれていたときにタグとして解釈される。
 * 出力は {@html} で描画するので、この順序が唯一の防御になる。
 */
export function rich(src: string): string {
  const escaped = src
    .trim()
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');

  const marked = escaped
    .replace(/\*\*([\s\S]+?)\*\*/g, '<strong>$1</strong>')
    .replace(/`([^`]+?)`/g, '<code>$1</code>');

  return marked
    .split(/\n\s*\n/)
    .map((p) => p.trim())
    .filter(Boolean)
    .map((p) => `<p>${p.replace(/\n/g, '<br>')}</p>`)
    .join('');
}

/** 段落で包まずに **強調** だけを適用する。訂正の一文など、行内で使う場合。 */
export function richInline(src: string): string {
  return src
    .trim()
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/\*\*([\s\S]+?)\*\*/g, '<strong>$1</strong>');
}
