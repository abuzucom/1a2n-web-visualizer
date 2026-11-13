/* Recovery regressions: a rebuilt visualizer releases the old instance and
 * reloads the experimental textures, a render failure escalates to a rebuild,
 * a late worklet module never leaves a running node, and a chunk that arrives
 * after its timeout becomes eligible again. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const test = require('node:test');
const vm = require('node:vm');

const SUPPORT_SCRIPTS = [
  'src/js/render-driver.js',
  'src/js/audible-keepalive.js',
  'src/js/audio-watchdog.js',
  'src/js/device-errors.js',
  'src/js/demo-audio.js',
];
const SETTLE_MS = 10;
const CHUNK_TIMEOUT_MS = 10000;

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

function FakeAudioContext() {
  this.currentTime = 0;
  this.sampleRate = 48000;
  this.state = 'running';
  this.destination = fakeNode();
  this.resume = async function () {};
  this.close = async function () {};
  this.createMediaStreamSource = function () { return fakeNode(); };
  this.createOscillator = function () { return fakeNode({ frequency: fakeParam(), detune: fakeParam() }); };
  this.createGain = function () { return fakeNode({ gain: fakeParam() }); };
}

function createMediaDevices() {
  const device = { kind: 'audioinput', deviceId: 'dev-a', label: 'Built-in Mic' };
  return {
    enumerateDevices: async function () { return [device]; },
    getUserMedia: async function () {
      const track = {
        kind: 'audio', label: device.label, readyState: 'live', muted: false,
        getSettings: function () { return { deviceId: device.deviceId }; },
        stop: function () { track.readyState = 'ended'; },
      };
      return { getTracks: function () { return [track]; }, getAudioTracks: function () { return [track]; } };
    },
  };
}

/** Each butterchurn instance records what the core asked of it. */
function createButterchurn(instances) {
  return {
    createVisualizer: function () {
      const instance = {
        renders: 0,
        renderFailures: 0,
        connects: [],
        disconnects: [],
        extraImages: [],
        loadPreset: function () {},
        render: function () {
          if (instance.renderFailures > 0) {
            instance.renderFailures -= 1;
            throw new Error('render failed');
          }
          instance.renders += 1;
        },
        connectAudio: function (node) { instance.connects.push(node); },
        disconnectAudio: function (node) { instance.disconnects.push(node); },
        loadExtraImages: function (images) { instance.extraImages.push(images); },
      };
      instances.push(instance);
      return instance;
    },
  };
}

/** Timers the test fires by hand, so a ten second chunk timeout runs at once. */
function createManualTimers() {
  const pending = [];
  return {
    pending: pending,
    setTimeout: function (callback, delay) {
      const timer = { callback: callback, delay: delay };
      pending.push(timer);
      return timer;
    },
    clearTimeout: function (timer) {
      const index = pending.indexOf(timer);
      if (index !== -1) pending.splice(index, 1);
    },
    fire: function (delay) {
      const due = pending.filter(function (timer) { return timer.delay === delay; });
      due.forEach(function (timer) {
        pending.splice(pending.indexOf(timer), 1);
        timer.callback();
      });
      return due.length;
    },
  };
}

function createWindow(instances, frames, extraIndex) {
  const window = {
    butterchurnPresets: { getPresets: function () { return { aaa: { baseVals: {} } }; } },
    BCExtraPresetIndex: extraIndex || { chunks: [], files: [] },
    devicePixelRatio: 1,
    innerWidth: 100,
    innerHeight: 50,
    addEventListener: function () {},
    requestAnimationFrame: function (callback) { frames.push(callback); return frames.length; },
    cancelAnimationFrame: function () {},
    requestIdleCallback: function (callback) { callback(); },
    setTimeout: unrefTimeout,
    clearTimeout: clearTimeout,
    setInterval: function () { return 0; },
    clearInterval: function () {},
    AudioContext: FakeAudioContext,
    butterchurn: createButterchurn(instances),
  };
  SUPPORT_SCRIPTS.forEach(function (path) {
    vm.runInNewContext(readSource(path), { window: window, console: console });
  });
  return window;
}

