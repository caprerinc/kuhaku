<script lang="ts">
  /**
   * 注記。文言は描画契約（Python側）で決まっている。
   * ここはリンクを含む文を「断片の配列」として並べるだけで、解釈を持たない。
   */
  type Segment = { text: string; href?: string | null };
  let { segments }: { segments: Segment[] } = $props();
</script>

<p class="tiny">
  {#each segments as s}{#if s.href}<a class="rev" href={s.href} rel="nofollow">{s.text}</a
    >{:else}{s.text}{/if}{/each}
</p>
