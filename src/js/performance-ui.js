/* performance-ui.js - keyboard-only wiring for performance.html */
(function () {
  'use strict';

  const canvas = document.getElementById('viz');
  const toast = document.getElementById('toast');
  const help = document.getElementById('help');
  const startPrompt = document.getElementById('startPrompt');
  const startError = document.getElementById('startError');

  const MAX_TOAST_LENGTH = 60;
  const TRUNCATED_TOAST_LENGTH = 57;
  const TOAST_DURATION_MS = 2400;
  const TEXT_ENTRY_TAGS = ['INPUT', 'TEXTAREA', 'SELECT'];
  const ACTIVATION_TAGS = ['BUTTON', 'A', 'SUMMARY'];

  let toastTimer = null;
  let startupPending = false;

  function say(msg) {
    const text = msg.length > MAX_TOAST_LENGTH ? msg.slice(0, TRUNCATED_TOAST_LENGTH) + '\u2026' : msg;
    toast.textContent = text;
    toast.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { toast.classList.remove('show'); }, TOAST_DURATION_MS);
  }

  /* Both globals arrive as separate deferred scripts, so the pages' script
   * order is what makes them present. */
  function describeDeviceError(error) {
    const errors = window.BCDeviceErrors;
    if (errors && typeof errors.describe === 'function') return errors.describe(error);
    return (error && error.name ? error.name + ': ' : '') + ((error && error.message) || String(error));
  }

  const NO_PREFS = {
    read: function () { return null; },
    write: function () { return false; },
    clear: function () {},
    resolve: function () { return ''; },
  };
  const audioPrefs = window.BCAudioPrefs || NO_PREFS;

  const viz = BCViz.create(canvas, {
    onToast: say, cycleSecs: 20, cycleOn: false, shuffle: false, randomFirst: true,
  });

  const energyCatalog = window.BCEnergyCatalog || { presets: {} };
  const performanceCatalog = window.BCPerformanceCatalog || { presets: [] };

  /* The runtime knows presets by name. A catalog entry names its preset as
   * pack and name, so the catalog maps onto the runtime by name. */
  function idName(identifier) {
    const separator = identifier.indexOf(':');
    return separator === -1 ? identifier : identifier.slice(separator + 1);
  }

  function buildEnergyByName() {
    const byName = new Map();
    const presets = energyCatalog.presets || {};
    Object.keys(presets).forEach(function (identifier) {
      byName.set(idName(identifier), presets[identifier]);
    });
    return byName;
  }

  function buildMemberNames() {
    const names = new Set();
    (performanceCatalog.presets || []).forEach(function (identifier) {
      names.add(idName(identifier));
    });
    return names;
  }

  function buildRuntimeIndex() {
    const index = new Map();
    viz.keys().forEach(function (name, position) { index.set(name, position); });
    return index;
  }

  const energyByName = buildEnergyByName();
  const memberNames = buildMemberNames();
  const runtimeIndex = buildRuntimeIndex();
  const cycles = new Map();

  /* Only curated presets that carry the pressed category can play. */
  function eligibleNames(category) {
    const names = [];
    memberNames.forEach(function (name) {
      if (energyByName.get(name) !== category) return;
      if (!runtimeIndex.has(name)) return;
      names.push(name);
    });
    return names;
  }

  function shuffled(list) {
    const order = list.slice();
    for (let index = order.length - 1; index > 0; index -= 1) {
      const other = Math.floor(Math.random() * (index + 1));
      const swap = order[index];
      order[index] = order[other];
      order[other] = swap;
    }
    return order;
  }

  function sameOrder(left, right) {
    if (left.length !== right.length) return false;
    for (let index = 0; index < left.length; index += 1) {
      if (left[index] !== right[index]) return false;
    }
    return true;
  }

  /* A cycle plays every eligible preset once. The next cycle is shuffled
   * into an order that differs from the one before it. */
  function buildCycle(category, eligible) {
    const order = shuffled(eligible);
    const previous = cycles.get(category);
    if (previous && previous.order.length > 1 && sameOrder(order, previous.order)) {
      order.push(order.shift());
    }
    return { order: order, position: 0 };
  }

  function playCategory(category) {
    const eligible = eligibleNames(category);
    if (!eligible.length) {
      say('No ' + category + ' presets are curated yet');
      return;
    }
    let cycle = cycles.get(category);
    if (!cycle || cycle.position >= cycle.order.length) {
      cycle = buildCycle(category, eligible);
      cycles.set(category, cycle);
    }
    const name = cycle.order[cycle.position];
    cycle.position += 1;
    const index = runtimeIndex.get(name);
    if (index === undefined) return;
    viz.goto(index);
    say(category + ': ' + name);
  }

  async function start() {
    if (viz.isStarted() || startupPending) return;
    startupPending = true;
    startError.textContent = '';
    try {
      await viz.start(audioPrefs.resolve(viz.listDevices(), audioPrefs.read()) || undefined);
      startPrompt.hidden = true;
      help.classList.add('hidden');
      document.body.classList.add('running');
      say('\u25B6 Running \u2014 press 7, 8 or 9');
    } catch (error) {
      startError.textContent = 'Audio error: ' + describeDeviceError(error);
      say('Audio error: ' + describeDeviceError(error));
    } finally {
      startupPending = false;
    }
  }

  /* Shortcuts must not steal keys that the focused element handles natively. */
  function shouldIgnoreShortcut(e) {
    if (e.ctrlKey || e.metaKey || e.altKey) return true;
    const target = e.target;
    if (!target || !target.tagName) return false;
    if (TEXT_ENTRY_TAGS.indexOf(target.tagName) !== -1 || target.isContentEditable) {
      return e.key !== 'Escape';
    }
    if (ACTIVATION_TAGS.indexOf(target.tagName) !== -1) {
      return e.key === ' ' || e.key === 'Enter';
    }
    return false;
  }

  document.addEventListener('keydown', function (e) {
    if (shouldIgnoreShortcut(e)) return;
    if (!viz.isStarted()) {
      if (e.key.length === 1 || e.key === 'Enter') start();
      return;
    }
    switch (e.key) {
      case '7': playCategory('low'); break;
      case '8': playCategory('medium'); break;
      case '9': playCategory('high'); break;
      case '?': help.classList.toggle('hidden'); break;
    }
  });
  document.addEventListener('click', function () { if (!viz.isStarted()) start(); });

  if (!viz.keys().length) say('\u26A0 Preset library failed to load');
})();
