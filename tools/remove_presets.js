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
 * Matching is exact-name only (no fuzzy/substring matching). Nothing is
 * written to disk unless every requested name was found. An edited vendor
 * pack must still load and lose exactly the requested names before any
 * write. A typo in one name therefore aborts the whole run.
 *
 * The ledger row is written first. Each later file is replaced atomically,
 * one file at a time. A run that fails partway leaves the remaining files
 * unchanged. Running the same command again completes the removal. A
 * consistency check after the writes compares the index and inventory
 * counts and prints a warning on a mismatch.
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
const osModule = require('os');
const path = require('path');

const ROOT = path.join(__dirname, '..');
const INDEX_PATH = path.join(ROOT, 'src/presets-extra/index.js');
const CSV_PATH = path.join(ROOT, 'preset-inventory.csv');
const REMOVED_CSV_PATH = path.join(ROOT, 'removed-presets.csv');
const CHUNK_DIR = path.join(ROOT, 'src/presets-extra');
const VENDOR_DIR = path.join(ROOT, 'src/vendor');
const ENERGY_CATALOG_PATH = path.join(ROOT, 'energy-catalog.json');
const PERFORMANCE_CATALOG_PATH = path.join(ROOT, 'performance-catalog.json');
const ENERGY_BUNDLE_PATH = path.join(ROOT, 'src/catalogs/energy-catalog.js');
const PERFORMANCE_BUNDLE_PATH = path.join(ROOT, 'src/catalogs/performance-catalog.js');
const ENERGY_GLOBAL = 'BCEnergyCatalog';
const PERFORMANCE_GLOBAL = 'BCPerformanceCatalog';
const CATALOG_INDENT = 2;
let chunkFiles = null;

const ARGS_START = 2;
const CHUNK_PAD_LENGTH = 3;
const DATE_LENGTH = 10;
const REGEX_GROUP_NAME_QUOTED = 1;
const REGEX_GROUP_NAME_UNQUOTED = 2;
const REGEX_GROUP_PACK = 3;
const REGEX_GROUP_CHUNK = 4;

/**
 * Read and return preset names from a newline-separated file.
 */
function readNamesFile(path) {
  const lines = fs.readFileSync(path, 'utf8').split('\n');
  return lines.map((line) => line.replace(/\r$/, '')).filter((line) => line.length > 0);
}

/**
 * Return the value that follows a flag, or exit when it is missing.
 */
function requireFlagValue(argv, index, flag) {
  const value = argv[index];
  if (value === undefined) {
    console.error(`${flag} requires a value. No changes made.`);
    process.exit(1);
  }
  return value;
}

/**
 * Warn when a names file resolves outside the repository root.
 *
 * The run still reads the file. Callers that keep a names file elsewhere
 * keep working. The warning makes an unexpected read location visible.
 */
function warnIfOutsideRoot(filePath) {
  const relative = path.relative(ROOT, path.resolve(filePath));
  const outside = relative === '..' || relative.startsWith(`..${path.sep}`) || path.isAbsolute(relative);
  if (outside) {
    console.error(`WARNING: --names-file ${JSON.stringify(filePath)} is outside the repository.`);
  }
}

/**
 * Parse and return the command-line arguments.
 *
 * An unrecognized argument prints a warning and the run continues. Callers
 * that pass extra arguments keep working. The warning makes a misspelled
 * --dry-run visible before the output reports real removals.
 */
function parseArgs(argv) {
  const names = [];
  let dryRun = false;
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--name') {
      names.push(requireFlagValue(argv, ++i, a));
    } else if (a === '--names-file') {
      const namesFile = requireFlagValue(argv, ++i, a);
      warnIfOutsideRoot(namesFile);
      names.push(...readNamesFile(namesFile));
    } else if (a === '--dry-run') {
      dryRun = true;
    } else if (a === '--help' || a === '-h') {
      console.log(__filename);
      process.exit(0);
    } else {
      console.error(`WARNING: ignoring unrecognized argument ${JSON.stringify(a)}.`);
    }
  }
  return { names, dryRun };
}

