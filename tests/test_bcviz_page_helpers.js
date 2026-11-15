const assert = require('node:assert/strict');
const fs = require('node:fs');
const test = require('node:test');
const vm = require('node:vm');

const CORE_SOURCE = fs.readFileSync('src/js/visualizer-core.js', 'utf8');

/* Loads visualizer-core.js the way the pages do: support scripts first, each
 * one publishing its global on the shared window. */
function loadCore(supportScripts) {
  const window = {};
  (supportScripts || []).forEach(function (path) {
    vm.runInNewContext(fs.readFileSync(path, 'utf8'), { window: window, console: console });
  });
  vm.runInNewContext(CORE_SOURCE, { window: window, console: console });
  return window;
}

function namedError(name, message) {
  const error = new Error(message);
  error.name = name;
  return error;
}

function keyEvent(key, target, modifiers) {
  return Object.assign({ key: key, target: target }, modifiers || {});
}

test('describeDeviceError uses the shared wording when device-errors.js is loaded', function () {
  const window = loadCore(['src/js/device-errors.js']);
  const error = namedError('NotReadableError', 'Could not start audio source');

  assert.equal(window.BCViz.describeDeviceError(error), window.BCDeviceErrors.describe(error));
  assert.match(window.BCViz.describeDeviceError(error), /exclusively locked/);
});

test('describeDeviceError degrades to name and message without device-errors.js', function () {
  const window = loadCore([]);

  assert.equal(
    window.BCViz.describeDeviceError(namedError('NotFoundError', 'gone')),
    'NotFoundError: gone',
  );
  assert.equal(window.BCViz.describeDeviceError('plain failure'), 'plain failure');
});

test('audioPrefs returns the loaded store', function () {
  const window = loadCore([]);
  const store = { read: function () { return null; } };
  window.BCAudioPrefs = store;

  assert.equal(window.BCViz.audioPrefs(), store);
});

test('audioPrefs falls back to an inert store without audio-prefs.js', function () {
  const window = loadCore([]);
  const prefs = window.BCViz.audioPrefs();

  assert.equal(prefs.read(), null);
  assert.equal(prefs.write('dev-a', 'Mic'), false);
  assert.equal(prefs.clear(), undefined);
  assert.equal(prefs.resolve([{ deviceId: 'dev-a' }], { deviceId: 'dev-a' }), '');
});

test('shouldIgnoreShortcut passes browser and system key combinations through', function () {
  const window = loadCore([]);
  const ignore = window.BCViz.shouldIgnoreShortcut;

  assert.equal(ignore(keyEvent('n', null, { ctrlKey: true })), true);
  assert.equal(ignore(keyEvent('n', null, { metaKey: true })), true);
  assert.equal(ignore(keyEvent('n', null, { altKey: true })), true);
  assert.equal(ignore(keyEvent('?', null, { shiftKey: true })), false);
});

test('shouldIgnoreShortcut leaves typing to text fields except Escape', function () {
  const window = loadCore([]);
  const ignore = window.BCViz.shouldIgnoreShortcut;

  ['INPUT', 'TEXTAREA', 'SELECT'].forEach(function (tagName) {
    assert.equal(ignore(keyEvent('n', { tagName: tagName })), true, tagName);
    assert.equal(ignore(keyEvent('Escape', { tagName: tagName })), false, tagName);
  });
  assert.equal(ignore(keyEvent('n', { tagName: 'DIV', isContentEditable: true })), true);
});

test('shouldIgnoreShortcut leaves Space and Enter to buttons and links', function () {
  const window = loadCore([]);
  const ignore = window.BCViz.shouldIgnoreShortcut;

  ['BUTTON', 'A', 'SUMMARY'].forEach(function (tagName) {
    assert.equal(ignore(keyEvent(' ', { tagName: tagName })), true, tagName);
    assert.equal(ignore(keyEvent('Enter', { tagName: tagName })), true, tagName);
    assert.equal(ignore(keyEvent('n', { tagName: tagName })), false, tagName);
  });
  assert.equal(ignore(keyEvent(' ', { tagName: 'CANVAS' })), false);
  assert.equal(ignore(keyEvent(' ', null)), false);
});
