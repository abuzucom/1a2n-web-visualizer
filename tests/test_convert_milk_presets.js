const assert = require('node:assert/strict');
const test = require('node:test');

const { validatePresetEquations } = require('../tools/convert-milk-presets');

test('accepts a valid equation without a trailing semicolon', function () {
  assert.doesNotThrow(function () {
    validatePresetEquations({
      init_eqs_str: '',
      frame_eqs_str: 'wave_r = 1.0',
      pixel_eqs_str: '',
      shapes: [],
      waves: [],
    });
  });
});
