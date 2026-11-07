/* Performance page regressions: the curated performance catalog, the energy
 * tiers, and the per-category playback cycles. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const test = require('node:test');
const vm = require('node:vm');

function readSource(path) {
  return fs.readFileSync(path, 'utf8');
}

function createClassList() {
  const classes = new Set();
  return {
    add: function (name) { classes.add(name); },
    remove: function (name) { classes.delete(name); },
    toggle: function (name, force) {
      const next = force === undefined ? !classes.has(name) : Boolean(force);
      if (next) classes.add(name); else classes.delete(name);
      return next;
    },
    contains: function (name) { return classes.has(name); },
  };
}

function createElement(id, tagName) {
  const element = {
    id: id,
    tagName: tagName || 'DIV',
    hidden: false,
    inert: false,
    value: '',
    textContent: '',
    listeners: {},
    children: [],
    classList: createClassList(),
    style: {},
    attributes: {},
    parentElement: { setAttribute: function () {}, removeAttribute: function () {}, getAttribute: function () { return null; } },
    addEventListener: function (event, callback) {
      if (!element.listeners[event]) element.listeners[event] = [];
      element.listeners[event].push(callback);
    },
    dispatch: function (event, payload) {
      const handlers = element.listeners[event] || [];
      const evt = Object.assign({ target: element, stopPropagation: function () {} }, payload || {});
      handlers.forEach(function (handler) { handler(evt); });
    },
    setAttribute: function (name, value) { element.attributes[name] = String(value); },
    removeAttribute: function (name) { delete element.attributes[name]; },
    getAttribute: function () { return null; },
    appendChild: function (child) { element.children.push(child); return child; },
    focus: function () {},
    select: function () {},
  };
  return element;
}

function createDocument(elements) {
  const listeners = {};
  const document = {
    activeElement: null,
    body: createElement('body', 'BODY'),
    documentElement: {},
    fullscreenElement: null,
    createElement: function (tag) { return createElement('created', String(tag).toUpperCase()); },
    getElementById: function (id) { return elements[id]; },
    addEventListener: function (event, callback) {
      if (!listeners[event]) listeners[event] = [];
      listeners[event].push(callback);
    },
    dispatch: function (event, payload) {
      const evt = Object.assign({
        target: document.body,
        repeat: false,
        defaultPrevented: false,
        preventDefault: function () { evt.defaultPrevented = true; },
        stopPropagation: function () {},
      }, payload || {});
      (listeners[event] || []).forEach(function (handler) { handler(evt); });
      return evt;
    },
  };
  document.body.getAttribute = function () { return null; };
  document.activeElement = document.body;
  return document;
}

/** A deterministic random source so the shuffle order is predictable. */
function createMath(value) {
  return {
    random: function () { return value; },
    floor: Math.floor,
    min: Math.min,
    max: Math.max,
  };
}

const RUNTIME_NAMES = ['Low One', 'Low Two', 'Medium One', 'High One', 'Not Curated'];
const LAZY_NAME = 'Lazy Collection Preset';

function createHarness(options) {
  const settings = options || {};
  const elements = {};
  ['viz', 'toast', 'help', 'startPrompt', 'startError'].forEach(function (id) {
    elements[id] = createElement(id, 'DIV');
  });
  const document = createDocument(elements);
  const played = [];
  const window = {
    BCEnergyCatalog: settings.energy || { version: 1, presets: {} },
    BCPerformanceCatalog: settings.performance || { version: 1, presets: [] },
  };
  const viz = {
    keys: function () { return RUNTIME_NAMES.concat([LAZY_NAME]); },
    isStarted: function () { return true; },
    goto: function (index) { played.push(RUNTIME_NAMES.concat([LAZY_NAME])[index]); },
    start: function () { return Promise.resolve(); },
    listDevices: function () { return []; },
    currentDeviceId: function () { return ''; },
  };
  const context = {
    window: window,
    document: document,
    navigator: {},
    location: { search: '' },
    BCViz: { create: function () { return viz; } },
    Math: createMath(settings.random === undefined ? 0 : settings.random),
    setTimeout: function () { return 0; },
    clearTimeout: function () {},
    console: console,
  };
  vm.runInNewContext(readSource('src/js/performance-ui.js'), context);
  return { elements: elements, document: document, played: played };
}

function catalogs(energy, performance) {
  return {
    energy: { version: 1, presets: energy },
    performance: { version: 1, presets: performance },
  };
}

test('a category key plays a curated preset of that energy', function () {
  const harness = createHarness(catalogs(
    { 'presets-extra:Low One': 'low', 'presets-extra:Medium One': 'medium' },
    ['presets-extra:Low One', 'presets-extra:Medium One'],
  ));

  harness.document.dispatch('keydown', { key: '7' });

  assert.deepEqual(harness.played, ['Low One']);
});

