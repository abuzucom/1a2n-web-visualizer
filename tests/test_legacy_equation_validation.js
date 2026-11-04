const assert = require('node:assert/strict');
const test = require('node:test');
const { validatePresetEquations } = require('../tools/convert-milk-presets');

test('accepts absent equations that Butterchurn does not compile', function acceptDisabledItems() {
  assert.doesNotThrow(function validateDisabledItems() {
    validatePresetEquations({
      init_eqs_str: '', frame_eqs_str: '',
      shapes: [{ baseVals: { enabled: 0 } }],
      waves: [{ baseVals: {} }],
    });
  });
});

test('rejects missing frame equations on enabled shapes', function rejectEnabledShape() {
  assert.throws(function validateEnabledShape() {
    validatePresetEquations({
      init_eqs_str: '', frame_eqs_str: '', pixel_eqs_str: '',
      shapes: [{ baseVals: { enabled: 1 }, init_eqs_str: '' }], waves: [],
    });
  }, /shape\[0\].frame_eqs_str/);
});

test('accepts absent point equations on an enabled wave', function acceptOptionalPoint() {
  assert.doesNotThrow(function validateOptionalPoint() {
    validatePresetEquations({
      init_eqs_str: '', frame_eqs_str: '', pixel_eqs_str: '', shapes: [],
      waves: [{ baseVals: { enabled: 1 }, init_eqs_str: '', frame_eqs_str: '' }],
    });
  });
});
