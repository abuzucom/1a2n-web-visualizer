/* Energy curation regressions: the fullscreen curation keys, the assigned
 * preset panel, and the session set of presets that already played. */
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
    getAttribute: function (name) {
      return Object.prototype.hasOwnProperty.call(element.attributes, name) ? element.attributes[name] : null;
    },
    appendChild: function (child) { element.children.push(child); return child; },
    focus: function () { element.focusCount = (element.focusCount || 0) + 1; },
    select: function () {},
  };
  return element;
}

function createTimers() {
  return {
    setTimeout: function () { return 0; },
    clearTimeout: function () {},
    setInterval: function () { return 0; },
    clearInterval: function () {},
  };
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

const ELEMENT_IDS = [
  'viz', 'toast', 'help', 'startPrompt', 'startupStatus', 'startupStatusText',
  'startupProgressBar', 'startError', 'removeBtn', 'excludedBtn', 'favoriteBtn',
  'favoritesBtn', 'excludedPanel', 'excludedList', 'copyExcludedBtn', 'closeExcludedBtn',
  'favoritesPanel', 'favoritesListText', 'copyFavoritesBtn', 'closeFavoritesBtn',
];

const CURATION_ELEMENT_IDS = [
  'assignedPanel', 'assignedList', 'assignmentBlock', 'copyAssignedBtn',
  'copyAssignmentsBtn', 'closeAssignedBtn',
];

const BUTTON_IDS = [
  'removeBtn', 'excludedBtn', 'favoriteBtn', 'favoritesBtn', 'copyExcludedBtn',
  'closeExcludedBtn', 'copyFavoritesBtn', 'closeFavoritesBtn', 'copyAssignedBtn',
  'copyAssignmentsBtn', 'closeAssignedBtn',
];

const TEXTAREA_IDS = ['excludedList', 'favoritesListText', 'assignedList', 'assignmentBlock'];

function createHarness(options) {
  const settings = options || {};
  const elements = {};
  ELEMENT_IDS.concat(settings.withCuration === false ? [] : CURATION_ELEMENT_IDS).forEach(function (id) {
    const tag = BUTTON_IDS.indexOf(id) !== -1 ? 'BUTTON'
      : TEXTAREA_IDS.indexOf(id) !== -1 ? 'TEXTAREA' : 'DIV';
    elements[id] = createElement(id, tag);
  });
  ['excludedPanel', 'favoritesPanel', 'assignedPanel'].forEach(function (id) {
    if (!elements[id]) return;
    elements[id].classList.add('hidden');
    elements[id].inert = true;
  });
  const document = createDocument(elements);
  const timers = createTimers();
  const copied = [];
  const calls = { next: 0, random: 0, playUnplayed: 0, exclude: 0, current: 'Preset One' };
  const window = {
    BCHyperspeed: { create: function () { return { toggle: function () { return true; } }; } },
    setTimeout: timers.setTimeout,
    clearTimeout: timers.clearTimeout,
    setInterval: timers.setInterval,
    clearInterval: timers.clearInterval,
  };
  const navigator = {
    clipboard: {
      writeText: function (text) {
        copied.push(text);
        return Promise.resolve();
      },
    },
  };
  vm.runInNewContext(readSource('src/js/diagnostics.js'), { window: window });
  vm.runInNewContext(readSource('src/js/energy-curation.js'), { window: window });
  const viz = {
    keys: function () { return ['Preset One', 'Preset Two', 'Preset Three']; },
    isStarted: function () { return true; },
    next: function () { calls.next += 1; },
    prev: function () {},
    random: function () { calls.random += 1; },
    excludedList: function () { return []; },
    favoritesList: function () { return []; },
    diagnostics: function () { return {}; },
    setAudioGuard: function () { return false; },
    isDemo: function () { return false; },
    currentName: function () { return calls.current; },
    removeCurrentFromShuffle: function () { calls.exclude += 1; return 'Preset One'; },
    favoriteCurrentPreset: function () { return 'Preset One'; },
    playUnplayedRandom: function () { calls.playUnplayed += 1; return 'Preset Two'; },
    getCycleSecs: function () { return 20; },
    setCycleSecs: function (value) { return value; },
    toggleCycle: function () { return true; },
    toggleShuffle: function () { return true; },
    isShuffling: function () { return true; },
    nextDevice: function () { return Promise.resolve(); },
    listDevices: function () { return []; },
    currentDeviceId: function () { return ''; },
    start: function () { return Promise.resolve(); },
  };
  const context = {
    window: window,
    document: document,
    navigator: navigator,
    location: { search: '' },
    BCViz: { create: function () { return viz; } },
    setTimeout: timers.setTimeout,
    clearTimeout: timers.clearTimeout,
    console: console,
  };
  vm.runInNewContext(readSource('src/js/fullscreen-ui.js'), context);
  return { elements: elements, document: document, calls: calls, copied: copied };
}

test('the curation keys assign the current preset an energy category', function () {
  const harness = createHarness();

  harness.document.dispatch('keydown', { key: '8' });

  assert.equal(harness.calls.playUnplayed, 1, 'the curation key advances to another preset');
  assert.match(harness.elements.toast.textContent, /^medium/, 'the toast names the category');
});

test('a later assignment replaces the earlier category for that preset', function () {
  const harness = createHarness();

  harness.document.dispatch('keydown', { key: '7' });
  harness.document.dispatch('keydown', { key: '9' });
  harness.document.dispatch('keydown', { key: '"' });

  const block = JSON.parse(harness.elements.assignmentBlock.value);
  assert.equal(block.presets['Preset One'], 'high', 'the last assignment wins');
  assert.equal(Object.keys(block.presets).length, 1, 'one preset holds one category');
});

test('the curation keys never touch the excluded preset list', function () {
  const harness = createHarness();

  harness.document.dispatch('keydown', { key: '7' });

  assert.equal(harness.calls.exclude, 0, 'the excluded list is not written');
  assert.equal(harness.elements.excludedList.value, '', 'the excluded panel stays empty');
});

test('the quote key lists the assigned presets grouped by category', function () {
  const harness = createHarness();

  harness.document.dispatch('keydown', { key: '8' });
  harness.document.dispatch('keydown', { key: '"' });

  assert.equal(harness.elements.assignedPanel.classList.contains('hidden'), false);
  assert.equal(harness.elements.assignedPanel.inert, false);
  assert.match(harness.elements.assignedList.value, /\[low\]/);
  assert.match(harness.elements.assignedList.value, /\[medium\]/);
  assert.match(harness.elements.assignedList.value, /Preset One/);
});

test('the copied list holds bare preset names for a removal session', function () {
  const harness = createHarness();

  harness.document.dispatch('keydown', { key: '7' });
  harness.document.dispatch('keydown', { key: '"' });
  harness.elements.copyAssignedBtn.dispatch('click');

  assert.equal(harness.copied.length, 1);
  assert.equal(harness.copied[0], 'Preset One');
});

test('the assignment block copy stays separate from the removal list', function () {
  const harness = createHarness();

  harness.document.dispatch('keydown', { key: '7' });
  harness.document.dispatch('keydown', { key: '"' });
  harness.elements.copyAssignmentsBtn.dispatch('click');

  assert.equal(harness.copied.length, 1);
  const block = JSON.parse(harness.copied[0]);
  assert.equal(block.version, 1);
  assert.equal(block.presets['Preset One'], 'low');
});

test('the demo build keeps the curation keys inert', function () {
  const harness = createHarness({ withCuration: false });

  harness.document.dispatch('keydown', { key: '7' });
  harness.document.dispatch('keydown', { key: '"' });

  assert.equal(harness.calls.playUnplayed, 0, 'no curation without the panel markup');
});

test('the fullscreen markup gives the assignment panel dialog semantics', function () {
  const html = readSource('src/fullscreen.html');
  const tag = html.match(/<div id="assignedPanel"[^>]*>/);
  assert.ok(tag, 'the page defines #assignedPanel');
  assert.match(tag[0], /role="dialog"/);
  assert.match(tag[0], /aria-labelledby="assignedTitle"/);
  assert.match(tag[0], /\sinert[\s>]/);
  assert.match(html, /<h1 id="assignedTitle">/);
  assert.match(html, /<textarea id="assignedList"[^>]*aria-labelledby="assignedTitle"/);
  assert.match(html, /<textarea id="assignmentBlock"[^>]*aria-labelledby="assignedTitle"/);
});

test('the fullscreen help lists the curation keys', function () {
  const html = readSource('src/fullscreen.html');
  assert.match(html, /<kbd>7<\/kbd> \/ <kbd>8<\/kbd> \/ <kbd>9<\/kbd>/);
  assert.match(html, /<kbd>"<\/kbd>/);
});

test('the played session skips presets that already played', function () {
  const window = {};
  vm.runInNewContext(readSource('src/js/visualizer-core.js'), { window: window, console: console });
  const session = window.BCViz.createPlayedSession();
  const names = ['a', 'b', 'c'];

  session.markPlayed('a');

  assert.equal(session.hasPlayed('a'), true);
  assert.equal(session.size(), 1);
  assert.equal(session.pickUnplayed(names, 'c'), 'b', 'only the unplayed preset remains');
  assert.equal(session.pickUnplayed(names, 'a'), 'b', 'the current preset is never picked');
});

test('the played session starts a new cycle after every preset played', function () {
  const window = {};
  vm.runInNewContext(readSource('src/js/visualizer-core.js'), { window: window, console: console });
  const session = window.BCViz.createPlayedSession();
  const names = ['a', 'b'];

  session.markPlayed('a');
  session.markPlayed('b');
  assert.equal(session.size(), 2);

  const picked = session.pickUnplayed(names, null);

  assert.notEqual(picked, null, 'a new cycle starts');
  assert.ok(names.indexOf(picked) !== -1, 'the new cycle picks from the whole pool');
  assert.equal(session.size(), 0, 'the played set restarts empty');
});
