import { createReadStream } from 'node:fs';
import { appendFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';

export const DEFAULT_ENDPOINT = 'https://caprer-ci-artifacts.caprer.workers.dev';
export function input(name, fallback = '') {
  return process.env[`INPUT_${name.replaceAll(' ', '_').toUpperCase()}`]?.trim() || fallback;
}
export function serviceEndpoint(value) {
  const url = new URL(value || DEFAULT_ENDPOINT);
  if (url.protocol !== 'https:' || url.username || url.password || url.search || url.hash || url.pathname !== '/') {
    throw new Error('Artifact endpoint must be an HTTPS origin');
  }
  return url.origin;
}
export async function identity() {
  const url = new URL(process.env.ACTIONS_ID_TOKEN_REQUEST_URL || 'https://invalid/');
  if (url.hostname === 'invalid' || !process.env.ACTIONS_ID_TOKEN_REQUEST_TOKEN) {
    throw new Error('The upload/download job requires permissions: id-token: write');
  }
  url.searchParams.set('audience', 'caprer-ci-artifacts');
  const response = await fetch(url, {
    headers: { Authorization: `Bearer ${process.env.ACTIONS_ID_TOKEN_REQUEST_TOKEN}` },
    redirect: 'error', signal: AbortSignal.timeout(30000),
  });
  if (!response.ok) throw new Error(`GitHub identity request failed (${response.status})`);
  const { value } = await response.json();
  if (!value) throw new Error('GitHub did not return an identity token');
  console.log(`::add-mask::${value}`);
  return value;
}
export async function request(endpoint, path, { method = 'GET', body, token, json = false } = {}) {
  const response = await fetch(new URL(path, endpoint), {
    method, body: json ? JSON.stringify(body) : body,
    headers: { Authorization: `Bearer ${token || await identity()}`,
      ...(json ? { 'Content-Type': 'application/json' } : {}) },
    redirect: 'error', signal: AbortSignal.timeout(120000),
  });
  if (!response.ok) throw new Error(`Artifact service failed (${response.status}): ${(await response.text()).slice(0, 500)}`);
  return response;
}
export async function sha256(file) {
  const hash = createHash('sha256');
  for await (const chunk of createReadStream(file)) hash.update(chunk);
  return hash.digest('hex');
}
export async function output(name, value) {
  if (process.env.GITHUB_OUTPUT) await appendFile(process.env.GITHUB_OUTPUT, `${name}=${value}\n`);
}
