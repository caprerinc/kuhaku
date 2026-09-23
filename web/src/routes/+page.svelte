<script lang="ts">
  import '../app.css';
  let { data } = $props();
  // $derived にしないと data の初期値だけを捕まえる（Svelte 5）。
  const vm = $derived(data.vm);
</script>

<svelte:head><title>空白図鑑 暮らし編</title></svelte:head>

<main>
  <h1>空白図鑑</h1>
  <p>足場の疎通確認。描画契約 schema {vm.schema_version} / 証拠 {vm.evidence_run_id}</p>
  <ul>
    <li>全 {vm.counts.concepts_total} 件 / 判定済み {vm.counts.judged} 件 / 未検証 {vm.counts.unjudged} 件</li>
    <li>訂正: 判定変更 {vm.counts.verdict_changed} 件・根拠更新 {vm.counts.evidence_updated} 件</li>
  </ul>
  <h2>判定の種類</h2>
  <dl>
    {#each vm.labels.verdict_order as v}
      <dt>{vm.labels.verdict_public[v]}</dt>
      <dd>{vm.labels.verdict_def[v]}</dd>
    {/each}
  </dl>
</main>
