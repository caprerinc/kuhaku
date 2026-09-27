<script lang="ts">
  import Meta from '$lib/Meta.svelte';
  let { data } = $props();
  const vm = $derived(data.vm);
  const c = $derived(vm.counts);
  const ver = $derived(vm.verification);
</script>

<Meta
  title="データ — 空白図鑑 暮らし編"
  description="全{c.concepts_total}件の CSV/JSON と、公開値をネットワーク無しで検算する手順。"
  path="/data"
/>

<p class="crumb"><a href="/">空白図鑑</a> ／ データ</p>

<section>
  <h2>データ</h2>
  <p class="sec-note prose">
    全{c.concepts_total}件分を配布します。人手検証をしていない{c.unjudged}件も、
    <strong>必ず「未検証」と記録した上で</strong>含めています。数値だけを取り出せる表は作っていません。
    引用の際は判定と確からしさも併せてご利用ください。
  </p>
  <div class="dl">
    <a href="/kuhaku-zukan.csv" download>CSV をダウンロード</a>
    <a href="/kuhaku-zukan.json" download>JSON をダウンロード（探索記録・訂正履歴つき）</a>
    <a href="/naive-check.csv" download>機械判定と人手判定の突き合わせ（CSV）</a>
  </div>
  <div class="dl"><a href="https://github.com/caprerinc/kuhaku">ソースコードと生データ（GitHub）</a></div>
  <p class="sec-note prose" style="margin-top:1rem">
    観測の実行ID <code>{vm.evidence_run_id}</code>／算出規則 <code>{vm.calc_version}</code>。
    各項目の改訂IDから、測定した版そのものを開けます。
  </p>

  <h3 style="font-size:1rem;margin:2.2rem 0 .5rem">この数字を検算する</h3>
  <p class="sec-note prose">
    「再現できます」と書くだけでは足りないので、検算するコマンドを用意しました。
    取得したAPI応答は1件ずつ保存してあり（{ver.raw_hash_ok}件）、そこから観測値を作り直して、
    <strong>上で配布しているCSVの数字</strong>に突き合わせます。<strong>ネットワークは使いません。</strong>
  </p>
  <pre class="cmd">git clone https://github.com/caprerinc/kuhaku
cd kuhaku &amp;&amp; ./run.sh verify</pre>
  <p class="sec-note prose">
    保存した生データ{ver.raw_hash_ok}件はすべてファイル名のハッシュと一致。
    観測{ver.recomputed}件（実ページ{ver.pages}件）を作り直し、記事が無いと記録した{ver.absent_checked}件も応答で確認しました。
    <strong>公開しているCSVの{ver.published_rows}行すべてが再計算値と一致</strong>し、不一致はありません。
  </p>
  <p class="sec-note prose">
    この検査が示すのは<strong>「同梱の応答から公開値を作り直せる」ことだけ</strong>です。
    その応答が本当にWikipediaから取得されたものであること、算出規則そのものの妥当性、人手判定の妥当性は示しません。
  </p>

  <h3 style="font-size:1rem;margin:2.2rem 0 .5rem">この数字はいつのものか</h3>
  <p class="sec-note prose">
    記事は日々書き換わるので、ここの数字は測定した版のものです。
    <code>./run.sh drift</code> で、現在の版と比べて何が変わったかを確認できます。
  </p>
  <p class="sec-note prose">
    {#if vm.drift}{vm.drift.measured_at} に実行したところ、対象{vm.drift.targets}ページのうち<strong
        >{vm.drift.changed}ページ</strong
      >で改訂IDが変わっていました。{:else}まだ測っていません。{/if}
    記事が変わること自体は当たり前で、誤りではありません。
    ここで言えるのは、公開した数字は時間とともに古くなる、ということだけです。
    実行結果は <code>data/drift/</code> に日付つきで残してあります。
  </p>
</section>
