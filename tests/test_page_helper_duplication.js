/* The page scripts share describeDeviceError, the audio-prefs fallback, and
 * the shortcut filter through BCViz. A local copy drifts from the shared one,
 * so each page must call the shared helper instead of defining its own. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const test = require('node:test');

const PAGE_SCRIPTS = ['src/js/obs-ui.js', 'src/js/fullscreen-ui.js', 'src/js/performance-ui.js'];
const LOCAL_COPIES = [
  { label: 'describeDeviceError', pattern: /function\s+describeDeviceError\s*\(/ },
  { label: 'shouldIgnoreShortcut', pattern: /function\s+shouldIgnoreShortcut\s*\(/ },
  { label: 'NO_PREFS', pattern: /\bNO_PREFS\b/ },
  { label: 'BCAudioPrefs fallback', pattern: /window\.BCAudioPrefs\s*\|\|/ },
];

PAGE_SCRIPTS.forEach(function (path) {
  test(path + ' uses the shared BCViz page helpers', function () {
    const source = fs.readFileSync(path, 'utf8');
    const copies = LOCAL_COPIES
      .filter(function (copy) { return copy.pattern.test(source); })
      .map(function (copy) { return copy.label; });

    assert.deepEqual(copies, [], path + ' defines its own ' + copies.join(', '));
  });
});