// --- CSV parsing (name,pack,chunk) ---

/**
 * Parse a CSV line into fields, respecting quoted commas.
 */
function parseCsvLine(line) {
  const match = line.match(/^(?:"((?:[^"]|"")*)"|([^,]*)),([^,]*),([^,]*)(?:,(.*))?$/);
  if (!match) return null;
  const name = match[REGEX_GROUP_NAME_QUOTED] !== undefined
    ? match[REGEX_GROUP_NAME_QUOTED].replace(/""/g, '"')
    : match[REGEX_GROUP_NAME_UNQUOTED];
  return { name, pack: match[REGEX_GROUP_PACK], chunk: match[REGEX_GROUP_CHUNK] };
}

// --- src/presets-extra/index.js (JSON) ---

/**
 * Read and return the index.js mappings.
 */
function readIndex() {
  const raw = fs.readFileSync(INDEX_PATH, 'utf8');
  const prefix = 'window.BCExtraPresetIndex=';
  const suffix = ';';
  const trimmed = raw.trimEnd();
  if (!raw.startsWith(prefix) || !trimmed.endsWith(suffix)) {
    throw new Error('unexpected index.js wrapper format');
  }
  const json = trimmed.slice(prefix.length, trimmed.length - suffix.length);
  const data = JSON.parse(json);
  if (data.files && data.files.length !== data.chunks.length) {
    throw new Error('index.js chunks/files mapping has different lengths');
  }
  return { data, prefix, suffix };
}

/**
 * Format and return the index.js file content.
 */
function writeIndex({ data, prefix, suffix }) {
  atomicWrite(INDEX_PATH, prefix + JSON.stringify(data) + suffix);
}

// --- src/presets-extra/chunk-NNN.js (JSON) ---

/**
 * Format and return the filesystem path for a chunk ID.
 */
function chunkPath(id) {
  const filename = chunkFiles && chunkFiles[id]
    ? chunkFiles[id] : `chunk-${String(id).padStart(CHUNK_PAD_LENGTH, '0')}.js`;
  return path.join(CHUNK_DIR, filename);
}

/**
 * Read and return a chunk file's content and parsed JSON.
 */
function readChunk(id) {
  const raw = fs.readFileSync(chunkPath(id), 'utf8');
  const prefix = `window.__bcPresetChunk(${id},`;
  const suffix = ');';
  const trimmed = raw.trimEnd();
  if (!raw.startsWith(prefix) || !trimmed.endsWith(suffix)) {
    throw new Error(`unexpected wrapper format in ${path.basename(chunkPath(id))}`);
  }
  const json = trimmed.slice(prefix.length, trimmed.length - suffix.length);
  return { data: JSON.parse(json), prefix, suffix };
}

/**
 * Format and return a chunk file's content.
 */
function writeChunk(id, { data, prefix, suffix }) {
  atomicWrite(chunkPath(id), prefix + JSON.stringify(data) + suffix);
}

/**
 * Atomically write text to a file using a temporary intermediate file.
 */
function atomicWrite(filePath, content) {
  const directory = fs.mkdtempSync(path.join(path.dirname(filePath), '.curation-'));
  const temporaryPath = path.join(directory, path.basename(filePath));
  try {
    fs.writeFileSync(temporaryPath, content);
    try {
      fs.renameSync(temporaryPath, filePath);
    } catch (error) {
      if (error.code !== 'EPERM') throw error;
      // Windows can reject replacing a tracked file while an external scanner
      // briefly holds the destination. The content was prepared and checked.
      // Copy it over as the platform-specific fallback.
      fs.copyFileSync(temporaryPath, filePath);
      fs.unlinkSync(temporaryPath);
    }
  } finally {
    fs.rmSync(directory, { recursive: true, force: true });
  }
}

// --- src/vendor/*.min.js (minified UMD bundles) ---

