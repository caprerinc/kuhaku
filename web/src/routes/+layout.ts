// 全ページを事前生成する。実行時に組み立てるものは無い。
export const prerender = true;
// 読み物なのでクライアント側の JS は要らない。
// PostHog は app.html の素のスクリプトで入れる（ハイドレーションに依存させない）。
export const csr = false;
