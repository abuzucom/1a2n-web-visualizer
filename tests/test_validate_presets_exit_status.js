'use strict';
// Preset validator regressions: the exit status that CI gates on, and an
// index without the physical `files` map. The validators load
// convert-milk-presets.js, which requires installed npm packages. The CI
// unit-tests job installs those packages before it runs the Node suite.
const assert = require('node:assert');
const { afterEach, beforeEach, test } = require('node:test');
const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const REPO_ROOT = path.join(__dirname, '..');
const TOOLS = ['validate-experimental-presets.js', 'validate-preset-chunks.js', 'convert-milk-presets.js'];
const INDEX_PREFIX = 'window.BCExtraPresetIndex=';
const EXIT_SUCCESS = 0;
const EXIT_FAILURE = 1;

const VALID_PRESET = { init_eqs_str: '', frame_eqs_str: "a['zoom'] = 1;", shapes: [], waves: [] };
const INVALID_PRESET = { init_eqs_str: '', frame_eqs_str: "a['zoom'] = ;", shapes: [], waves: [] };

let fixtureRoot;

beforeEach(() => {
  fixtureRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'validate-presets-'));
  fs.mkdirSync(path.join(fixtureRoot, 'tools'));
  fs.mkdirSync(path.join(fixtureRoot, 'src', 'presets-extra'), { recursive: true });
  for (const tool of TOOLS) {
    fs.copyFileSync(path.join(REPO_ROOT, 'tools', tool), path.join(fixtureRoot, 'tools', tool));
  }
});

afterEach(() => {
  fs.rmSync(fixtureRoot, { recursive: true, force: true });
});

/** Write the fixture preset index. */
function writeIndex(index) {
  const text = `${INDEX_PREFIX}${JSON.stringify(index)};\n`;
  fs.writeFileSync(path.join(fixtureRoot, 'src', 'presets-extra', 'index.js'), text);
}

/** Write one fixture chunk file under its physical name. */
function writeChunk(filename, logicalId, presets) {
  const text = `window.__bcPresetChunk(${logicalId},${JSON.stringify(presets)});\n`;
  fs.writeFileSync(path.join(fixtureRoot, 'src', 'presets-extra', filename), text);
}

/** Run one validator and return its process result and reported preset names. */
function runValidator(tool) {
  const reportPath = path.join(fixtureRoot, 'report.json');
  const result = spawnSync(process.execPath, [path.join(fixtureRoot, 'tools', tool), reportPath], {
    cwd: fixtureRoot,
    encoding: 'utf8',
    env: { ...process.env, NODE_PATH: path.join(REPO_ROOT, 'node_modules') },
  });
  let names = null;
  if (fs.existsSync(reportPath)) {
    const report = JSON.parse(fs.readFileSync(reportPath, 'utf8'));
    names = report.presets.map((entry) => entry.experimentalName || entry.name);
  }
  return { result, names };
}

test('experimental validator fails on an invalid equation', () => {
  writeIndex({ v: 2, chunks: [['Mainline'], ['[EXP] Broken']], files: ['chunk-000.js', 'chunk-9000.js'] });
  writeChunk('chunk-000.js', 0, { Mainline: VALID_PRESET });
  writeChunk('chunk-9000.js', 1, { '[EXP] Broken': INVALID_PRESET });

  const { result, names } = runValidator('validate-experimental-presets.js');

  assert.deepStrictEqual(names, ['[EXP] Broken'], result.stderr);
  assert.strictEqual(result.status, EXIT_FAILURE, result.stdout);
});

test('experimental validator passes valid presets', () => {
  writeIndex({ v: 2, chunks: [['Mainline'], ['[EXP] Valid']], files: ['chunk-000.js', 'chunk-9000.js'] });
  writeChunk('chunk-000.js', 0, { Mainline: VALID_PRESET });
  writeChunk('chunk-9000.js', 1, { '[EXP] Valid': VALID_PRESET });

  const { result, names } = runValidator('validate-experimental-presets.js');

  assert.deepStrictEqual(names, [], result.stderr);
  assert.strictEqual(result.status, EXIT_SUCCESS, result.stderr);
});

test('experimental validator accepts an index without files', () => {
  writeIndex({ v: 1, chunks: [['Mainline']] });
  writeChunk('chunk-000.js', 0, { Mainline: VALID_PRESET });

  const { result, names } = runValidator('validate-experimental-presets.js');

  assert.deepStrictEqual(names, [], result.stderr);
  assert.strictEqual(result.status, EXIT_SUCCESS, result.stderr);
});

test('chunk validator reads padded names without files', () => {
  writeIndex({ v: 1, chunks: [['Valid'], ['Broken']] });
  writeChunk('chunk-000.js', 0, { Valid: VALID_PRESET });
  writeChunk('chunk-001.js', 1, { Broken: INVALID_PRESET });

  const { result, names } = runValidator('validate-preset-chunks.js');

  assert.deepStrictEqual(names, ['Broken'], result.stderr);
  assert.strictEqual(result.status, EXIT_FAILURE, result.stdout);
});