/**
 * Find and return the index of the matching closing bracket in a Javascript string.
 */
function findMatchingCloser(s, openIdx) {
  const open = s[openIdx];
  const close = open === '{' ? '}' : ']';
  let depth = 0;
  let inStr = false;
  let strCh = null;
  let esc = false;
  for (let i = openIdx; i < s.length; i++) {
    const char = s[i];
    if (inStr) {
      if (esc) esc = false;
      else if (char === '\\') esc = true;
      else if (char === strCh) inStr = false;
      continue;
    }
    if (char === '"' || char === "'") {
      inStr = true;
      strCh = char;
      continue;
    }
    if (char === open) depth++;
    else if (char === close) {
      depth--;
      if (depth === 0) return i;
    }
  }
  return -1;
}

/**
 * Read and return the keys of presets inside a vendor pack.
 */
function loadVendorPresetNames(source) {
  // fs.mkdtempSync gives us a securely-generated, unpredictable directory
  // name. This differs from a hand-rolled Date.now()/Math.random() filename.
  // The temp file inside it can't be pre-guessed or collide with another
  // process's file in the shared os.tmpdir().
  const dir = fs.mkdtempSync(path.join(osModule.tmpdir(), 'vendor-check-'));
  const tmp = path.join(dir, 'bundle.js');
  fs.writeFileSync(tmp, source);
  try {
    delete require.cache[require.resolve(tmp)];
    const moduleObj = require(tmp);
    const presets = moduleObj && moduleObj.default && typeof moduleObj.default.getPresets === 'function'
      ? moduleObj.default.getPresets()
      : (moduleObj && typeof moduleObj.getPresets === 'function' ? moduleObj.getPresets() : moduleObj);
    return new Set(Object.keys(presets));
  } finally {
    delete require.cache[require.resolve(tmp)];
    fs.rmSync(dir, { recursive: true, force: true });
  }
}

// Pattern A: `var presets={...};return{default:{getPresets:function(){return presets}}}`.
// The whole preset map is one JSON-parseable object literal assigned to `presets`.
/**
 * Attempt to match and return the vendor map using the standard Butterchurn pattern.
 */
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

// Pattern B: A comma-expression chain of `_["name"]=t(N)` assignments building up
// an object that's returned as the preset map. Each preset's data lives in its own
// numbered webpack module referenced by t(N). Drop the map entry.
/**
 * Attempt to match and return the vendor map using the fallback pattern.
 */
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
    'no recognized preset-map pattern found in this vendor pack (Pattern A/B both failed). Manual edit required',
  );
}

// --- main ---

/**
 * Calculate and return the total number of presets in the index chunks.
 */
function countIndexNames(data) {
  let total = 0;
  for (const arr of data.chunks) total += arr.length;
  return total;
}

/**
 * Parse, validate, and return the list of names to remove.
 */
function parseAndValidateNames() {
  const { names: rawNames, dryRun } = parseArgs(process.argv.slice(ARGS_START));
  const names = [...new Set(rawNames)];
  if (names.length === 0) {
    console.error('No names given. Use --name "<exact name>" and/or --names-file <path>.');
    process.exit(1);
  }
  return { names, dryRun };
}

/**
 * Read and return a map of preset rows from a CSV.
 */
function loadCsvByName(csvLines) {
  const byName = new Map();
  for (const line of csvLines) {
    const parsed = line ? parseCsvLine(line) : null;
    if (parsed) byName.set(parsed.name, parsed);
  }
  return byName;
}

/**
 * Resolve and return the removal targets grouped by pack and chunk.
 */
function resolveTargets(names, byName, alreadyRemoved) {
  const notFound = names.filter((n) => !byName.has(n) && !alreadyRemoved.has(n));
  if (notFound.length > 0) {
    console.error(`Aborting. ${notFound.length} name(s) not found in preset-inventory.csv (no changes made):`);
    for (const n of notFound) console.error(`  ${JSON.stringify(n)}`);
    process.exit(1);
  }

  const byPack = new Map(); // pack -> [name]
  for (const n of names) {
    if (!byName.has(n)) continue;
    const { pack } = byName.get(n);
    if (!byPack.has(pack)) byPack.set(pack, []);
    byPack.get(pack).push(n);
  }
  return byPack;
}

