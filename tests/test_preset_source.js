/* The JS curation tools share one bracket matcher and one reader for the
 * index.js and chunk wrappers. These cases pin the shared behavior. */
const assert = require('node:assert/strict');
const test = require('node:test');

const {
  findMatchingCloser,
  parseIndexSource,
  parseChunkSource,
} = require('../tools/preset_source.js');

test('findMatchingCloser returns the closer that balances the opener', function () {
  const source = 'var presets={"a":{"b":1},"c":[1,{"d":2}]};';
  const openIdx = source.indexOf('{');

  assert.equal(findMatchingCloser(source, openIdx), source.length - 2);
});

test('findMatchingCloser matches square brackets from a square opener', function () {
  const source = 'x=[1,[2,3],{"k":[4]}];';
  const openIdx = source.indexOf('[');

  assert.equal(findMatchingCloser(source, openIdx), source.length - 2);
});

test('findMatchingCloser ignores brackets inside strings and escaped quotes', function () {
  const source = '{"a":"}{","b":\'}\',"c":"say \\"}\\"","d":1}';

  assert.equal(findMatchingCloser(source, 0), source.length - 1);
});

test('findMatchingCloser reports -1 for an unbalanced opener', function () {
  assert.equal(findMatchingCloser('{"a":{"b":1}', 0), -1);
});

test('parseIndexSource returns the payload and the wrapper parts', function () {
  const raw = 'window.BCExtraPresetIndex={"v":2,"chunks":[["a"]],"files":["chunk-000.js"]};\n';
  const parsed = parseIndexSource(raw);

  assert.deepEqual(parsed.data, { v: 2, chunks: [['a']], files: ['chunk-000.js'] });
  assert.equal(parsed.prefix, 'window.BCExtraPresetIndex=');
  assert.equal(parsed.suffix, ';');
});

test('parseIndexSource rejects an unexpected wrapper', function () {
  assert.throws(function () { parseIndexSource('window.Other={"chunks":[]};'); }, /index\.js wrapper/);
  assert.throws(function () { parseIndexSource('window.BCExtraPresetIndex={"chunks":[]}'); }, /index\.js wrapper/);
});

test('parseChunkSource returns the payload for the matching chunk id', function () {
  const raw = 'window.__bcPresetChunk(7,{"name":{"baseVals":{}}});\n';
  const parsed = parseChunkSource(raw, 7, 'chunk-007.js');

  assert.deepEqual(parsed.data, { name: { baseVals: {} } });
  assert.equal(parsed.prefix, 'window.__bcPresetChunk(7,');
  assert.equal(parsed.suffix, ');');
});

test('parseChunkSource rejects a chunk whose callback names another id', function () {
  const raw = 'window.__bcPresetChunk(8,{});';

  assert.throws(function () { parseChunkSource(raw, 7, 'chunk-007.js'); }, /chunk-007\.js/);
});
