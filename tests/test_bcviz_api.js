const assert = require('node:assert/strict');
const fs = require('node:fs');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync('src/js/visualizer-core.js', 'utf8');

// visualizer-core.js reads these off `window`, exactly as the pages load them
// with their own <script defer> tags ahead of it.
const SUPPORT_SCRIPTS = [
  'src/js/render-driver.js',
  'src/js/audible-keepalive.js',
  'src/js/audio-watchdog.js',
  'src/js/device-errors.js',
  'src/js/demo-audio.js',
];

// Mimic the vendored bundle's equation compilation. Use a SPACE before
// "return a;" so unterminated final statements throw at load time.
function compileEquation(equationSource) {
  if (typeof equationSource !== 'string') return;
  new Function('a', ''.concat(equationSource, ' return a;'));
}

function compilePresetEquations(preset) {
  ['init_eqs_str', 'frame_eqs_str', 'pixel_eqs_str'].forEach(function (field) {
    compileEquation(preset[field]);
  });
  [preset.shapes, preset.waves].forEach(function (items) {
    (items || []).forEach(function (item) {
      ['init_eqs_str', 'frame_eqs_str', 'point_eqs_str'].forEach(function (field) {
        compileEquation(item[field]);
      });
    });
  });
}

/** Fakes navigator.mediaDevices, tracking how many open (unstopped) streams
 * exist per deviceId so a test can prove the code never attempts a second
 * concurrent getUserMedia against a device it already has open. Throws a
 * NotReadableError-shaped error in exactly that situation, matching the
 * real browser's behavior against an exclusive-mode WDM device. */
function createFakeMediaDevices(devices, options) {
  const opts = options || {};
  const list = devices || [{ kind: 'audioinput', deviceId: 'default', label: 'Voicemeeter Out B1' }];
  const openCounts = new Map();
  const calls = [];
  const enumerateCalls = [];
  function notReadable() {
    const err = new Error('Could not start audio source');
    err.name = 'NotReadableError';
    return err;
  }
  function makeTrack(device) {
    const track = {
      kind: 'audio', label: device.label, readyState: 'live', muted: false,
      getSettings: function () { return { deviceId: device.deviceId }; },
      stop: function () {
        if (track.readyState === 'ended') return;
        track.readyState = 'ended';
        openCounts.set(device.deviceId, Math.max(0, (openCounts.get(device.deviceId) || 0) - 1));
      },
    };
    return track;
  }
  return {
    calls: calls,
    enumerateCalls: enumerateCalls,
    openCountFor: function (deviceId) { return openCounts.get(deviceId) || 0; },
    enumerateDevices: async function () {
      enumerateCalls.push(true);
      return list.slice();
    },
    getUserMedia: async function (constraints) {
      const wanted = constraints && constraints.audio && constraints.audio.deviceId
        ? constraints.audio.deviceId.exact : (opts.defaultDeviceId || null);
      calls.push(wanted);
      const device = wanted ? list.find(function (d) { return d.deviceId === wanted; }) : list[0];
      if (!device) {
        const err = new Error('Requested device unavailable');
        err.name = 'OverconstrainedError';
        throw err;
      }
      if ((openCounts.get(device.deviceId) || 0) > 0) throw notReadable();
      openCounts.set(device.deviceId, 1);
      const track = makeTrack(device);
      return { getTracks: function () { return [track]; }, getAudioTracks: function () { return [track]; } };
    },
  };
}

