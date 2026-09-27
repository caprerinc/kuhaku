// 表示層が読むのは描画契約（data/viewmodel.json）**だけ**。
// 全ルートで共有するので layout で1回だけ読む。
import vm from '../../../data/viewmodel.json';

export function load() {
  return { vm };
}
