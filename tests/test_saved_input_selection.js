/* Saved audio input regressions: the fullscreen and performance pages request
 * the remembered input on start, and a failed device switch stops naming the
 * input it released. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const test = require('node:test');
const vm = require('node:vm');

const STORAGE_KEY = 'bcviz.audioInput.v1';
const SETTLE_MS = 10;
const OS_DEFAULT_ID = 'dev-a';
const SAVED_ID = 'dev-b';
const DEVICES = [
  { kind: 'audioinput', deviceId: OS_DEFAULT_ID, label: 'Built-in Mic' },
  { kind: 'audioinput', deviceId: SAVED_ID, label: 'Voicemeeter Out B1' },
];
const FULLSCREEN_IDS = [
  'viz', 'toast', 'help', 'startPrompt', 'startupStatus', 'startupStatusText',
  'startupProgressBar', 'startError', 'removeBtn', 'excludedBtn', 'favoriteBtn',
  'favoritesBtn', 'excludedPanel', 'excludedList', 'copyExcludedBtn', 'closeExcludedBtn',
  'favoritesPanel', 'favoritesListText', 'copyFavoritesBtn', 'closeFavoritesBtn',
];
const PERFORMANCE_IDS = ['viz', 'toast', 'help', 'startPrompt', 'startError'];

function readSource(path) {
  return fs.readFileSync(path, 'utf8');
}

function sleep(ms) {
  return new Promise(function (resolve) { setTimeout(resolve, ms); });
}

/** Schedule like the browser, without holding the test process open. */
function unrefTimeout(callback, delay) {
  const timer = setTimeout(callback, delay);
  timer.unref();
  return timer;
}

function createClassList() {
  const classes = new Set();
  return {
    add: function (name) { classes.add(name); },
    remove: function (name) { classes.delete(name); },
    toggle: function (name) {
      if (classes.has(name)) { classes.delete(name); return false; }
      classes.add(name); return true;
    },
    contains: function (name) { return classes.has(name); },
  };
}

function createElement(id) {
  const element = {
    id: id,
    tagName: 'DIV',
    hidden: false,
    inert: false,
    value: '',
    textContent: '',
    listeners: {},
    classList: createClassList(),
    style: {},
    parentElement: { setAttribute: function () {}, removeAttribute: function () {} },
    addEventListener: function (event, callback) {
      if (!element.listeners[event]) element.listeners[event] = [];
      element.listeners[event].push(callback);
    },
    setAttribute: function () {},
    removeAttribute: function () {},
    getAttribute: function () { return null; },
    focus: function () {},
  };
  return element;
}

function createDocument(ids) {
  const elements = {};
  ids.forEach(function (id) { elements[id] = createElement(id); });
  const listeners = {};
  const body = createElement('body');
  const document = {
    body: body,
    activeElement: body,
    documentElement: {},
    fullscreenElement: null,
    createElement: function (tag) { return createElement(String(tag)); },
    getElementById: function (id) { return elements[id]; },
    addEventListener: function (event, callback) {
      if (!listeners[event]) listeners[event] = [];
      listeners[event].push(callback);
    },
    pressKey: function (key) {
      const evt = { key: key, target: body, repeat: false, preventDefault: function () {} };
      (listeners.keydown || []).forEach(function (handler) { handler(evt); });
    },
  };
  return document;
}

function createStorage(saved) {
  const entries = {};
  if (saved) entries[STORAGE_KEY] = JSON.stringify(saved);
  return {
    getItem: function (key) {
      return Object.prototype.hasOwnProperty.call(entries, key) ? entries[key] : null;
    },
    setItem: function (key, value) { entries[key] = String(value); },
    removeItem: function (key) { delete entries[key]; },
  };
}

/** A controller fake that behaves like visualizer-core: the device list stays
 * empty until getDevices() enumerates, and an unconstrained start opens the
 * operating system default. */
