const assert = require('node:assert/strict');
const fs = require('node:fs');
const test = require('node:test');
const vm = require('node:vm');

function loadScript(path, window) {
  const source = fs.readFileSync(path, 'utf8');
  vm.runInNewContext(source, { window: window, console: console });
}

function createNode(kind, log) {
  const node = {
    kind: kind,
    connectedTo: [],
    disconnects: 0,
    started: 0,
    stopped: 0,
    gain: { value: null },
    frequency: { value: null },
    connect: function (target) { node.connectedTo.push(target); return target; },
    disconnect: function () { node.disconnects += 1; },
    start: function () { node.started += 1; },
    stop: function () { node.stopped += 1; },
  };
  log.push(node);
  return node;
}

function createFakeContext(log) {
  const context = {
    state: 'running',
    destination: { kind: 'destination' },
    closed: 0,
    createOscillator: function () { return createNode('oscillator', log); },
    createGain: function () { return createNode('gain', log); },
    resume: function () { context.state = 'running'; return Promise.resolve(); },
    close: function () { context.closed += 1; context.state = 'closed'; return Promise.resolve(); },
  };
  return context;
}

function createHarness() {
  const nodes = [];
  const contexts = [];
  const window = {
    AudioContext: function () {
      const context = createFakeContext(nodes);
      contexts.push(context);
      return context;
    },
  };
  loadScript('src/js/audible-keepalive.js', window);
  return {
    window: window,
    nodes: nodes,
    contexts: contexts,
    create: function () { return window.BCKeepalive.create({ window: window }); },
  };
}

const LOOPBACK_LABELS = [
  'Voicemeeter Out B1 (VB-Audio Voicemeeter VAIO)',
  'CABLE Output (VB-Audio Virtual Cable)',
  'Stereo Mix (Realtek High Definition Audio)',
  'Monitor of Built-in Audio Analog Stereo',
  'BlackHole 2ch',
  'Loopback Audio',
];

test('keepalive starts and drives its own context for a normal input', function () {
  const harness = createHarness();
  const keepalive = harness.create();

  keepalive.setInputLabel('Scarlett 2i2 USB');
  keepalive.start();

  const stats = keepalive.stats();
  assert.equal(stats.active, true);
  assert.equal(stats.suppressed, false);
  assert.equal(harness.contexts.length, 1);

  const oscillator = harness.nodes.find(function (node) { return node.kind === 'oscillator'; });
  const gain = harness.nodes.find(function (node) { return node.kind === 'gain'; });
  assert.equal(oscillator.started, 1);
  assert.deepEqual(oscillator.connectedTo, [gain]);
  assert.deepEqual(gain.connectedTo, [harness.contexts[0].destination]);
  assert.ok(gain.gain.value > 0, 'must emit a non-zero signal to register as audible');
  assert.ok(gain.gain.value < 0.01, 'must stay far below an audible level');
});

LOOPBACK_LABELS.forEach(function (label) {
  test('keepalive is suppressed for loopback input ' + label, function () {
    const harness = createHarness();
    const keepalive = harness.create();

    keepalive.setInputLabel(label);
    keepalive.start();

    const stats = keepalive.stats();
    assert.equal(stats.active, false);
    assert.equal(stats.suppressed, true);
    assert.match(stats.reason, /loopback/i);
    assert.equal(harness.contexts.length, 0, 'no audio graph is built while suppressed');
  });
});

test('keepalive re-evaluates in both directions when the device changes', function () {
  const harness = createHarness();
  const keepalive = harness.create();

  keepalive.setInputLabel('Scarlett 2i2 USB');
  keepalive.start();
  assert.equal(keepalive.stats().active, true);

  keepalive.setInputLabel('Voicemeeter Out B1');
  assert.equal(keepalive.stats().active, false);
  assert.equal(keepalive.stats().suppressed, true);
  const oscillator = harness.nodes.find(function (node) { return node.kind === 'oscillator'; });
  assert.equal(oscillator.stopped, 1, 'the running signal is torn down on suppression');

  keepalive.setInputLabel('Scarlett 2i2 USB');
  assert.equal(keepalive.stats().active, true);
  assert.equal(keepalive.stats().suppressed, false);
});

test('keepalive treats an unknown device label as suppressed', function () {
  const harness = createHarness();
  const keepalive = harness.create();

  // Labels are empty until getUserMedia permission is granted. Emitting into an
  // unidentified device risks feeding a loopback capture, so stay quiet.
  keepalive.setInputLabel('');
  keepalive.start();

  assert.equal(keepalive.stats().active, false);
  assert.equal(keepalive.stats().suppressed, true);
});

test('keepalive never touches the analysis context', function () {
  const harness = createHarness();
  const analysisContext = createFakeContext([]);
  const keepalive = harness.create();

  keepalive.setInputLabel('Scarlett 2i2 USB');
  keepalive.start();

  assert.equal(harness.contexts.length, 1);
  assert.notEqual(harness.contexts[0], analysisContext);
  assert.equal(analysisContext.closed, 0);
});

test('keepalive stop tears down the graph and closes its context', function () {
  const harness = createHarness();
  const keepalive = harness.create();

  keepalive.setInputLabel('Scarlett 2i2 USB');
  keepalive.start();
  keepalive.stop();

  const oscillator = harness.nodes.find(function (node) { return node.kind === 'oscillator'; });
  assert.equal(oscillator.stopped, 1);
  assert.equal(harness.contexts[0].closed, 1);
  assert.equal(keepalive.stats().active, false);
});

test('keepalive survives an environment with no AudioContext', function () {
  const window = {};
  loadScript('src/js/audible-keepalive.js', window);
  const keepalive = window.BCKeepalive.create({ window: window });

  keepalive.setInputLabel('Scarlett 2i2 USB');
  keepalive.start();

  assert.equal(keepalive.stats().active, false);
  assert.match(keepalive.stats().reason, /unavailable/i);
});
