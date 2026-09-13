# データのライセンスと構成

## ライセンス

このディレクトリのデータ、および `concepts/`・`judgments/`・`site/public/` に含まれる
Wikipedia 由来の観測値と引用は、**CC BY-SA 4.0** です。

- 出典: 日本語版Wikipedia および英語版Wikipedia の各改訂版（contributors）
- 各項目に **改訂ID (revision ID)** を記録してあります。
  `https://ja.wikipedia.org/w/index.php?oldid=<revid>` で、測定した版そのものを開けます。
- ライセンス全文: https://creativecommons.org/licenses/by-sa/4.0/deed.ja

再配布・改変する場合は、Wikipedia contributors への帰属表示と、同一ライセンスでの提供が必要です。

コード（`pipeline/`、`site/*.py`、`run.sh`）は MIT です。ルートの `LICENSE` を参照してください。

## 構成

```
evidence/living-latest.json              最新の証拠バンドル（これを使う）
evidence/living-run-<runid>.json         実行ごとの証拠バンドル
evidence/invalid/                        使ってはいけない過去の実行（下記）
raw/<run_id>/<応答のSHA-256>.json.gz     API応答の生データ 344件
dataset.json / dataset.csv               判定を突き合わせた手元用の集計
```

配布用のデータセットは `../site/public/kuhaku-zukan.{csv,json}` です。
全47件、**すべての行に判定と検証状態を持たせて**あります。数値だけを取り出せる表は作っていません。

## `evidence/invalid/` について

**ここに入っているものは分析に使わないでください。** 修正前のパイプラインによる実行です。

消していないのは、その実行が誤っていたこと自体が調査の一部であり、公開している
訂正の記録の根拠になるためです。既知のバグ・影響を受けるフィールド・後継の実行IDは
同名の `.meta.json` に書いてあります。

## 観測値の定義

いずれも観測値であり、品質評価ではありません。足し合わせて一つのスコアにはしません。

| 項目 | 定義 |
|---|---|
| `body_chars` | レンダリング済み平文から附録節（脚注・出典・関連項目・外部リンク等）をその子節ごと除き、空白を除いた文字数 |
| `top_level_sections` | 最上位（`==`）の節の数。附録節を除く |
| `external_ref_domains` | wikitext に直接書かれた `<ref>...</ref>` 内のURLのみを対象とし、Wikimedia・短縮URL・SNS・識別子リゾルバを除いた eTLD+1 のユニーク数 |

**英語1文字と日本語1文字は情報量が同じではありません。** 文字数の比較には限界があります。

### 既知の限界

- `{{sfn}}` `{{harvnb}}` `{{efn}}` `{{reflist|refs=}}` 形式の脚注は拾えず、系統的に過少計上になります。
  度合いは `template_footnote_markers` で確認できます。
- eTLD+1 は同梱の簡易サフィックス表で求めています。完全な Public Suffix List ではないため、
  `github.io` のようなホスティングは1発行元に潰れます。
- 「ドメイン数」は発行元の独立性を保証しません。
