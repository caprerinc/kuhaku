<script lang="ts">
  /**
   * 探索記録。**このサイトの中身はここ。**
   * 「どれだけ探して見つからなかったか」を、第三者が同じ手順を踏める形で残す。
   * 全文検索で拾っただけの候補は契約の時点で除いてある（比較対象に選ばない規則）。
   */
  let { item } = $props();
</script>

<div class="trail">
  <div class="trail-head">探索記録　<span class="n">{item.judged_at}</span></div>

  <div class="trail-sec">
    <span class="tl">候補タイトル</span>
    <span class="tn">{item.candidates.length}件を完全一致で照会</span>
  </div>
  <ul class="cands">
    {#each item.candidates as c}
      <li class={c.exists ? 'hit' : 'miss'}>
        <span class="mk">{c.exists ? '○' : '✗'}</span><span class="ttl">{c.title}</span><span
          class="src">{c.source_label}</span
        >{#if c.redirected}<span class="red"> →「{c.resolved_title}」に転送</span>{/if}
      </li>
    {/each}
  </ul>

  {#if item.checked_containers.length}
    <div class="trail-sec">
      <span class="tl">上位・隣接記事</span>
      <span class="tn">{item.checked_containers.length}件を通読</span>
    </div>
    <ul class="conts">
      {#each item.checked_containers as c}<li>{c}</li>{/each}
    </ul>
  {/if}

  {#if item.search_terms.length}
    <div class="trail-sec">
      <span class="tl">検索語</span>
      <span class="tn">{item.search_terms.length}語</span>
    </div>
    <p class="terms">{#each item.search_terms as t}<span>{t}</span>{/each}</p>
  {/if}
</div>
