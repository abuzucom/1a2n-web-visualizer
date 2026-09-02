const assert = require('node:assert/strict');
const fs = require('node:fs');
const test = require('node:test');
const vm = require('node:vm');

function loadScript(path, window) {
  const source = fs.readFileSync(path, 'utf8');
  vm.runInNewContext(source, { window: window });
}

function createHyperspeedHarness(extraOptions) {
  const timers = [];
  const cleared = [];
  const changes = [];
  let visibilityHandler = null;
  let shuffleCount = 0;
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
  const options = Object.assign({
    shuffle: function () { shuffleCount += 1; },
    intervalMs: 100,
    visibilityTarget: document,
    onChange: function (enabled) { changes.push(enabled); },
  }, extraOptions || {});
  return {
    controller: window.BCHyperspeed.create(options),
    timers: timers,
    cleared: cleared,
    changes: changes,
    document: document,
    shuffleCount: function () { return shuffleCount; },
    hasVisibilityHandler: function () { return Boolean(visibilityHandler); },
    hide: function () {
      document.hidden = true;
      if (visibilityHandler) visibilityHandler();
    },
  };
}

test('hyperspeed toggles exactly one scheduler', function () {
  const harness = createHyperspeedHarness();

  assert.equal(harness.controller.toggle(), true);
  assert.equal(harness.shuffleCount(), 1);
  assert.equal(harness.timers.length, 1);
  assert.equal(harness.timers[0].interval, 100);
  harness.timers[0].callback();
  assert.equal(harness.shuffleCount(), 2);

  assert.equal(harness.controller.toggle(), false);
  assert.deepEqual(harness.changes, [true, false]);
  assert.deepEqual(harness.cleared, [harness.timers[0]]);
});

test('hyperspeed keeps running while the page is hidden by default', function () {
  const harness = createHyperspeedHarness();

  harness.controller.toggle();
  harness.hide();

  // The render driver keeps producing frames while hidden, so hyperspeed has
  // no reason to switch itself off any more.
  assert.equal(harness.controller.isEnabled(), true);
  assert.deepEqual(harness.changes, [true]);
  assert.deepEqual(harness.cleared, []);
  assert.equal(harness.hasVisibilityHandler(), false, 'no listener is attached at all');

  harness.timers[0].callback();
  assert.equal(harness.shuffleCount(), 2, 'and it keeps shuffling');
});

test('hyperspeed still stops on hide when pauseWhenHidden is requested', function () {
  const harness = createHyperspeedHarness({ pauseWhenHidden: true });

  assert.equal(harness.controller.toggle(), true);
  assert.equal(harness.shuffleCount(), 1);
  harness.timers[0].callback();
  assert.equal(harness.shuffleCount(), 2);

  harness.hide();
  assert.equal(harness.controller.isEnabled(), false);
  assert.deepEqual(harness.changes, [true, false]);
  assert.deepEqual(harness.cleared, [harness.timers[0]]);
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

function createFullscreenHarness(vizOverrides, options) {
  const opts = options || {};
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
    body: { classList: bodyClassList, appendChild: function () {} },
    documentElement: {},
    fullscreenElement: null,
    createElement: function () {
      return {
        className: '', textContent: '', hidden: false,
        appendChild: function (child) { return child; },
        setAttribute: function () {},
      };
    },
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
  // Real diagnostics module, so the I key and the ?diag/?guard flags are
  // exercised against the code the pages actually load.
  loadScript('src/js/diagnostics.js', window);
  let armed = false;
  const viz = Object.assign({
    keys: function () { return ['preset']; },
    diagnostics: function () { return { armed: armed }; },
    isAudioGuardArmed: function () { return armed; },
    setAudioGuard: function (next) { armed = Boolean(next); return armed; },
    toggleAudioGuard: function () { armed = !armed; return armed; },
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
    location: { search: opts.search || '' },
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

test('fullscreen A arms and disarms the audio guard', function () {
  const harness = createFullscreenHarness();

  assert.equal(harness.viz.isAudioGuardArmed(), false, 'disarmed until asked');

  harness.listeners.keydown.forEach(function (handler) {
    handler({ key: 'a', preventDefault: function () {} });
  });
  assert.equal(harness.viz.isAudioGuardArmed(), true);

  harness.listeners.keydown.forEach(function (handler) {
    handler({ key: 'A', preventDefault: function () {} });
  });
  assert.equal(harness.viz.isAudioGuardArmed(), false);
});

test('fullscreen ?guard=1 pre-arms the audio guard at load', function () {
  const armed = createFullscreenHarness(null, { search: '?guard=1' });
  assert.equal(armed.viz.isAudioGuardArmed(), true);

  const plain = createFullscreenHarness(null, { search: '?diag=1' });
  assert.equal(plain.viz.isAudioGuardArmed(), false);
});

test('fullscreen keyboard help prevents wrapping shortcut key combinations', function () {
  const css = fs.readFileSync('src/css/fullscreen.css', 'utf8');
  const html = fs.readFileSync('src/fullscreen.html', 'utf8');

  assert.match(
    html,
    /<td class="k"><kbd>Space<\/kbd> \/ <kbd>N<\/kbd><\/td>/,
    'fullscreen markup defines the Space / N shortcut in a key cell'
  );
  assert.match(
    css,
    /#help td\.k\s*\{[^}]*white-space:\s*nowrap/m,
    'fullscreen stylesheet prevents keyboard shortcut columns from wrapping to multiple lines'
  );
});

