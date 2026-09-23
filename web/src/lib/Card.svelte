<script lang="ts">
  import ObsTable from './ObsTable.svelte';
  import Trail from './Trail.svelte';
  import Verdict from './Verdict.svelte';
  import { rich, richInline } from './rich';

  /** 概念1件。判定・観測値・探索記録・訂正・根拠を1枚にまとめる。 */
  let { item, index }: { item: any; index: number } = $props();
  const no = $derived(String(index).padStart(2, '0'));
</script>

<article class="card v-{item.verdict.order}" id={item.concept_id}>
  <header>
    <div class="cno">{no}</div>
    <div class="ctitles">
      <h3>{item.display_name}</h3>
      <p class="en">{item.en_title}</p>
    </div>
    <div class="verdict">
      <Verdict label={item.verdict.public} order={item.verdict.order} />
      <span class="conf" title={item.confidence.note}>{item.confidence.label}</span>
    </div>
  </header>

  <p class="why">{item.why}</p>

  {#if item.correction}
    <div class="change">
      <span class="cbadge {item.correction.kind}">{item.correction.label}</span>
      <span>{@html richInline(item.correction.body)}</span>
    </div>
  {/if}

  <ObsTable {item} />
  <Trail {item} />

  <details class="reason">
    <summary>判定の根拠を読む</summary>
    {@html rich(item.rationale)}
    <p class="meta">
      判定 {item.judgment_id}・確認日 {item.judged_at}・ 対象 {item.theme}・採用基準 {item.eligibility}（{item.eligibility_text}）・
      <a href="#{item.concept_id}">この項目のURL</a>
    </p>
  </details>
</article>