/**
 * Analyze and return the required changes to the chunk files and index.
 */
function chunkChanges(targets, indexData, alreadyRemoved) {
  const byChunk = new Map(); // chunk id -> [name]
  for (const n of targets) {
    const id = indexData.chunks.findIndex((names) => names.includes(n));
    if (id === -1) {
      if (alreadyRemoved.has(n)) continue;
      throw new Error(`"${n}" not found in index.js`);
    }
    if (!byChunk.has(id)) byChunk.set(id, []);
    byChunk.get(id).push(n);
  }
  return byChunk;
}

/**
 * Remove specified presets from a chunk and return the new string content.
 *
 * A name the ledger already records may be missing from the chunk file.
 * The ledger row comes first. A failed run can stop after the chunk write
 * and before the index write. The re-run then finishes the index and the
 * inventory.
 */
function removeFromChunk(id, chunkNames, indexData, alreadyRemoved) {
  const arr = indexData.chunks[id];
  if (!arr) throw new Error(`index.js has no chunk ${id}`);
  for (const n of chunkNames) {
    const pos = arr.indexOf(n);
    if (pos === -1) throw new Error(`"${n}" not found in index.js chunks[${id}] (CSV says chunk ${id})`);
    arr.splice(pos, 1);
  }

  const chunk = readChunk(id);
  for (const n of chunkNames) {
    if (n in chunk.data) {
      delete chunk.data[n];
    } else if (!alreadyRemoved.has(n)) {
      throw new Error(`"${n}" not found as a key in ${path.basename(chunkPath(id))}`);
    }
  }
  return chunk;
}

/**
 * Prepare and return all filesystem writes for the presets-extra directory.
 */
function preparePresetsExtraWrites(byPack, byName, pendingWrites, summary, alreadyRemoved) {
  if (!byPack.has('presets-extra')) return;
  const targets = byPack.get('presets-extra');
  const { data: indexData, prefix: idxPrefix, suffix: idxSuffix } = readIndex();
  const byChunk = chunkChanges(targets, indexData, alreadyRemoved);

  for (const [id, chunkNames] of byChunk) {
    const chunk = removeFromChunk(id, chunkNames, indexData, alreadyRemoved);
    pendingWrites.push({ kind: 'chunk', id, chunk });
    summary.presetsExtra += chunkNames.length;
  }

  pendingWrites.push({ kind: 'index', data: indexData, prefix: idxPrefix, suffix: idxSuffix });
}

/**
 * Remove matching presets from a vendor pack and return the updated count and content.
 */
function removeFromVendorPackValidated(pack, targets, alreadyRemoved) {
  const vendorPath = path.join(VENDOR_DIR, `${pack}.min.js`);
  if (!fs.existsSync(vendorPath)) throw new Error(`unknown pack "${pack}". No file at ${vendorPath}`);
  const before = fs.readFileSync(vendorPath, 'utf8');
  const beforeNames = loadVendorPresetNames(before);
  const activeTargets = targets.filter((name) => beforeNames.has(name));
  const missing = targets.filter((name) => !beforeNames.has(name) && !alreadyRemoved.has(name));
  if (missing.length > 0) {
    throw new Error(`could not locate these presets in ${pack}: ${missing.map((n) => JSON.stringify(n)).join(', ')}`);
  }
  if (activeTargets.length === 0) return null;

  const { newSource, removed } = removeFromVendorPack(before, activeTargets);
  const notRemoved = activeTargets.filter((n) => !removed.includes(n));
  if (notRemoved.length > 0) {
    const names = notRemoved.map((n) => JSON.stringify(n)).join(', ');
    throw new Error(`could not locate these presets in ${pack}: ${names}`);
  }

  // validate the edited bundle still loads and only the intended names changed
  const afterNames = loadVendorPresetNames(newSource);
  const actuallyRemoved = [...beforeNames].filter((n) => !afterNames.has(n));
  const actuallyAdded = [...afterNames].filter((n) => !beforeNames.has(n));
  if (actuallyAdded.length > 0) {
    throw new Error(`editing ${pack} unexpectedly added preset(s): ${actuallyAdded.join(', ')}`);
  }
  const removedSet = new Set(actuallyRemoved);
  const expectedSet = new Set(activeTargets);
  if (actuallyRemoved.length !== activeTargets.length || [...expectedSet].some((n) => !removedSet.has(n))) {
    throw new Error(
      `editing ${pack} did not remove exactly the requested names (removed: ${actuallyRemoved.join(', ')})`,
    );
  }
  return { vendorPath, newSource, removedCount: activeTargets.length };
}

