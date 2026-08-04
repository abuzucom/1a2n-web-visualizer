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
 * The commit list is discovered automatically (every commit that ever
 * touched src/presets-extra/ or src/vendor/, oldest first) rather
 * than hand-maintained — a hardcoded list drifts out of sync with history
 * rewrites (rebases/squashes change hashes) and is easy to forget to
 * update. recordsFromIndexDiff/recordsFromVendorDiff only produce records
 * for names that actually disappeared, so "add" commits are naturally a
 * no-op here.
 *
 * Usage:
 *   node tools/analyze_curation_history.js
 *   node tools/analyze_curation_history.js --csv out.csv
 */

const { execFileSync } = require('child_process');
const fs = require('fs');

const ROOT = require('path').join(__dirname, '..');

const MAX_BUFFER_SIZE = 209715200;
const HASH_LENGTH = 8;
const DATE_LENGTH = 10;
const MIN_WORD_LENGTH = 3;
const DEFAULT_MIN_COUNT = 3;
const DEFAULT_LIMIT = 40;
const MAX_PREFIX_LENGTH = 40;
const ARGS_START = 2;

/**
 * Find and return all commit hashes modifying curation records.
 */
function discoverCurationCommits() {
  const out = git(['log', '--reverse', '--format=%H', '--', 'src/presets-extra', 'src/vendor']);
  return out.trim().split('\n').filter(Boolean);
}

const VENDOR_FILES = {
  butterchurnPresets: 'src/vendor/butterchurnPresets.min.js',
  butterchurnPresetsExtra: 'src/vendor/butterchurnPresetsExtra.min.js',
  butterchurnPresetsExtra2: 'src/vendor/butterchurnPresetsExtra2.min.js',
  butterchurnPresetsMD1: 'src/vendor/butterchurnPresetsMD1.min.js',
};

/**
 * Execute a Git command and return its standard output as a string.
 */
function git(args) {
  return execFileSync('git', args, {
    cwd: ROOT,
    maxBuffer: MAX_BUFFER_SIZE,
    encoding: 'utf8',
  });
}

/**
 * Verify if the commit hash matches a known schema and return true if valid.
 */
function validateCommit(hash) {
  if (!/^[0-9a-f]{4,64}\^?$/i.test(hash)) {
    throw new Error(`unexpected Git commit reference: ${hash}`);
  }
  return hash;
}

/**
 * Extract and return metadata for a specific commit hash.
 */
function commitMeta(hash) {
  const out = git(['show', '-s', '--format=%H%x09%ci%x09%s', validateCommit(hash)]).trim();
  const [h, date, ...rest] = out.split('\t');
  return { hash: h.slice(0, HASH_LENGTH), date: date.slice(0, DATE_LENGTH), subject: rest.join('\t') };
}

/**
 * Return true if a file existed at the given commit hash.
 */
function fileExistsAt(hash, path) {
  try {
    execFileSync('git', ['cat-file', '-e', `${validateCommit(hash)}:${path}`], {
      cwd: ROOT,
      stdio: 'ignore',
    });
    return true;
  } catch {
    return false;
  }
}

/**
 * Read and return the preset index mapping at the specified commit hash.
 */
function getIndexChunks(hash) {
  const raw = git(['show', `${validateCommit(hash)}:src/presets-extra/index.js`]);
  const prefix = 'window.BCExtraPresetIndex=';
  const trimmed = raw.trimEnd();
  const json = trimmed.slice(prefix.length, trimmed.length - 1);
  return JSON.parse(json).chunks;
}

/**
 * Read and return the keys of presets inside a vendor pack at the given commit.
 */
function getVendorKeys(hash, vendorPath) {
  const raw = git(['show', `${validateCommit(hash)}:${vendorPath}`]);
  const returnMatch = raw.match(/getPresets\s*:\s*function\s*\(\)\s*\{\s*return\s+([A-Za-z_$][\w$]*)/);
  const presetVariable = returnMatch ? returnMatch[1] : 'presets';
  const marker = new RegExp(`var\\s+${presetVariable}\\s*=\\s*\\{`);
  const markerMatch = marker.exec(raw);
  const markerIdx = markerMatch ? markerMatch.index : -1;
  if (markerIdx !== -1) {
    const openIdx = markerIdx + markerMatch[0].lastIndexOf('{');
    const closeIdx = findMatchingCloser(raw, openIdx);
    if (closeIdx === -1) throw new Error(`could not parse vendor map in ${vendorPath}`);
    return new Set(Object.keys(JSON.parse(raw.slice(openIdx, closeIdx + 1))));
  }

  const names = new Set();
  const assignment = /\["([^"]+)"\]\s*=\s*[A-Za-z_$][\w$]*\(/g;
  for (const match of raw.matchAll(assignment)) names.add(match[1]);
  if (!names.size) throw new Error(`unrecognized vendor map in ${vendorPath}`);
  return names;
}

/**
 * Find and return the matching closing bracket in a Javascript source string.
 */
function findMatchingCloser(text, startIndex, opener = '{', closer = '}') {
  let depth = 0;
  let inString = null;
  let escaped = false;
  for (let i = startIndex; i < text.length; i++) {
    const character = text[i];
    if (inString) {
      if (escaped) escaped = false;
      else if (character === '\\') escaped = true;
      else if (character === inString) inString = null;
      continue;
    }
    if (character === '"' || character === "'") {
      inString = character;
    } else if (character === opener) {
      depth++;
    } else if (character === closer && --depth === 0) {
      return i;
    }
  }
  return -1;
}

