import { execFileSync } from 'node:child_process';
import { DEFAULT_ENDPOINT, request } from './api.mjs';

const repository = process.argv[2];
if (!/^caprerinc\/[A-Za-z0-9_.-]+$/.test(repository || '')) {
  console.error('Usage: node client/list.mjs caprerinc/REPOSITORY [RUN_ID]');
  process.exitCode = 1;
} else {
  try {
    const token = process.env.GH_TOKEN || process.env.GITHUB_TOKEN || execFileSync('gh', ['auth', 'token'], { encoding: 'utf8' }).trim();
    const url = new URL('/v1/list', DEFAULT_ENDPOINT);
    url.searchParams.set('repository', repository);
    if (process.argv[3]) url.searchParams.set('runId', process.argv[3]);
    else url.searchParams.set('latest', 'true');
    console.log(JSON.stringify(await (await request(DEFAULT_ENDPOINT, url.href, { token })).json(), null, 2));
  } catch (error) { console.error(error.message); process.exitCode = 1; }
}