/**
 * Prepare and return all filesystem writes for vendor packs.
 */
function prepareVendorWrites(byPack, pendingWrites, summary, alreadyRemoved) {
  for (const [pack, targets] of byPack) {
    if (pack === 'presets-extra') continue;
    const result = removeFromVendorPackValidated(pack, targets, alreadyRemoved);
    if (!result) continue;
    const { vendorPath, newSource } = result;
    pendingWrites.push({ kind: 'vendor', path: vendorPath, content: newSource });
    summary.vendor[pack] = result.removedCount;
  }
}

/**
 * Prepare and return the updated preset inventory CSV text.
 */
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

// --- catalogs (energy categories and performance membership) ---

/**
 * Read one catalog file and return its payload, or null when it is absent.
 */
function readCatalog(filePath) {
  if (!fs.existsSync(filePath)) return null;
  return JSON.parse(fs.readFileSync(filePath, 'utf8'));
}

/**
 * Return the preset name inside a catalog identifier.
 */
function catalogIdName(identifier) {
  const separator = identifier.indexOf(':');
  return separator === -1 ? identifier : identifier.slice(separator + 1);
}

/**
 * Return the pack inside a catalog identifier.
 */
function catalogIdPack(identifier) {
  const separator = identifier.indexOf(':');
  return separator === -1 ? '' : identifier.slice(0, separator);
}

/**
 * Return the catalog file text for one payload.
 */
function catalogText(data) {
  return JSON.stringify(data, null, CATALOG_INDENT) + '\n';
}

/**
 * Return the runtime bundle text for one catalog payload.
 */
function bundleText(globalName, data) {
  return `window.${globalName} = ${JSON.stringify(data)};\n`;
}

/**
 * Return whether a catalog entry names a preset this run removed.
 *
 * The entry names a pack and a preset, and the removal targets one pack,
 * so an entry for another pack keeps pointing at a preset that still
 * plays.
 */
function catalogEntryRemoved(identifier, removedByPack) {
  const names = removedByPack.get(catalogIdPack(identifier));
  return Boolean(names) && names.has(catalogIdName(identifier));
}

/**
 * Prepare the catalog writes for the removed presets.
 *
 * Each runtime bundle follows its catalog in the same batch.
 */
