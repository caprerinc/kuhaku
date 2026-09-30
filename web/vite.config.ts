import { fileURLToPath } from 'node:url';

import { sveltekit } from '@sveltejs/kit/vite';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig, lazyPlugins } from 'vite-plus';

// 描画契約はリポジトリ直下の data/ にある。Python が所有する唯一の入力。
// プロジェクト外なので dev サーバに読み取りを許す必要がある。
const dataDir = fileURLToPath(new URL('../data', import.meta.url));

export default defineConfig({
	// SvelteKit の雛形（sv create）が入れる Prettier 設定と同じ形。
	// oxfmt の .svelte 整形は prettier-plugin-svelte を同梱したもので、出力も SvelteKit 標準と一致する。
	fmt: {
		useTabs: true,
		singleQuote: true,
		trailingComma: 'none',
		printWidth: 100,
		svelte: true,
		sortImports: {},
		sortTailwindcss: { stylesheet: './src/app.css' },
		// app.html は整形しない。PostHog の圧縮済みスニペットが展開され、全ページの配信バイトが変わる
		// （公開履歴 published/ はバイト単位で照合している）。
		ignorePatterns: ['src/app.html']
	},
	// oxlint は .svelte の <script> だけを見る。テンプレート・a11y・型は svelte-check が受け持つ。
	// typeCheck は切る：tsgolint は .svelte の module script からの export を読めず、誤検出になる。
	lint: {
		jsPlugins: [{ name: 'vite-plus', specifier: 'vite-plus/oxlint-plugin' }],
		rules: { 'vite-plus/prefer-vite-plus-imports': 'error' },
		options: { typeAware: true, typeCheck: false }
	},
	test: {
		// Vitest v4 compatibility: preserve mock call history.
		// Remove after tests no longer rely on calls from setup or earlier tests.
		// https://viteplus.dev/guide/vitest-v5#remove-unneeded-compatibility-settings
		// https://vitest.dev/guide/migration/#clearmocks-is-enabled-by-default
		clearMocks: false
	},
	plugins: lazyPlugins(() => [tailwindcss(), sveltekit()]),
	server: { fs: { allow: [dataDir] } }
});
