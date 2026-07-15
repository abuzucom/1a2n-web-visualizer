const assert = require('node:assert/strict');
const fs = require('node:fs');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync('src/js/visualizer-core.js', 'utf8');

function createHarness() {
  const canvas = {};
  const window = {
    BCExtraPresetIndex: { chunks: [['lazy']], files: ['chunk-000.js'] },
    devicePixelRatio: 3,
    innerWidth: 100,
    innerHeight: 50,
    addEventListener: function () {},
  };
  const document = {
    createElement: function () { return {}; },
    head: { appendChild: function () {} },
  };
  vm.runInNewContext(source, {
    window: window,
    document: document,
    navigator: {},
    console: console,
    setTimeout: setTimeout,
    clearTimeout: clearTimeout,
  });
  return { canvas: canvas, window: window };
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
  const viz = harness.window.BCViz.create({}, { cycleOn: false });

  harness.window.__bcPresetChunk(0, { lazy: { baseVals: {} } });

  assert.deepEqual(Array.from(viz.keys()), ['lazy']);
  assert.equal(viz.currentIndex(), 0);
});
