/* The OBS preset filter matches names case-insensitively. obs-ui.js
 * lowercases the preset names once at load and reuses them on each rebuild. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const test = require('node:test');
const vm = require('node:vm');
const { createBCVizStub } = require('./support/bcviz-stub.js');

const SUPPORT_SCRIPTS = ['src/js/diagnostics.js', 'src/js/device-errors.js', 'src/js/audio-prefs.js'];
const ELEMENT_IDS = [
  'viz', 'panel', 'device', 'preset', 'presetFilter', 'status',
  'cycle', 'cycleSecs', 'audioGuard', 'startBtn', 'nextBtn', 'prevBtn', 'randBtn',
];
const PRESET_NAMES = ['Aderrasi - Swamp', 'Geiss - Bright Swamp', 'Krash - Rainbow'];

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
  const listeners = {};
  const element = {
    id: id,
    value: '',
    textContent: '',
    checked: false,
    children: [],
    listeners: listeners,
    classList: createClassList(),
    style: {},
    addEventListener: function (event, callback) {
      if (!listeners[event]) listeners[event] = [];
      listeners[event].push(callback);
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

/** Load obs-ui.js against fake elements. Timers run at once, so the
 * debounced filter rebuild happens inside the input event. */
function loadObsPage() {
  const elements = {};
  ELEMENT_IDS.forEach(function (id) { elements[id] = createElement(id); });
  elements.cycleSecs.value = '20';
  const document = {
    body: { classList: createClassList(), appendChild: function () {} },
    createElement: function () { return createElement('option'); },
    createDocumentFragment: function () {
      const fragment = createElement('fragment');
      fragment.isFragment = true;
      return fragment;
    },
    getElementById: function (id) { return elements[id]; },
    addEventListener: function () {},
  };
  const runNow = function (callback) { callback(); return 0; };
  const window = {
    localStorage: { getItem: function () { return null; }, setItem: function () {}, removeItem: function () {} },
    setTimeout: runNow,
    clearTimeout: function () {},
    setInterval: function () { return 0; },
    clearInterval: function () {},
  };
  SUPPORT_SCRIPTS.forEach(function (path) {
    vm.runInNewContext(fs.readFileSync(path, 'utf8'), { window: window, console: console });
  });
  const viz = {
    keys: function () { return PRESET_NAMES.slice(); },
    currentIndex: function () { return 0; },
    diagnostics: function () { return {}; },
    isAudioGuardArmed: function () { return false; },
    setAudioGuard: function (armed) { return Boolean(armed); },
    listDevices: function () { return []; },
    getDevices: function () { return Promise.resolve([]); },
  };
  vm.runInNewContext(fs.readFileSync('src/js/obs-ui.js', 'utf8'), {
    window: window,
    document: document,
    navigator: {},
    location: { search: '' },
    BCViz: createBCVizStub(window, function () { return viz; }),
    setTimeout: runNow,
    clearTimeout: function () {},
    console: console,
  });
  return elements;
}

function shownNames(elements) {
  return elements.preset.children.map(function (option) { return option.textContent; });
}

function typeFilter(elements, text) {
  elements.presetFilter.value = text;
  elements.presetFilter.listeners.input.forEach(function (handler) { handler(); });
}

test('the preset list starts with every preset', function () {
  const elements = loadObsPage();

  assert.deepEqual(shownNames(elements), PRESET_NAMES);
});

test('the preset filter ignores letter case in both the query and the names', function () {
  const elements = loadObsPage();

  typeFilter(elements, 'SWAMP');
  assert.deepEqual(shownNames(elements), ['Aderrasi - Swamp', 'Geiss - Bright Swamp']);

  typeFilter(elements, 'kRaSh');
  assert.deepEqual(shownNames(elements), ['Krash - Rainbow']);
});

test('clearing the preset filter shows every preset again', function () {
  const elements = loadObsPage();

  typeFilter(elements, 'geiss');
  typeFilter(elements, '');

  assert.deepEqual(shownNames(elements), PRESET_NAMES);
});

test('a filter that matches nothing leaves the list empty', function () {
  const elements = loadObsPage();

  typeFilter(elements, 'no such preset');

  assert.deepEqual(shownNames(elements), []);
});
