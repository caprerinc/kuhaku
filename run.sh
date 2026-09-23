#!/usr/bin/env bash
# 空白図鑑 — 生成・検査・配信の入口。
#
# **文面チェックを通らないものは配信しない。** ここがこの製品の生命線なので、
# 手順の外側から deploy できてしまう状態にしない。
#
#   ./run.sh build     生成のみ
#   ./run.sh check     生成 + 全チェック（HTML / 元データ / 記事）
#   ./run.sh deploy    生成 + 全チェック + 配信（チェックが落ちたら配信しない）
#   ./run.sh stats     素朴な自動判定が人手検証と比べてどれだけ外したかを数える
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
  # 描画契約。表示層はこれだけを読むので、判定を変えたら必ず作り直す。
  # 生成を忘れると契約だけ古いまま残り、そのまま古い主張が公開される。
  python3 -m pipeline.viewmodel > /dev/null
  python3 site/build_site.py
}

check() {
  echo "── 証拠の完全性"
  python3 -m pipeline.verify | sed 's/^/  /'
  echo "── 公開HTML"
  python3 site/lint_copy.py
  echo "── 元データ"
  python3 site/lint_copy.py --sources
  echo "── 描画契約"
  python3 site/parity.py --contract
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
  stats)
    python3 -m pipeline.stats
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
    # wrangler は版を固定する。@latest だと配信ツールだけ再現性が無い。
    # 導入済みがあればそれを使う（npx は npm キャッシュへ書けない環境で落ちる）。
    : "${WRANGLER_VERSION:=4.98.0}"
    if command -v wrangler >/dev/null 2>&1; then
      echo "   wrangler $(wrangler --version 2>/dev/null | grep -Eo '^[0-9]+\.[0-9]+\.[0-9]+' | head -1)（導入済み）"
      (cd site && wrangler deploy)
    else
      echo "   wrangler ${WRANGLER_VERSION}（npx）"
      (cd site && npx --yes "wrangler@${WRANGLER_VERSION}" deploy)
    fi
    echo "── 配信後の確認"
    # 以前は表示するだけで、落ちていても成功扱いだった。CI 側(deploy.yml)は
    # 強制しているのに手元だけ素通りする、という食い違いも直す。
    post_ok=1
    for p in "/" "/kuhaku-zukan.csv" "/kuhaku-zukan.json" "/naive-check.csv"; do
      code="$(curl -s -o /dev/null -w '%{http_code}' -m 20 "https://kuhaku.caprer.co.jp$p")"
      printf "   %-22s HTTP %s\n" "$p" "$code"
      [ "$code" = "200" ] || post_ok=0
    done
    for p in "/.claude/" "/.claude/settings.local.json" "/.assetsignore"; do
      code="$(curl -s -o /dev/null -w '%{http_code}' -m 20 "https://kuhaku.caprer.co.jp$p")"
      printf "   %-22s HTTP %s （公開されていないこと）\n" "$p" "$code"
      [ "$code" != "200" ] || post_ok=0
    done
    [ "$post_ok" = "1" ] || { echo "   ★ 配信後の確認に失敗"; exit 1; }
    ;;
  *)
    echo "usage: ./run.sh {collect|build|check|stats|verify|drift|deploy}" >&2
    exit 2
    ;;
esac
