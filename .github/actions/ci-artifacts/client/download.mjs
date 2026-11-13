import { execFileSync } from 'node:child_process';
import { createWriteStream } from 'node:fs';
import { rename, rm } from 'node:fs/promises';
import { Readable } from 'node:stream';
import { pipeline } from 'node:stream/promises';
import { sha256 } from './api.mjs';

export async function download(urlValue, destination, token, allowedOrigin) {
  const url = new URL(urlValue);
  if (url.protocol !== 'https:' || url.origin !== allowedOrigin || url.pathname !== '/v1/artifact') {
    throw new Error('Unexpected artifact URL; refusing to send a GitHub credential');
  }
  const response = await fetch(url, { headers: { Authorization: `Bearer ${token}` },
    redirect: 'error', signal: AbortSignal.timeout(300000) });
  if (!response.ok) throw new Error(`Download failed (${response.status})`);
  const expected = response.headers.get('x-artifact-sha256');
  if (!/^[a-f0-9]{64}$/.test(expected)) throw new Error('Artifact checksum missing');
  const temp = `${destination}.${crypto.randomUUID()}.part`;
  try {
    await pipeline(Readable.fromWeb(response.body), createWriteStream(temp, { flags: 'wx', mode: 0o600 }));
    if (await sha256(temp) !== expected) throw new Error('Artifact checksum mismatch');
    await rename(temp, destination);
  } finally { await rm(temp, { force: true }); }
}

if (process.argv[1] && import.meta.url === new URL(`file://${process.argv[1]}`).href) {
  (async () => {
    const [url, destination = 'artifact.tar.gz'] = process.argv.slice(2);
    if (!url) throw new Error('Usage: node client/download.mjs ARTIFACT_URL [OUTPUT.tar.gz]');
    const { DEFAULT_ENDPOINT } = await import('./api.mjs');
    const token = process.env.GH_TOKEN || process.env.GITHUB_TOKEN || execFileSync('gh', ['auth', 'token'], { encoding: 'utf8' }).trim();
    await download(url, destination, token, DEFAULT_ENDPOINT);
    console.log(`Downloaded and verified ${destination}`);
  })().catch(error => { console.error(error.message); process.exitCode = 1; });
}
