<script lang="ts">
  import Meta from '$lib/Meta.svelte';
  import Verdict from '$lib/Verdict.svelte';

  let { data } = $props();
  const vm = $derived(data.vm);
  type VerdictKey = keyof typeof data.vm.labels.verdict_public;
  const order = $derived(vm.labels.verdict_order as VerdictKey[]);
  const c = $derived(vm.counts);
  const sc = $derived(vm.scorecard);
  const nm = (n: number | null) => (n === null ? '—' : n.toLocaleString('ja-JP'));
  const fq = $derived(vm.flagship_quote);
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

<Meta
  title="空白図鑑 暮らし編 — 日本語版Wikipediaの空白を、探索記録つきで"
  ogTitle="空白図鑑 暮らし編"
  description="暮らしに関わる{c.concepts_total}の概念について、日本語版Wikipediaに対応する記事があるかを調べ、{c.judged}件を人手で検証した記録。判定手順・誤り・訂正履歴をすべて公開しています。"
  ogDescription="日本語版Wikipediaに対応する記事があるかを{c.concepts_total}概念で調べ、{c.judged}件を人手検証した記録。"
  path="/"
/>

<header class="cover">
  <h1 class="brand">空白図鑑</h1>
  <p class="brand-sub">暮らし編</p>

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
    >。残りは、記事を確認できないもの{c.by_verdict['欠落']}件、別の記事の中に定義があるもの{c.by_verdict[
      '実質包含'
    ]}件、扱う範囲が違って比較できないもの{c.by_verdict['判定不能']}件、
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
    訂正は上書きせず、すべて履歴として残しています。→ <a href="/corrections">訂正の記録</a>
  </p>
</section>

<section>
  <h2>判定の種類</h2>
  <p class="sec-note prose">
    塗りの濃さは「日本語版にどれだけ記述があるか」の分類を表しています。
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
    {c.judged}件。判定の種類ごとに並べました。数字はすべて観測値です。文字数・節数・脚注の数は
    それぞれ別の量であり、足し合わせて「情報量」とは呼びません。
    各項目をひらくと、観測値・探索記録・判定の根拠があります。
  </p>

  {#each groups as g}
    <div class="vgroup">
      <h3>{g.label}<span class="vcount">{g.items.length}件</span></h3>
      <p>{g.def}</p>
    </div>
    {#if g.key === '実質包含' && fq}
      <!-- 看板の引用。分割したとき一度落としてしまった。この頁で一番強い証拠なので
           一覧側に置く。出典の改訂IDは契約が判定の探索記録と突き合わせている。 -->
      <blockquote class="quote prose">
        <p>{fq.text}</p>
        <cite
          >日本語版Wikipedia「{fq.source_title}」<a class="rev" href={fq.source_rev_url} rel="nofollow"
            >rev.{fq.source_revid}</a
          >（記事全体で{nm(fq.source_body_chars)}字）</cite
        >
      </blockquote>
      <p class="sec-note prose">
        英語版で{nm(fq.en_body_chars)}字ある「<a href="/c/{fq.concept_id}">{name(fq.concept_id)}</a
        >」を、日本語版で確認できたのはこの一文です。
        ここに並ぶ類型は研究史上の分類を説明したものであり、<strong>親を評価するものではありません</strong>。
      </p>
    {/if}
    <div class="tblwrap">
      <table class="plain index">
        <thead>
          <tr>
            <th></th><th>概念</th><th>日本語版 本文</th><th>英語版 本文</th><th>確からしさ</th>
          </tr>
        </thead>
        <tbody>
          {#each g.items as item}
            <tr>
              <td class="n idx">{String(vm.items.indexOf(item) + 1).padStart(2, '0')}</td>
              <td>
                <a href="/c/{item.concept_id}">{item.display_name}</a>
                {#if item.correction}<span class="cbadge {item.correction.kind} mini"
                    >{item.correction.label}</span
                  >{/if}
                <span class="idx-en">{item.en_title}</span>
              </td>
              <td class="n">{nm(item.observations.ja.body_chars)}</td>
              <td class="n">{nm(item.observations.en.body_chars)}</td>
              <td class="un">{item.confidence.label}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/each}
</section>

<section>
  <h2>この調査について</h2>
  <ul class="limits sec-note prose">
    <li><a href="/method">調べかた</a> — 候補の集め方から判定規則まで</li>
    <li><a href="/limits">この調査の限界</a> — 言えないことを先に書いています</li>
    <li><a href="/data">データ</a> — CSV/JSON の配布と、公開値を検算する手順</li>
    <li><a href="/corrections">訂正の記録</a> — {c.verdict_changed + c.evidence_updated}件。過去の判定は消していません</li>
    <li><a href="/unjudged">人手検証をしていない{c.unjudged}件</a> — 欠けていることを意味しません</li>
  </ul>
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
