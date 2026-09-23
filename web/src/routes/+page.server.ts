import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

/**
 * 表示層が読むのは描画契約（data/viewmodel.json）**だけ**。
 * concepts / judgments / evidence を直接読まない。意味づけを JS 側に二重化させないため。
 * 事前生成なので、この読み込みはビルド時に一度だけ走る。
 */
export function load() {
  const path = fileURLToPath(new URL('../../../data/viewmodel.json', import.meta.url));
  return { vm: JSON.parse(readFileSync(path, 'utf-8')) };
}