function createHarness(presets, initialWebglErrors, deviceOpts) {
  const canvas = {};
  const schedule = function (callback, delay) {
    const timer = setTimeout(callback, delay);
    timer.unref();
    return timer;
  };
  const canvasHandlers = new Map();
  canvas.addEventListener = function (event, handler) { canvasHandlers.set(event, handler); };
  const webglErrors = (initialWebglErrors || []).slice();
  const webgl = {
    NO_ERROR: 0,
    LINK_STATUS: 0x8b82,
    getError: function () { return webglErrors.shift() || 0; },
    linkProgram: function () {},
    getProgramParameter: function (program) { return !(program && program.linkFails); },
    getProgramInfoLog: function () { return 'mock link error'; },
  };
  canvas.getContext = function () { return webgl; };
  const loadCalls = [];
  let chunkLoads = 0;
  let imagePartLoads = 0;
  let intervalCalls = 0;
  const frameCallbacks = new Map();
  let nextFrameHandle = 0;
  const trackedSetInterval = function (callback, delay) {
    intervalCalls += 1;
    const timer = setInterval(callback, delay);
    timer.unref();
    return timer;
  };
  const window = {
    BCExtraPresetIndex: { chunks: [['lazy']], files: ['chunk-000.js'] },
    butterchurnPresets: presets ? { getPresets: function () { return presets; } } : null,
    devicePixelRatio: 3,
    innerWidth: 100,
    innerHeight: 50,
    addEventListener: function () {},
    requestAnimationFrame: function (callback) {
      nextFrameHandle += 1;
      frameCallbacks.set(nextFrameHandle, callback);
      return nextFrameHandle;
    },
    // Real cancellation, so a cancelled frame cannot be run by a later test step.
    cancelAnimationFrame: function (handle) { frameCallbacks.delete(handle); },
    requestIdleCallback: function (callback) { callback(); },
    setTimeout: schedule,
    clearTimeout: clearTimeout,
    // Untracked on purpose: intervalCalls() must keep counting only the preset
    // cycle timer, not the watchdog's health sweep.
    setInterval: function (callback, delay) {
      const timer = setInterval(callback, delay);
      timer.unref();
      return timer;
    },
    clearInterval: clearInterval,
  };
  // Full enough for demo-audio.js to build its graph: connect() must return
  // its target so chains work, and every AudioParam needs its scheduling
  // methods, not just a value.
  const audioContexts = [];
  function fakeParam() {
    return {
      value: 0,
      setValueAtTime: function (v) { this.value = v; return this; },
      linearRampToValueAtTime: function () { return this; },
      exponentialRampToValueAtTime: function () { return this; },
      setTargetAtTime: function (v) { this.value = v; return this; },
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
    const context = this;
    audioContexts.push(context);
    this.currentTime = 0;
    this.sampleRate = 48000;
    this.state = 'running';
    this.destination = fakeNode({});
    this.resume = async function () {};
    this.close = async function () {};
    this.createMediaStreamSource = function () { return fakeNode({}); };
    this.createOscillator = function () {
      return fakeNode({ type: '', frequency: fakeParam(), detune: fakeParam() });
    };
    this.createGain = function () { return fakeNode({ gain: fakeParam() }); };
    this.createBiquadFilter = function () {
      return fakeNode({ type: '', frequency: fakeParam(), Q: fakeParam() });
    };
    this.createBufferSource = function () {
      return fakeNode({ buffer: null, loop: false, playbackRate: fakeParam() });
    };
    this.createBuffer = function (channels, length, rate) {
      return {
        numberOfChannels: channels, length: length, sampleRate: rate || context.sampleRate,
        getChannelData: function () { return new Float32Array(length); },
      };
    };
  };
  let renderCount = 0;
  const audioConnects = [];
  const audioDisconnects = [];
  window.butterchurn = {
    createVisualizer: function () {
      return {
        // Act like the real bundle. Compile equations and link shaders without
        // checking LINK_STATUS. The preset doubles as the program handle.
        loadPreset: function (preset) {
          compilePresetEquations(preset);
          webgl.linkProgram(preset);
          loadCalls.push(preset);
        },
        render: function () { renderCount += 1; },
        connectAudio: function (node) { audioConnects.push(node); },
        disconnectAudio: function (node) { audioDisconnects.push(node); },
      };
    },
  };
  const visibilityHandlers = [];
  const document = {
    visibilityState: 'visible',
    hidden: false,
    addEventListener: function (event, callback) {
      if (event === 'visibilitychange') visibilityHandlers.push(callback);
    },
    createElement: function () { return {}; },
    head: {
      appendChild: function (script) {
        if (script.src && script.src.indexOf('presets-extra/') === 0) chunkLoads += 1;
        if (script.src && script.src.indexOf('vendor/butterchurnExtraImagesExp-part-') === 0) imagePartLoads += 1;
      },
    },
  };
  SUPPORT_SCRIPTS.forEach(function (path) {
    vm.runInNewContext(fs.readFileSync(path, 'utf8'), { window: window, console: console });
  });
  const mediaDevices = (deviceOpts && deviceOpts.fakeMediaDevices)
    || createFakeMediaDevices(deviceOpts && deviceOpts.devices, deviceOpts);
  vm.runInNewContext(source, {
    window: window,
    document: document,
    navigator: { mediaDevices: mediaDevices },
    console: console,
    setTimeout: schedule,
    clearTimeout: clearTimeout,
    setInterval: trackedSetInterval,
    clearInterval: clearInterval,
  });
  return {
    canvas: canvas,
    window: window,
    mediaDevices: mediaDevices,
    loadCalls: loadCalls,
    audioConnects: audioConnects,
    audioDisconnects: audioDisconnects,
    audioContexts: audioContexts,
    fireCanvas: function (event) {
      const handler = canvasHandlers.get(event);
      if (!handler) throw new Error('no handler registered for ' + event);
      handler({ preventDefault: function () {} });
    },
    chunkLoads: function () { return chunkLoads; },
    imagePartLoads: function () { return imagePartLoads; },
    intervalCalls: function () { return intervalCalls; },
    renderCount: function () { return renderCount; },
    runFrame: function () {
      const next = frameCallbacks.keys().next();
      if (next.done) return false;
      const callback = frameCallbacks.get(next.value);
      frameCallbacks.delete(next.value);
      callback();
      return true;
    },
    setHidden: function (hidden) {
      document.hidden = hidden;
      document.visibilityState = hidden ? 'hidden' : 'visible';
      visibilityHandlers.forEach(function (handler) { handler(); });
    },
  };
}

function sleep(ms) {
  return new Promise(function (resolve) { setTimeout(resolve, ms); });
}

test('create exposes the controller API and caps canvas pixel ratio', function () {
  const harness = createHarness();
  const viz = harness.window.BCViz.create(harness.canvas, { cycleOn: false });

  assert.deepEqual(Array.from(viz.keys()), ['lazy']);
  assert.equal(harness.canvas.width, 200);
  assert.equal(harness.canvas.height, 100);
  assert.equal(viz.isCycling(), false);
  assert.equal(viz.currentName(), 'lazy');
});

test('registered lazy chunks retain their indexed preset names', function () {
  const harness = createHarness();
  const viz = harness.window.BCViz.create(harness.canvas, { cycleOn: false });

  harness.window.__bcPresetChunk(0, { lazy: { baseVals: {} } });

  assert.deepEqual(Array.from(viz.keys()), ['lazy']);
  assert.equal(viz.currentIndex(), 0);
});

test('startup selects a resident preset without loading a lazy chunk', async function () {
  const harness = createHarness({ vendor: { baseVals: {} } });
  const viz = harness.window.BCViz.create(harness.canvas, { cycleOn: false });

  await viz.start();

  assert.equal(viz.currentName(), 'vendor');
  assert.equal(harness.chunkLoads(), 0);
  assert.equal(harness.imagePartLoads(), 1);
});

test('accepts a valid equation without a trailing semicolon', async function () {
  const harness = createHarness({
    vendor: { baseVals: {}, frame_eqs_str: 'a = 1' },
  });
  const viz = harness.window.BCViz.create(harness.canvas, { cycleOn: false });

  await viz.start();

  assert.equal(viz.currentName(), 'vendor');
});

test('invalid equations are rejected and restore the last good preset', async function () {
  const bad = { baseVals: {}, frame_eqs_str: 'return )' };
  const harness = createHarness({
    bad: bad,
    good: { baseVals: {} },
  });
  const viz = harness.window.BCViz.create(harness.canvas, { cycleOn: false });

  await viz.start();
  viz.goto(0);

  assert.equal(harness.loadCalls.includes(bad), false);
  assert.equal(harness.loadCalls.length > 0, true);
  assert.equal(viz.currentName(), 'good');
});

test('does not reject a preset for queued WebGL errors', async function () {
  const harness = createHarness({
    bad: { baseVals: {} },
    good: { baseVals: {} },
  }, [0x502, 0x502, 0x501, 0]);
  const viz = harness.window.BCViz.create(harness.canvas, { cycleOn: false });

  await viz.start();

  assert.equal(viz.currentName(), 'bad');
  assert.equal(harness.loadCalls.length, 1);
});

test('normalizes unterminated equations before butterchurn compiles them', async function () {
  const harness = createHarness({
    vendor: { baseVals: {}, frame_eqs_str: 'a = 1' },
  });
  const viz = harness.window.BCViz.create(harness.canvas, { cycleOn: false });

  await viz.start();

  assert.equal(viz.currentName(), 'vendor');
  assert.equal(harness.loadCalls[0].frame_eqs_str, 'a = 1\n');
});

test('normalization is idempotent and preserves empty equation strings', async function () {
  const vendor = {
    baseVals: {},
    init_eqs_str: '',
    frame_eqs_str: 'a = 1',
    pixel_eqs_str: '',
    shapes: [{ baseVals: {}, init_eqs_str: 's = 1', frame_eqs_str: '' }],
    waves: [{ baseVals: {}, init_eqs_str: '', frame_eqs_str: 'w = 2', point_eqs_str: 'p = 3' }],
  };
  const harness = createHarness({ vendor: vendor });
  const viz = harness.window.BCViz.create(harness.canvas, { cycleOn: false });

  await viz.start();
  viz.goto(viz.currentIndex());

  assert.equal(vendor.frame_eqs_str, 'a = 1\n');
  assert.equal(vendor.init_eqs_str, '');
  assert.equal(vendor.pixel_eqs_str, '');
  assert.equal(vendor.shapes[0].init_eqs_str, 's = 1\n');
  assert.equal(vendor.shapes[0].frame_eqs_str, '');
  assert.equal(vendor.waves[0].init_eqs_str, '');
  assert.equal(vendor.waves[0].frame_eqs_str, 'w = 2\n');
  assert.equal(vendor.waves[0].point_eqs_str, 'p = 3\n');
});

test('rejects presets whose shaders fail to link and restores the last good preset', async function () {
  const aaa = { baseVals: {} };
  const broken = { baseVals: {}, linkFails: true };
  const harness = createHarness({ aaa: aaa, broken: broken });
  const viz = harness.window.BCViz.create(harness.canvas, { cycleOn: false });

  await viz.start();
  assert.equal(viz.currentName(), 'aaa');

  viz.goto(Array.from(viz.keys()).indexOf('broken'));

  assert.equal(viz.currentName(), 'aaa');
  assert.equal(harness.loadCalls[harness.loadCalls.length - 1], aaa);
  assert.equal(viz.excludedList().includes('broken'), true);
});

test('runtime-broken presets are added to the exportable excluded list', async function () {
  const harness = createHarness({
    bad: { baseVals: {}, frame_eqs_str: 'return )' },
    good: { baseVals: {} },
  });
  const viz = harness.window.BCViz.create(harness.canvas, { cycleOn: false });

  await viz.start();
  viz.goto(0);

  assert.equal(viz.excludedList().includes('bad'), true);
});

test('favoriting the current preset returns and records its name', async function () {
  const harness = createHarness({ aaa: { baseVals: {} }, bbb: { baseVals: {} } });
  const viz = harness.window.BCViz.create(harness.canvas, { cycleOn: false });

  await viz.start();
  const name = viz.favoriteCurrentPreset();

  assert.equal(name, viz.currentName());
  assert.equal(viz.favoritesList().includes(name), true);
});

test('favoriting the same preset twice does not duplicate it', async function () {
  const harness = createHarness({ aaa: { baseVals: {} } });
  const viz = harness.window.BCViz.create(harness.canvas, { cycleOn: false });

  await viz.start();
  viz.favoriteCurrentPreset();
  viz.favoriteCurrentPreset();

  assert.equal(viz.favoritesList().length, 1);
});

test('favoriting the current preset never advances playback or restarts the cycle timer', async function () {
  const harness = createHarness({ aaa: { baseVals: {} }, bbb: { baseVals: {} } });
  const viz = harness.window.BCViz.create(harness.canvas, { cycleOn: true, cycleSecs: 5 });

  await viz.start();
  const indexBefore = viz.currentIndex();
  const loadCallsBefore = harness.loadCalls.length;
  const cycleSecsBefore = viz.getCycleSecs();
  const intervalCallsBefore = harness.intervalCalls();

  viz.favoriteCurrentPreset();

  assert.equal(viz.currentIndex(), indexBefore);
  assert.equal(harness.loadCalls.length, loadCallsBefore);
  assert.equal(viz.getCycleSecs(), cycleSecsBefore);
  assert.equal(harness.intervalCalls(), intervalCallsBefore);
});

test('rendering keeps running after the page is hidden', async function () {
  const harness = createHarness({ aaa: { baseVals: {} } });
  const viz = harness.window.BCViz.create(harness.canvas, { cycleOn: false });

  await viz.start();
  harness.runFrame();
  assert.ok(harness.renderCount() > 0, 'renders through requestAnimationFrame while visible');
  assert.equal(viz.diagnostics().tickSource, 'raf');

  harness.setHidden(true);
  await sleep(10);
  const hiddenBaseline = harness.renderCount();
  assert.equal(viz.diagnostics().hidden, true);
  assert.equal(viz.diagnostics().tickSource, 'timeout', 'no AudioWorklet here, so timers carry it');

  // The whole point: frames keep being produced with no rAF in sight.
  await sleep(80);
  assert.ok(harness.renderCount() > hiddenBaseline, 'frames continue while hidden');

  harness.setHidden(false);
  const visibleBaseline = harness.renderCount();
  harness.runFrame();
  assert.ok(harness.renderCount() > visibleBaseline, 'requestAnimationFrame takes back over');
});

test('a visibility round trip leaks no cycle timers', async function () {
  const harness = createHarness({ aaa: { baseVals: {} }, bbb: { baseVals: {} } });
  const viz = harness.window.BCViz.create(harness.canvas, { cycleOn: true, cycleSecs: 5 });

  await viz.start();
  const intervalCallsBefore = harness.intervalCalls();

  harness.setHidden(true);
  await sleep(20);
  harness.setHidden(false);

  assert.equal(harness.intervalCalls(), intervalCallsBefore, 'no duplicate cycle timer');
  assert.equal(viz.isCycling(), true);
});

test('the audio guard is disarmed until it is explicitly armed', async function () {
  const harness = createHarness({ aaa: { baseVals: {} } });
  const viz = harness.window.BCViz.create(harness.canvas, { cycleOn: false });

  await viz.start();
  assert.equal(viz.isAudioGuardArmed(), false);
  assert.equal(viz.diagnostics().armed, false);

  assert.equal(viz.toggleAudioGuard(), true);
  assert.equal(viz.diagnostics().armed, true);
  assert.equal(viz.toggleAudioGuard(), false);
});

test('diagnostics report the live input and suppressed keepalive', async function () {
  const harness = createHarness({ aaa: { baseVals: {} } });
  const viz = harness.window.BCViz.create(harness.canvas, { cycleOn: false });

  await viz.start();
  // start() resolves before connectInitialStream has finished opening the
  // stream, so let that settle before reading the input back.
  await sleep(5);
  const stats = viz.diagnostics();

  assert.equal(stats.device, 'Voicemeeter Out B1');
  assert.equal(stats.trackState, 'live');
  // A Voicemeeter input is a loopback, so the keepalive must stay quiet rather
  // than feed its own tone back into the analysis graph.
  assert.match(stats.keepalive, /suppressed: loopback/);
});

/* Some virtual/pro-audio WDM devices (e.g. Voicemeeter's outputs registered
 * as Windows recording devices, with exclusive-mode control enabled) allow
 * only one open client stream at a time. Cycling to the device already in
 * use, which is guaranteed whenever there is only one input device, must
 * never attempt a second concurrent open against it. */
test('cycling to the only device is a no-op, not a conflicting reopen', async function () {
  const harness = createHarness({ aaa: { baseVals: {} } });
  const viz = harness.window.BCViz.create(harness.canvas, { cycleOn: false });

  await viz.start();
  await sleep(5);
  const openCallsBefore = harness.mediaDevices.calls.length;

  await viz.nextDevice();

  assert.equal(harness.mediaDevices.calls.length, openCallsBefore,
    'no second getUserMedia call is made for the device already open');
  assert.equal(viz.diagnostics().trackState, 'live');
});

test('switching to a genuinely different device connects cleanly', async function () {
  const devices = [
    { kind: 'audioinput', deviceId: 'dev-a', label: 'Voicemeeter Out B1' },
    { kind: 'audioinput', deviceId: 'dev-b', label: 'Physical Mic' },
  ];
  const harness = createHarness({ aaa: { baseVals: {} } }, undefined, { devices: devices });
  const viz = harness.window.BCViz.create(harness.canvas, { cycleOn: false });

  await viz.start();
  await sleep(5);
  assert.equal(viz.currentDeviceId(), 'dev-a');

  await viz.useDeviceById('dev-b');

  assert.equal(viz.currentDeviceId(), 'dev-b');
  assert.equal(viz.diagnostics().device, 'Physical Mic');
  assert.equal(viz.diagnostics().trackState, 'live');
});

/* A Windows exclusive-mode WDM driver can be slow to actually free a handle
 * after track.stop(); one bounded retry absorbs that. Only NotReadableError
 * qualifies. */
test('a NotReadableError on switch retries once and recovers', async function () {
  const deviceA = { kind: 'audioinput', deviceId: 'dev-a', label: 'Voicemeeter Out B1' };
  const deviceB = { kind: 'audioinput', deviceId: 'dev-b', label: 'Physical Mic' };
  const openCounts = new Map();
  let deviceBAttempts = 0;
  function makeTrack(device) {
    const track = {
      kind: 'audio', label: device.label, readyState: 'live', muted: false,
      getSettings: function () { return { deviceId: device.deviceId }; },
      stop: function () {
        if (track.readyState === 'ended') return;
        track.readyState = 'ended';
        openCounts.set(device.deviceId, Math.max(0, (openCounts.get(device.deviceId) || 0) - 1));
      },
    };
    return track;
  }
  const fakeMediaDevices = {
    enumerateDevices: async function () { return [deviceA, deviceB]; },
    getUserMedia: async function (constraints) {
      const wanted = constraints.audio.deviceId ? constraints.audio.deviceId.exact : deviceA.deviceId;
      const device = wanted === deviceB.deviceId ? deviceB : deviceA;
      if (device.deviceId === deviceB.deviceId) {
        deviceBAttempts += 1;
        if (deviceBAttempts === 1) {
          const err = new Error('Could not start audio source');
          err.name = 'NotReadableError';
          throw err;
        }
      }
      if ((openCounts.get(device.deviceId) || 0) > 0) throw new Error('unexpected concurrent open in test fake');
      openCounts.set(device.deviceId, 1);
      const track = makeTrack(device);
      return { getTracks: function () { return [track]; }, getAudioTracks: function () { return [track]; } };
    },
  };
  const harness = createHarness({ aaa: { baseVals: {} } }, undefined, { fakeMediaDevices: fakeMediaDevices });
  const viz = harness.window.BCViz.create(harness.canvas, { cycleOn: false });

  await viz.start();
  await sleep(5);

  // The retry delay is scheduled on an unref'd timer (so a leaked one can
  // never keep a real page alive), so this test needs its own real-time wait
  // to give that timer a chance to fire before asserting on it.
  const switchPromise = viz.useDeviceById('dev-b');
  await sleep(300);
  await switchPromise;

  assert.equal(deviceBAttempts, 2, 'the NotReadableError was retried exactly once');
  assert.equal(viz.currentDeviceId(), 'dev-b');
  assert.equal(viz.diagnostics().trackState, 'live');
});

test('a non-retryable device error on switch rejects immediately without retrying', async function () {
  const deviceA = { kind: 'audioinput', deviceId: 'dev-a', label: 'Voicemeeter Out B1' };
  const deviceB = { kind: 'audioinput', deviceId: 'dev-b', label: 'Physical Mic' };
  let deviceBCalls = 0;
  function makeTrack(device) {
    const track = {
      kind: 'audio', label: device.label, readyState: 'live', muted: false,
      getSettings: function () { return { deviceId: device.deviceId }; },
      stop: function () { track.readyState = 'ended'; },
    };
    return track;
  }
  const fakeMediaDevices = {
    enumerateDevices: async function () { return [deviceA, deviceB]; },
    getUserMedia: async function (constraints) {
      const wanted = constraints.audio.deviceId ? constraints.audio.deviceId.exact : deviceA.deviceId;
      if (wanted === deviceB.deviceId) {
        deviceBCalls += 1;
        const err = new Error('Requested device unavailable');
        err.name = 'NotFoundError';
        throw err;
      }
      return { getTracks: function () { return [makeTrack(deviceA)]; },
        getAudioTracks: function () { return [makeTrack(deviceA)]; } };
    },
  };
  const harness = createHarness({ aaa: { baseVals: {} } }, undefined, { fakeMediaDevices: fakeMediaDevices });
  const viz = harness.window.BCViz.create(harness.canvas, { cycleOn: false });

  await viz.start();
  await sleep(5);

  await assert.rejects(viz.useDeviceById('dev-b'), function (error) { return error.name === 'NotFoundError'; });

  assert.equal(deviceBCalls, 1, 'no retry attempted for a non-NotReadableError failure');
  // The old stream was already released before the failed switch, so the
  // visualizer is honestly silent rather than misreporting the old device as
  // still connected.
  assert.equal(viz.diagnostics().trackState, 'none');
});

/* Every getUserMedia failure at startup used to collapse into one generic
 * toast, so a permission denial looked exactly like an unplugged cable. The
 * visualizer still keeps running; it just says which failure it hit. */
test('a permission denial at start names the error instead of a generic message', async function () {
  const toasts = [];
  const fakeMediaDevices = {
    enumerateDevices: async function () { return []; },
    getUserMedia: async function () {
      const err = new Error('Permission denied');
      err.name = 'NotAllowedError';
      throw err;
    },
  };
  const harness = createHarness({ aaa: { baseVals: {} } }, undefined, { fakeMediaDevices: fakeMediaDevices });
  const viz = harness.window.BCViz.create(harness.canvas, {
    cycleOn: false,
    onToast: function (message) { toasts.push(message); },
  });

  await viz.start();
  await sleep(5);

  const reported = toasts.find(function (message) { return message.indexOf('NotAllowedError') >= 0; });
  assert.ok(reported, 'the toast names the error: ' + JSON.stringify(toasts));
  assert.match(reported, /URL source/);
  assert.equal(viz.isStarted(), true, 'the visualizer keeps running without an input');
});

test('deviceIdx syncs to whichever device the initial default connect resolved to', async function () {
  const deviceA = { kind: 'audioinput', deviceId: 'dev-a', label: 'Built-in Mic' };
  const deviceB = { kind: 'audioinput', deviceId: 'dev-b', label: 'Voicemeeter Out B1' };
  const fakeMediaDevices = createFakeMediaDevices([deviceA, deviceB], { defaultDeviceId: 'dev-b' });
  const harness = createHarness({ aaa: { baseVals: {} } }, undefined, { fakeMediaDevices: fakeMediaDevices });
  const viz = harness.window.BCViz.create(harness.canvas, { cycleOn: false });

  await viz.start();
  await sleep(5);

  // The unconstrained startup connect resolved to deviceB (index 1), not the
  // first enumerated device; deviceIdx must reflect the device that actually
  // connected, not stay at its initial 0.
  assert.equal(viz.currentDeviceId(), 'dev-b');
});

test('demo mode never touches the microphone or the device list', async function () {
  const harness = createHarness({ vendor: { baseVals: {} } });
  const viz = harness.window.BCViz.create(harness.canvas, { demo: true, cycleOn: false });
  await viz.start();
  await sleep(5);

  assert.equal(viz.isStarted(), true);
  assert.equal(viz.isDemo(), true);
  assert.equal(harness.mediaDevices.calls.length, 0, 'getUserMedia must never be reached');
  assert.equal(harness.mediaDevices.enumerateCalls.length, 0, 'enumerateDevices must never be reached');
});

test('demo mode feeds the visualizer the synthetic node', async function () {
  const harness = createHarness({ vendor: { baseVals: {} } });
  const viz = harness.window.BCViz.create(harness.canvas, { demo: true, cycleOn: false });
  await viz.start();
  await sleep(5);

  assert.equal(harness.audioConnects.length, 1, 'exactly one source is connected');
  const connected = harness.audioConnects[0];
  assert.ok(connected && connected.gain, 'the synthetic source is the demo master gain');
});

test('demo mode reports itself in the diagnostics', async function () {
  const harness = createHarness({ vendor: { baseVals: {} } });
  const viz = harness.window.BCViz.create(harness.canvas, { demo: true, cycleOn: false });
  await viz.start();
  await sleep(5);
  const stats = viz.diagnostics();

  assert.equal(stats.device, 'Synthetic demo track');
  assert.equal(stats.trackState, 'synthetic');
  assert.match(stats.demo, /trance 140 BPM/);
  // The keepalive must engage: demo mode has no capture path, so its tone
  // cannot feed back, and without it a hidden demo tab gets throttled.
  assert.equal(stats.keepalive, 'active');
  assert.equal(stats.audioLost, false, 'a page with no stream has no input to lose');
});

test('demo mode keeps the device API inert even with the guard armed', async function () {
  const harness = createHarness({ vendor: { baseVals: {} } });
  const viz = harness.window.BCViz.create(harness.canvas, { demo: true, cycleOn: false });
  await viz.start();
  await sleep(5);
  viz.setAudioGuard(true);

  assert.equal(await viz.nextDevice(), null);
  // Length, not deepEqual: the array comes from the vm realm, so it has a
  // different Array.prototype and would fail a strict structural compare.
  assert.equal((await viz.getDevices()).length, 0);
  assert.equal(await viz.useDeviceById('default'), null);
  assert.equal(viz.currentDeviceId(), '');
  assert.equal(harness.mediaDevices.calls.length, 0, 'an armed guard must not reconnect to a device');
  assert.equal(harness.mediaDevices.enumerateCalls.length, 0);
});

test('the demo API is a safe no-op when demo mode is off', async function () {
  const harness = createHarness({ vendor: { baseVals: {} } });
  const viz = harness.window.BCViz.create(harness.canvas, { cycleOn: false });
  await viz.start();
  await sleep(5);

  assert.equal(viz.isDemo(), false);
  assert.equal(viz.getDemoTempo(), 0);
  assert.equal(viz.setDemoTempo(140), 0);
  assert.equal(viz.cycleDemoTempo(), 0);
  assert.equal(viz.getDemoIntensity(), 0);
  assert.equal(viz.setDemoIntensity(0.5), 0);
  assert.equal(viz.diagnostics().demo, '');
});

test('the demo tempo and intensity API clamps and cycles genres', async function () {
  const harness = createHarness({ vendor: { baseVals: {} } });
  const viz = harness.window.BCViz.create(harness.canvas, { demo: true, cycleOn: false });
  await viz.start();
  await sleep(5);
  const limits = harness.window.BCDemoAudio;

  assert.equal(viz.getDemoTempo(), limits.DEFAULT_BPM);
  assert.equal(viz.cycleDemoTempo(), 87);
  assert.match(viz.diagnostics().demo, /house 87 BPM/);
  assert.equal(viz.cycleDemoTempo(), 174);
  assert.match(viz.diagnostics().demo, /liquid 174 BPM/);
  assert.equal(viz.cycleDemoTempo(), limits.DEFAULT_BPM);
  assert.equal(viz.setDemoTempo(99999), limits.MAX_BPM);
  assert.equal(viz.setDemoIntensity(9), limits.MAX_INTENSITY);
  assert.equal(viz.setDemoIntensity(-9), limits.MIN_INTENSITY);
});

test('a missing demo module leaves the visualizer running', async function () {
  const harness = createHarness({ vendor: { baseVals: {} } });
  const toasts = [];
  delete harness.window.BCDemoAudio;
  const viz = harness.window.BCViz.create(harness.canvas, {
    demo: true, cycleOn: false, onToast: function (message) { toasts.push(message); },
  });
  await viz.start();
  await sleep(5);

  assert.equal(viz.isStarted(), true);
  assert.ok(toasts.some(function (m) { return /Demo audio unavailable/.test(m); }));
  assert.equal(harness.mediaDevices.calls.length, 0, 'a demo failure must not fall back to the microphone');
});

test('a WebGL recovery reconnects the audio source', async function () {
  const harness = createHarness({ vendor: { baseVals: {} } });
  const viz = harness.window.BCViz.create(harness.canvas, { cycleOn: false });
  await viz.start();
  await sleep(5);
  assert.equal(harness.audioConnects.length, 1);
  const original = harness.audioConnects[0];

  harness.fireCanvas('webglcontextlost');
  harness.fireCanvas('webglcontextrestored');

  assert.equal(harness.audioConnects.length, 2, 'the rebuilt visualizer must be reconnected');
  assert.equal(harness.audioConnects[1], original, 'the same source node is reattached');
});

test('a WebGL recovery reconnects the synthetic source too', async function () {
  const harness = createHarness({ vendor: { baseVals: {} } });
  const viz = harness.window.BCViz.create(harness.canvas, { demo: true, cycleOn: false });
  await viz.start();
  await sleep(5);
  const original = harness.audioConnects[0];

  harness.fireCanvas('webglcontextlost');
  harness.fireCanvas('webglcontextrestored');

  assert.equal(harness.audioConnects.length, 2);
  assert.equal(harness.audioConnects[1], original);
  assert.equal(harness.mediaDevices.calls.length, 0);
});

/* connectInitialStream is awaited, so the input is connected before
 * `started` is set and a later failure in startAudio runs its catch with a
 * live capture stream. That catch closed the AudioContext but left the stream
 * open and `prepared` true, which held the microphone and left prepareAudio
 * short-circuiting onto a null context, so every retry died. */
test('a start that fails after the input connects releases it and can be retried', async function () {
  const harness = createHarness({ aaa: { baseVals: {} } });
  const realDriver = harness.window.BCRenderDriver;
  let failNextStart = true;
  harness.window.BCRenderDriver = {
    create: function (options) {
      const driver = realDriver.create(options);
      const start = driver.start;
      driver.start = function (context) {
        if (failNextStart) {
          failNextStart = false;
          throw new Error('render driver failed to start');
        }
        return start.call(driver, context);
      };
      return driver;
    },
  };
  const viz = harness.window.BCViz.create(harness.canvas, { cycleOn: false });

  await assert.rejects(function () { return viz.start(); }, /render driver failed to start/);

  assert.equal(viz.isStarted(), false);
  assert.equal(harness.mediaDevices.openCountFor('default'), 0,
    'the failed start does not keep the capture device open');

  await viz.start();

  assert.equal(viz.isStarted(), true, 'a retry after a failed start still works');
});
