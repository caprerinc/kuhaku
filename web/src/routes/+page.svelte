<script lang="ts">
  import '../app.css';
  import Card from '$lib/Card.svelte';
  import Verdict from '$lib/Verdict.svelte';
  import { richInline } from '$lib/rich';

  let { data } = $props();
  const vm = $derived(data.vm);
  type VerdictKey = keyof typeof data.vm.labels.verdict_public;
  const order = $derived(vm.labels.verdict_order as VerdictKey[]);
  const c = $derived(vm.counts);
  const sc = $derived(vm.scorecard);
  const ver = $derived(vm.verification);
  const fq = $derived(vm.flagship_quote);
  const nm = (n: number) => n.toLocaleString('ja-JP');
  const name = (cid: string) =>
    vm.items.find((i: any) => i.concept_id === cid)?.display_name ?? cid;

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

<svelte:head>
  <title>空白図鑑 暮らし編 — 日本語版Wikipediaの空白を、探索記録つきで</title>
</svelte:head>

<div class="wrap">
  <header class="cover">
    <h1 class="brand">空白図鑑</h1>
    <p class="brand-sub">暮らし編</p>

    <!-- 旧版はここが「2件」の直書きだった。判定ログから導けない語りの数字だったので、
         公開データから計算できる突き合わせの数に置き換えている。 -->
    <p class="thesis prose">
      英語版にある概念が、日本語版に見当たらない。<br />
      機械的にそう出た{sc.flagged_missing}件のうち{sc.contradicted.length}件は、探索範囲を広げると<br />
      別の記事の中に書かれていました。
    </p>

    <p class="thesis2 prose">差分を取るだけでは、あるとも無いとも言えない。これはその記録です。</p>

    <p class="lede prose">
      暮らしに関わる<strong>{c.concepts_total}の概念</strong>について、日本語版Wikipediaに対応する記事があるかを調べ、
      <strong>{c.judged}件</strong>を人手で検証しました。分かったのは、日本語の知識が全体的に遅れているということではありません。
      <strong>抜けかたが一様ではない</strong>ということです。独立した記事が無くても、別の記事の一文として存在していることがある。
      記事があっても、同じ名前の別の概念だったりする。観測した指標では日本語版が上回る概念もある。<br /><br />
      ここで言えるのは<strong>「Wikipedia日本語版に対応する記事を確認できたか」だけ</strong>です。
      日本語で情報が手に入るかどうかを調べたものではありません。<br />また、独立した記事が無いことは、<strong
        >編集上の欠陥や、独立記事にすべきだということを意味しません</strong
      >。上位の記事にまとめるのは、多くの場合それ自体が妥当な編集判断です。
    </p>

    <p class="breakdown prose">
      {c.judged}件のうち、日本語版に記事はあるが英語版で扱われる論点を確認できなかったのが<strong
        >{c.by_verdict['薄い']}件</strong
      >。残りは、記事を確認できないもの{c.by_verdict['欠落']}件、別の記事の中に定義があるもの{c
        .by_verdict['実質包含']}件、扱う範囲が違って比較できないもの{c.by_verdict['判定不能']}件、
      観測した指標では日本語版が上回るもの{c.by_verdict['該当なし']}件に分かれました。
      <strong>短いことと、無いことは別です。</strong>
    </p>
  </header>

  <section class="corr-policy">
    <h2>先に、間違いについて</h2>
    <p class="prose">
      この調査では、<span class="n">{c.judged}</span>件のうち<span class="n">{c.verdict_changed}</span
      >件で<strong>判定そのものを後から変更</strong>し、
      <span class="n">{c.evidence_updated}</span>件で根拠と確からしさを更新しました。
    </p>
    <p class="prose">
      最初に代表例として選んだ事例が、2回続けて誤りでした。どちらも「日本語版に無い」と判断したものが、
      探索範囲を広げると別の記事の中にあった、というものです。公開後に6件を追加で検証したときにも、同じことが2回起きました。
    </p>
    <p class="sec-note prose">
      訂正は上書きせず、すべて履歴として残しています。→ <a href="#corrections">訂正の記録</a>
    </p>
  </section>

  <section>
    <h2>判定の種類</h2>
    <p class="sec-note prose">
      先に定義を示します。塗りの濃さは「日本語版にどれだけ記述があるか」の分類を表しています。
    </p>
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
      {c.judged}件。判定の種類ごとに並べ、各項目に探索記録を付けました。数字はすべて観測値です。
      文字数・節数・脚注の数はそれぞれ別の量であり、足し合わせて「情報量」とは呼びません。
    </p>

    {#each groups as g}
      <div class="vgroup">
        <h2>{g.label}</h2>
        <p>{g.def}</p>
      </div>
      {#if g.key === '実質包含' && fq}
        <blockquote class="quote prose">
          <p>{fq.text}</p>
          <cite
            >日本語版Wikipedia「{fq.source_title}」<a
              class="rev"
              href={fq.source_rev_url}
              rel="nofollow">rev.{fq.source_revid}</a
            >（記事全体で{nm(fq.source_body_chars)}字）</cite
          >
        </blockquote>
        <p class="sec-note prose">
          英語版で{nm(fq.en_body_chars)}字ある「{name(fq.concept_id)}」を、日本語版で確認できたのはこの一文です。
          ここに並ぶ類型は研究史上の分類を説明したものであり、<strong>親を評価するものではありません</strong>。
        </p>
      {/if}
      {#each g.items as item}
        <Card {item} index={vm.items.indexOf(item) + 1} />
      {/each}
    {/each}
  </section>

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
              <td><a href="#{cr.concept_id}">{name(cr.concept_id)}</a></td>
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

  <section>
    <h2>この調査の限界</h2>
    <ul class="limits sec-note prose">
      <li><strong>調べたのは Wikipedia 日本語版だけです。</strong>辞典、論文、書籍、記事など日本語の情報源全体を調べたものではありません。「日本語に情報が無い」ことは主張していません。</li>
      <li><strong>「確認できず」は不在の証明ではありません。</strong>示した別名と隣接記事の範囲で見つからなかった、という意味です。範囲外に記述がある可能性は常に残ります。見つけた方はご指摘ください。</li>
      <li><strong>文字数の比較には限界があります。</strong>英語1文字と日本語1文字は情報量が同じではありません。文字数は内容の量そのものを表しません。</li>
      <li><strong>脚注の数え方に取りこぼしがあります。</strong>本文に直接書かれた <code>&lt;ref&gt;</code> の中のURLだけを数えており、テンプレート形式の脚注は拾えません。この形式を多用する記事では実際より少なく出ます。</li>
      <li><strong>ドメイン数は発行元の独立性を保証しません。</strong>同じ発行元が複数のドメインを持つこともあります。名称も「脚注内の外部参照ドメイン数」であり、「出典の数」ではありません。</li>
      <li><strong>英語版が正しい基準だとは考えていません。</strong>記述が長いことと正確であることは別です。日本語版が独立記事を作らず上位記事に統合しているのは、多くの場合それ自体が妥当な編集判断です。</li>
      <li><strong>記述内容の正確性は評価していません。</strong>調べたのは、どの論点が扱われているかだけです。</li>
    </ul>
  </section>

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

  <section>
    <div class="cta">
      <h2>この調査をやった人</h2>
      <p class="sec-note prose">
        株式会社Caprer が作りました。素朴に差分を取ると誤判定が出る領域で、
        検証手順と誤り率を公開できる形に整えるのが仕事です。
        日本語データの品質調査や、AI・RAG の評価系の構築をお手伝いしています。
      </p>
      <p class="sec-note"><a href="https://caprer.co.jp">caprer.co.jp</a></p>
    </div>
  </section>

  <section>
    <h2>人手検証をしていない{c.unjudged}件</h2>
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
              <td class="n">{u.observations.en.body_chars === null ? '—' : nm(u.observations.en.body_chars)}</td>
              <td class="n">{u.observations.ja.body_chars === null ? '—' : nm(u.observations.ja.body_chars)}</td>
              <td class="un">未検証</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  </section>

  <footer>
    <p class="flinks">
      <a href="https://github.com/caprerinc/kuhaku">ソースコードとデータ</a>
      <a href="https://github.com/caprerinc/kuhaku/issues/new?template=correction.yml">誤りを報告する</a>
      <a href="#corrections">訂正の記録</a>
    </p>
    <p>空白図鑑 暮らし編</p>
    <p>
      Wikipedia 由来のデータは
      <a href="https://creativecommons.org/licenses/by-sa/4.0/deed.ja" rel="license">CC BY-SA 4.0</a> です。
      本文の引用および観測値は、日本語版・英語版Wikipedia の各改訂版に基づきます。
    </p>
    <p>
      誤りを見つけたら<a href="https://github.com/caprerinc/kuhaku/issues/new?template=correction.yml">Issue</a
      >で教えてください。訂正は上書きせず、履歴として公開します。
    </p>
  </footer>
</div>
