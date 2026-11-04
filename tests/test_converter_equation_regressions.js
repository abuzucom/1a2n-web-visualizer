const assert = require('node:assert/strict');
const test = require('node:test');
const vm = require('node:vm');
const { convertMilkText, validatePresetEquations } = require('../tools/convert-milk-presets');

/** Execute only the trusted equations generated from the fixed fixtures below. */
function runEquation(source, values) {
  const context = { a: values };
  vm.runInNewContext(source, context, { timeout: 1000 });
  return context.a;
}

test('converts custom wave point equations with the wave parser', function convertWavePoint() {
  const { preset, warnings } = convertMilkText([
    'MILKDROP_PRESET_VERSION=201',
    '[preset00]',
    'wavecode_0_enabled=1',
    'wave_0_init1=t1=2;',
    'wave_0_per_frame1=r=0.75;',
    'wave_0_per_point1=x=sample*0.5;',
  ].join('\n'));
  assert.deepEqual(warnings, []);
  const wave = preset.waves[0];
  assert.equal(runEquation(wave.init_eqs_str, {}).t1, 2);
  assert.equal(runEquation(wave.frame_eqs_str, {}).r, 0.75);
  assert.equal(runEquation(wave.point_eqs_str, { sample: 0.5 }).x, 0.25);
});

test('converts custom shape equations with the shape parser', function convertShapeFrame() {
  const { preset, warnings } = convertMilkText([
    'MILKDROP_PRESET_VERSION=201',
    '[preset00]',
    'shapecode_0_enabled=1',
    'shape_0_init1=t1=3;',
    'shape_0_per_frame1=rad=0.25;',
  ].join('\n'));
  assert.deepEqual(warnings, []);
  const shape = preset.shapes[0];
  assert.equal(runEquation(shape.init_eqs_str, {}).t1, 3);
  assert.equal(runEquation(shape.frame_eqs_str, {}).rad, 0.25);
});

test('rejects missing required equation fields before compilation', function rejectMissingField() {
  assert.throws(function validateMissingField() {
    validatePresetEquations({
      frame_eqs_str: '', pixel_eqs_str: '', shapes: [], waves: [],
    });
  }, /init_eqs_str/);
});

test('preserves empty required equations on disabled items', function preserveEmptyFields() {
  const { preset } = convertMilkText('MILKDROP_PRESET_VERSION=201\n[preset00]\nfDecay=0.98\n');
  for (const shape of preset.shapes) {
    assert.equal(shape.init_eqs_str, '');
    assert.equal(shape.frame_eqs_str, '');
  }
  for (const wave of preset.waves) {
    assert.equal(wave.init_eqs_str, '');
    assert.equal(wave.frame_eqs_str, '');
    assert.equal(wave.point_eqs_str, '');
  }
});
