#!/usr/bin/env node
/**
 * remove_presets.js
 *
 * Removes named presets from this repo's preset library: drops each name
 * from src/presets-extra/index.js and its owning chunk-NNN.js file, from
 * any vendored src/vendor/*.min.js pack that contains it, and from the
 * matching row(s) in preset-inventory.csv — and appends a row to
 * removed-presets.csv, the durable "never re-add this" ledger that fetch
 * scripts consult so a future preset pull can't resurrect it. This is the
 * same mechanical procedure the "Curation" section in README.md documents;
 * this tool exists so that procedure doesn't have to be reconstructed by
 * hand (or via an AI session) every time someone wants to curate the
 * library.
 *
 * Matching is exact-name only (no fuzzy/substring matching), and nothing
 * is written to disk unless every requested name was found and every
 * modified file passes a post-edit consistency/syntax check — so a typo
 * in one name aborts the whole run instead of partially applying it.
 *
 * This tool does NOT update README.md/CHANGELOG.md/package.json preset
 * counts — those involve prose, not just data, so that's a manual
 * follow-up step (see the "Curation" section of the README for the
 * numbers to recompute).
 *
 * Usage:
 *   node tools/remove_presets.js --names-file names.txt
 *   node tools/remove_presets.js --name "Foo" --name "Bar"
 *   node tools/remove_presets.js --names-file names.txt --dry-run
 *
 * names.txt: one exact preset name per line (blank lines ignored).
 */

const fs = require('fs');
const os = require('os');
const path = require('path');

const ROOT = path.join(__dirname, '..');
const INDEX_PATH = path.join(ROOT, 'src/presets-extra/index.js');
const CSV_PATH = path.join(ROOT, 'preset-inventory.csv');
const REMOVED_CSV_PATH = path.join(ROOT, 'removed-presets.csv');
const CHUNK_DIR = path.join(ROOT, 'src/presets-extra');
const VENDOR_DIR = path.join(ROOT, 'src/vendor');

function readNamesFile(file) {
  const lines = fs.readFileSync(file, 'utf8').split('\n');
  return lines.map((line) => line.replace(/\r$/, '')).filter((line) => line.length > 0);
}

function parseArgs(argv) {
  const names = [];
  let dryRun = false;
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--name') {
      names.push(argv[++i]);
    } else if (a === '--names-file') {
      names.push(...readNamesFile(argv[++i]));
    } else if (a === '--dry-run') {
      dryRun = true;
    } else if (a === '--help' || a === '-h') {
      console.log(__filename);
      process.exit(0);
    }
  }
  return { names, dryRun };
}

// --- CSV parsing (name,pack,chunk) ---

function parseCsvLine(line) {
  const m = line.match(/^(?:"((?:[^"]|"")*)"|([^,]*)),([^,]*),(.*)$/);
  if (!m) return null;
  const name = m[1] !== undefined ? m[1].replace(/""/g, '"') : m[2];
  return { name, pack: m[3], chunk: m[4] };
}

// --- src/presets-extra/index.js (JSON) ---

function readIndex() {
  const raw = fs.readFileSync(INDEX_PATH, 'utf8');
  const prefix = 'window.BCExtraPresetIndex=';
  const suffix = ';';
  const trimmed = raw.trimEnd();
  if (!raw.startsWith(prefix) || !trimmed.endsWith(suffix)) {
    throw new Error('unexpected index.js wrapper format');
  }
  const json = trimmed.slice(prefix.length, trimmed.length - suffix.length);
  return { data: JSON.parse(json), prefix, suffix };
}

function writeIndex({ data, prefix, suffix }) {
  fs.writeFileSync(INDEX_PATH, prefix + JSON.stringify(data) + suffix);
}

// --- src/presets-extra/chunk-NNN.js (JSON) ---

function chunkPath(id) {
  return path.join(CHUNK_DIR, `chunk-${String(id).padStart(3, '0')}.js`);
}

function readChunk(id) {
  const raw = fs.readFileSync(chunkPath(id), 'utf8');
  const prefix = `window.__bcPresetChunk(${id},`;
  const suffix = ');';
  const trimmed = raw.trimEnd();
  if (!raw.startsWith(prefix) || !trimmed.endsWith(suffix)) {
    throw new Error(`unexpected wrapper format in chunk-${String(id).padStart(3, '0')}.js`);
  }
  const json = trimmed.slice(prefix.length, trimmed.length - suffix.length);
  return { data: JSON.parse(json), prefix, suffix };
}