function prepareCatalogWrites(removedByPack, pendingWrites, summary) {
  const energy = readCatalog(ENERGY_CATALOG_PATH);
  if (energy && energy.presets) {
    const kept = {};
    let dropped = 0;
    for (const [identifier, category] of Object.entries(energy.presets)) {
      if (catalogEntryRemoved(identifier, removedByPack)) { dropped += 1; continue; }
      kept[identifier] = category;
    }
    if (dropped > 0) {
      energy.presets = kept;
      pendingWrites.push({ kind: 'catalog', path: ENERGY_CATALOG_PATH, content: catalogText(energy) });
      pendingWrites.push({
        kind: 'catalog', path: ENERGY_BUNDLE_PATH, content: bundleText(ENERGY_GLOBAL, energy),
      });
      summary.energyCatalog = dropped;
    }
  }
  const performance = readCatalog(PERFORMANCE_CATALOG_PATH);
  if (performance && Array.isArray(performance.presets)) {
    const kept = performance.presets.filter((identifier) => !catalogEntryRemoved(identifier, removedByPack));
    const dropped = performance.presets.length - kept.length;
    if (dropped > 0) {
      performance.presets = kept;
      pendingWrites.push({
        kind: 'catalog', path: PERFORMANCE_CATALOG_PATH, content: catalogText(performance),
      });
      pendingWrites.push({
        kind: 'catalog', path: PERFORMANCE_BUNDLE_PATH, content: bundleText(PERFORMANCE_GLOBAL, performance),
      });
      summary.performanceCatalog = dropped;
    }
  }
}

/**
 * Print a summary of the pending removal operations.
 */
function logSummary(prefix, names, summary) {
  console.log(`${prefix} ${names.length} presets:`);
  console.log(`  presets-extra: ${summary.presetsExtra}`);
  for (const [pack, count] of Object.entries(summary.vendor)) console.log(`  ${pack}: ${count}`);
  console.log(`  preset-inventory.csv rows: ${summary.csv}`);
  console.log(`  energy catalog entries: ${summary.energyCatalog}`);
  console.log(`  performance catalog entries: ${summary.performanceCatalog}`);
}

/**
 * Execute all prepared filesystem writes.
 */
function writeAll(pendingWrites, keptLines) {
  for (const w of pendingWrites) {
    if (w.kind === 'index') writeIndex(w);
    else if (w.kind === 'chunk') writeChunk(w.id, w.chunk);
    else if (w.kind === 'vendor') atomicWrite(w.path, w.content);
    else if (w.kind === 'catalog') atomicWrite(w.path, w.content);
  }
  atomicWrite(CSV_PATH, keptLines.join('\n'));
}

// --- removed-presets.csv (durable ledger of all curated-out presets) ---

/**
 * Escape a string for safe inclusion in a CSV file.
 */
