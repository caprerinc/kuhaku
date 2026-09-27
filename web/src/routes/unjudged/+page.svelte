<script lang="ts">
  import Meta from '$lib/Meta.svelte';
  let { data } = $props();
  const vm = $derived(data.vm);
  const nm = (n: number | null) => (n === null ? '—' : n.toLocaleString('ja-JP'));
</script>

<Meta
  title="人手検証をしていない項目 — 空白図鑑 暮らし編"
  description="観測値だけを取得した{vm.counts.unjudged}件。欠けていることを意味しません。"
  path="/unjudged"
/>

<p class="crumb"><a href="/">空白図鑑</a> ／ 未検証</p>

<section>
  <h2>人手検証をしていない{vm.counts.unjudged}件</h2>
  <p class="sec-note prose">
    観測値だけを取得したものです。<strong>欠けていることを意味しません。</strong>
    同じ手順で人手検証をするまでは判定を出しません。
  </p>
  <div class="tblwrap">
    <table class="plain">
      <thead>
        <tr>
          <th>テーマ</th><th>英語版の記事</th><th>英語版 本文文字数</th><th>日本語版 本文文字数</th><th>状態</th>
        </tr>
      </thead>
      <tbody>
        {#each vm.unjudged as u}
          <tr>
            <td class="theme">{u.theme}</td>
            <td>{u.en_title}</td>
            <td class="n">{nm(u.observations.en.body_chars)}</td>
            <td class="n">{nm(u.observations.ja.body_chars)}</td>
            <td class="un">未検証</td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
</section>
