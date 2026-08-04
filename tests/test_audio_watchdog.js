const assert = require('node:assert/strict');
const fs = require('node:fs');
const test = require('node:test');
const vm = require('node:vm');

function loadScript(path, window) {
  const source = fs.readFileSync(path, 'utf8');
  vm.runInNewContext(source, { window: window, console: console });
}

function flushMicrotasks() {
  return new Promise(function (resolve) { setImmediate(resolve); });
}

function createTrack(overrides) {
  const track = {
    readyState: 'live',
    muted: false,
    listeners: {},
    addEventListener: function (event, callback) { track.listeners[event] = callback; },
    stop: function () { track.readyState = 'ended'; },
  };
  return Object.assign(track, overrides || {});
}

function createHarness(options) {
  const opts = options || {};
  const calls = {
    restartDriver: 0,
    recoverVisualizer: 0,
    resume: 0,
    listDevices: 0,
    reconnect: [],
    toasts: [],
  };
  let clock = 1000;
  let intervalCallback = null;

  const audioCtx = { state: opts.contextState || 'running', resume: function () {
    calls.resume += 1;
    return opts.resumeFails ? Promise.reject(new Error('nope')) : Promise.resolve();
  } };
  const driverStats = { lastTickAt: clock, tickSource: 'raf', frames: 10 };
  let track = opts.track === undefined ? createTrack() : opts.track;

  const window = {
    setInterval: function (callback) { intervalCallback = callback; return { id: 1 }; },
    clearInterval: function () { intervalCallback = null; },
  };
  loadScript('src/js/audio-watchdog.js', window);

  const watchdog = window.BCWatchdog.create({
    window: window,
    now: function () { return clock; },
    graceMs: 20000,
    stallMs: 5000,
    getDriverStats: function () { return driverStats; },
    restartDriver: function () { calls.restartDriver += 1; driverStats.lastTickAt = clock; },
    recoverVisualizer: function () { calls.recoverVisualizer += 1; },
    getAudioContext: function () { return audioCtx; },
    getTrack: function () { return track; },
    getDeviceId: function () { return opts.deviceId || 'device-old'; },
    getDeviceLabel: function () { return opts.deviceLabel || 'Voicemeeter Out B1'; },
    listDevices: function () {
      calls.listDevices += 1;
      return Promise.resolve(opts.devices || []);
    },
    reconnect: function (deviceId) {
      calls.reconnect.push(deviceId);
      return opts.reconnectFails ? Promise.reject(new Error('busy')) : Promise.resolve();
    },
    onToast: function (message) { calls.toasts.push(message); },
  });

  return {
    watchdog: watchdog,
    calls: calls,
    audioCtx: audioCtx,
    driverStats: driverStats,
    window: window,
    setTrack: function (next) { track = next; },
    getTrack: function () { return track; },
    advance: function (ms) { clock += ms; },
    now: function () { return clock; },
    tick: async function () {
      if (intervalCallback) intervalCallback();
      await flushMicrotasks();
    },
  };
}

test('watchdog restarts a stalled render loop once, then backs off', async function () {
  const harness = createHarness();
  harness.watchdog.start();

  harness.advance(1000);
  await harness.tick();
  assert.equal(harness.calls.restartDriver, 0, 'a fresh tick is not a stall');

  harness.driverStats.lastTickAt = harness.now() - 9000;
  await harness.tick();
  assert.equal(harness.calls.restartDriver, 1);

  // Restart set lastTickAt, so the next sweep sees a healthy loop.
  await harness.tick();
  assert.equal(harness.calls.restartDriver, 1);

  // A stall that persists past the backoff window escalates rather than
  // hammering restart every sweep.
  harness.advance(1000);
  harness.driverStats.lastTickAt = harness.now() - 9000;
  await harness.tick();
  assert.equal(harness.calls.restartDriver, 1, 'backoff suppresses an immediate second restart');

  harness.advance(30000);
  harness.driverStats.lastTickAt = harness.now() - 9000;
  await harness.tick();
  assert.equal(harness.calls.restartDriver, 2);
});

test('watchdog escalates to visualizer recovery when restarts do not take', async function () {
  const harness = createHarness();
  harness.watchdog.start();

  for (let attempt = 0; attempt < 6; attempt += 1) {
    harness.advance(60000);
    harness.driverStats.lastTickAt = harness.now() - 9000;
    await harness.tick();
    harness.driverStats.lastTickAt = harness.now() - 9000;
  }

  assert.ok(harness.calls.restartDriver >= 2);
  assert.ok(harness.calls.recoverVisualizer >= 1, 'repeated failure escalates');
});

