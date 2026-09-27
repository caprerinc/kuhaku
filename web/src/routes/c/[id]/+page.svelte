<script lang="ts">
  import Card from '$lib/Card.svelte';
  let { data } = $props();
  const item = $derived(data.item);
</script>

<svelte:head>
  <title>{item.display_name} — 空白図鑑 暮らし編</title>
  <meta name="description" content={item.why} />
</svelte:head>

<p class="crumb"><a href="/">空白図鑑</a> ／ {item.verdict.public}</p>

<Card {item} index={data.index} standalone />

<nav class="pager">
  {#if data.prev}
    <a href="/c/{data.prev.concept_id}">← {data.prev.display_name}</a>
  {:else}<span></span>{/if}
  <a href="/">一覧へ</a>
  {#if data.next}
    <a href="/c/{data.next.concept_id}">{data.next.display_name} →</a>
  {:else}<span></span>{/if}
</nav>
