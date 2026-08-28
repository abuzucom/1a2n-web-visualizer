const assert = require('node:assert/strict');
const fs = require('node:fs');
const test = require('node:test');
const vm = require('node:vm');

const SOURCE = fs.readFileSync('src/js/audio-prefs.js', 'utf8');

function createStorage(initial) {
  const entries = Object.assign({}, initial);
  return {
    entries: entries,
    getItem: function (key) {
      return Object.prototype.hasOwnProperty.call(entries, key) ? entries[key] : null;
    },
    setItem: function (key, value) { entries[key] = String(value); },
    removeItem: function (key) { delete entries[key]; },
  };
}

/* Some file:// and privacy-mode configurations throw on the very first touch
 * of localStorage, so every accessor has to survive a storage that explodes. */
function createHostileStorage() {
  const boom = function () { throw new Error('access denied'); };
  return { getItem: boom, setItem: boom, removeItem: boom };
}

function loadPrefs(storage) {
  const window = { localStorage: storage };
  vm.runInNewContext(SOURCE, { window: window, console: console });
  return { prefs: window.BCAudioPrefs, storage: storage };
}

test('a saved input round-trips through storage', function () {
  const loaded = loadPrefs(createStorage());

  assert.equal(loaded.prefs.write('dev-a', 'Voicemeeter Out B1'), true);
  // Field-wise, not deepEqual: the module parses inside its own vm realm, so
  // the returned object does not share this realm's Object prototype.
  const saved = loaded.prefs.read();
  assert.equal(saved.deviceId, 'dev-a');
  assert.equal(saved.label, 'Voicemeeter Out B1');
});

test('clearing removes the saved input', function () {
  const loaded = loadPrefs(createStorage());

  loaded.prefs.write('dev-a', 'Voicemeeter Out B1');
  loaded.prefs.clear();
  assert.equal(loaded.prefs.read(), null);
});

test('reading unwritten or corrupt storage yields no preference', function () {
  assert.equal(loadPrefs(createStorage()).prefs.read(), null);
  assert.equal(loadPrefs(createStorage({ 'bcviz.audioInput.v1': 'not json' })).prefs.read(), null);
  assert.equal(loadPrefs(createStorage({ 'bcviz.audioInput.v1': '[]' })).prefs.read(), null);
});

test('a storage that throws never propagates out of the accessors', function () {
  const loaded = loadPrefs(createHostileStorage());

  assert.equal(loaded.prefs.read(), null);
  assert.equal(loaded.prefs.write('dev-a', 'Voicemeeter Out B1'), false);
  assert.doesNotThrow(function () { loaded.prefs.clear(); });
});

test('a missing localStorage is treated as no preference', function () {
  const window = {};
  vm.runInNewContext(SOURCE, { window: window, console: console });

  assert.equal(window.BCAudioPrefs.read(), null);
  assert.equal(window.BCAudioPrefs.write('dev-a', 'Mic'), false);
});

test('resolve prefers an exact device id match', function () {
  const prefs = loadPrefs(createStorage()).prefs;
  const devices = [
    { deviceId: 'dev-a', label: 'Built-in Mic' },
    { deviceId: 'dev-b', label: 'Voicemeeter Out B1' },
  ];

  assert.equal(prefs.resolve(devices, { deviceId: 'dev-b', label: 'Voicemeeter Out B1' }), 'dev-b');
});

/* A Voicemeeter restart hands the device back under a new id with the same
 * label, which is the case an id-only match would silently lose. */
test('resolve falls back to the label when the saved id is gone', function () {
  const prefs = loadPrefs(createStorage()).prefs;
  const devices = [
    { deviceId: 'dev-a', label: 'Built-in Mic' },
    { deviceId: 'dev-c', label: 'Voicemeeter Out B1' },
  ];

  assert.equal(prefs.resolve(devices, { deviceId: 'dev-b', label: 'Voicemeeter Out B1' }), 'dev-c');
});

test('resolve yields no constraint when nothing matches', function () {
  const prefs = loadPrefs(createStorage()).prefs;
  const devices = [{ deviceId: 'dev-a', label: 'Built-in Mic' }];

  assert.equal(prefs.resolve(devices, { deviceId: 'dev-b', label: 'Voicemeeter Out B1' }), '');
  assert.equal(prefs.resolve(devices, null), '');
  assert.equal(prefs.resolve([], { deviceId: 'dev-a', label: 'Built-in Mic' }), '');
});

/* Pre-permission enumeration returns blank labels for every device, so an
 * empty saved label must never match one of them. */
test('resolve never matches a blank label against blank device labels', function () {
  const prefs = loadPrefs(createStorage()).prefs;
  const devices = [{ deviceId: 'dev-x', label: '' }, { deviceId: 'dev-y', label: '' }];

  assert.equal(prefs.resolve(devices, { deviceId: 'dev-b', label: '' }), '');
});

/* Two identical interfaces enumerate under the same label. Picking the first
 * one reconnects to the wrong input and the stream looks healthy, so the
 * failure reads as "no audio" mid-set rather than as a wrong choice. */
test('resolve declines a label shared by more than one device', function () {
  const prefs = loadPrefs(createStorage()).prefs;
  const devices = [
    { deviceId: 'dev-a', label: 'Microphone (USB Audio Device)' },
    { deviceId: 'dev-b', label: 'Microphone (USB Audio Device)' },
  ];

  assert.equal(prefs.resolve(devices, { deviceId: 'gone', label: 'Microphone (USB Audio Device)' }), '');
});

/* The saved id still wins outright, so an ambiguous label is only a reason to
 * decline the fallback, not a reason to drop an exact match. */
test('an exact id match still resolves when its label is ambiguous', function () {
  const prefs = loadPrefs(createStorage()).prefs;
  const devices = [
    { deviceId: 'dev-a', label: 'Microphone (USB Audio Device)' },
    { deviceId: 'dev-b', label: 'Microphone (USB Audio Device)' },
  ];

  assert.equal(prefs.resolve(devices, { deviceId: 'dev-b', label: 'Microphone (USB Audio Device)' }), 'dev-b');
});