function escCsv(s) {
  return /[",\n]/.test(String(s)) ? `"${String(s).replace(/"/g, '""')}"` : s;
}

/**
 * Append records for removed presets to the durable ledger CSV.
 */
function appendRemovedPresetsCsv(names, byName, indexData) {
  const today = new Date().toISOString().slice(0, DATE_LENGTH);
  const rows = names.filter((n) => byName.has(n)).map((n) => {
    const { pack, chunk: inventoryChunk } = byName.get(n);
    // Vendor pack rows carry an empty chunk. A presets-extra name the index
    // no longer lists keeps the chunk the inventory recorded.
    const indexChunk = indexData.chunks.findIndex((chunkNames) => chunkNames.includes(n));
    const chunk = pack === 'presets-extra' && indexChunk !== -1
      ? indexChunk
      : inventoryChunk;
    return [escCsv(n), pack, chunk, '', today, ''].join(',');
  });

  const existing = fs.existsSync(REMOVED_CSV_PATH)
    ? fs.readFileSync(REMOVED_CSV_PATH, 'utf8')
    : 'name,pack,chunk,commit,date,subject\n';
  const newline = existing.includes('\r\n') ? '\r\n' : '\n';
  const existingNames = new Set(existing.split(/\r?\n/).map(parseCsvLine)
    .filter(Boolean).map((row) => row.name));
  const newRows = rows.filter((row) => {
    const name = parseCsvLine(row)?.name;
    return name && !existingNames.has(name);
  });
  if (newRows.length > 0) atomicWrite(REMOVED_CSV_PATH, existing + newRows.join(newline) + newline);
}

/**
 * Read and return a set of all previously removed preset names.
 */
function loadRemovedNames() {
  if (!fs.existsSync(REMOVED_CSV_PATH)) return new Set();
  return new Set(fs.readFileSync(REMOVED_CSV_PATH, 'utf8').split(/\r?\n/)
    .map(parseCsvLine).filter(Boolean).map((row) => row.name));
}

/**
 * Verify consistency between the index and the target records.
 */
function verifyConsistency(indexCountBefore, csvRowCountBefore, summary, removedByPack) {
  const indexCountAfter = countIndexNames(readIndex().data);
  const csvRowCountAfter = fs.readFileSync(CSV_PATH, 'utf8').split('\n').filter((l) => l.length > 0).length;
  const indexDelta = indexCountBefore - indexCountAfter;
  const csvDelta = csvRowCountBefore - csvRowCountAfter;
  console.log(
    `\nConsistency check: index.js names -${indexDelta} (expected -${summary.presetsExtra}), ` +
      `preset-inventory.csv rows -${csvDelta} (expected -${summary.csv}).`,
  );
  if (indexDelta !== summary.presetsExtra || csvDelta !== summary.csv) {
    console.warn('WARNING: deltas do not match expectations. Investigate before committing.');
  }
  const stale = countStaleCatalogEntries(removedByPack);
  if (stale > 0) {
    console.warn(`WARNING: ${stale} catalog entr(ies) still name a removed preset.`);
  }
}

/**
 * Count the catalog entries that still name one of the removed presets.
 */
function countStaleCatalogEntries(removedByPack) {
  let stale = 0;
  const energy = readCatalog(ENERGY_CATALOG_PATH);
  if (energy && energy.presets) {
    stale += Object.keys(energy.presets)
      .filter((identifier) => catalogEntryRemoved(identifier, removedByPack)).length;
  }
  const performance = readCatalog(PERFORMANCE_CATALOG_PATH);
  if (performance && Array.isArray(performance.presets)) {
    stale += performance.presets
      .filter((identifier) => catalogEntryRemoved(identifier, removedByPack)).length;
  }
  return stale;
}

/**
 * Manage the removal of presets from the repository.
 */
function main() {
  const { names, dryRun } = parseAndValidateNames();

  const initialIndex = readIndex().data;
  chunkFiles = initialIndex.files || null;
  const indexCountBefore = countIndexNames(initialIndex);
  const csvRowCountBefore = fs.readFileSync(CSV_PATH, 'utf8').split('\n').filter((l) => l.length > 0).length;

  const csvLines = fs.readFileSync(CSV_PATH, 'utf8').split('\n');
  const byName = loadCsvByName(csvLines);
  const alreadyRemoved = loadRemovedNames();
  const byPack = resolveTargets(names, byName, alreadyRemoved);
  const csvTargets = names.filter((name) => byName.has(name));

  const pendingWrites = []; // [{ kind, ... }] entries that writeAll applies
  const summary = { presetsExtra: 0, vendor: {}, csv: 0, energyCatalog: 0, performanceCatalog: 0 };
  const removedByPack = new Map();
  for (const [pack, packNames] of byPack) {
    removedByPack.set(pack, new Set(packNames));
  }
  preparePresetsExtraWrites(byPack, byName, pendingWrites, summary, alreadyRemoved);
  prepareVendorWrites(byPack, pendingWrites, summary, alreadyRemoved);
  const keptLines = prepareCsvUpdate(csvLines, csvTargets, summary);
  prepareCatalogWrites(removedByPack, pendingWrites, summary);

  if (dryRun) {
    console.log('Dry run. No files written.');
    logSummary('Would remove', names, summary);
    return;
  }

  // Record the ledger entry before the larger, multi-file destructive
  // writes below, not after. If those fail partway through, the ledger
  // having already recorded these names is the fail-safe direction. A
  // future fetch won't resurrect them. The reverse order could let a name
  // slip back in upon failure.
  appendRemovedPresetsCsv(names, byName, initialIndex);
  writeAll(pendingWrites, keptLines);
  logSummary('Removed', names, summary);
  verifyConsistency(indexCountBefore, csvRowCountBefore, summary, removedByPack);
}

main();
