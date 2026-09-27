<script lang="ts">
  let { data } = $props();
  const sc = $derived(data.vm.scorecard);
</script>

<svelte:head><title>調べかた — 空白図鑑 暮らし編</title></svelte:head>

<p class="crumb"><a href="/">空白図鑑</a> ／ 調べかた</p>

<section>
  <h2>調べかた</h2>
  <ol class="method sec-note prose">
    <li>英語版の記事から Wikidata の項目を特定し、日本語版への言語間リンク・日本語ラベル・別名を集める。</li>
    <li>人手で用意した候補も加え、<strong>すべて完全一致で</strong>日本語版に存在するか照会する。転送は追跡し、転送先を実体として扱う。</li>
    <li>全文検索は<strong>候補を思いつくためだけ</strong>に使う。語の一部が一致しただけの記事を掴むため、比較対象には選ばない。</li>
    <li>本文（レンダリング後の平文から、脚注・出典・関連項目・外部リンクなどの附録節をその子節ごと除いたもの）の文字数、節の数、脚注に直接書かれた外部URLのドメイン数、最終更新を記録する。</li>
    <li>人手で英語版と日本語版を読み比べ、上位・隣接記事も通読したうえで判定する。<strong>文字数が少ないというだけでは「論点に差がある」とはしない。</strong>英語版で扱われていて日本語版の記事では確認できない論点を、具体的に特定できた場合だけそう判定する。</li>
    <li>「確認できず」と判断する場合も、<strong>確からしさは「断定保留」までにとどめる</strong>。不在は原理的に完全には証明できないため、確認した記事とその改訂ID、使った検索語をすべて公開する。</li>
  </ol>

  <h3 style="font-size:1rem;margin:2.2rem 0 .5rem">なぜこの手順が要るのか</h3>
  <p class="sec-note prose">Wikidata の言語間リンクを見るだけなら一瞬です。実際にやってみた結果がこれです。</p>
  <p class="sec-note prose">
    人手で検証した{sc.judged}件のうち、<strong>言語間リンクが無いので機械的には「日本語版に無い」と出るもの</strong>が
    {sc.flagged_missing}件ありました。人手で確認したところ、そのうち<strong
      >{sc.contradicted.length}件は別の記事の中に定義がありました。</strong
    >残る{sc.not_contradicted.length}件は人手で調べても確認できませんでした。
  </p>
  <p class="sec-note prose">
    <strong>これは精度の評価ではありません。</strong>{sc.judged}件は手選びで、無作為に抽出したものではありません。
    また「人手でも確認できなかった」ことは、その機械判定が正しかったことを意味しません。
    たとえばスクリーンタイムは、同じ名前で別概念の記事が日本語版に実在しますが、
    言語間リンクが無いというだけでフラグが立っています。結論は反証されていませんが、
    この規則が同名の別概念を見分けられたわけではありません。
  </p>
  <p class="sec-note prose">
    集計の元になった{sc.judged}行の表は <a href="/naive-check.csv" download>naive-check.csv</a> で配布しています。
    <code>./run.sh stats</code> で計算し直せます。
  </p>
  <p class="sec-note prose">
    取得はすべて Python の標準ライブラリだけで行っています。第三者が追加インストールなしに同じ手順を再現できることを優先しました。
  </p>
</section>
