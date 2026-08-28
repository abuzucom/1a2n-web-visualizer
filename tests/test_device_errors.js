const assert = require('node:assert/strict');
const fs = require('node:fs');
const test = require('node:test');
const vm = require('node:vm');

function loadDeviceErrors() {
  const window = {};
  const source = fs.readFileSync('src/js/device-errors.js', 'utf8');
  vm.runInNewContext(source, { window: window, console: console });
  return window.BCDeviceErrors;
}

function makeError(name, message) {
  const error = new Error(message);
  error.name = name;
  return error;
}

test('an exclusive-mode lock points at the app holding the device', function () {
  const describe = loadDeviceErrors().describe;

  ['NotReadableError', 'AbortError'].forEach(function (name) {
    const text = describe(makeError(name, 'Could not start audio source'));
    assert.ok(text.startsWith(name + ': Could not start audio source'), text);
    assert.match(text, /exclusively locked by another app/);
  });
});

test('a missing device points at the cable, not at permissions', function () {
  const describe = loadDeviceErrors().describe;

  const text = describe(makeError('NotFoundError', 'Requested device not found'));
  assert.match(text, /unplugged or disabled/);
});

test('a stale device id asks for a re-select', function () {
  const describe = loadDeviceErrors().describe;

  const text = describe(makeError('OverconstrainedError', 'Constraint not satisfied'));
  assert.match(text, /no longer valid; re-select an input/);
});

/* Chromium distinguishes an embedder or site block from an operating-system
 * privacy block by message alone, and the two need different fixes, so the
 * hint has to branch on the message rather than on the name. */
test('a page-level permission denial names the OBS URL-source fix', function () {
  const describe = loadDeviceErrors().describe;

  const text = describe(makeError('NotAllowedError', 'Permission denied'));
  assert.ok(text.startsWith('NotAllowedError: Permission denied'), text);
  assert.match(text, /URL source/);
  assert.doesNotMatch(text, /privacy settings/);
});

test('a system-level permission denial names the OS privacy fix', function () {
  const describe = loadDeviceErrors().describe;

  const text = describe(makeError('NotAllowedError', 'Permission denied by system'));
  assert.match(text, /privacy settings/);
  assert.doesNotMatch(text, /URL source/);
});

test('an insecure origin asks for localhost or https', function () {
  const describe = loadDeviceErrors().describe;

  const text = describe(makeError('SecurityError', 'Blocked'));
  assert.match(text, /localhost/);
});

test('an unrecognized error still reports its name and message', function () {
  const describe = loadDeviceErrors().describe;

  assert.equal(describe(makeError('TypeError', 'boom')), 'TypeError: boom');
});

test('a non-error value is described without a leading separator', function () {
  const describe = loadDeviceErrors().describe;

  assert.equal(describe('plain failure'), 'plain failure');
  assert.equal(describe(null), 'null');
});
