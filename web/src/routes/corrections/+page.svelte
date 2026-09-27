<script lang="ts">
  let { data } = $props();
  const vm = $derived(data.vm);
  const c = $derived(vm.counts);
  const name = (cid: string) =>
    vm.items.find((i: any) => i.concept_id === cid)?.display_name ?? cid;
</script>

<svelte:head><title>訂正の記録 — 空白図鑑 暮らし編</title></svelte:head>

<p class="crumb"><a href="/">空白図鑑</a> ／ 訂正の記録</p>

<section id="corrections">
  <h2>訂正の記録</h2>
  <p class="sec-note prose">
    判定を変更したもの（{c.verdict_changed}件）と、判定は変えずに根拠・確からしさを更新したもの（{c.evidence_updated}件）。
    過去の判定は消していません。
  </p>
  <div class="tblwrap">
    <table class="plain">
      <thead>
        <tr><th>概念</th><th>初回 → 現在</th><th>種類</th><th>理由</th><th>日付</th></tr>
      </thead>
      <tbody>
        {#each vm.corrections as cr}
          <tr>
            <td><a href="/c/{cr.concept_id}">{name(cr.concept_id)}</a></td>
            <td>{cr.prev_verdict_public}<span class="arw">→</span>{cr.verdict_public}</td>
            <td class="kind">{cr.label}</td>
            <td class="un">{cr.reason}</td>
            <td class="n">{cr.judged_at}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
</section>
