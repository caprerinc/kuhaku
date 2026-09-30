<script lang="ts">
	import '../app.css';
	let { children } = $props();
</script>

<div class="wrap">
	{@render children()}

	<footer>
		<p class="flinks">
			<a href="/">図鑑</a>
			<a href="/corrections">訂正の記録</a>
			<a href="/method">調べかた</a>
			<a href="/limits">この調査の限界</a>
			<a href="/data">データ</a>
			<a href="/unjudged">未検証</a>
		</p>
		<p class="flinks">
			<a href="https://github.com/caprerinc/kuhaku">ソースコードとデータ</a>
			<a href="https://github.com/caprerinc/kuhaku/issues/new?template=correction.yml"
				>誤りを報告する</a
			>
		</p>
		<p>空白図鑑 暮らし編</p>
		<p>
			Wikipedia 由来のデータは
			<a href="https://creativecommons.org/licenses/by-sa/4.0/deed.ja" rel="license">CC BY-SA 4.0</a
			> です。 本文の引用および観測値は、日本語版・英語版Wikipedia の各改訂版に基づきます。
		</p>
		<p>
			誤りを見つけたら<a
				href="https://github.com/caprerinc/kuhaku/issues/new?template=correction.yml">Issue</a
			>で教えてください。訂正は上書きせず、履歴として公開します。
		</p>
	</footer>
</div>
