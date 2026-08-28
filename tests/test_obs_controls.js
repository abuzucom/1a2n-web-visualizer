const assert = require('node:assert/strict');
const fs = require('node:fs');
const test = require('node:test');
const vm = require('node:vm');

const SUPPORT_SCRIPTS = ['src/js/diagnostics.js', 'src/js/device-errors.js', 'src/js/audio-prefs.js'];
const ELEMENT_IDS = [
  'viz', 'panel', 'device', 'preset', 'presetFilter', 'status',
  'cycle', 'cycleSecs', 'audioGuard', 'startBtn', 'nextBtn', 'prevBtn', 'randBtn',
];

function sleep(ms) {
  return new Promise(function (resolve) { setTimeout(resolve, ms); });
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
    value: '',
    textContent: '',
    checked: false,
    children: [],
    listeners: {},
    classList: createClassList(),
    style: {},
    addEventListener: function (event, callback) {
      if (!element.listeners[event]) element.listeners[event] = [];
      element.listeners[event].push(callback);
    },
    appendChild: function (child) {
      if (child && child.isFragment) {
        child.children.forEach(function (grandchild) { element.children.push(grandchild); });
        return child;
      }
      element.children.push(child);
      return child;
    },
  };
  Object.defineProperty(element, 'innerHTML', {
    get: function () { return ''; },
    set: function () { element.children.length = 0; },
  });
  return element;
}

function createStorage() {
  const entries = {};
  return {
    entries: entries,
    getItem: function (key) {
      return Object.prototype.hasOwnProperty.call(entries, key) ? entries[key] : null;
    },
    setItem: function (key, value) { entries[key] = String(value); },
    removeItem: function (key) { delete entries[key]; },
  };
}

function createHarness(vizOverrides, options) {
  const opts = options || {};
  const elements = {};
  const documentListeners = {};
  ELEMENT_IDS.forEach(function (id) { elements[id] = createElement(id); });
  elements.cycleSecs.value = '20';
  elements.cycle.checked = true;
  const document = {
    body: { classList: createClassList(), appendChild: function () {} },
    createElement: function () { return createElement('created'); },
    createDocumentFragment: function () {
      const fragment = createElement('fragment');
      fragment.isFragment = true;
      return fragment;
    },
    getElementById: function (id) { return elements[id]; },
    addEventListener: function (event, callback) {
      if (!documentListeners[event]) documentListeners[event] = [];
      documentListeners[event].push(callback);
    },
  };
  const storage = opts.storage || createStorage();
  const window = {
    localStorage: storage,
    setTimeout: setTimeout,
    clearTimeout: clearTimeout,
    setInterval: function () { return 1; },
    clearInterval: function () {},
  };
  SUPPORT_SCRIPTS.forEach(function (path) {
    vm.runInNewContext(fs.readFileSync(path, 'utf8'), { window: window, console: console });
  });
  const state = { started: false, deviceId: 'dev-a', startCalls: [] };
  const devices = opts.devices || [
    { deviceId: 'dev-a', label: 'Built-in Mic' },
    { deviceId: 'dev-b', label: 'Voicemeeter Out B1' },
  ];
  const viz = Object.assign({
    keys: function () { return ['preset']; },
    currentIndex: function () { return 0; },
    diagnostics: function () { return { trackState: 'live' }; },
    isAudioGuardArmed: function () { return false; },
    setAudioGuard: function (armed) { return Boolean(armed); },
    isStarted: function () { return state.started; },
    isCycling: function () { return true; },
    toggleCycle: function () { return true; },
    setCycleSecs: function (seconds) { return seconds; },
    next: function () {}, prev: function () {}, random: function () {}, goto: function () {},
    listDevices: function () { return devices.slice(); },
    getDevices: function () { return Promise.resolve(devices.slice()); },
    currentDeviceId: function () { return state.deviceId; },
    start: function (deviceId) {
      state.startCalls.push(deviceId);
      state.started = true;
      if (deviceId) state.deviceId = deviceId;
      return Promise.resolve();
    },
    useDeviceById: function (deviceId) {
      state.deviceId = deviceId;
      return Promise.resolve(devices.find(function (d) { return d.deviceId === deviceId; }) || null);
    },
  }, vizOverrides || {});
  vm.runInNewContext(fs.readFileSync('src/js/obs-ui.js', 'utf8'), {
    window: window,
    document: document,
    navigator: { mediaDevices: {} },
    location: { search: '' },
    BCViz: { create: function () { return viz; } },
    setTimeout: setTimeout,
    clearTimeout: clearTimeout,
    console: console,
  });
  return {
    elements: elements,
    documentListeners: documentListeners,
    viz: viz,
    state: state,
    storage: storage,
    prefs: window.BCAudioPrefs,
    status: function () { return elements.status.textContent; },
    change: function (id, value) {
      elements[id].value = value;
      return Promise.all(elements[id].listeners.change.map(function (handler) { return handler(); }));
    },
    click: function (id) {
      return Promise.all(elements[id].listeners.click.map(function (handler) { return handler(); }));
    },
  };
}

/* The reported bug: picking an input the browser or the OS refuses left the
 * operator with a bare "NotAllowedError: Permission denied". */
test('a denied switch reports the permission hint and reverts the dropdown', async function () {
  const harness = createHarness({
    isStarted: function () { return true; },
    useDeviceById: function () {
      const error = new Error('Permission denied');
      error.name = 'NotAllowedError';
      return Promise.reject(error);
    },
  });

  await harness.change('device', 'dev-b');

  assert.match(harness.status(), /NotAllowedError: Permission denied/);
  assert.match(harness.status(), /URL source/);
  assert.equal(harness.elements.device.value, 'dev-a', 'the dropdown shows the input still connected');
});

