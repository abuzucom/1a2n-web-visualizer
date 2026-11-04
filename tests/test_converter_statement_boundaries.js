const assert = require('node:assert/strict');
const test = require('node:test');
const vm = require('node:vm');
const { convertMilkText } = require('../tools/convert-milk-presets');

test('separates converted bare expressions from the runtime return', function separateRuntimeReturn() {
  const { preset, warnings } = convertMilkText([
    'MILKDROP_PRESET_VERSION=201', '[preset00]',
    'wavecode_0_enabled=1', 'wave_0_init1=t',
  ].join('\n'));
  assert.deepEqual(warnings, []);
  assert.doesNotThrow(function compileRuntimeWrapper() {
    new vm.Script(`(function(a) {${preset.waves[0].init_eqs_str} return a;})`);
  });
});
