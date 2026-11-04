const assert = require('node:assert/strict');
const test = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const utils = require('milkdrop-preset-utils');

const workerSource = fs.readFileSync(path.join(__dirname, '../tools/convert-shader-worker.js'), 'utf8');
// Fixed compiler output exercises the real worker and upstream postprocessor.
const compiled = `#version 300 es
out vec4 _glesFragData[4];
in highp vec2 xlv_TEXCOORD0;
uniform float time;
float helper(float x) { return clamp(x, 0.0, 1.0); }
void main ()
{
  highp vec2 mutableUv = xlv_TEXCOORD0;
  mutableUv.x += time;
  highp vec4 color = vec4(helper(mutableUv.x));
  _glesFragData[0] = color;
}
`;

/** Supply compiler output at the native dependency boundary. */
function runWorker(output) {
  let response = '';
  const dependencies = {
    fs: { readFileSync: () => 'shader_body { ret = float3(1,1,1); }' },
    'milkdrop-preset-utils': utils,
    'milkdrop-shader-converter': { convertHLSLString: () => output },
  };
  vm.runInNewContext(workerSource, {
    require: name => dependencies[name],
    process: { argv: ['node', 'worker', 'fixture'], stdout: { write: value => { response += value; } } },
    Buffer,
  }, { timeout: 1000 });
  return JSON.parse(response);
}

test('preserves helper functions and adapts optimized shader output', function preserveShaderHelpers() {
  const result = runWorker(Buffer.from(compiled));
  assert.equal(result.ok, true, result.error);
  assert.match(result.glsl, /float helper\(float x\)/);
  assert.match(result.glsl, /mutableUv = uv/);
  assert.match(result.glsl, /ret = color.xyz/);
  assert.doesNotMatch(result.glsl, /void main|_glesFragData|uniform float time|#version/);
});

test('rejects empty native output', function rejectEmptyOutput() {
  const result = runWorker(Buffer.from(''));
  assert.equal(result.ok, false);
  assert.match(result.error, /empty/i);
});

test('rejects malformed native entry point', function rejectMalformedOutput() {
  const result = runWorker(Buffer.from('void main () {'));
  assert.equal(result.ok, false);
});

test('rejects missing native output', function rejectMissingOutput() {
  const result = runWorker(undefined);
  assert.equal(result.ok, false);
});