/**
 * Return true if a file path matches the provided pattern.
 */
function touchedFile(commit, relPath) {
  const out = git(['show', '--stat', validateCommit(commit), '--', relPath]);
  return out.includes(relPath);
}

/**
 * Analyze and return a list of curation records from index differences.
 */
function recordsFromIndexDiff(currentCommit, parentCommit, meta) {
  const records = [];
  const indexPath = 'src/presets-extra/index.js';
  if (!fileExistsAt(parentCommit, indexPath) || !fileExistsAt(currentCommit, indexPath)) return records;

  const before = getIndexChunks(parentCommit);
  const after = getIndexChunks(currentCommit);
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

/**
 * Analyze and return a list of curation records from vendor pack differences.
 */
function recordsFromVendorDiff(currentCommit, parentCommit, meta) {
  const records = [];
  for (const [packName, relPath] of Object.entries(VENDOR_FILES)) {
    if (!touchedFile(currentCommit, relPath)) continue;
    if (!fileExistsAt(parentCommit, relPath) || !fileExistsAt(currentCommit, relPath)) continue;

    const before = getVendorKeys(parentCommit, relPath);
    const after = getVendorKeys(currentCommit, relPath);
    for (const name of before) {
      if (after.has(name)) continue;
      records.push({ name, pack: packName, chunk: '', commit: meta.hash, date: meta.date, subject: meta.subject });
    }
  }
  return records;
}

/**
 * Reconstruct and return the full ledger of all curated-out preset operations.
 */
function reconstruct(commits) {
  const records = [];
  for (const commit of commits) {
    const parent = `${commit}^`;
    const meta = commitMeta(commit);
    records.push(...recordsFromIndexDiff(commit, parent, meta));
    records.push(...recordsFromVendorDiff(commit, parent, meta));
  }
  return records;
}

// --- neutral frequency analysis ---

const STOPWORDS = new Set([
  'the', 'a', 'an', 'and', 'or', 'of', 'in', 'on', 'at', 'to', 'for', 'with',
  'my', 'i', 'is', 'it', 'mix', 'remix', 'edit', 'v2', 'v3', 'v4', 'v5',
]);

/**
 * Return a list of normalized tokens extracted from a preset name.
 */
function tokenize(name) {
  return name
    .toLowerCase()
    .replace(/[_\-+.,!?()[\]'"=]/g, ' ')
    .split(/\s+/)
    .filter((w) => w.length >= MIN_WORD_LENGTH && !STOPWORDS.has(w) && !/^\d+$/.test(w));
}

/**
 * Generate and return an array of sequential bigrams from a list of tokens.
 */
function bigrams(tokens) {
  const out = [];
  for (let i = 0; i < tokens.length - 1; i++) out.push(`${tokens[i]} ${tokens[i + 1]}`);
  return out;
}

/**
 * Sort and return the most frequently occurring items in a frequency map.
 */
function topCounts(counts, minCount = DEFAULT_MIN_COUNT, limit = DEFAULT_LIMIT) {
  return Object.entries(counts)
    .filter(([, c]) => c >= minCount)
    .sort((a, b) => b[1] - a[1])
    .slice(0, limit);
}

/**
 * Analyze the curation history ledger and print the resulting analytics.
 */
function analyze(records) {
  const uniqueNames = [...new Set(records.map((r) => r.name))];

  const wordCounts = {};
  const bigramCounts = {};
  const prefixCounts = {};

  for (const name of uniqueNames) {
    const tokens = tokenize(name);
    for (const w of new Set(tokens)) wordCounts[w] = (wordCounts[w] || 0) + 1;
    for (const bg of new Set(bigrams(tokens))) bigramCounts[bg] = (bigramCounts[bg] || 0) + 1;

    const p = name.split(/[-+]/)[0].trim().toLowerCase();
    if (p.length >= MIN_WORD_LENGTH && p.length <= MAX_PREFIX_LENGTH) prefixCounts[p] = (prefixCounts[p] || 0) + 1;
  }

  return {
    uniqueNames,
    words: topCounts(wordCounts),
    bigrams: topCounts(bigramCounts),
    prefixes: topCounts(prefixCounts),
  };
}

/**
 * Write a list of string records to a CSV file.
 */
function writeCsv(records, outPath) {
  const esc = (s) => (/[",\n]/.test(String(s)) ? `"${String(s).replace(/"/g, '""')}"` : s);
  const lines = ['name,pack,chunk,commit,date,subject'];
  for (const r of records) {
    lines.push([esc(r.name), r.pack, r.chunk, r.commit, r.date, esc(r.subject)].join(','));
  }
  fs.writeFileSync(outPath, lines.join('\n') + '\n');
}

/**
 * Coordinate the retrieval and analysis of curation history.
 */
function main() {
  const args = process.argv.slice(ARGS_START);
  const csvIdx = args.indexOf('--csv');
  const csvPath = csvIdx !== -1 ? args[csvIdx + 1] : null;

  const commits = discoverCurationCommits();
  const records = reconstruct(commits);
  const { uniqueNames, words, bigrams: bg, prefixes } = analyze(records);

  console.log(`Curation commits analyzed: ${commits.length}`);
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
