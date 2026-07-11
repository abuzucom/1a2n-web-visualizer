#!/usr/bin/env node
/**
 * analyze_curation_history.js
 *
 * Reconstructs the full history of presets that have been curated out of
 * this repo (see the "Curation" section in README.md) and prints neutral
 * frequency statistics over their names — top single words, top bigrams,
 * and top name-prefixes (a proxy for contributor/collab handles).
 *
 * This tool intentionally does NOT hardcode any notion of "risky" or
 * "unwanted" content (no keyword lists like "flash"/"strobe"/"seizure").
 * It only reconstructs what was historically removed and reports raw
 * statistics; deciding what those statistics mean, and what (if anything)
 * to curate next, is left entirely to whoever runs it.
 *
 * How CURATION_COMMITS was built: `git log --oneline` was reviewed by hand
 * for commits that remove named presets from src/presets-extra/ and/or the
 * src/vendor/*.min.js packs (subjects like "Remove N presets from..." or
 * "Curate and remove N presets..."). Not every curation commit's subject
 * follows the same wording (e.g. one is titled "Remove some bad presets,
 * make exclude and copy buttons fade out automatically"), so this list is
 * a manually maintained, append-only record rather than an auto-detected
 * one. When you make a new curation commit, add its short hash below.
 *
 * Usage:
 *   node tools/analyze_curation_history.js
 *   node tools/analyze_curation_history.js --csv out.csv
 */

const { execSync } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

const ROOT = path.join(__dirname, '..');

// Append new curation commit hashes here as they're made.
const CURATION_COMMITS = [
  '62b8b23', // Remove some bad presets, make exclude and copy buttons fade out automatically
  'e4dcf44', // Remove 13 presets from extra preset collection
  '711d8eb', // Remove 53 presets from the preset collection
  '0e7a1ac', // Remove 45 presets from the extra collection
  'bf1e4e6', // Remove 44 presets from all preset sources
  'bde927b', // Remove 130 more presets from all preset sources
  'b6476ac', // Curate and remove 24 presets from visualizer packs and documentation
  '8c2b4ee', // Curate and remove 52 additional presets (Batch 2) and update metrics
  'a6f24b3', // Curate and remove 28 additional presets (Batch 3) and update metrics
  '8b6307e', // Curate and remove 32 more presets (seizure/sezure batch)
  '1e5ffd1', // Curate and remove 186 more presets, add reusable curation tooling
];

const VENDOR_FILES = {
  butterchurnPresets: 'src/vendor/butterchurnPresets.min.js',
  butterchurnPresetsExtra: 'src/vendor/butterchurnPresetsExtra.min.js',
  butterchurnPresetsExtra2: 'src/vendor/butterchurnPresetsExtra2.min.js',
  butterchurnPresetsMD1: 'src/vendor/butterchurnPresetsMD1.min.js',
};

function git(cmd) {
  return execSync(`git ${cmd}`, { cwd: ROOT, maxBuffer: 1024 * 1024 * 200 }).toString();
}

function commitMeta(commit) {
  const out = git(`show -s --format='%H%x09%ci%x09%s' ${commit}`).trim();
  const [hash, date, ...rest] = out.split('\t');
  return { hash: hash.slice(0, 8), date: date.slice(0, 10), subject: rest.join('\t') };
}

function fileExistsAt(ref, relPath) {
  try {
    execSync(`git cat-file -e ${ref}:${relPath}`, { cwd: ROOT, stdio: 'ignore' });
    return true;
  } catch {
    return false;
  }
}

function getIndexChunks(ref) {
  const raw = git(`show ${ref}:src/presets-extra/index.js`);
  const prefix = 'window.BCExtraPresetIndex=';
  const trimmed = raw.trimEnd();
  const json = trimmed.slice(prefix.length, trimmed.length - 1);
  return JSON.parse(json).chunks;
}

function getVendorKeys(ref, relPath) {
  const raw = git(`show ${ref}:${relPath}`);
  // fs.mkdtempSync gives us a securely-generated, unpredictable directory
  // name (unlike a hand-rolled Date.now()/Math.random() filename), so the
  // temp file inside it can't be pre-guessed or collide with another
  // process's file in the shared os.tmpdir().
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'vendor-'));
  const tmp = path.join(dir, 'bundle.js');
  fs.writeFileSync(tmp, raw);
  try {
    const m = require(tmp);
    const presets = m && m.default && typeof m.default.getPresets === 'function'
      ? m.default.getPresets()
      : (m && typeof m.getPresets === 'function' ? m.getPresets() : m);
    return new Set(Object.keys(presets));
  } finally {
    delete require.cache[require.resolve(tmp)];
    fs.rmSync(dir, { recursive: true, force: true });
  }
}

function touchedFile(commit, relPath) {
  const out = git(`show --stat ${commit} -- ${JSON.stringify(relPath)}`);
  return out.includes(relPath);
}

