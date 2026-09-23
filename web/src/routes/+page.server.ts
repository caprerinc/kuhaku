// 表示層が読むのは描画契約（data/viewmodel.json）**だけ**。
// concepts / judgments / evidence を直接読まない。意味づけを JS 側に二重化させないため。
//
// 静的インポートにしてビルド時に取り込む。実行時に fs で読むと、バンドル後は
// .svelte-kit/output/server/ が基準になりパスが壊れる（実際に壊した）。
// 別名（$data）ではなく相対パスにしているのは、tsconfig の paths を上書きすると
// SvelteKit 自身の別名を壊すため。相対パスなら tsc も Vite も素で解決できる。
import vm from '../../../data/viewmodel.json';

// server 側に置くことで、クライアントのバンドルには絶対に入らない。
export function load() {
  return { vm };
}
