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
    body: {
      classList: bodyClassList,
      appendChild: function () {},
      getAttribute: function (name) {
        return name === 'data-demo' && opts.demo ? '1' : null;
      },
    },
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
  const captured = { opts: null };
  let demoTempo = 140;
  let demoIntensity = 0.6;
  let demoCycles = 0;
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
    isDemo: function () { return Boolean(opts.demo); },
    getDemoTempo: function () { return demoTempo; },
    setDemoTempo: function (bpm) { demoTempo = bpm; return demoTempo; },
    cycleDemoTempo: function () { demoCycles += 1; demoTempo = 87; return demoTempo; },
    getDemoIntensity: function () { return demoIntensity; },
    setDemoIntensity: function (value) { demoIntensity = value; return demoIntensity; },
  }, vizOverrides || {});
  const context = {
    window: window,
    document: document,
    navigator: {},
    location: { search: opts.search || '' },
    BCViz: {
      create: function (canvas, createOpts) {
        captured.opts = createOpts;
        return viz;
      },
    },
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
    demoTempo: function () { return demoTempo; },
    demoIntensity: function () { return demoIntensity; },
    demoCycles: function () { return demoCycles; },
    createOpts: function () { return captured.opts; },
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
  const fullscreenHtml = fs.readFileSync('src/fullscreen.html', 'utf8');
  const demoHtml = fs.readFileSync('src/demo.html', 'utf8');

  assert.match(
    fullscreenHtml,
    /<td class="k"><kbd>Space<\/kbd> \/ <kbd>N<\/kbd><\/td>/,
    'fullscreen markup defines the Space / N shortcut in a key cell'
  );
  assert.match(
    demoHtml,
    /<td class="k"><kbd>Space<\/kbd> \/ <kbd>N<\/kbd><\/td>/,
    'demo markup defines the Space / N shortcut in a key cell'
  );
  assert.match(
    css,
    /#help td\.k\s*\{[^}]*white-space:\s*nowrap/m,
    'fullscreen stylesheet prevents keyboard shortcut columns from wrapping to multiple lines'
  );
});

function pressKeys(harness, keys) {
  keys.forEach(function (key) {
    harness.listeners.keydown.forEach(function (handler) {
      handler({ key: key, repeat: false, preventDefault: function () {} });
    });
  });
}

test('demo keys change genre, tempo and intensity on the demo build', function () {
  const harness = createFullscreenHarness({
    diagnostics: function () { return { armed: false, demo: 'house 87 BPM 60%' }; },
  }, { demo: true });

  pressKeys(harness, ['B']);
  assert.equal(harness.demoCycles(), 1, 'B cycles the genre');

  pressKeys(harness, ['.', '.']);
  assert.equal(harness.demoTempo(), 95, 'two nudges up move tempo by 8 BPM');
  pressKeys(harness, [',']);
  assert.equal(harness.demoTempo(), 91);

  pressKeys(harness, ['=']);
  assert.ok(harness.demoIntensity() > 0.6, '= raises intensity');
  pressKeys(harness, ['-', '-']);
  assert.ok(harness.demoIntensity() < 0.6, '- lowers it again');
});

test('shifted demo keys work without checking the modifier', function () {
  const harness = createFullscreenHarness({
    diagnostics: function () { return { armed: false, demo: 'trance 140 BPM 60%' }; },
  }, { demo: true });

  pressKeys(harness, ['>']);
  assert.equal(harness.demoTempo(), 144);
  pressKeys(harness, ['<']);
  assert.equal(harness.demoTempo(), 140);
  pressKeys(harness, ['+']);
  assert.ok(harness.demoIntensity() > 0.6);
  pressKeys(harness, ['_']);
  assert.ok(Math.abs(harness.demoIntensity() - 0.6) < 1e-9);
});

test('demo keys are inert on the ordinary fullscreen build', function () {
  const harness = createFullscreenHarness();

  pressKeys(harness, ['B', '.', ',', '=', '-']);

  assert.equal(harness.demoCycles(), 0);
  assert.equal(harness.demoTempo(), 140, 'tempo is untouched without demo mode');
  assert.equal(harness.demoIntensity(), 0.6);
});

test('D reports demo mode instead of switching devices', function () {
  let deviceCalls = 0;
  const harness = createFullscreenHarness({
    nextDevice: function () { deviceCalls += 1; return Promise.resolve(); },
    diagnostics: function () { return { armed: false, demo: 'trance 140 BPM 60%' }; },
  }, { demo: true });

  pressKeys(harness, ['D']);
  assert.equal(deviceCalls, 0, 'the demo build never asks for another device');

  const plain = createFullscreenHarness({
    nextDevice: function () { deviceCalls += 1; return Promise.resolve(); },
  });
  pressKeys(plain, ['D']);
  assert.equal(deviceCalls, 1, 'the fullscreen build still switches devices');
});

test('?demo=1 turns the fullscreen page into the demo build', function () {
  const flagged = createFullscreenHarness({}, { search: '?demo=1' });
  assert.equal(flagged.createOpts().demo, true, 'the query flag switches the build');

  const attributed = createFullscreenHarness({}, { demo: true });
  assert.equal(attributed.createOpts().demo, true, 'so does data-demo on the body');

  const plain = createFullscreenHarness();
  assert.equal(plain.createOpts().demo, false, 'and the plain page is unchanged');
});

