/* Accessibility regressions: keyboard startup, focus handling for hidden
 * panels, shortcut scoping, live regions, field labels, and text contrast. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const test = require('node:test');
const vm = require('node:vm');

const MIN_TEXT_CONTRAST = 4.5;

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
    disabled: false,
    focusCount: 0,
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
    contains: function (other) { return other === element || element.children.indexOf(other) !== -1; },
    focus: function () { element.focusCount += 1; },
    select: function () {},
  };
  return element;
}

function createTimers() {
  let nextId = 1;
  const pending = new Map();
  return {
    setTimeout: function (callback) {
      const timerId = nextId;
      nextId += 1;
      pending.set(timerId, callback);
      return timerId;
    },
    clearTimeout: function (timerId) { pending.delete(timerId); },
    setInterval: function () { return 0; },
    clearInterval: function () {},
    runAll: function () {
      const callbacks = Array.from(pending.values());
      pending.clear();
      callbacks.forEach(function (callback) { callback(); });
    },
  };
}

function createDocument(elements, bodyAttributes) {
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
  document.body.getAttribute = function (name) {
    return bodyAttributes && Object.prototype.hasOwnProperty.call(bodyAttributes, name)
      ? bodyAttributes[name] : null;
  };
  document.activeElement = document.body;
  return document;
}

function createMobileHarness(vizOverrides) {
  const ids = [
    'viz', 'toast', 'help', 'startPrompt', 'startupStatus', 'startError', 'controls',
    'shuffleBtn', 'backBtn', 'intervalBtn', 'intervalValue', 'hyperspeedBtn', 'hyperspeedValue',
  ];
  const buttonIds = ['startPrompt', 'shuffleBtn', 'backBtn', 'intervalBtn', 'hyperspeedBtn'];
  const elements = {};
  ids.forEach(function (id) {
    elements[id] = createElement(id, buttonIds.indexOf(id) === -1 ? 'DIV' : 'BUTTON');
  });
  ['shuffleBtn', 'backBtn', 'intervalBtn', 'hyperspeedBtn'].forEach(function (id) {
    elements.controls.appendChild(elements[id]);
  });
  elements.controls.inert = true;
  const document = createDocument(elements);
  const timers = createTimers();
  const state = { started: false, startCalls: 0 };
  const window = {
    setTimeout: timers.setTimeout,
    clearTimeout: timers.clearTimeout,
    setInterval: timers.setInterval,
    clearInterval: timers.clearInterval,
  };
  ['src/js/mobile-state.js', 'src/js/hyperspeed.js', 'src/js/diagnostics.js'].forEach(function (path) {
    vm.runInNewContext(readSource(path), { window: window });
  });
  const viz = Object.assign({
    keys: function () { return ['preset']; },
    isStarted: function () { return state.started; },
    start: function () {
      state.startCalls += 1;
      state.started = true;
      return Promise.resolve();
    },
    random: function () {},
    goto: function () {},
    setCycleSecs: function (seconds) { return seconds; },
    setAudioGuard: function () { return false; },
    diagnostics: function () { return {}; },
    resize: function () {},
  }, vizOverrides || {});
  const context = {
    window: window,
    document: document,
    location: { search: '' },
    BCViz: { create: function () { return viz; } },
    setTimeout: timers.setTimeout,
    clearTimeout: timers.clearTimeout,
    console: console,
  };
  vm.runInNewContext(readSource('src/js/mobile-ui.js'), context);
  return { elements: elements, document: document, timers: timers, state: state };
}

function flushPromises() {
  return new Promise(function (resolve) { setImmediate(resolve); });
}

test('mobile start prompt is a native button', function () {
  const html = readSource('src/mobile.html');
  assert.match(html, /<button[^>]*id="startPrompt"[^>]*>/);
  assert.match(html, /<button[^>]*type="button"[^>]*id="startPrompt"|<button[^>]*id="startPrompt"[^>]*type="button"/);
});

test('mobile start button click starts the visualizer and unlocks the controls', async function () {
  const harness = createMobileHarness();

  harness.elements.startPrompt.dispatch('click');
  await flushPromises();

  assert.equal(harness.state.startCalls, 1);
  assert.equal(harness.elements.controls.inert, false);
  assert.equal(harness.elements.help.inert, true);
});

test('mobile start failure leaves a persistent error message', async function () {
  const harness = createMobileHarness({
    start: function () { return Promise.reject(new Error('Permission denied')); },
  });

  harness.elements.startPrompt.dispatch('click');
  await flushPromises();

  assert.match(harness.elements.startError.textContent, /Permission denied/);
  assert.equal(harness.elements.controls.inert, true);
});

test('mobile controls wake on focus and stay visible while focus is inside', async function () {
  const harness = createMobileHarness();
  harness.elements.startPrompt.dispatch('click');
  await flushPromises();
  harness.timers.runAll();
  assert.equal(harness.document.body.classList.contains('controls-idle'), true);

  harness.document.activeElement = harness.elements.shuffleBtn;
  harness.elements.controls.dispatch('focusin', { target: harness.elements.shuffleBtn });
  assert.equal(harness.document.body.classList.contains('controls-idle'), false);

  harness.timers.runAll();
  assert.equal(harness.document.body.classList.contains('controls-idle'), false);
});

test('mobile controls wake on keyboard interaction', async function () {
  const harness = createMobileHarness();
  harness.elements.startPrompt.dispatch('click');
  await flushPromises();
  harness.timers.runAll();
  assert.equal(harness.document.body.classList.contains('controls-idle'), true);

  harness.document.dispatch('keydown', { key: 'Tab' });
  assert.equal(harness.document.body.classList.contains('controls-idle'), false);
});

function createFullscreenHarness(vizOverrides) {
  const ids = [
    'viz', 'toast', 'help', 'startPrompt', 'startupStatus', 'startupStatusText', 'startupProgressBar',
    'startError', 'removeBtn', 'excludedBtn', 'excludedPanel', 'excludedList', 'copyExcludedBtn',
    'closeExcludedBtn', 'favoriteBtn', 'favoritesBtn', 'favoritesPanel', 'favoritesListText',
    'copyFavoritesBtn', 'closeFavoritesBtn',
  ];
  const tags = {
    removeBtn: 'BUTTON', excludedBtn: 'BUTTON', favoriteBtn: 'BUTTON', favoritesBtn: 'BUTTON',
    copyExcludedBtn: 'BUTTON', closeExcludedBtn: 'BUTTON', copyFavoritesBtn: 'BUTTON',
    closeFavoritesBtn: 'BUTTON', excludedList: 'TEXTAREA', favoritesListText: 'TEXTAREA',
  };
  const elements = {};
  ids.forEach(function (id) { elements[id] = createElement(id, tags[id]); });
  ['excludedPanel', 'favoritesPanel'].forEach(function (id) {
    elements[id].classList.add('hidden');
    elements[id].inert = true;
  });
  const document = createDocument(elements);
  const timers = createTimers();
  const calls = { next: 0, random: 0 };
  const window = {
    BCHyperspeed: { create: function () { return { toggle: function () { return true; } }; } },
    setTimeout: timers.setTimeout,
    clearTimeout: timers.clearTimeout,
    setInterval: timers.setInterval,
    clearInterval: timers.clearInterval,
  };
  vm.runInNewContext(readSource('src/js/diagnostics.js'), { window: window });
  const viz = Object.assign({
    keys: function () { return ['preset']; },
    isStarted: function () { return true; },
    next: function () { calls.next += 1; },
    prev: function () {},
    random: function () { calls.random += 1; },
    excludedList: function () { return ['a']; },
    favoritesList: function () { return ['b']; },
    diagnostics: function () { return {}; },
    setAudioGuard: function () { return false; },
    isDemo: function () { return false; },
  }, vizOverrides || {});
  const context = {
    window: window,
    document: document,
    navigator: {},
    location: { search: '' },
    BCViz: { create: function () { return viz; } },
    setTimeout: timers.setTimeout,
    clearTimeout: timers.clearTimeout,
    console: console,
  };
  vm.runInNewContext(readSource('src/js/fullscreen-ui.js'), context);
  return { elements: elements, document: document, calls: calls };
}

test('Space on a focused button keeps native activation', function () {
  const harness = createFullscreenHarness();

  const evt = harness.document.dispatch('keydown', { key: ' ', target: harness.elements.favoriteBtn });

  assert.equal(harness.calls.next, 0);
  assert.equal(evt.defaultPrevented, false);
});

test('Space outside interactive elements still advances the preset', function () {
  const harness = createFullscreenHarness();

  const evt = harness.document.dispatch('keydown', { key: ' ' });

  assert.equal(harness.calls.next, 1);
  assert.equal(evt.defaultPrevented, true);
});

test('modified shortcuts are left to the browser', function () {
  const harness = createFullscreenHarness();

  harness.document.dispatch('keydown', { key: 'r', ctrlKey: true });
  harness.document.dispatch('keydown', { key: 'r', metaKey: true });
  harness.document.dispatch('keydown', { key: 'n', altKey: true });

  assert.equal(harness.calls.random, 0);
  assert.equal(harness.calls.next, 0);
});

test('letters typed in a panel textarea do not trigger shortcuts', function () {
  const harness = createFullscreenHarness();

  harness.document.dispatch('keydown', { key: 'n', target: harness.elements.excludedList });
  harness.document.dispatch('keydown', { key: ' ', target: harness.elements.excludedList });

  assert.equal(harness.calls.next, 0);
});

test('opening a list panel removes inert and Escape restores focus to the opener', function () {
  const harness = createFullscreenHarness();
  const opener = harness.elements.excludedBtn;
  harness.document.activeElement = opener;

  opener.dispatch('click');
  assert.equal(harness.elements.excludedPanel.inert, false);
  assert.equal(harness.elements.excludedPanel.classList.contains('hidden'), false);
  assert.equal(harness.elements.removeBtn.inert, true, 'background buttons leave the tab order');

  harness.document.activeElement = harness.elements.excludedList;
  harness.document.dispatch('keydown', { key: 'Escape', target: harness.elements.excludedList });

  assert.equal(harness.elements.excludedPanel.inert, true);
  assert.equal(harness.elements.excludedPanel.classList.contains('hidden'), true);
  assert.equal(harness.elements.removeBtn.inert, false);
  assert.equal(opener.focusCount, 1);
});

test('fullscreen and demo markup gives panels dialog semantics and hides them from focus', function () {
  ['src/fullscreen.html', 'src/demo.html'].forEach(function (path) {
    const html = readSource(path);
    [['excludedPanel', 'excludedTitle', 'excludedList'], ['favoritesPanel', 'favoritesTitle', 'favoritesListText']]
      .forEach(function (ids) {
        const panel = new RegExp('<div id="' + ids[0] + '"[^>]*>');
        const tag = html.match(panel);
        assert.ok(tag, path + ' defines #' + ids[0]);
        assert.match(tag[0], /role="dialog"/, path + ' #' + ids[0] + ' role');
        assert.match(tag[0], new RegExp('aria-labelledby="' + ids[1] + '"'), path + ' #' + ids[0] + ' name');
        assert.match(tag[0], /\sinert[\s>]/, path + ' #' + ids[0] + ' starts inert');
        assert.match(html, new RegExp('<h1 id="' + ids[1] + '">'), path + ' heading id');
        assert.match(html, new RegExp('<textarea id="' + ids[2] + '"[^>]*aria-labelledby="' + ids[1] + '"'),
          path + ' textarea label');
      });
    ['removeBtn', 'excludedBtn', 'favoriteBtn', 'favoritesBtn'].forEach(function (id) {
      const tag = html.match(new RegExp('<button id="' + id + '"[^>]*>'));
      assert.ok(tag, path + ' defines #' + id);
      assert.match(tag[0], /\sinert[\s>]/, path + ' #' + id + ' starts inert');
      assert.match(tag[0], /aria-label="[^"]+"/, path + ' #' + id + ' has a name');
    });
    assert.match(html, /<div id="toast"[^>]*role="status"/, path + ' toast is a live region');
    assert.match(html, /id="startError"[^>]*role="alert"/, path + ' persistent start error');
  });
});

test('OBS status is a live region and every field has a label', function () {
  const html = readSource('src/obs.html');
  assert.match(html, /<div id="status"[^>]*role="status"/);
  assert.match(html, /<label[^>]*for="presetFilter"[^>]*>[^<]+<\/label>/);
  assert.match(html, /<label[^>]*for="cycleSecs"[^>]*>[^<]*seconds[^<]*<\/label>/i);
});

test('hiding the OBS panel removes it from the tab order', function () {
  const elementIds = [
    'viz', 'panel', 'device', 'preset', 'presetFilter', 'status',
    'cycle', 'cycleSecs', 'audioGuard', 'startBtn', 'nextBtn', 'prevBtn', 'randBtn',
  ];
  const elements = {};
  elementIds.forEach(function (id) { elements[id] = createElement(id); });
  elements.cycleSecs.value = '20';
  const document = createDocument(elements);
  document.createDocumentFragment = function () { return createElement('fragment'); };
  const window = {
    setTimeout: setTimeout, clearTimeout: clearTimeout,
    setInterval: function () { return 0; }, clearInterval: function () {},
  };
  ['src/js/diagnostics.js', 'src/js/device-errors.js', 'src/js/audio-prefs.js'].forEach(function (path) {
    vm.runInNewContext(readSource(path), { window: window, console: console });
  });
  const viz = {
    keys: function () { return ['preset']; },
    currentIndex: function () { return 0; },
    diagnostics: function () { return {}; },
    setAudioGuard: function () { return false; },
    isAudioGuardArmed: function () { return false; },
  };
  vm.runInNewContext(readSource('src/js/obs-ui.js'), {
    window: window,
    document: document,
    navigator: {},
    location: { search: '' },
    BCViz: { create: function () { return viz; } },
    setTimeout: setTimeout,
    clearTimeout: clearTimeout,
    console: console,
  });

  document.dispatch('keydown', { key: 'h', target: elements.startBtn });
  assert.equal(elements.panel.classList.contains('hidden'), true);
  assert.equal(elements.panel.inert, true);

  document.dispatch('keydown', { key: 'h', target: elements.startBtn });
  assert.equal(elements.panel.inert, false);
});

function readBrandTokens() {
  const tokens = {};
  const css = readSource('src/css/brand.css');
  const pattern = /--(brand-[a-z]+):\s*(#[0-9a-f]{6})/gi;
  let match = pattern.exec(css);
  while (match) {
    tokens[match[1]] = match[2];
    match = pattern.exec(css);
  }
  return tokens;
}

function relativeLuminance(hex) {
  const channels = [1, 3, 5].map(function (offset) {
    const value = parseInt(hex.slice(offset, offset + 2), 16) / 255;
    return value <= 0.03928 ? value / 12.92 : Math.pow((value + 0.055) / 1.055, 2.4);
  });
  return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
}

function contrastRatio(first, second) {
  const lighter = Math.max(relativeLuminance(first), relativeLuminance(second));
  const darker = Math.min(relativeLuminance(first), relativeLuminance(second));
  return (lighter + 0.05) / (darker + 0.05);
}

function readRule(css, selector) {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const match = css.match(new RegExp('(?:^|\\n)' + escaped + '\\s*\\{([^}]*)\\}'));
  assert.ok(match, 'rule ' + selector + ' exists');
  return match[1];
}

function readToken(body, property, tokens) {
  const match = body.match(new RegExp('(?:^|[\\s;])' + property + ':\\s*var\\(--(brand-[a-z]+)\\)'));
  assert.ok(match, property + ' uses a brand token');
  return tokens[match[1]];
}

test('small landing and OBS text reaches 4.5:1 contrast', function () {
  const tokens = readBrandTokens();
  const landing = readSource('src/css/landing.css');
  const panel = readSource('src/css/panel.css');
  const paper = tokens['brand-paper'];
  // The OBS panel is charcoal at 96% opacity; a white preset frame behind it
  // gives the lightest composite background.
  const panelWorstCase = '#2d2d2d';

  const pairs = [
    ['p.sub', readToken(readRule(landing, 'p.sub'), 'color', tokens), paper],
    ['footer', readToken(readRule(landing, 'footer'), 'color', tokens), paper],
    ['.hint', readToken(readRule(panel, '.hint'), 'color', tokens), panelWorstCase],
  ];
  const demoCard = readRule(landing, 'a.card.demo-card');
  const demoSpan = readRule(landing, 'a.card.demo-card span');
  const demoBackground = readToken(demoCard, 'background', tokens);
  pairs.push(['demo card title', readToken(demoCard, 'color', tokens), demoBackground]);
  pairs.push(['demo card text', readToken(demoSpan, 'color', tokens), demoBackground]);

  pairs.forEach(function (pair) {
    const ratio = contrastRatio(pair[1], pair[2]);
    assert.ok(ratio >= MIN_TEXT_CONTRAST, pair[0] + ' contrast ' + ratio.toFixed(2) + ':1');
  });
});