function createViz() {
  const state = { started: false, enumerated: false, deviceId: '', startCalls: [] };
  const viz = {
    state: state,
    keys: function () { return ['preset']; },
    isStarted: function () { return state.started; },
    isDemo: function () { return false; },
    diagnostics: function () { return {}; },
    setAudioGuard: function () { return false; },
    listDevices: function () { return state.enumerated ? DEVICES.slice() : []; },
    getDevices: function () {
      state.enumerated = true;
      return Promise.resolve(DEVICES.slice());
    },
    currentDeviceId: function () { return state.deviceId; },
    start: function (deviceId) {
      state.startCalls.push(deviceId);
      state.enumerated = true;
      state.deviceId = deviceId || OS_DEFAULT_ID;
      state.started = true;
      return Promise.resolve();
    },
  };
  return viz;
}

function createPageWindow(storage) {
  const window = {
    localStorage: storage,
    setTimeout: unrefTimeout,
    clearTimeout: clearTimeout,
    setInterval: function () { return 0; },
    clearInterval: function () {},
    BCHyperspeed: { create: function () { return { toggle: function () { return true; } }; } },
    BCEnergyCatalog: { version: 1, presets: {} },
    BCPerformanceCatalog: { version: 1, presets: [] },
  };
  ['src/js/diagnostics.js', 'src/js/device-errors.js', 'src/js/audio-prefs.js', 'src/js/energy-curation.js']
    .forEach(function (path) {
      vm.runInNewContext(readSource(path), { window: window, console: console });
    });
  return window;
}

function loadPage(path, ids, storage) {
  const window = createPageWindow(storage);
  const document = createDocument(ids);
  const viz = createViz();
  vm.runInNewContext(readSource(path), {
    window: window,
    document: document,
    navigator: {},
    location: { search: '' },
    BCViz: { create: function () { return viz; } },
    setTimeout: unrefTimeout,
    clearTimeout: clearTimeout,
    console: console,
  });
  return { window: window, document: document, viz: viz };
}

[
  ['fullscreen', 'src/js/fullscreen-ui.js', FULLSCREEN_IDS],
  ['performance', 'src/js/performance-ui.js', PERFORMANCE_IDS],
].forEach(function (page) {
  test('the ' + page[0] + ' page starts on the remembered input', async function () {
    const storage = createStorage({ deviceId: SAVED_ID, label: 'Voicemeeter Out B1' });
    const harness = loadPage(page[1], page[2], storage);

    harness.document.pressKey('n');
    await sleep(SETTLE_MS);

    assert.equal(harness.viz.state.startCalls.length, 1);
    assert.equal(harness.viz.state.startCalls[0], SAVED_ID, 'start requests the saved device');
    assert.equal(harness.window.BCAudioPrefs.read().deviceId, SAVED_ID, 'the saved choice survives start');
  });
});

/* A minimal browser for visualizer-core.js: a fake butterchurn, a fake audio
 * graph, and a media device fake whose saved device refuses to open. */
