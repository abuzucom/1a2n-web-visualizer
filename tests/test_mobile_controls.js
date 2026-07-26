const assert = require('node:assert/strict');
const fs = require('node:fs');
const test = require('node:test');
const vm = require('node:vm');

function loadScript(path, window) {
  const source = fs.readFileSync(path, 'utf8');
  vm.runInNewContext(source, { window: window });
}

test('hyperspeed toggles one scheduler and stops on visibility changes', function () {
  const timers = [];
  const cleared = [];
  let visibilityHandler = null;
  let shuffleCount = 0;
  const changes = [];
  const window = {
    setInterval: function (callback, interval) {
      const timer = { callback: callback, interval: interval };
      timers.push(timer);
      return timer;
    },
    clearInterval: function (timer) { cleared.push(timer); },
  };
  const document = {
    hidden: false,
    addEventListener: function (event, callback) {
      if (event === 'visibilitychange') visibilityHandler = callback;
    },
  };
  loadScript('src/js/hyperspeed.js', window);
  const controller = window.BCHyperspeed.create({
    shuffle: function () { shuffleCount += 1; },
    intervalMs: 100,
    visibilityTarget: document,
    onChange: function (enabled) { changes.push(enabled); },
  });

  assert.equal(controller.toggle(), true);
  assert.equal(shuffleCount, 1);
  assert.equal(timers.length, 1);
  assert.equal(timers[0].interval, 100);
  timers[0].callback();
  assert.equal(shuffleCount, 2);

  document.hidden = true;
  visibilityHandler();
  assert.equal(controller.isEnabled(), false);
  assert.deepEqual(changes, [true, false]);
  assert.deepEqual(cleared, [timers[0]]);
});

test('mobile history is session-only and supports returning through visits', function () {
  const window = {};
  loadScript('src/js/mobile-state.js', window);
  const history = window.BCMobileState.createHistory(2);

  history.visit(10);
  history.visit(20);
  history.visit(30);
  assert.equal(history.back(), 20);
  history.visit(20);
  assert.equal(history.back(), 10);

  const freshHistory = window.BCMobileState.createHistory(2);
  assert.equal(freshHistory.canGoBack(), false);
});

test('mobile interval cycle wraps through configured values', function () {
  const window = {};
  loadScript('src/js/mobile-state.js', window);
  const cycle = window.BCMobileState.createIntervalCycle([15, 30, 60], 1);

  assert.equal(cycle.current(), 30);
  assert.equal(cycle.next(), 60);
  assert.equal(cycle.next(), 15);
  assert.equal(cycle.next(), 30);
});

function createClassList() {
  const classes = new Set();
  return {
    classes: classes,
    add: function (name) { classes.add(name); },
    remove: function (name) { classes.delete(name); },
    toggle: function (name) {
      if (classes.has(name)) { classes.delete(name); return false; }
      classes.add(name); return true;
    },
    contains: function (name) { return classes.has(name); },
  };
}

function createFullscreenHarness(vizOverrides) {
  const listeners = {};
  const elements = {};
  const bodyClassList = createClassList();
  const elementIds = [
    'viz', 'toast', 'help', 'startPrompt', 'startupStatus', 'startupStatusText',
    'startupProgressBar', 'removeBtn', 'excludedBtn', 'excludedPanel',
    'excludedList', 'copyExcludedBtn', 'closeExcludedBtn',
    'favoriteBtn', 'favoritesBtn', 'favoritesPanel', 'favoritesListText',
    'copyFavoritesBtn', 'closeFavoritesBtn',
  ];
  elementIds.forEach(function (id) {
    elements[id] = {
      classList: createClassList(),
      style: {},
      parentElement: { setAttribute: function () {}, removeAttribute: function () {} },
      addEventListener: function () {},
      focus: function () {},
      select: function () {},
    };
  });
  const document = {
    body: { classList: bodyClassList },
    documentElement: {},
    fullscreenElement: null,
    getElementById: function (id) { return elements[id]; },
    addEventListener: function (event, callback) {
      if (!listeners[event]) listeners[event] = [];
      listeners[event].push(callback);
    },
  };
  let toggles = 0;
  const window = {
    BCHyperspeed: {
      create: function () {
        return {
          toggle: function () { toggles += 1; return true; },
        };
      },
    },
    setTimeout: function () { return 1; },
    clearTimeout: function () {},
    setInterval: function () { return 1; },
    clearInterval: function () {},
  };
  const viz = Object.assign({
    keys: function () { return ['preset']; },
    isStarted: function () { return true; },
    removeCurrentFromShuffle: function () { return null; },
    excludedList: function () { return []; },
    favoriteCurrentPreset: function () { return null; },
    favoritesList: function () { return []; },
    next: function () {},
    prev: function () {},
    random: function () {},
    toggleCycle: function () { return true; },
    toggleShuffle: function () { return true; },
    setCycleSecs: function (seconds) { return seconds; },
    getCycleSecs: function () { return 20; },
    nextDevice: function () { return Promise.resolve(); },
  }, vizOverrides || {});
  const context = {
    window: window,
    document: document,
    navigator: {},
    BCViz: { create: function () { return viz; } },
    setTimeout: window.setTimeout,
    clearTimeout: window.clearTimeout,
    setInterval: window.setInterval,
    clearInterval: window.clearInterval,
    console: console,
  };
  const source = fs.readFileSync('src/js/fullscreen-ui.js', 'utf8');
  vm.runInNewContext(source, context);
  return {
    listeners: listeners,
    elements: elements,
    viz: viz,
    toggles: function () { return toggles; },
  };
}

test('fullscreen T toggles hyperspeed once per physical key press', function () {
  const harness = createFullscreenHarness();

  harness.listeners.keydown.forEach(function (handler) {
    handler({ key: 'T', repeat: false, preventDefault: function () {} });
    handler({ key: 'T', repeat: true, preventDefault: function () {} });
    handler({ key: 'T', repeat: false, preventDefault: function () {} });
  });
  assert.equal(harness.toggles(), 2);
});

test('fullscreen M favorites the current preset', function () {
  let favoriteCalls = 0;
  const harness = createFullscreenHarness({
    favoriteCurrentPreset: function () { favoriteCalls += 1; return 'preset'; },
  });

  harness.listeners.keydown.forEach(function (handler) {
    handler({ key: 'M', repeat: false, preventDefault: function () {} });
    handler({ key: 'm', repeat: false, preventDefault: function () {} });
  });
  assert.equal(favoriteCalls, 2);
});

test('fullscreen K shows the favorites panel and Escape closes both panels', function () {
  const harness = createFullscreenHarness({
    favoritesList: function () { return ['a', 'b']; },
  });
  harness.elements.favoritesPanel.classList.add('hidden');
  harness.elements.excludedPanel.classList.add('hidden');

  harness.listeners.keydown.forEach(function (handler) {
    handler({ key: 'K', repeat: false, preventDefault: function () {} });
  });
  assert.equal(harness.elements.favoritesPanel.classList.contains('hidden'), false);

  harness.listeners.keydown.forEach(function (handler) {
    handler({ key: 'Escape', repeat: false, preventDefault: function () {} });
  });
  assert.equal(harness.elements.favoritesPanel.classList.contains('hidden'), true);
  assert.equal(harness.elements.excludedPanel.classList.contains('hidden'), true);
});
