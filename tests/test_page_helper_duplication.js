/* The page scripts share describeDeviceError, the audio-prefs fallback, and
 * the shortcut filter through BCViz. A local copy drifts from the shared one,
 * so each page must call the shared helper instead of defining its own. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const test = require('node:test');

const PAGE_SCRIPTS = ['src/js/obs-ui.js', 'src/js/fullscreen-ui.js', 'src/js/performance-ui.js'];
/* A copy can be a declaration or a function expression bound to the name.
 * Binding the name to the shared BCViz helper is not a copy. */
function definitionPattern(name) {
  return new RegExp(
    'function\\s+' + name + '\\s*\\(' +
    '|\\b' + name + '\\s*=\\s*(?:async\\s+)?function\\b' +
    '|\\b' + name + '\\s*=\\s*(?:async\\s+)?(?:\\([^)]*\\)|\\w+)\\s*=>',
  );
}

const LOCAL_COPIES = [
  { label: 'describeDeviceError', pattern: definitionPattern('describeDeviceError') },
  { label: 'shouldIgnoreShortcut', pattern: definitionPattern('shouldIgnoreShortcut') },
  { label: 'NO_PREFS', pattern: /\bNO_PREFS\b/ },
  { label: 'BCAudioPrefs fallback', pattern: /window\.BCAudioPrefs\s*\|\|/ },
];

test('the copy patterns catch every definition form but not the shared binding', function () {
  const pattern = definitionPattern('describeDeviceError');

  [
    'function describeDeviceError(error) {',
    'const describeDeviceError = function (error) {',
    'let describeDeviceError = async function named(error) {',
    'const describeDeviceError = (error) => error.name;',
    'const describeDeviceError = error => error.name;',
  ].forEach(function (source) {
    assert.equal(pattern.test(source), true, source);
  });
  assert.equal(pattern.test('const describeDeviceError = BCViz.describeDeviceError;'), false);
});

PAGE_SCRIPTS.forEach(function (path) {
  test(path + ' uses the shared BCViz page helpers', function () {
    const source = fs.readFileSync(path, 'utf8');
    const copies = LOCAL_COPIES
      .filter(function (copy) { return copy.pattern.test(source); })
      .map(function (copy) { return copy.label; });

    assert.deepEqual(copies, [], path + ' defines its own ' + copies.join(', '));
  });
});
