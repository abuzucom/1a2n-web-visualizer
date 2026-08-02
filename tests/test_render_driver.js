const assert = require('node:assert/strict');
const fs = require('node:fs');
const test = require('node:test');
const vm = require('node:vm');

function loadScript(path, window) {
  const source = fs.readFileSync(path, 'utf8');
  vm.runInNewContext(source, { window: window, console: console });
}

/** Deferred promise, so tests can await the driver's async worklet setup. */
function flushMicrotasks() {
  return new Promise(function (resolve) { setImmediate(resolve); });
}

function createWorkletNode(context) {
  const node = {
    context: context,
    connected: [],
    disconnected: 0,
    port: { onmessage: null, close: function () { node.portClosed = true; } },
    portClosed: false,
    connect: function (target) { node.connected.push(target); },
    disconnect: function () { node.disconnected += 1; },
  };
  return node;
}

function createAudioContext(options) {
  const opts = options || {};
  const context = {
    state: 'running',
    destination: { id: 'destination' },
    nodes: [],
    addModuleCalls: [],
  };
  if (!opts.noWorklet) {
    context.audioWorklet = {
      addModule: function (url) {
        context.addModuleCalls.push(url);
        return opts.addModuleFails
          ? Promise.reject(new Error('addModule blocked'))
          : Promise.resolve();
      },
    };
  }
  return context;
}

function createHarness(options) {
  const opts = options || {};
  const rafCallbacks = [];
  const timeouts = [];
  const listeners = {};
  const ticks = [];
  const cancelledFrames = [];
  const clearedTimeouts = [];
  const wakeLocks = [];

  const document = {
    visibilityState: 'visible',
    hidden: false,
    addEventListener: function (event, callback) { listeners[event] = callback; },
  };
  const window = {
    requestAnimationFrame: function (callback) {
      rafCallbacks.push(callback);
      return rafCallbacks.length;
    },
    cancelAnimationFrame: function (handle) { cancelledFrames.push(handle); },
    setTimeout: function (callback, delay) {
      const timer = { callback: callback, delay: delay };
      timeouts.push(timer);
      return timer;
    },
    clearTimeout: function (timer) { clearedTimeouts.push(timer); },
  };
  const navigator = {};
  if (!opts.noWakeLock) {
    navigator.wakeLock = {
      request: function (type) {
        if (opts.wakeLockFails) return Promise.reject(new Error('not allowed'));
        const lock = { type: type, released: false, release: function () {
          lock.released = true;
          return Promise.resolve();
        } };
        wakeLocks.push(lock);
        return Promise.resolve(lock);
      },
    };
  }

  const AudioWorkletNode = function (context, name) {
    const node = createWorkletNode(context);
    node.name = name;
    context.nodes.push(node);
    return node;
  };
  window.AudioWorkletNode = AudioWorkletNode;

  loadScript('src/js/render-driver.js', window);
  const driver = window.BCRenderDriver.create({
    window: window,
    document: document,
    navigator: navigator,
    workletUrl: 'js/render-tick-processor.js',
    onTick: function () { ticks.push(Date.now()); },
  });

  return {
    driver: driver,
    document: document,
    window: window,
    tickCount: function () { return ticks.length; },
    runFrame: function () {
      const callback = rafCallbacks.shift();
      if (callback) callback();
      return Boolean(callback);
    },
    pendingFrames: function () { return rafCallbacks.length; },
    runTimeout: function () {
      const timer = timeouts.shift();
      if (timer) timer.callback();
      return Boolean(timer);
    },
    pendingTimeouts: function () { return timeouts.length; },
    clearedTimeouts: clearedTimeouts,
    cancelledFrames: cancelledFrames,
    wakeLocks: wakeLocks,
    setHidden: async function (hidden) {
      document.hidden = hidden;
      document.visibilityState = hidden ? 'hidden' : 'visible';
      listeners.visibilitychange();
      await flushMicrotasks();
    },
  };
}

test('driver renders through requestAnimationFrame while visible', async function () {
  const harness = createHarness();
  harness.driver.start(createAudioContext());
  await flushMicrotasks();

  assert.equal(harness.tickCount(), 0);
  harness.runFrame();
  assert.equal(harness.tickCount(), 1);
  harness.runFrame();
  assert.equal(harness.tickCount(), 2);
  assert.equal(harness.driver.stats().tickSource, 'raf');
  assert.equal(harness.pendingTimeouts(), 0, 'no timer fallback while visible');
});

test('driver switches to the audio worklet tick when hidden', async function () {
  const harness = createHarness();
  const context = createAudioContext();
  harness.driver.start(context);
  await flushMicrotasks();
  harness.runFrame();

  await harness.setHidden(true);
  assert.deepEqual(context.addModuleCalls, ['js/render-tick-processor.js']);
  assert.equal(context.nodes.length, 1);
  const node = context.nodes[0];
  assert.deepEqual(node.connected, [context.destination]);
  assert.equal(harness.driver.stats().tickSource, 'worklet');

  const before = harness.tickCount();
  node.port.onmessage({ data: 1 });
  node.port.onmessage({ data: 2 });
  assert.equal(harness.tickCount(), before + 2);
});

