<script lang="ts">
  /**
   * 数えられる量（節の数・脚注内の外部参照ドメイン数）の表示。
   *
   * **数値が主、図は従。** 旧版は図だけを出し、幅 14rem で折り返したうえ
   * 60 個を超えると「…」で切っていた。数えられない図は符号化として嘘になる。
   * ここでは数値を必ず出し、図は入るところまで並べる。図が欠けても真は失われない。
   *
   * null は「照合する候補がそもそも無かった」。0 とは違う。取り違えると
   * 「0字の記事がある」と読める（公開ページに注記もある）。
   */
  let { value, shape = 'sq' }: { value: number | null; shape?: 'sq' | 'ci' } = $props();

  // 欠測の字形はここ一箇所で決める。旧版は – と — が混在していた。
  const MISSING = '—';
  const MAX_GLYPHS = 40;
  const glyphs = $derived(value === null ? 0 : Math.min(value, MAX_GLYPHS));
</script>

{#if value === null}
  <span class="count none" title="照合する候補が無かった。0 ではない。">{MISSING}</span>
{:else if value === 0}
  <span class="count zero">なし</span>
{:else}
  <span class="count">
    <span class="num">{value.toLocaleString('ja-JP')}</span>
    <span class="glyphs" aria-hidden="true">
      {#each Array(glyphs) as _}<i class={shape}></i>{/each}
    </span>
  </span>
{/if}