function createCoreHarness() {
  const window = {
    butterchurnPresets: { getPresets: function () { return { aaa: { baseVals: {} } }; } },
    BCExtraPresetIndex: { chunks: [], files: [] },
    devicePixelRatio: 1,
    innerWidth: 100,
    innerHeight: 50,
    addEventListener: function () {},
    requestAnimationFrame: function () { return 0; },
    cancelAnimationFrame: function () {},
    requestIdleCallback: function () {},
    setTimeout: unrefTimeout,
    clearTimeout: clearTimeout,
    setInterval: function () { return 0; },
    clearInterval: function () {},
  };
  function fakeParam() {
    return {
      value: 0,
      setValueAtTime: function () { return this; },
      linearRampToValueAtTime: function () { return this; },
      exponentialRampToValueAtTime: function () { return this; },
      setTargetAtTime: function () { return this; },
      cancelScheduledValues: function () { return this; },
    };
  }
  function fakeNode(extra) {
    return Object.assign({
      connect: function (target) { return target; },
      disconnect: function () {},
      start: function () {},
      stop: function () {},
    }, extra || {});
  }
  window.AudioContext = function () {
    this.currentTime = 0;
    this.sampleRate = 48000;
    this.state = 'running';
    this.destination = fakeNode();
    this.resume = async function () {};
    this.close = async function () {};
    this.createMediaStreamSource = function () { return fakeNode(); };
    this.createOscillator = function () { return fakeNode({ frequency: fakeParam(), detune: fakeParam() }); };
    this.createGain = function () { return fakeNode({ gain: fakeParam() }); };
  };
  window.butterchurn = {
    createVisualizer: function () {
      return {
        loadPreset: function () {},
        render: function () {},
        connectAudio: function () {},
        disconnectAudio: function () {},
      };
    },
  };
  const mediaDevices = {
    enumerateDevices: async function () { return DEVICES.slice(); },
    getUserMedia: async function (constraints) {
      const wanted = constraints.audio.deviceId ? constraints.audio.deviceId.exact : OS_DEFAULT_ID;
      if (wanted === SAVED_ID) {
        const error = new Error('Requested device unavailable');
        error.name = 'NotFoundError';
        throw error;
      }
      const device = DEVICES[0];
      const track = {
        kind: 'audio', label: device.label, readyState: 'live', muted: false,
        getSettings: function () { return { deviceId: device.deviceId }; },
        stop: function () { track.readyState = 'ended'; },
      };
      return { getTracks: function () { return [track]; }, getAudioTracks: function () { return [track]; } };
    },
  };
  const document = {
    visibilityState: 'visible',
    hidden: false,
    addEventListener: function () {},
    createElement: function () { return {}; },
    head: { appendChild: function () {} },
  };
  ['src/js/render-driver.js', 'src/js/audible-keepalive.js', 'src/js/audio-watchdog.js',
    'src/js/device-errors.js', 'src/js/demo-audio.js'].forEach(function (path) {
    vm.runInNewContext(readSource(path), { window: window, console: console });
  });
  vm.runInNewContext(readSource('src/js/visualizer-core.js'), {
    window: window,
    document: document,
    navigator: { mediaDevices: mediaDevices },
    console: console,
    setTimeout: unrefTimeout,
    clearTimeout: clearTimeout,
    setInterval: function () { return 0; },
    clearInterval: function () {},
  });
  const canvas = { addEventListener: function () {}, getContext: function () { return null; } };
  return { window: window, canvas: canvas };
}

test('a failed switch stops reporting the input it released', async function () {
  const harness = createCoreHarness();
  const viz = harness.window.BCViz.create(harness.canvas, { cycleOn: false });
  await viz.start();
  await sleep(SETTLE_MS);
  assert.equal(viz.currentDeviceId(), OS_DEFAULT_ID);

  await assert.rejects(viz.useDeviceById(SAVED_ID), function (error) { return error.name === 'NotFoundError'; });

  assert.equal(viz.diagnostics().trackState, 'none', 'the released input stays released');
  assert.equal(viz.currentDeviceId(), '', 'no device id is reported for a released input');
  assert.equal(viz.diagnostics().device, '', 'no device label is reported for a released input');
});

test('the next device after a failed switch starts from the first input', async function () {
  const harness = createCoreHarness();
  const viz = harness.window.BCViz.create(harness.canvas, { cycleOn: false });
  await viz.start();
  await sleep(SETTLE_MS);
  await assert.rejects(viz.useDeviceById(SAVED_ID));

  const device = await viz.nextDevice();

  assert.equal(device.deviceId, OS_DEFAULT_ID);
  assert.equal(viz.currentDeviceId(), OS_DEFAULT_ID);
  assert.equal(viz.diagnostics().trackState, 'live');
});