function writeChunk(id, { data, prefix, suffix }) {
  fs.writeFileSync(chunkPath(id), prefix + JSON.stringify(data) + suffix);
}

// --- src/vendor/*.min.js (minified UMD bundles) ---

function findMatchingCloser(s, openIdx) {
  const open = s[openIdx];
  const close = open === '{' ? '}' : ']';
  let depth = 0;
  let inStr = false;
  let strCh = null;
  let esc = false;
  for (let i = openIdx; i < s.length; i++) {
    const c = s[i];
    if (inStr) {
      if (esc) esc = false;
      else if (c === '\\') esc = true;
      else if (c === strCh) inStr = false;
      continue;
    }
    if (c === '"' || c === "'") {
      inStr = true;
      strCh = c;
      continue;
    }
    if (c === open) depth++;
    else if (c === close) {
      depth--;
      if (depth === 0) return i;
    }
  }
  return -1;
}

function loadVendorPresetNames(source) {
  // fs.mkdtempSync gives us a securely-generated, unpredictable directory
  // name (unlike a hand-rolled Date.now()/Math.random() filename), so the
  // temp file inside it can't be pre-guessed or collide with another
  // process's file in the shared os.tmpdir().
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'vendor-check-'));
  const tmp = path.join(dir, 'bundle.js');
  fs.writeFileSync(tmp, source);
  try {
    delete require.cache[require.resolve(tmp)];
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

// Pattern A: `var presets={...};return{default:{getPresets:function(){return presets}}}` —
// the whole preset map is one JSON-parseable object literal assigned to `presets`.
function tryPatternA(source, names) {
  const marker = 'var presets={';
  const markerIdx = source.indexOf(marker);
  if (markerIdx === -1) return null;
  const openIdx = markerIdx + marker.length - 1; // index of the '{'
  const closeIdx = findMatchingCloser(source, openIdx);
  if (closeIdx === -1) throw new Error('could not find matching closer for var presets={...}');
  const blob = source.slice(openIdx, closeIdx + 1);
  const data = JSON.parse(blob);
  const removed = [];
  for (const name of names) {
    if (name in data) {
      delete data[name];
      removed.push(name);
    }
  }
  if (removed.length === 0) return null;
  const newBlob = JSON.stringify(data);
  const newSource = source.slice(0, openIdx) + newBlob + source.slice(closeIdx + 1);
  return { newSource, removed };
}

// Pattern B: a comma-expression chain of `_["name"]=t(N)` assignments building up
// an object that's returned as the preset map (each preset's data lives in its own
// numbered webpack module referenced by t(N); we only need to drop the map entry).
function tryPatternB(source, names) {
  let out = source;
  const removed = [];
  for (const name of names) {
    const key = JSON.stringify(name); // exact double-quoted, JSON-escaped form
    const needle = `_[${key}]=t(`;
    const start = out.indexOf(needle);
    if (start === -1) continue;
    const parenClose = out.indexOf(')', start + needle.length);
    if (parenClose === -1) throw new Error(`malformed Pattern B clause for ${name}`);
    let clauseEnd = parenClose + 1;
    let clauseStart = start;
    // absorb one adjacent comma to keep the comma-expression syntactically valid
    if (out[clauseEnd] === ',') {
      clauseEnd += 1;
    } else if (out[clauseStart - 1] === ',') {
      clauseStart -= 1;
    }
    out = out.slice(0, clauseStart) + out.slice(clauseEnd);
    removed.push(name);
  }
  if (removed.length === 0) return null;
  return { newSource: out, removed };
}

function removeFromVendorPack(source, names) {
  const a = tryPatternA(source, names);
  if (a) return a;
  const b = tryPatternB(source, names);
  if (b) return b;
  throw new Error(
    'no recognized preset-map pattern found in this vendor pack (Pattern A/B both failed) — manual edit required',
  );
}

// --- main ---

function countIndexNames(data) {
  let total = 0;
  for (const arr of data.chunks) total += arr.length;
  return total;
}

function parseAndValidateNames() {
  const { names: rawNames, dryRun } = parseArgs(process.argv.slice(2));
  const names = [...new Set(rawNames)];
  if (names.length === 0) {
    console.error('No names given. Use --name "<exact name>" and/or --names-file <path>.');
    process.exit(1);
  }
  return { names, dryRun };
}

function loadCsvByName(csvLines) {
  const byName = new Map();
  for (const line of csvLines) {
    const parsed = line ? parseCsvLine(line) : null;
    if (parsed) byName.set(parsed.name, parsed);
  }
  return byName;
}

function resolveTargets(names, byName) {
  const notFound = names.filter((n) => !byName.has(n));
  if (notFound.length > 0) {
    console.error(`Aborting — ${notFound.length} name(s) not found in preset-inventory.csv (no changes made):`);
    for (const n of notFound) console.error(`  ${JSON.stringify(n)}`);
    process.exit(1);
  }

  const byPack = new Map(); // pack -> [name]
  for (const n of names) {
    const { pack } = byName.get(n);
    if (!byPack.has(pack)) byPack.set(pack, []);
    byPack.get(pack).push(n);
  }
  return byPack;
}

function chunkChanges(targets, byName) {
  const byChunk = new Map(); // chunk id -> [name]
  for (const n of targets) {
    const { chunk } = byName.get(n);
    const id = Number(chunk);
    if (!byChunk.has(id)) byChunk.set(id, []);
    byChunk.get(id).push(n);
  }
  return byChunk;
}

function removeFromChunk(id, chunkNames, indexData) {
  const arr = indexData.chunks[id];
  if (!arr) throw new Error(`index.js has no chunk ${id}`);
  for (const n of chunkNames) {
    const pos = arr.indexOf(n);
    if (pos === -1) throw new Error(`"${n}" not found in index.js chunks[${id}] (CSV says chunk ${id})`);
    arr.splice(pos, 1);
  }

  const chunk = readChunk(id);
  for (const n of chunkNames) {
    if (!(n in chunk.data)) throw new Error(`"${n}" not found as a key in chunk-${String(id).padStart(3, '0')}.js`);
    delete chunk.data[n];
  }
  return chunk;
}

function preparePresetsExtraWrites(byPack, byName, pendingWrites, summary) {
  if (!byPack.has('presets-extra')) return;
  const targets = byPack.get('presets-extra');
  const { data: indexData, prefix: idxPrefix, suffix: idxSuffix } = readIndex();
  const byChunk = chunkChanges(targets, byName);

  for (const [id, chunkNames] of byChunk) {
    const chunk = removeFromChunk(id, chunkNames, indexData);
    pendingWrites.push({ kind: 'chunk', id, chunk });
    summary.presetsExtra += chunkNames.length;
  }

  pendingWrites.push({ kind: 'index', data: indexData, prefix: idxPrefix, suffix: idxSuffix });
}

function removeFromVendorPackValidated(pack, targets) {
  const vendorPath = path.join(VENDOR_DIR, `${pack}.min.js`);
  if (!fs.existsSync(vendorPath)) throw new Error(`unknown pack "${pack}" — no file at ${vendorPath}`);
  const before = fs.readFileSync(vendorPath, 'utf8');
  const beforeNames = loadVendorPresetNames(before);

  const { newSource, removed } = removeFromVendorPack(before, targets);
  const missing = targets.filter((n) => !removed.includes(n));
  if (missing.length > 0) {
    throw new Error(`could not locate these presets in ${pack}: ${missing.map((n) => JSON.stringify(n)).join(', ')}`);
  }

  // validate the edited bundle still loads and only the intended names changed
  const afterNames = loadVendorPresetNames(newSource);
  const actuallyRemoved = [...beforeNames].filter((n) => !afterNames.has(n));
  const actuallyAdded = [...afterNames].filter((n) => !beforeNames.has(n));
  if (actuallyAdded.length > 0) {
    throw new Error(`editing ${pack} unexpectedly added preset(s): ${actuallyAdded.join(', ')}`);
  }
  const removedSet = new Set(actuallyRemoved);
  const expectedSet = new Set(targets);
  if (actuallyRemoved.length !== targets.length || [...expectedSet].some((n) => !removedSet.has(n))) {
    throw new Error(
      `editing ${pack} did not remove exactly the requested names (removed: ${actuallyRemoved.join(', ')})`,
    );
  }
  return { vendorPath, newSource };
}

function prepareVendorWrites(byPack, pendingWrites, summary) {
  for (const [pack, targets] of byPack) {
    if (pack === 'presets-extra') continue;
    const { vendorPath, newSource } = removeFromVendorPackValidated(pack, targets);
    pendingWrites.push({ kind: 'vendor', path: vendorPath, content: newSource });
    summary.vendor[pack] = targets.length;
  }
}

function prepareCsvUpdate(csvLines, names, summary) {
  const removeSet = new Set(names);
  const keptLines = csvLines.filter((line) => {
    if (line === '') return true;
    const parsed = parseCsvLine(line);
    if (!parsed) return true;
    if (!removeSet.has(parsed.name)) return true;
    summary.csv += 1;
    return false;
  });

  if (summary.csv !== names.length) {
    throw new Error(`expected to remove ${names.length} CSV rows, actually removed ${summary.csv}`);
  }
  return keptLines;
}

function logSummary(prefix, names, summary) {
  console.log(`${prefix} ${names.length} presets:`);
  console.log(`  presets-extra: ${summary.presetsExtra}`);
  for (const [pack, count] of Object.entries(summary.vendor)) console.log(`  ${pack}: ${count}`);
  console.log(`  preset-inventory.csv rows: ${summary.csv}`);
}

function writeAll(pendingWrites, keptLines) {
  for (const w of pendingWrites) {
    if (w.kind === 'index') writeIndex(w);
    else if (w.kind === 'chunk') writeChunk(w.id, w.chunk);
    else if (w.kind === 'vendor') fs.writeFileSync(w.path, w.content);
  }
  fs.writeFileSync(CSV_PATH, keptLines.join('\n'));
}

// --- removed-presets.csv (durable ledger of everything ever curated out) ---

function escCsv(s) {
  return /[",\n]/.test(String(s)) ? `"${String(s).replace(/"/g, '""')}"` : s;
}

function appendRemovedPresetsCsv(names, byName) {
  const today = new Date().toISOString().slice(0, 10);
  const rows = names.map((n) => {
    const { pack, chunk } = byName.get(n);
    return [escCsv(n), pack, chunk, '', today, ''].join(',');
  });

  if (!fs.existsSync(REMOVED_CSV_PATH)) {
    fs.writeFileSync(REMOVED_CSV_PATH, 'name,pack,chunk,commit,date,subject\n');
  }
  fs.appendFileSync(REMOVED_CSV_PATH, rows.join('\n') + '\n');
}

// Consistency check: verify each file dropped by exactly the expected amount
// relative to its own pre-run count (index.js and preset-inventory.csv report
// different populations — the CSV reflects the runtime-deduplicated view, ~67
// presets-extra names are shadowed by an identical vendored-pack name and
// never appear in it at all — so compare deltas, not the two files' raw counts).
function verifyConsistency(indexCountBefore, csvRowCountBefore, summary) {
  const indexCountAfter = countIndexNames(readIndex().data);
  const csvRowCountAfter = fs.readFileSync(CSV_PATH, 'utf8').split('\n').filter((l) => l.length > 0).length;
  const indexDelta = indexCountBefore - indexCountAfter;
  const csvDelta = csvRowCountBefore - csvRowCountAfter;
  console.log(
    `\nConsistency check: index.js names -${indexDelta} (expected -${summary.presetsExtra}), ` +
      `preset-inventory.csv rows -${csvDelta} (expected -${summary.csv}).`,
  );
  if (indexDelta !== summary.presetsExtra || csvDelta !== summary.csv) {
    console.warn('WARNING: deltas do not match expectations — investigate before committing.');
  }
}

function main() {
  const { names, dryRun } = parseAndValidateNames();

  const indexCountBefore = countIndexNames(readIndex().data);
  const csvRowCountBefore = fs.readFileSync(CSV_PATH, 'utf8').split('\n').filter((l) => l.length > 0).length;

  const csvLines = fs.readFileSync(CSV_PATH, 'utf8').split('\n');
  const byName = loadCsvByName(csvLines);
  const byPack = resolveTargets(names, byName);

  const pendingWrites = []; // [{ path, content }]
  const summary = { presetsExtra: 0, vendor: {}, csv: 0 };
  preparePresetsExtraWrites(byPack, byName, pendingWrites, summary);
  prepareVendorWrites(byPack, pendingWrites, summary);
  const keptLines = prepareCsvUpdate(csvLines, names, summary);

  if (dryRun) {
    console.log('Dry run — no files written.');
    logSummary('Would remove', names, summary);
    return;
  }

  writeAll(pendingWrites, keptLines);
  appendRemovedPresetsCsv(names, byName);
  logSummary('Removed', names, summary);
  verifyConsistency(indexCountBefore, csvRowCountBefore, summary);
}

main();
