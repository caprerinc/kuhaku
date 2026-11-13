import { execFileSync } from 'node:child_process';
import { mkdir, mkdtemp, rm } from 'node:fs/promises';
import path from 'node:path';
import { tmpdir } from 'node:os';
import { identity, input, request, serviceEndpoint } from './api.mjs';
import { download } from './download.mjs';

async function main() {
  const endpoint = serviceEndpoint(input('endpoint'));
  const query = new URL('/v1/list', endpoint);
  query.searchParams.set('repository', process.env.GITHUB_REPOSITORY);
  query.searchParams.set('runId', input('run-id', process.env.GITHUB_RUN_ID));
  query.searchParams.set('name', input('name'));
  query.searchParams.set('latest', 'true');
  const artifacts = await (await request(endpoint, query.href)).json();
  if (artifacts.length !== 1) throw new Error(`Expected one matching artifact, found ${artifacts.length}`);
  const temp = await mkdtemp(path.join(process.env.RUNNER_TEMP || tmpdir(), 'r2-download-'));
  try {
    const file = path.join(temp, 'artifact.tar.gz');
    await download(artifacts[0].url, file, await identity(), endpoint);
    const names = execFileSync('tar', ['-tzf', file], { encoding: 'utf8', maxBuffer: 16 * 1024 * 1024 }).split('\n').filter(Boolean);
    if (names.some(name => path.isAbsolute(name) || name.split('/').includes('..'))) throw new Error('Unsafe archive entry');
    const destination = path.resolve(input('path', '.'));
    await mkdir(destination, { recursive: true });
    execFileSync('tar', ['-xzf', file, '-C', destination, '--no-same-owner', '--no-same-permissions'], { stdio: 'inherit' });
  } finally { await rm(temp, { recursive: true, force: true }); }
}
main().catch(error => { console.error(`::error::${error.message}`); process.exitCode = 1; });
