import { fileURLToPath } from 'node:url';
import { sveltekit } from '@sveltejs/kit/vite';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'vitest/config';

// 描画契約はリポジトリ直下の data/ にある。Python が所有する唯一の入力。
const dataDir = fileURLToPath(new URL('../data', import.meta.url));

export default defineConfig({
  plugins: [tailwindcss(), sveltekit()],
  resolve: {
    // 実行時に fs で読むとバンドル後のパスが壊れる（実際に壊れた）。
    // ビルド時に取り込むことで、契約が変われば Vite が再ビルドする。
    alias: { $data: dataDir },
  },
  server: { fs: { allow: [dataDir] } },
});
