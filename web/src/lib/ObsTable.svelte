<script lang="ts">
  import Count from './Count.svelte';
  import Note from './Note.svelte';

  /**
   * 観測値。3つの量を**別々に**並べる。足し合わせて単一のスコアにしない。
   * 空欄（—）は照合する候補が無かったという意味で、0字ではない。注記で明示する。
   */
  let { item } = $props();
  const o = $derived(item.observations);
  const fmt = (n: number | null) => (n === null ? '—' : n.toLocaleString('ja-JP'));
  const day = (s: string | null) => (s ? s.slice(0, 10) : '—');
</script>

<table class="obs">
  <thead>
    <tr>
      <th></th>
      <th
        >日本語版<br /><span class="revcell"
          >{#if o.ja.rev_url}<a class="rev" href={o.ja.rev_url} rel="nofollow"
              >rev.{o.ja.revid}</a
            >{:else}—{/if}</span
        ></th
      >
      <th
        >英語版<br /><span class="revcell"
          >{#if o.en.rev_url}<a class="rev" href={o.en.rev_url} rel="nofollow"
              >rev.{o.en.revid}</a
            >{:else}—{/if}</span
        ></th
      >
      <th></th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th>本文文字数</th>
      <td><span class="n">{fmt(o.ja.body_chars)}</span></td>
      <td><span class="n">{fmt(o.en.body_chars)}</span></td>
      <td class="note">言語間で1字あたりの情報量は同じではない。比較の目安にとどまる</td>
    </tr>
    <tr>
      <th>節の数</th>
      <td><Count value={o.ja.sections} /></td>
      <td><Count value={o.en.sections} /></td>
      <td class="note"></td>
    </tr>
    <tr>
      <th>脚注内の外部参照ドメイン数</th>
      <td><Count value={o.ja.ref_domains} shape="ci" /></td>
      <td><Count value={o.en.ref_domains} shape="ci" /></td>
      <td class="note"></td>
    </tr>
    <tr>
      <th>最終更新</th>
      <td><span class="n">{day(o.ja.last_modified)}</span></td>
      <td><span class="n">{day(o.en.last_modified)}</span></td>
      <td class="note"></td>
    </tr>
  </tbody>
</table>

{#each item.observation_notes as segs}<Note segments={segs} />{/each}
