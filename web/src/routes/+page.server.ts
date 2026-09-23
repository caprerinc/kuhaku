// 表示層が読むのは描画契約（data/viewmodel.json）**だけ**。
// concepts / judgments / evidence を直接読まない。意味づけを JS 側に二重化させないため。
// server 側に置くことで、クライアントのバンドルには絶対に入らない。
import vm from '$data/viewmodel.json';

export function load() {
  return { vm };
}
