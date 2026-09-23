<script lang="ts">
  /**
   * 判定ラベル。塗りの量で序列を、斜線・破線で種別を表す（色だけに頼らない）。
   * 公開ラベルへの言い換えは Python 側（描画契約）で済んでいる。
   * ここで内部語から引き直すと意味づけが二重化するので、渡された文字列をそのまま出す。
   */
  let {
    label,
    order,
    unverified = false,
  }: { label: string; order: number; unverified?: boolean } = $props();
</script>

<span class="vlabel dl-{order}" class:unverified>{label}</span>
