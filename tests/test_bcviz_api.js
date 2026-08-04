const assert = require('node:assert/strict');
const fs = require('node:fs');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync('src/js/visualizer-core.js', 'utf8');

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

function createHarness(presets, initialWebglErrors) {
  const canvas = {};
  const schedule = function (callback, delay) {
    const timer = setTimeout(callback, delay);
    timer.unref();
    return timer;
  };
  canvas.addEventListener = function () {};
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
    requestAnimationFrame: function () { return 1; },
    cancelAnimationFrame: function () {},
    requestIdleCallback: function (callback) { callback(); },
    setTimeout: schedule,
    clearTimeout: clearTimeout,
  };
  window.AudioContext = function () {
    this.resume = async function () {};
    this.close = async function () {};
    this.createMediaStreamSource = function () { return {}; };
  };
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
        render: function () {},
        connectAudio: function () {},
        disconnectAudio: function () {},
      };
    },
  };
  const document = {
    createElement: function () { return {}; },
    head: {
      appendChild: function (script) {
        if (script.src && script.src.indexOf('presets-extra/') === 0) chunkLoads += 1;
        if (script.src && script.src.indexOf('vendor/butterchurnExtraImagesExp-part-') === 0) imagePartLoads += 1;
      },
    },
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
    setTimeout: schedule,
    clearTimeout: clearTimeout,
    setInterval: trackedSetInterval,
    clearInterval: clearInterval,
  });
  return {
    canvas: canvas,
    window: window,
    loadCalls: loadCalls,
    chunkLoads: function () { return chunkLoads; },
    imagePartLoads: function () { return imagePartLoads; },
    intervalCalls: function () { return intervalCalls; },
  };
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
