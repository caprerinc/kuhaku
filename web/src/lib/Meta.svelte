<script lang="ts">
	/**
	 * 検索結果とリンクのプレビュー（LinkedIn・Slack・X など）に出る情報。
	 *
	 * 本文ではないので、文言の比較（parity）には映らない。移植で一度
	 * description と OGP を丸ごと落とした。全ページこの部品を通す。
	 */
	let {
		title,
		description,
		path,
		type = 'article',
		ogTitle,
		ogDescription
	}: {
		title: string;
		description: string;
		path: string;
		type?: string;
		ogTitle?: string;
		ogDescription?: string;
	} = $props();

	const ORIGIN = 'https://kuhaku.caprer.co.jp';
	const url = $derived(ORIGIN + path);
</script>

<svelte:head>
	<title>{title}</title>
	<meta name="description" content={description} />
	<link rel="canonical" href={url} />
	<meta property="og:site_name" content="空白図鑑 暮らし編" />
	<meta property="og:title" content={ogTitle ?? title} />
	<meta property="og:description" content={ogDescription ?? description} />
	<meta property="og:type" content={type} />
	<meta property="og:url" content={url} />
	<meta property="og:locale" content="ja_JP" />
</svelte:head>