test('a successful switch remembers the chosen input', async function () {
  const harness = createHarness({ isStarted: function () { return true; } });

  await harness.change('device', 'dev-b');

  const saved = harness.prefs.read();
  assert.equal(saved.deviceId, 'dev-b');
  assert.equal(saved.label, 'Voicemeeter Out B1');
});

/* useDeviceById resolves with null rather than rejecting when the id is gone,
 * so without an explicit check the dropdown silently does nothing. */
test('a device that is no longer present is reported, not ignored', async function () {
  const harness = createHarness({
    isStarted: function () { return true; },
    useDeviceById: function () { return Promise.resolve(null); },
  });

  await harness.change('device', 'dev-b');

  assert.match(harness.status(), /no longer/i);
});

test('start requests the remembered input', async function () {
  const storage = createStorage();
  storage.setItem('bcviz.audioInput.v1', JSON.stringify({ deviceId: 'dev-b', label: 'Voicemeeter Out B1' }));
  const harness = createHarness({}, { storage: storage });

  await harness.click('startBtn');

  assert.equal(harness.state.startCalls[0], 'dev-b');
});

/* A Voicemeeter restart hands the device back under a new id, so the saved id
 * misses and only the label can find it again. */
test('start falls back to the remembered label when the saved id is stale', async function () {
  const storage = createStorage();
  storage.setItem('bcviz.audioInput.v1', JSON.stringify({ deviceId: 'gone', label: 'Voicemeeter Out B1' }));
  const harness = createHarness({}, { storage: storage });

  await harness.click('startBtn');

  assert.equal(harness.state.startCalls[0], 'dev-b');
});

test('start with no saved input leaves the device to the operating system', async function () {
  const harness = createHarness();

  await harness.click('startBtn');

  assert.equal(harness.state.startCalls[0], undefined);
});

test('the device list re-selects whichever input is actually live', async function () {
  const harness = createHarness();
  harness.state.deviceId = 'dev-b';

  await harness.click('startBtn');

  assert.equal(harness.elements.device.value, 'dev-b');
});

test('a failure to start is described rather than reduced to its message', async function () {
  const error = new Error('Permission denied by system');
  error.name = 'NotAllowedError';
  const harness = createHarness({ start: function () { return Promise.reject(error); } });

  await harness.click('startBtn');

  assert.match(harness.status(), /NotAllowedError/);
  assert.match(harness.status(), /privacy settings/);
});

test('picking an input before Start says it takes effect on Start', async function () {
  const harness = createHarness({ isStarted: function () { return false; } });

  await harness.change('device', 'dev-b');
  await sleep(1);

  assert.match(harness.status(), /Start/);
});


/* Pre-permission enumeration reports every label blank, so the saved device
 * can only be matched by id on the first pass. The second pass, after the
 * stream opens and the labels arrive, is the only thing that recovers a device
 * whose id changed. This harness models that: blank labels until start. */
function createTwoPassHarness(vizOverrides) {
  const storage = createStorage();
  storage.setItem('bcviz.audioInput.v1', JSON.stringify({ deviceId: 'gone', label: 'Voicemeeter Out B1' }));
  const blank = [
    { deviceId: 'dev-a', label: '' },
    { deviceId: 'dev-b', label: '' },
  ];
  const labeled = [
    { deviceId: 'dev-a', label: 'Built-in Mic' },
    { deviceId: 'dev-b', label: 'Voicemeeter Out B1' },
  ];
  let granted = false;
  const overrides = Object.assign({
    listDevices: function () { return (granted ? labeled : blank).slice(); },
    start: function (deviceId) {
      granted = true;
      return Promise.resolve(deviceId);
    },
  }, vizOverrides || {});
  return createHarness(overrides, { storage: storage, devices: blank });
}

test('the second pass recovers a saved device whose id changed', async function () {
  const switched = [];
  const harness = createTwoPassHarness({
    useDeviceById: function (deviceId) {
      switched.push(deviceId);
      return Promise.resolve({ deviceId: deviceId, label: 'Voicemeeter Out B1' });
    },
  });

  await harness.click('startBtn');
  await sleep(1);

  assert.equal(harness.state.startCalls[0], undefined, 'a blank label matches nothing on the first pass');
  assert.deepEqual(switched, ['dev-b'], 'the second pass matched the saved label');
});

/* That second pass runs after viz.start() has already succeeded, so its
 * failure is not a failure to start. The visualizer is running on the default
 * input; reporting "Audio error" over it just prompts a pointless reload. */
test('a failed second-pass reselect still reaches the running state', async function () {
  const harness = createTwoPassHarness({
    useDeviceById: function () {
      const error = new Error('Could not start audio source');
      error.name = 'NotReadableError';
      return Promise.reject(error);
    },
  });

  await harness.click('startBtn');
  await sleep(1);

  assert.match(harness.status(), /Running/, 'status reports the running visualizer: ' + harness.status());
  assert.match(harness.status(), /NotReadableError/, 'and still names why the saved input was skipped');
  assert.match(harness.status(), /exclusively locked/);
});

test('a failed second-pass reselect still remembers the input actually connected', async function () {
  const harness = createTwoPassHarness({
    useDeviceById: function () {
      const error = new Error('Could not start audio source');
      error.name = 'NotReadableError';
      return Promise.reject(error);
    },
  });

  await harness.click('startBtn');
  await sleep(1);

  const saved = harness.prefs.read();
  assert.equal(saved.deviceId, 'dev-a', 'the remembered device is the one feeding the visualizer');
});