test('a preset outside the performance catalog never plays', function () {
  const harness = createHarness(catalogs(
    { 'presets-extra:Not Curated': 'low' },
    ['presets-extra:Low One'],
  ));

  harness.document.dispatch('keydown', { key: '7' });

  assert.deepEqual(harness.played, []);
});

test('a curated preset without an energy category never plays', function () {
  const harness = createHarness(catalogs(
    { 'presets-extra:Medium One': 'medium' },
    ['presets-extra:Low One', 'presets-extra:Medium One'],
  ));

  harness.document.dispatch('keydown', { key: '7' });

  assert.deepEqual(harness.played, []);
});

test('an empty category leaves the visualizer unchanged and shows a message', function () {
  const harness = createHarness(catalogs(
    { 'presets-extra:Medium One': 'medium' },
    ['presets-extra:Medium One'],
  ));

  harness.document.dispatch('keydown', { key: '7' });

  assert.deepEqual(harness.played, [], 'nothing plays');
  assert.match(harness.elements.toast.textContent, /low/);
});

test('a category cycle plays every eligible preset once', function () {
  const harness = createHarness(catalogs(
    { 'presets-extra:Low One': 'low', 'presets-extra:Low Two': 'low' },
    ['presets-extra:Low One', 'presets-extra:Low Two'],
  ));

  harness.document.dispatch('keydown', { key: '7' });
  harness.document.dispatch('keydown', { key: '7' });

  assert.equal(harness.played.length, 2);
  assert.equal(harness.played[0] === 'Low One' || harness.played[0] === 'Low Two', true);
  assert.notEqual(harness.played[0], harness.played[1], 'the cycle holds no repeats');
});

test('a following cycle uses an order that differs from the previous one', function () {
  const harness = createHarness(catalogs(
    { 'presets-extra:Low One': 'low', 'presets-extra:Low Two': 'low', 'presets-extra:Medium One': 'low' },
    ['presets-extra:Low One', 'presets-extra:Low Two', 'presets-extra:Medium One'],
  ));

  harness.document.dispatch('keydown', { key: '7' });
  harness.document.dispatch('keydown', { key: '7' });
  harness.document.dispatch('keydown', { key: '7' });
  const firstCycle = harness.played.slice();

  harness.document.dispatch('keydown', { key: '7' });
  const secondCycleFirst = harness.played[3];

  assert.notEqual(secondCycleFirst, firstCycle[0], 'the new cycle starts in a different order');
});

test('a category with one eligible preset repeats it', function () {
  const harness = createHarness(catalogs(
    { 'presets-extra:High One': 'high' },
    ['presets-extra:High One'],
  ));

  harness.document.dispatch('keydown', { key: '9' });
  harness.document.dispatch('keydown', { key: '9' });

  assert.deepEqual(harness.played, ['High One', 'High One']);
});

test('each category keeps its own cycle', function () {
  const harness = createHarness(catalogs(
    { 'presets-extra:Low One': 'low', 'presets-extra:Medium One': 'medium' },
    ['presets-extra:Low One', 'presets-extra:Medium One'],
  ));

  harness.document.dispatch('keydown', { key: '8' });
  harness.document.dispatch('keydown', { key: '7' });
  harness.document.dispatch('keydown', { key: '8' });

  assert.deepEqual(harness.played, ['Medium One', 'Low One', 'Medium One']);
});

test('a preset that loads lazily still plays', function () {
  const harness = createHarness(catalogs(
    { 'presets-extra:Lazy Collection Preset': 'low' },
    ['presets-extra:Lazy Collection Preset'],
  ));

  harness.document.dispatch('keydown', { key: '7' });

  assert.deepEqual(harness.played, ['Lazy Collection Preset']);
});

test('a two preset category never repeats the previous order', function () {
  const harness = createHarness(catalogs(
    { 'presets-extra:Low One': 'low', 'presets-extra:Low Two': 'low' },
    ['presets-extra:Low One', 'presets-extra:Low Two'],
  ));

  harness.document.dispatch('keydown', { key: '7' });
  harness.document.dispatch('keydown', { key: '7' });
  harness.document.dispatch('keydown', { key: '7' });
  harness.document.dispatch('keydown', { key: '7' });
  const firstCycle = harness.played.slice(0, 2);
  const secondCycle = harness.played.slice(2, 4);

  assert.equal(firstCycle.length, 2);
  assert.equal(secondCycle.length, 2);
  assert.notDeepEqual(secondCycle, firstCycle, 'the new cycle uses a different order');
});

test('the performance page holds no preset list and no curation controls', function () {
  const html = readSource('src/performance.html');
  assert.equal(html.indexOf('textarea'), -1, 'the page shows no preset list');
  assert.equal(html.indexOf('copyAssignedBtn'), -1, 'the page has no curation controls');
  assert.equal(html.indexOf('excludedPanel'), -1, 'the page has no excluded panel');
  assert.match(html, /<canvas id="viz">/);
  assert.match(html, /catalogs\/energy-catalog\.js/);
  assert.match(html, /catalogs\/performance-catalog\.js/);
});