/** Capture the options the core hands the watchdog, so a test can play the
 * watchdog's part without waiting out its stall window. */
function spyOnWatchdog(window) {
  const captured = {};
  const realWatchdog = window.BCWatchdog;
  window.BCWatchdog = {
    selectInputDevice: realWatchdog.selectInputDevice,
    create: function (options) {
      captured.options = options;
      return realWatchdog.create(options);
    },
  };
  return captured;
}

function createCoreHarness(options) {
  const opts = options || {};
  const instances = [];
  const frames = [];
  const canvasHandlers = new Map();
  const imageParts = [];
  const window = createWindow(instances, frames, opts.extraIndex);
  const watchdog = spyOnWatchdog(window);
  const timers = opts.manualTimers ? createManualTimers() : null;
  // The texture wait shares the chunk timeout length. Without an idle
  // callback the texture prefetch waits on a timer the test never fires.
  if (timers) delete window.requestIdleCallback;
  const document = {
    visibilityState: 'visible',
    hidden: false,
    addEventListener: function () {},
    createElement: function () { return {}; },
    head: {
      appendChild: function (script) {
        if (script.src && script.src.indexOf('vendor/butterchurnExtraImagesExp-part-') === 0) {
          imageParts.push(script.src);
        }
      },
    },
  };
  vm.runInNewContext(readSource('src/js/visualizer-core.js'), {
    window: window,
    document: document,
    navigator: { mediaDevices: createMediaDevices() },
    console: console,
    setTimeout: timers ? timers.setTimeout : unrefTimeout,
    clearTimeout: timers ? timers.clearTimeout : clearTimeout,
    setInterval: function () { return 0; },
    clearInterval: function () {},
  });
  const canvas = {
    addEventListener: function (event, handler) { canvasHandlers.set(event, handler); },
    getContext: function () { return null; },
  };
  return {
    window: window,
    canvas: canvas,
    instances: instances,
    imageParts: imageParts,
    timers: timers,
    watchdog: watchdog,
    fireCanvas: function (event) {
      canvasHandlers.get(event)({ preventDefault: function () {} });
    },
    /** Run the frames queued now. Frames the run queues wait for the next call. */
    runQueuedFrames: function () {
      const queued = frames.splice(0, frames.length);
      queued.forEach(function (callback) { callback(); });
      return queued.length;
    },
  };
}

async function startViz(harness) {
  const viz = harness.window.BCViz.create(harness.canvas, { cycleOn: false });
  await viz.start();
  await sleep(SETTLE_MS);
  return viz;
}

test('a WebGL recovery disconnects the audio source from the old instance', async function () {
  const harness = createCoreHarness();
  await startViz(harness);
  const original = harness.instances[0];
  const source = original.connects[0];

  harness.fireCanvas('webglcontextlost');
  harness.fireCanvas('webglcontextrestored');

  assert.equal(harness.instances.length, 2, 'the recovery builds a new instance');
  assert.equal(original.disconnects.length, 1, 'the old instance releases its analyser chain');
  assert.equal(original.disconnects[0], source);
  assert.equal(harness.instances[1].connects[0], source, 'the new instance takes the same source');
});

test('a WebGL recovery reloads the experimental textures for the new instance', async function () {
  const harness = createCoreHarness();
  await startViz(harness);
  assert.equal(harness.imageParts.length, 1, 'startup requests the first texture part');
  harness.window.__bcExtraImagesExpPart(0, 1, { texture: { data: 'x' } });
  await sleep(SETTLE_MS);

  harness.fireCanvas('webglcontextlost');
  harness.fireCanvas('webglcontextrestored');
  await sleep(SETTLE_MS);

  assert.equal(harness.imageParts.length, 2, 'the rebuilt instance requests the texture parts again');
  harness.window.__bcExtraImagesExpPart(0, 1, { texture: { data: 'x' } });
  const rebuilt = harness.instances[1];
  assert.ok(rebuilt.extraImages.some(function (images) { return images && images.texture; }),
    'the rebuilt instance receives the experimental textures');
});