test('watchdog stall and context recovery run while disarmed', async function () {
  const harness = createHarness({ contextState: 'suspended' });
  harness.watchdog.start();
  assert.equal(harness.watchdog.isArmed(), false, 'disarmed by default');

  harness.advance(1000);
  harness.driverStats.lastTickAt = harness.now() - 9000;
  await harness.tick();

  assert.equal(harness.calls.restartDriver, 1);
  assert.equal(harness.calls.resume, 1);
});

test('watchdog tolerates a rejected context resume', async function () {
  const harness = createHarness({ contextState: 'suspended', resumeFails: true });
  harness.watchdog.start();

  await harness.tick();
  await harness.tick();

  assert.equal(harness.calls.resume, 2, 'a failed resume does not stop the sweep');
});

test('watchdog does not touch the input while disarmed', async function () {
  const harness = createHarness({ devices: [{ deviceId: 'device-new', label: 'Voicemeeter Out B1' }] });
  harness.watchdog.start();

  harness.getTrack().readyState = 'ended';
  harness.advance(60000);
  await harness.tick();

  assert.equal(harness.calls.listDevices, 0);
  assert.deepEqual(harness.calls.reconnect, []);
  assert.equal(harness.watchdog.stats().audioLost, true, 'loss is still reported');
  assert.equal(harness.calls.toasts.length, 1, 'operator is told once');

  await harness.tick();
  assert.equal(harness.calls.toasts.length, 1, 'and not told again every sweep');
});

test('watchdog waits out the grace window before reconnecting', async function () {
  const harness = createHarness({ devices: [{ deviceId: 'device-new', label: 'Voicemeeter Out B1' }] });
  harness.watchdog.start();
  harness.watchdog.setArmed(true);

  harness.getTrack().readyState = 'ended';
  await harness.tick();
  assert.deepEqual(harness.calls.reconnect, [], 'no immediate reconnect');

  harness.advance(19000);
  await harness.tick();
  assert.deepEqual(harness.calls.reconnect, [], 'still inside the grace window');
  assert.ok(harness.watchdog.stats().recoverInSecs > 0);

  harness.advance(2000);
  await harness.tick();
  assert.deepEqual(harness.calls.reconnect, ['device-new']);
  assert.equal(harness.watchdog.stats().recoveries, 1);
});

test('watchdog cancels the countdown when the input comes back inside the window', async function () {
  const harness = createHarness({ devices: [{ deviceId: 'device-new', label: 'Voicemeeter Out B1' }] });
  harness.watchdog.start();
  harness.watchdog.setArmed(true);

  harness.getTrack().readyState = 'ended';
  await harness.tick();
  harness.advance(10000);
  await harness.tick();
  assert.ok(harness.watchdog.stats().recoverInSecs > 0);

  harness.setTrack(createTrack());
  await harness.tick();
  assert.equal(harness.watchdog.stats().audioLost, false);

  harness.advance(60000);
  await harness.tick();
  assert.deepEqual(harness.calls.reconnect, [], 'a flap never swaps the device');
});

test('watchdog never reacts to silence on a live track', async function () {
  const harness = createHarness({ devices: [{ deviceId: 'device-new', label: 'Voicemeeter Out B1' }] });
  harness.watchdog.start();
  harness.watchdog.setArmed(true);

  // Intentional dead air during a DJ set: the track stays live and unmuted, it
  // just carries no signal. Nothing about that is a fault.
  for (let sweep = 0; sweep < 60; sweep += 1) {
    harness.advance(2000);
    await harness.tick();
  }

  assert.equal(harness.watchdog.stats().audioLost, false);
  assert.equal(harness.calls.listDevices, 0);
  assert.deepEqual(harness.calls.reconnect, []);
  assert.equal(harness.watchdog.stats().recoveries, 0);
  assert.deepEqual(harness.calls.toasts, []);
});

test('watchdog starts the countdown from the moment it is armed', async function () {
  const harness = createHarness({ devices: [{ deviceId: 'device-new', label: 'Voicemeeter Out B1' }] });
  harness.watchdog.start();

  harness.getTrack().readyState = 'ended';
  await harness.tick();
  harness.advance(120000);
  await harness.tick();
  assert.deepEqual(harness.calls.reconnect, [], 'disarmed, so nothing happened');

  harness.watchdog.setArmed(true);
  harness.advance(19000);
  await harness.tick();
  assert.deepEqual(harness.calls.reconnect, [], 'grace runs from the arm moment');

  harness.advance(2000);
  await harness.tick();
  assert.deepEqual(harness.calls.reconnect, ['device-new']);
});

test('watchdog disarming mid-countdown cancels the reconnect', async function () {
  const harness = createHarness({ devices: [{ deviceId: 'device-new', label: 'Voicemeeter Out B1' }] });
  harness.watchdog.start();
  harness.watchdog.setArmed(true);

  harness.getTrack().readyState = 'ended';
  await harness.tick();
  harness.advance(10000);
  await harness.tick();

  harness.watchdog.setArmed(false);
  harness.advance(60000);
  await harness.tick();

  assert.deepEqual(harness.calls.reconnect, []);
  assert.equal(harness.watchdog.stats().recoverInSecs, 0);
});

