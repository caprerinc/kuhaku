import adapter from '@sveltejs/adapter-cloudflare';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
export default {
  preprocess: vitePreprocess(),
  kit: {
    adapter: adapter(),
    // PostHog の Session Replay は相対パスのアセットを解決できず録画が壊れる。
    // SvelteKit の既定は相対パスなので明示的に切る（LaneDuel と同じ理由）。
    paths: { relative: false },
  },
};