test('a watchdog restart after a render failure rebuilds the visualizer', async function () {
  const harness = createCoreHarness();
  await startViz(harness);
  const original = harness.instances[0];
  original.renderFailures = 1;
  harness.runQueuedFrames();
  harness.runQueuedFrames();
  assert.equal(original.renders, 0, 'a render failure stops rendering');

  harness.watchdog.options.restartDriver();
  harness.runQueuedFrames();

  assert.equal(harness.instances.length, 2, 'the restart escalates to a rebuild');
  assert.ok(harness.instances[1].renders > 0, 'the rebuilt instance renders frames');
});

test('a watchdog restart during a context loss does not rebuild the visualizer', async function () {
  const harness = createCoreHarness();
  await startViz(harness);

  harness.fireCanvas('webglcontextlost');
  harness.watchdog.options.restartDriver();

  assert.equal(harness.instances.length, 1, 'only a context restore rebuilds after a loss');
});

test('a chunk that arrives after its timeout becomes eligible again', async function () {
  const harness = createCoreHarness({
    manualTimers: true,
    extraIndex: { chunks: [['lazy']], files: ['chunk-000.js'] },
  });
  const viz = harness.window.BCViz.create(harness.canvas, { cycleOn: false });
  await viz.start();
  await sleep(SETTLE_MS);
  assert.equal(viz.currentName(), 'aaa');

  viz.goto(Array.from(viz.keys()).indexOf('lazy'));
  await sleep(SETTLE_MS);
  assert.equal(harness.timers.fire(CHUNK_TIMEOUT_MS), 1, 'the chunk timeout fires');
  await sleep(SETTLE_MS);
  harness.window.__bcPresetChunk(0, { lazy: { baseVals: {} } });

  viz.next();

  assert.equal(viz.currentName(), 'lazy', 'next reaches the late chunk preset');
});

/* A render driver whose worklet module load the test resolves by hand. */
function createDriverHarness() {
  let resolveModule = null;
  const nodes = [];
  const listeners = {};
  const document = {
    visibilityState: 'hidden',
    hidden: true,
    addEventListener: function (event, callback) { listeners[event] = callback; },
  };
  const window = {
    requestAnimationFrame: function () { return 1; },
    cancelAnimationFrame: function () {},
    setTimeout: function () { return 1; },
    clearTimeout: function () {},
    AudioWorkletNode: function () {
      const node = {
        connected: 0,
        disconnected: 0,
        port: { onmessage: null },
        connect: function () { node.connected += 1; },
        disconnect: function () { node.disconnected += 1; },
      };
      nodes.push(node);
      return node;
    },
  };
  vm.runInNewContext(readSource('src/js/render-driver.js'), { window: window, console: console });
  const context = {
    state: 'running',
    destination: {},
    audioWorklet: {
      addModule: function () {
        return new Promise(function (resolve) { resolveModule = resolve; });
      },
    },
  };
  const driver = window.BCRenderDriver.create({
    window: window,
    document: document,
    navigator: {},
    workletUrl: 'js/render-tick-processor.js',
    onTick: function () {},
  });
  return {
    driver: driver,
    context: context,
    nodes: nodes,
    resolveModule: function () { resolveModule(); },
  };
}

test('a worklet module that loads after stop leaves no connected node', async function () {
  const harness = createDriverHarness();
  harness.driver.start(harness.context);
  harness.driver.stop();

  harness.resolveModule();
  await sleep(SETTLE_MS);

  const live = harness.nodes.filter(function (node) { return node.connected > node.disconnected; });
  assert.equal(live.length, 0, 'no worklet node keeps running after stop');
});