test('driver only requests the worklet module once across hide cycles', async function () {
  const harness = createHarness();
  const context = createAudioContext();
  harness.driver.start(context);
  await flushMicrotasks();

  await harness.setHidden(true);
  await harness.setHidden(false);
  await harness.setHidden(true);

  assert.equal(context.addModuleCalls.length, 1);
});

test('driver falls back to timers when the worklet module is unavailable', async function () {
  const harness = createHarness();
  harness.driver.start(createAudioContext({ addModuleFails: true }));
  await flushMicrotasks();

  await harness.setHidden(true);
  assert.equal(harness.driver.stats().tickSource, 'timeout');
  const before = harness.tickCount();
  harness.runTimeout();
  assert.equal(harness.tickCount(), before + 1, 'timer drives rendering');
});

test('driver falls back to timers when audioWorklet is missing entirely', async function () {
  const harness = createHarness();
  harness.driver.start(createAudioContext({ noWorklet: true }));
  await flushMicrotasks();

  await harness.setHidden(true);
  assert.equal(harness.driver.stats().tickSource, 'timeout');
  const before = harness.tickCount();
  harness.runTimeout();
  assert.equal(harness.tickCount(), before + 1);
});

test('driver runs exactly one tick source at a time', async function () {
  const harness = createHarness();
  const context = createAudioContext();
  harness.driver.start(context);
  await flushMicrotasks();
  harness.runFrame();

  await harness.setHidden(true);
  assert.equal(harness.cancelledFrames.length, 1, 'pending frame cancelled on hide');
  const node = context.nodes[0];
  node.port.onmessage({ data: 1 });
  const hiddenTicks = harness.tickCount();

  // A stale rAF callback queued before hiding must not double-render.
  harness.runFrame();
  assert.equal(harness.tickCount(), hiddenTicks, 'stale frame callback ignored');

  await harness.setHidden(false);
  assert.equal(harness.driver.stats().tickSource, 'raf');
  node.port.onmessage({ data: 2 });
  assert.equal(harness.tickCount(), hiddenTicks, 'worklet ignored once visible again');
  harness.runFrame();
  assert.equal(harness.tickCount(), hiddenTicks + 1);
});

test('driver stop tears down frames, timers, worklet node and wake lock', async function () {
  const harness = createHarness();
  const context = createAudioContext();
  harness.driver.start(context);
  await flushMicrotasks();
  await harness.setHidden(true);
  const node = context.nodes[0];

  harness.driver.stop();
  await flushMicrotasks();

  assert.equal(harness.driver.isRunning(), false);
  assert.equal(node.disconnected, 1);
  assert.equal(harness.wakeLocks[0].released, true);

  const before = harness.tickCount();
  node.port.onmessage({ data: 9 });
  harness.runFrame();
  harness.runTimeout();
  assert.equal(harness.tickCount(), before, 'no tick source survives stop');
});

test('driver acquires a screen wake lock and re-acquires it on return to visible', async function () {
  const harness = createHarness();
  harness.driver.start(createAudioContext());
  await flushMicrotasks();

  assert.equal(harness.wakeLocks.length, 1);
  assert.equal(harness.wakeLocks[0].type, 'screen');
  assert.equal(harness.driver.stats().wakeLock, true);

  // Chromium auto-releases the lock when the document hides and refuses a new
  // one until it is visible again, so the driver must re-request on return.
  await harness.setHidden(true);
  harness.wakeLocks[0].released = true;
  await harness.setHidden(false);
  assert.equal(harness.wakeLocks.length, 2);
});

test('driver renders normally when wake lock is unavailable or rejected', async function () {
  const missing = createHarness({ noWakeLock: true });
  missing.driver.start(createAudioContext());
  await flushMicrotasks();
  missing.runFrame();
  assert.equal(missing.tickCount(), 1);
  assert.equal(missing.driver.stats().wakeLock, false);

  const rejected = createHarness({ wakeLockFails: true });
  rejected.driver.start(createAudioContext());
  await flushMicrotasks();
  rejected.runFrame();
  assert.equal(rejected.tickCount(), 1);
  assert.equal(rejected.driver.stats().wakeLock, false);
});

test('driver stats report frames, hidden state and staleness', async function () {
  const harness = createHarness();
  harness.driver.start(createAudioContext());
  await flushMicrotasks();
  harness.runFrame();
  harness.runFrame();

  const stats = harness.driver.stats();
  assert.equal(stats.frames, 2);
  assert.equal(stats.hidden, false);
  assert.ok(stats.lastTickAt > 0);

  await harness.setHidden(true);
  assert.equal(harness.driver.stats().hidden, true);
});
