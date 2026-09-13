#!/usr/bin/env bash
# 空白図鑑 — 生成・検査・配信の入口。
#
# **文面チェックを通らないものは配信しない。** ここがこの製品の生命線なので、
# 手順の外側から deploy できてしまう状態にしない。
#
#   ./run.sh build     生成のみ
#   ./run.sh check     生成 + 全チェック（HTML / 元データ / 記事）
#   ./run.sh deploy    生成 + 全チェック + 配信（チェックが落ちたら配信しない）
#   ./run.sh verify    公開した数字を保存済みの生データから作り直して照合する
#   ./run.sh drift     さらに Wikipedia の現在の版と比べ、記事が変わっていないか見る
#   ./run.sh collect   Wikipedia から証拠を取り直す（時間がかかる）
set -euo pipefail
cd "$(dirname "$0")"

DOCS=../caprer/docs/business

build() {
  # data/dataset.{json,csv} と公開物を必ず同じ判定から作る。
  # 片方だけ更新すると、手元の集計と公開ページがずれる。
  python3 -m pipeline.build > /dev/null
  python3 site/build_site.py
}

check() {
  echo "── 証拠の完全性"
  python3 -m pipeline.verify | sed 's/^/  /'
  echo "── 公開HTML"
  python3 site/lint_copy.py
  echo "── 元データ"
  python3 site/lint_copy.py --sources
  if [ -f "$DOCS/kuhaku-zukan-note-article.md" ]; then
    echo "── 記事・投稿案"
    python3 site/lint_copy.py "$DOCS"/kuhaku-zukan-note-article.md "$DOCS"/kuhaku-zukan-x-posts.md
  fi
}

case "${1:-check}" in
  collect)
    python3 -m pipeline.collect concepts/living.toml
    python3 -m pipeline.build
    ;;
  build)
    build
    ;;
  verify)
    python3 -m pipeline.verify
    ;;
  drift)
    python3 -m pipeline.verify --drift
    ;;
  check)
    build && check
    ;;
  deploy)
    build && check
    echo "── 配信"
    (cd site && npx --yes wrangler@latest deploy)
    echo "── 配信後の確認"
    for p in "/" "/kuhaku-zukan.csv" "/kuhaku-zukan.json" "/.claude/"; do
      printf "   %-22s HTTP %s\n" "$p" \
        "$(curl -s -o /dev/null -w '%{http_code}' -m 20 "https://kuhaku.caprer.co.jp$p")"
    done
    ;;
  *)
    echo "usage: ./run.sh {collect|build|check|verify|drift|deploy}" >&2
    exit 2
    ;;
esac
