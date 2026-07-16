const assert = require('node:assert/strict');
const fs = require('node:fs');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync('src/js/visualizer-core.js', 'utf8');

function createHarness(presets, initialWebglErrors) {
  const canvas = {};
  canvas.addEventListener = function () {};
  const webglErrors = (initialWebglErrors || []).slice();
  const webgl = {
    NO_ERROR: 0,
    getError: function () { return webglErrors.shift() || 0; },
  };
  canvas.getContext = function () { return webgl; };
  const loadCalls = [];
  const window = {
    BCExtraPresetIndex: { chunks: [['lazy']], files: ['chunk-000.js'] },
    butterchurnPresets: presets ? { getPresets: function () { return presets; } } : null,
    devicePixelRatio: 3,
    innerWidth: 100,
    innerHeight: 50,
    addEventListener: function () {},
    requestAnimationFrame: function () { return 1; },
    cancelAnimationFrame: function () {},
  };
  window.AudioContext = function () {
    this.resume = async function () {};
    this.close = async function () {};
    this.createMediaStreamSource = function () { return {}; };
  };
  window.butterchurn = {
    createVisualizer: function () {
      return {
        loadPreset: function (preset) { loadCalls.push(preset); },
        render: function () {},
        connectAudio: function () {},
        disconnectAudio: function () {},
      };
    },
  };
  const document = {
    createElement: function () { return {}; },
    head: { appendChild: function () {} },
  };
  vm.runInNewContext(source, {
    window: window,
    document: document,
    navigator: {
      mediaDevices: {
        enumerateDevices: async function () { return [{ kind: 'audioinput', deviceId: 'default' }]; },
        getUserMedia: async function () { return { getTracks: function () { return []; } }; },
      },
    },
    console: console,
    setTimeout: setTimeout,
    clearTimeout: clearTimeout,
  });
  return { canvas: canvas, window: window, loadCalls: loadCalls };
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

test('drains queued WebGL errors before loading a fallback preset', async function () {
  const harness = createHarness({
    bad: { baseVals: {} },
    good: { baseVals: {} },
  }, [0x502, 0x502, 0x501, 0]);
  const viz = harness.window.BCViz.create(harness.canvas, { cycleOn: false });

  await viz.start();

  assert.equal(viz.currentName(), 'good');
  assert.equal(harness.loadCalls.length, 2);
});
