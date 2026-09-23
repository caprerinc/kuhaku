<script lang="ts">
  import '../app.css';
  import Count from '$lib/Count.svelte';
  import Verdict from '$lib/Verdict.svelte';

  let { data } = $props();
  // $derived にしないと data の初期値だけを捕まえる（Svelte 5）。
  const vm = $derived(data.vm);

  // 判定語の union は **契約の JSON 自身から導く**。
  // ここで型を手書きすると Python が持つ意味づけが二重化して、いずれずれる。
  type VerdictKey = keyof typeof data.vm.labels.verdict_public;
  const order = $derived(vm.labels.verdict_order as VerdictKey[]);
</script>

<svelte:head><title>空白図鑑 暮らし編</title></svelte:head>

<main class="wrap">
  <h1>空白図鑑</h1>
  <p class="prose">
    移植中の疎通確認。描画契約 schema {vm.schema_version} / 証拠 {vm.evidence_run_id}。
    全 {vm.counts.concepts_total} 件のうち {vm.counts.judged} 件を人手で検証。
    訂正は判定変更 {vm.counts.verdict_changed} 件・根拠更新 {vm.counts.evidence_updated} 件。
  </p>

  <h2>判定の種類</h2>
  <ul class="defs" style="list-style:none;padding:0">
    {#each order as v, i}
      <li>
        <Verdict label={vm.labels.verdict_public[v]} order={i} />
        <span class="prose" style="display:block">{vm.labels.verdict_def[v]}</span>
      </li>
    {/each}
    <li>
      <Verdict label="未検証" order={0} unverified />
      <span class="prose" style="display:block">
        観測値は取得したが、人手での確認をしていない。欠けていることを意味しない。
      </span>
    </li>
  </ul>

  <h2>観測値の出しかた</h2>
  <p class="prose">
    数えられる量だけを図示する。<strong>数値が主で図は従</strong>。図が入りきらなくても数値が真を持つ。
    「{'—'}」は照合する候補が無かったという意味で、0 ではない。
  </p>
  <table class="obs">
    <thead>
      <tr><th>概念</th><th>節の数（日本語版）</th><th>脚注ドメイン（英語版）</th></tr>
    </thead>
    <tbody>
      {#each vm.items.slice(0, 5) as it}
        <tr>
          <th>{it.concept_id}</th>
          <td><Count value={it.observations.ja.sections} /></td>
          <td><Count value={it.observations.en.ref_domains} shape="ci" /></td>
        </tr>
      {/each}
    </tbody>
  </table>
</main>