function recordsFromIndexDiff(commit, meta) {
  const records = [];
  const indexPath = 'src/presets-extra/index.js';
  if (!fileExistsAt(`${commit}^`, indexPath) || !fileExistsAt(commit, indexPath)) return records;

  const before = getIndexChunks(`${commit}^`);
  const after = getIndexChunks(commit);
  for (let i = 0; i < Math.max(before.length, after.length); i++) {
    const beforeNames = new Set(before[i] || []);
    const afterNames = new Set(after[i] || []);
    for (const name of beforeNames) {
      if (afterNames.has(name)) continue;
      records.push({
        name, pack: 'presets-extra', chunk: i, commit: meta.hash, date: meta.date, subject: meta.subject,
      });
    }
  }
  return records;
}

function recordsFromVendorDiff(commit, meta) {
  const records = [];
  for (const [packName, relPath] of Object.entries(VENDOR_FILES)) {
    if (!touchedFile(commit, relPath)) continue;
    if (!fileExistsAt(`${commit}^`, relPath) || !fileExistsAt(commit, relPath)) continue;

    const before = getVendorKeys(`${commit}^`, relPath);
    const after = getVendorKeys(commit, relPath);
    for (const name of before) {
      if (after.has(name)) continue;
      records.push({ name, pack: packName, chunk: '', commit: meta.hash, date: meta.date, subject: meta.subject });
    }
  }
  return records;
}

function reconstruct() {
  const records = [];
  for (const commit of CURATION_COMMITS) {
    const meta = commitMeta(commit);
    records.push(...recordsFromIndexDiff(commit, meta));
    records.push(...recordsFromVendorDiff(commit, meta));
  }
  return records;
}

// --- neutral frequency analysis ---

const STOPWORDS = new Set([
  'the', 'a', 'an', 'and', 'or', 'of', 'in', 'on', 'at', 'to', 'for', 'with',
  'my', 'i', 'is', 'it', 'mix', 'remix', 'edit', 'v2', 'v3', 'v4', 'v5',
]);

function tokenize(name) {
  return name
    .toLowerCase()
    .replace(/[_\-+.,!?()[\]'"=]/g, ' ')
    .split(/\s+/)
    .filter((w) => w.length >= 3 && !STOPWORDS.has(w) && !/^\d+$/.test(w));
}

function bigrams(tokens) {
  const out = [];
  for (let i = 0; i < tokens.length - 1; i++) out.push(`${tokens[i]} ${tokens[i + 1]}`);
  return out;
}

function topCounts(counts, minCount = 3, limit = 40) {
  return Object.entries(counts)
    .filter(([, c]) => c >= minCount)
    .sort((a, b) => b[1] - a[1])
    .slice(0, limit);
}

function analyze(records) {
  const uniqueNames = [...new Set(records.map((r) => r.name))];

  const wordCounts = {};
  const bigramCounts = {};
  const prefixCounts = {};

  for (const name of uniqueNames) {
    const tokens = tokenize(name);
    for (const w of new Set(tokens)) wordCounts[w] = (wordCounts[w] || 0) + 1;
    for (const bg of new Set(bigrams(tokens))) bigramCounts[bg] = (bigramCounts[bg] || 0) + 1;

    const m = name.match(/^([^-]+?)(?:\s*[-+]\s*|$)/);
    if (m) {
      const p = m[1].trim().toLowerCase();
      if (p.length >= 3 && p.length <= 40) prefixCounts[p] = (prefixCounts[p] || 0) + 1;
    }
  }

  return {
    uniqueNames,
    words: topCounts(wordCounts),
    bigrams: topCounts(bigramCounts),
    prefixes: topCounts(prefixCounts),
  };
}

function writeCsv(records, outPath) {
  const esc = (s) => (/[",\n]/.test(String(s)) ? `"${String(s).replace(/"/g, '""')}"` : s);
  const lines = ['name,pack,chunk,commit,date,subject'];
  for (const r of records) {
    lines.push([esc(r.name), r.pack, r.chunk, r.commit, r.date, esc(r.subject)].join(','));
  }
  fs.writeFileSync(outPath, lines.join('\n') + '\n');
}

function main() {
  const args = process.argv.slice(2);
  const csvIdx = args.indexOf('--csv');
  const csvPath = csvIdx !== -1 ? args[csvIdx + 1] : null;

  const records = reconstruct();
  const { uniqueNames, words, bigrams: bg, prefixes } = analyze(records);

  console.log(`Curation commits analyzed: ${CURATION_COMMITS.length}`);
  console.log(`Total removal records: ${records.length}`);
  console.log(`Unique preset names removed: ${uniqueNames.length}`);

  console.log('\n=== Top single words (name-count >= 3) ===');
  for (const [w, c] of words) console.log(`${c}\t${w}`);

  console.log('\n=== Top bigrams (name-count >= 3) ===');
  for (const [w, c] of bg) console.log(`${c}\t${w}`);

  console.log('\n=== Top name-prefixes / likely contributor handles (name-count >= 3) ===');
  for (const [w, c] of prefixes) console.log(`${c}\t${w}`);

  if (csvPath) {
    writeCsv(records, csvPath);
    console.log(`\nWrote ${records.length} records to ${csvPath}`);
  }
}

main();
