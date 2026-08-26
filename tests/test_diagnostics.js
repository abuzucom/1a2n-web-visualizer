const assert = require('node:assert/strict');
const fs = require('node:fs');
const test = require('node:test');
const vm = require('node:vm');

function loadScript(path, window) {
  const source = fs.readFileSync(path, 'utf8');
  vm.runInNewContext(source, { window: window, console: console });
}

function createElement(tag) {
  const element = {
    tag: tag,
    className: '',
    textContent: '',
    hidden: false,
    children: [],
    appendChild: function (child) { element.children.push(child); return child; },
    setAttribute: function (name, value) { element[name] = value; },
  };
  return element;
}

function collectText(element, found) {
  found.push(element.textContent);
  element.children.forEach(function (child) { collectText(child, found); });
  return found;
}

function createHarness(stats) {
  const body = createElement('body');
  const timers = [];
  const document = { body: body, createElement: createElement };
  const window = {
    setInterval: function (callback, delay) {
      const timer = { callback: callback, delay: delay };
      timers.push(timer);
      return timer;
    },
    clearInterval: function (timer) {
      const index = timers.indexOf(timer);
      if (index >= 0) timers.splice(index, 1);
    },
  };
  loadScript('src/js/diagnostics.js', window);
  const current = { stats: stats };
  const overlay = window.BCDiagnostics.create({
    window: window,
    document: document,
    getStats: function () { return current.stats; },
  });
  return {
    overlay: overlay,
    body: body,
    timers: timers,
    setStats: function (next) { current.stats = next; },
    text: function () { return collectText(body, []).join(' | '); },
  };
}

const BASE_STATS = {
  fps: 59,
  tickSource: 'worklet',
  hidden: true,
  wakeLock: true,
  keepalive: 'active',
  device: 'Voicemeeter Out B1',
  trackState: 'live',
  armed: true,
  recoveries: 2,
  recoverInSecs: 0,
};

test('diagnostics overlay stays out of the DOM until it is shown', function () {
  const harness = createHarness(BASE_STATS);

  assert.equal(harness.overlay.isVisible(), false);
  assert.equal(harness.body.children.length, 0);
  assert.equal(harness.timers.length, 0, 'no refresh timer while hidden');
});

test('diagnostics overlay reports every live value once shown', function () {
  const harness = createHarness(BASE_STATS);
  harness.overlay.show();

  const text = harness.text();
  assert.equal(harness.overlay.isVisible(), true);
  assert.match(text, /59/, 'fps');
  assert.match(text, /worklet/, 'tick source');
  assert.match(text, /hidden/i, 'visibility');
  assert.match(text, /Voicemeeter Out B1/, 'input device');
  assert.match(text, /live/, 'track state');
  assert.match(text, /2/, 'recovery count');
});

test('diagnostics overlay makes the guard state unmistakable', function () {
  const harness = createHarness(Object.assign({}, BASE_STATS, { armed: false }));
  harness.overlay.show();
  assert.match(harness.text(), /disarmed/i);

  harness.setStats(Object.assign({}, BASE_STATS, { armed: true }));
  harness.overlay.update();
  assert.match(harness.text(), /armed/i);
  assert.doesNotMatch(harness.text(), /disarmed/i);
});

test('diagnostics overlay surfaces the reconnect countdown only while it runs', function () {
  const harness = createHarness(BASE_STATS);
  harness.overlay.show();
  assert.doesNotMatch(harness.text(), /reconnect/i);

  harness.setStats(Object.assign({}, BASE_STATS, { recoverInSecs: 12 }));
  harness.overlay.update();
  const text = harness.text();
  assert.match(text, /reconnect/i);
  assert.match(text, /12/);
});

test('diagnostics overlay refreshes on a timer and stops when hidden', function () {
  const harness = createHarness(BASE_STATS);
  harness.overlay.show();
  assert.equal(harness.timers.length, 1);

  harness.setStats(Object.assign({}, BASE_STATS, { fps: 7 }));
  harness.timers[0].callback();
  assert.match(harness.text(), /\b7\b/);

  harness.overlay.hide();
  assert.equal(harness.overlay.isVisible(), false);
  assert.equal(harness.timers.length, 0, 'refresh timer released');
});

test('diagnostics overlay toggles and reuses one root element', function () {
  const harness = createHarness(BASE_STATS);

  assert.equal(harness.overlay.toggle(), true);
  assert.equal(harness.body.children.length, 1);
  assert.equal(harness.overlay.toggle(), false);
  assert.equal(harness.overlay.toggle(), true);
  assert.equal(harness.body.children.length, 1, 'the overlay is built once');
});

test('query flag parsing accepts the documented forms only', function () {
  const window = { setInterval: function () {}, clearInterval: function () {} };
  loadScript('src/js/diagnostics.js', window);
  const hasFlag = window.BCDiagnostics.hasFlag;

  assert.equal(hasFlag('?diag=1', 'diag'), true);
  assert.equal(hasFlag('?a=2&diag=1', 'diag'), true);
  assert.equal(hasFlag('?diag=true', 'diag'), true);
  assert.equal(hasFlag('?diag', 'diag'), true);
  assert.equal(hasFlag('?diag=0', 'diag'), false);
  assert.equal(hasFlag('?diagnostics=1', 'diag'), false);
  assert.equal(hasFlag('?guard=1', 'diag'), false);
  assert.equal(hasFlag('', 'diag'), false);
  assert.equal(hasFlag(undefined, 'diag'), false);
});

test('query flag names are matched literally, not as patterns', function () {
  const window = { setInterval: function () {}, clearInterval: function () {} };
  loadScript('src/js/diagnostics.js', window);
  const hasFlag = window.BCDiagnostics.hasFlag;

  // hasFlag is exported, so a name carrying regex metacharacters must neither
  // widen the match nor throw on an unparseable pattern.
  assert.equal(hasFlag('?diag=1', 'd.ag'), false);
  assert.equal(hasFlag('?dxag=1', 'd.ag'), false);
  assert.equal(hasFlag('?d.ag=1', 'd.ag'), true);
  assert.equal(hasFlag('?diag=1', 'di|guard'), false);
  assert.equal(hasFlag('?diag=1', '('), false);
  assert.equal(hasFlag('?diag=1', 'diag*'), false);
  assert.equal(hasFlag('?diag=1', ''), false);
});

test('diagnostics overlay tolerates missing stats', function () {
  const harness = createHarness(null);
  harness.overlay.show();

  assert.equal(harness.overlay.isVisible(), true);
  assert.ok(harness.text().length > 0);
});

test('the demo row stays hidden until there is something to report', function () {
  const harness = createHarness({ fps: 60, device: 'Built-in Microphone' });
  harness.overlay.show();
  const rows = harness.body.children[0].children;
  const demoRow = rows.find(function (row) {
    return row.children[0].textContent === 'Demo';
  });

  assert.ok(demoRow, 'the overlay always builds the row');
  assert.equal(demoRow.hidden, true, 'it is hidden with no demo stats');

  harness.setStats({ fps: 60, device: 'Synthetic demo track', demo: 'trance 140 BPM 60%' });
  harness.overlay.update();

  assert.equal(demoRow.hidden, false);
  assert.equal(demoRow.children[1].textContent, 'trance 140 BPM 60%');
});
