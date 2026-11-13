import { glob, lstat, readdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { execFileSync } from 'node:child_process';

export async function collectFiles(patterns, cwd, includeHidden = false) {
  const files = new Set();
  const matched = [];
  async function walk(file) {
    const info = await lstat(file);
    if (info.isSymbolicLink()) return; // Never follow links into credentials outside the requested tree.
    if (info.isDirectory()) {
      for (const child of await readdir(file)) {
        if (!includeHidden && child.startsWith('.')) continue;
        await walk(path.join(file, child));
      }
    } else if (info.isFile()) files.add(file);
  }
  for (const pattern of patterns.split(/\r?\n/).map(s => s.trim()).filter(Boolean)) {
    if (pattern.startsWith('!')) throw new Error('Negative glob patterns are not supported; use explicit paths');
    for await (const entry of glob(pattern, { cwd })) {
      const absolute = path.resolve(cwd, entry);
      if (!includeHidden && path.relative(cwd, absolute).split(path.sep).some(piece => piece.startsWith('.') && piece !== '..')) continue;
      matched.push(absolute);
      await walk(absolute);
    }
  }
  if (!files.size) return { files: [], root: cwd };
  // Match upload-artifact's common-root behavior, including single-directory uploads.
  const roots = [];
  for (const file of matched) roots.push((await lstat(file)).isDirectory() ? file : path.dirname(file));
  let root = roots[0];
  for (const directory of roots) {
    while (path.relative(root, directory).startsWith(`..${path.sep}`) || path.relative(root, directory) === '..') root = path.dirname(root);
  }
  return { files: [...files].sort(), root };
}

export async function archiveFiles(files, root, archive, listFile) {
  const names = files.map(file => path.relative(root, file));
  if (names.some(name => path.isAbsolute(name) || name.split(path.sep).includes('..'))) throw new Error('Unsafe archive path');
  await writeFile(listFile, names.join('\0') + '\0', { mode: 0o600 });
  execFileSync('tar', ['-czf', archive, '-C', root, '--null', '-T', listFile], { stdio: 'inherit' });
}
