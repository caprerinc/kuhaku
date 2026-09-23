import { fileURLToPath } from 'node:url';
import { sveltekit } from '@sveltejs/kit/vite';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'vitest/config';

// 描画契約はリポジトリ直下の data/ にある。Python が所有する唯一の入力。
// プロジェクト外なので dev サーバに読み取りを許す必要がある。
const dataDir = fileURLToPath(new URL('../data', import.meta.url));

export default defineConfig({
  plugins: [tailwindcss(), sveltekit()],
  server: { fs: { allow: [dataDir] } },
});
