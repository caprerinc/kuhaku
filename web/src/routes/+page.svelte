<script lang="ts">
  import '../app.css';
  import Card from '$lib/Card.svelte';
  import Verdict from '$lib/Verdict.svelte';

  let { data } = $props();
  const vm = $derived(data.vm);
  type VerdictKey = keyof typeof data.vm.labels.verdict_public;
  const order = $derived(vm.labels.verdict_order as VerdictKey[]);

  // 判定ごとにまとめる。契約の items は既に判定順に並んでいる。
  const groups = $derived(
    order
      .map((v) => ({
        key: v,
        label: vm.labels.verdict_public[v],
        def: vm.labels.verdict_def[v],
        items: vm.items.filter((i: any) => i.verdict.internal === v),
      }))
      .filter((g) => g.items.length > 0),
  );
</script>

<svelte:head><title>空白図鑑 暮らし編</title></svelte:head>

<div class="wrap">
  <h1>空白図鑑</h1>

  <section>
    <h2>判定の種類</h2>
    <p class="sec-note prose">塗りの濃さは「日本語版にどれだけ記述があるか」の分類を表しています。</p>
    <ul class="defs">
      {#each order as v, i}
        <li>
          <span><Verdict label={vm.labels.verdict_public[v]} order={i} /></span>
          <span class="d">{vm.labels.verdict_def[v]}</span>
        </li>
      {/each}
      <li>
        <span><Verdict label="未検証" order={0} unverified /></span>
        <span class="d">観測値は取得したが、人手での確認をしていない。欠けていることを意味しない。</span>
      </li>
    </ul>
  </section>

  <section>
    <h2>図鑑</h2>
    <p class="sec-note prose">
      {vm.counts.judged}件。判定の種類ごとに並べ、各項目に探索記録を付けました。数字はすべて観測値です。
      文字数・節数・脚注の数はそれぞれ別の量であり、足し合わせて「情報量」とは呼びません。
    </p>
  </section>

  {#each groups as g}
    <div class="vgroup">
      <h2>{g.label}</h2>
      <p>{g.def}</p>
    </div>
    {#each g.items as item, i}
      <Card {item} index={vm.items.indexOf(item) + 1} />
    {/each}
  {/each}
</div>
