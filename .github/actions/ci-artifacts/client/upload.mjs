import { appendFile, mkdtemp, open, rm, stat } from 'node:fs/promises';
import path from 'node:path';
import { tmpdir } from 'node:os';
import { archiveFiles, collectFiles } from './archive.mjs';
import { input, output, request, serviceEndpoint, sha256 } from './api.mjs';

export async function uploadFile(file, metadata, endpoint) {
  const size = (await stat(file)).size;
  const digest = await sha256(file);
  const upload = await (await request(endpoint, '/v1/uploads', {
    method: 'POST', json: true, body: { ...metadata, size, sha256: digest },
  })).json();
  const url = new URL('/v1/uploads', endpoint);
  url.searchParams.set('key', upload.key);
  url.searchParams.set('uploadId', upload.uploadId);
  const parts = [];
  const handle = await open(file, 'r');
  try {
    for (let offset = 0; offset < size; offset += upload.partSize) {
      const length = Math.min(upload.partSize, size - offset);
      const buffer = Buffer.alloc(length);
      let read = 0;
      while (read < length) {
        const { bytesRead } = await handle.read(buffer, read, length - read, offset + read);
        if (!bytesRead) throw new Error('Archive changed during upload');
        read += bytesRead;
      }
      url.searchParams.set('partNumber', String(parts.length + 1));
      // Parts are idempotent; retry transport/5xx errors without repacking the archive.
      let part;
      for (let attempt = 0; attempt < 3; attempt++) {
        try { part = await (await request(endpoint, url.href, { method: 'PUT', body: buffer })).json(); break; }
        catch (error) { if (attempt === 2 || /\(4\d\d\)/.test(error.message)) throw error; }
      }
      parts.push(part);
    }
    url.searchParams.delete('partNumber');
    const result = await (await request(endpoint, url.href, { method: 'POST', json: true, body: { parts } })).json();
    if (result.sha256 !== digest || result.size !== size) throw new Error('Stored artifact metadata mismatch');
    // Read back the actual stored bytes: do not claim integrity from an echoed digest alone.
    const downloaded = await request(endpoint, result.url);
    const { createHash } = await import('node:crypto');
    const verification = createHash('sha256');
    for await (const chunk of downloaded.body) verification.update(chunk);
    if (verification.digest('hex') !== digest) throw new Error('Stored artifact checksum mismatch');
    return result;
  } catch (error) {
    try { await request(endpoint, url.href, { method: 'DELETE' }); } catch { /* lifecycle aborts incomplete parts */ }
    throw error;
  } finally { await handle.close(); }
}

async function main() {
  const name = input('name');
  if (!name) throw new Error('Artifact name required');
  const policy = input('if-no-files-found', 'warn');
  if (!['warn', 'ignore', 'error'].includes(policy)) throw new Error('Invalid if-no-files-found policy');
  const { files, root } = await collectFiles(input('path'), process.env.GITHUB_WORKSPACE || process.cwd(), input('include-hidden-files') === 'true');
  if (!files.length) {
    if (policy === 'error') throw new Error('No artifact files found');
    if (policy === 'warn') console.log('::warning::No artifact files found');
    return;
  }
  const temp = await mkdtemp(path.join(process.env.RUNNER_TEMP || tmpdir(), 'r2-artifact-'));
  try {
    const archive = path.join(temp, 'artifact.tar.gz');
    await archiveFiles(files, root, archive, path.join(temp, 'files.txt'));
    const result = await uploadFile(archive, { name, retentionKey: input('retention-key', name),
      retentionDays: Number(input('retention-days', '7')) }, serviceEndpoint(input('endpoint')));
    await output('artifact-url', result.url);
    await output('artifact-id', result.key);
    await output('artifact-digest', result.sha256);
    if (process.env.GITHUB_STEP_SUMMARY) {
      await appendFile(process.env.GITHUB_STEP_SUMMARY,
        `\n### R2 artifact: ${name}\n\n${result.size} bytes · SHA256 \`${result.sha256}\`\n\nLatest generation is preserved; old generations expire after ${input('retention-days', '7')} days.\n\nDownload with repository access:\n\n\`\`\`sh\nnode client/download.mjs '${result.url}' '${name}.tar.gz'\n\`\`\`\n\nDownload CLI: caprerinc/ci-artifacts (clone once with gh repo clone).\n`);
    }
    console.log(`Uploaded and verified ${name} (${result.size} bytes)`);
  } finally { await rm(temp, { recursive: true, force: true }); }
}

if (process.argv[1] && import.meta.url === new URL(`file://${process.argv[1]}`).href) {
  main().catch(error => { console.error(`::error::${error.message}`); process.exitCode = 1; });
}