test('watchdog treats a muted track as loss and a stopped watchdog as inert', async function () {
  const harness = createHarness({ devices: [{ deviceId: 'device-new', label: 'Voicemeeter Out B1' }] });
  harness.watchdog.start();
  harness.watchdog.setArmed(true);

  harness.getTrack().muted = true;
  await harness.tick();
  assert.equal(harness.watchdog.stats().audioLost, true);

  harness.watchdog.stop();
  harness.advance(60000);
  await harness.tick();
  assert.deepEqual(harness.calls.reconnect, [], 'a stopped watchdog does nothing');
});

test('watchdog ignores the input entirely when nothing is being monitored', async function () {
  const window = { setInterval: function () {}, clearInterval: function () {} };
  loadScript('src/js/audio-watchdog.js', window);
  const toasts = [];
  let intervalCallback = null;
  window.setInterval = function (callback) { intervalCallback = callback; return { id: 1 }; };
  const watchdog = window.BCWatchdog.create({
    window: window,
    // Running without audio input is a supported mode: there is no stream to
    // lose, so it must not be reported as one.
    isMonitoring: function () { return false; },
    getTrack: function () { return null; },
    onToast: function (message) { toasts.push(message); },
  });
  watchdog.start();
  watchdog.setArmed(true);
  intervalCallback();
  await flushMicrotasks();

  assert.equal(watchdog.stats().audioLost, false);
  assert.deepEqual(toasts, []);
});

test('watchdog reports failure rather than capturing the room', async function () {
  const harness = createHarness({ devices: [{ deviceId: 'mic-1', label: 'Built-in Microphone' }] });
  harness.watchdog.start();
  harness.watchdog.setArmed(true);

  harness.getTrack().readyState = 'ended';
  await harness.tick();
  harness.advance(25000);
  await harness.tick();

  assert.deepEqual(harness.calls.reconnect, [], 'never falls back to a physical mic');
  assert.ok(harness.calls.toasts.some(function (message) { return /no .*input/i.test(message); }));
});

test('device ranking prefers the previous id, then Voicemeeter, then VB-Audio', function () {
  const window = { setInterval: function () {}, clearInterval: function () {} };
  loadScript('src/js/audio-watchdog.js', window);
  const select = window.BCWatchdog.selectInputDevice;

  const devices = [
    { deviceId: 'mic-1', label: 'Built-in Microphone' },
    { deviceId: 'default', label: 'Default' },
    { deviceId: 'vb-1', label: 'VB-Audio Point' },
    { deviceId: 'vm-1', label: 'Voicemeeter Out B1' },
    { deviceId: 'device-old', label: 'Voicemeeter Out B1' },
  ];

  assert.equal(select(devices, { deviceId: 'device-old', label: 'Voicemeeter Out B1' }).deviceId,
    'device-old', 'the exact previous device wins when it reappears');

  const withoutPrevious = devices.filter(function (d) { return d.deviceId !== 'device-old'; });
  assert.equal(select(withoutPrevious, { deviceId: 'device-old', label: 'Voicemeeter Out B1' }).deviceId, 'vm-1');

  const withoutVoicemeeter = withoutPrevious.filter(function (d) { return d.deviceId !== 'vm-1'; });
  assert.equal(select(withoutVoicemeeter, { deviceId: 'device-old', label: 'Scarlett 2i2' }).deviceId, 'vb-1');

  const onlyDefaultAndMic = [
    { deviceId: 'mic-1', label: 'Built-in Microphone' },
    { deviceId: 'default', label: 'Default' },
  ];
  assert.equal(select(onlyDefaultAndMic, { deviceId: 'gone', label: 'Scarlett 2i2' }).deviceId, 'default');

  const onlyMic = [{ deviceId: 'mic-1', label: 'Built-in Microphone' }];
  assert.equal(select(onlyMic, { deviceId: 'gone', label: 'Scarlett 2i2' }), null);
});

test('device ranking matches the previous label when the id changed', function () {
  const window = { setInterval: function () {}, clearInterval: function () {} };
  loadScript('src/js/audio-watchdog.js', window);
  const select = window.BCWatchdog.selectInputDevice;

  // A Voicemeeter restart hands back the same label under a new deviceId, which
  // is exactly why label ranking matters more than id here.
  const devices = [
    { deviceId: 'mic-1', label: 'Built-in Microphone' },
    { deviceId: 'new-id', label: 'Scarlett 2i2 USB' },
  ];
  assert.equal(select(devices, { deviceId: 'old-id', label: 'Scarlett 2i2 USB' }).deviceId, 'new-id');
});
