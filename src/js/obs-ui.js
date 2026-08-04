/* obs-ui.js - control-panel wiring for obs.html */
(function () {
  'use strict';

  const canvas   = document.getElementById('viz');
  const panel    = document.getElementById('panel');
  const deviceEl = document.getElementById('device');
  const presetEl = document.getElementById('preset');
  const statusEl = document.getElementById('status');
  const cycleEl  = document.getElementById('cycle');
  const secsEl   = document.getElementById('cycleSecs');
  const guardEl  = document.getElementById('audioGuard');

  function setStatus(msg) { statusEl.textContent = msg; }

  /** Turns a getUserMedia error into a short, actionable hint keyed on name,
   * so "Could not start audio source" points at the fix instead of just the
   * symptom. See docs/unattended-operation.md for the full explanation. */
  function describeDeviceError(error) {
    const name = error && error.name;
    const message = (error && error.message) || String(error);
    let hint = '';
    if (name === 'NotReadableError' || name === 'AbortError') {
      hint = ' (device may be exclusively locked by another app)';
    } else if (name === 'NotFoundError') {
      hint = ' (device appears to be unplugged or disabled)';
    } else if (name === 'OverconstrainedError') {
      hint = ' (device id no longer valid; re-select an input)';
    }
    return (name ? name + ': ' : '') + message + hint;
  }

  function reportDeviceError(error) {
    setStatus('Audio device error: ' + describeDeviceError(error));
  }

  const DEFAULT_CYCLE_SECS = 20;
  const FILTER_DEBOUNCE_MS = 150;
  const RADIX_DECIMAL = 10;

  const viz = BCViz.create(canvas, {
    onToast: setStatus,
    onPreset: function (i) { presetEl.value = i; },
    cycleSecs: parseInt(secsEl.value, RADIX_DECIMAL) || DEFAULT_CYCLE_SECS,
    cycleOn: cycleEl.checked
  });

  const diagnostics = window.BCDiagnostics.create({
    window: window,
    document: document,
    getStats: function () { return viz.diagnostics(); },
  });
  if (window.BCDiagnostics.hasFlag(location.search, 'diag')) diagnostics.show();

  /** Keep the checkbox, the A key and the visualizer in agreement. */
  function setAudioGuard(armed) {
    const next = viz.setAudioGuard(armed);
    guardEl.checked = next;
    setStatus(next
      ? 'Audio guard armed: a lost input is reconnected after 20s.'
      : 'Audio guard disarmed: the input is left alone.');
    return next;
  }

  if (window.BCDiagnostics.hasFlag(location.search, 'guard')) setAudioGuard(true);

  // Populate preset dropdown. With the extra collection this is 15k+
  // entries, so build the options off-DOM and offer a text filter.
  const keys = viz.keys();
  const filterEl = document.getElementById('presetFilter');

  function rebuildPresetList() {
    const needle = (filterEl.value || '').toLowerCase();
    const frag = document.createDocumentFragment();
    keys.forEach(function (name, i) {
      if (needle && name.toLowerCase().indexOf(needle) === -1) return;
      const o = document.createElement('option');
      o.value = i; o.textContent = name;
      frag.appendChild(o);
    });
    presetEl.innerHTML = '';
    presetEl.appendChild(frag);
    // Re-select the current preset; if it's filtered out the select just
    // shows no selection, which is fine.
    presetEl.value = String(viz.currentIndex());
  }

  if (keys.length) {
    rebuildPresetList();
  } else {
    setStatus('\u26A0 Preset library failed to load.');
  }

  let filterTimer = null;
  filterEl.addEventListener('input', function () {
    clearTimeout(filterTimer);
    filterTimer = setTimeout(rebuildPresetList, FILTER_DEBOUNCE_MS);
  });

  function refreshDeviceList() {
    const inputs = viz.listDevices();
    deviceEl.innerHTML = '';
    inputs.forEach(function (d, i) {
      const o = document.createElement('option');
      o.value = d.deviceId;
      o.textContent = d.label || ('Input ' + (i + 1));
      deviceEl.appendChild(o);
    });
    if (!inputs.length) {
      const o = document.createElement('option');
      o.value = ''; o.textContent = '\u2014 grant mic access first \u2014';
      deviceEl.appendChild(o);
    }
  }

  async function start() {
    try {
      await viz.start(deviceEl.value || undefined);
      refreshDeviceList();
      setStatus('\u25B6 Running. Press H to hide this panel.');
    } catch (e) {
      setStatus('Audio error: ' + e.message);
    }
  }

  document.getElementById('startBtn').addEventListener('click', start);
  document.getElementById('nextBtn').addEventListener('click', function () { viz.next(); });
  document.getElementById('prevBtn').addEventListener('click', function () { viz.prev(); });
  document.getElementById('randBtn').addEventListener('click', function () { viz.random(); });
  presetEl.addEventListener('change', function () { viz.goto(parseInt(presetEl.value, RADIX_DECIMAL)); });
  deviceEl.addEventListener('change', function () {
    if (viz.isStarted() && deviceEl.value) {
      viz.useDeviceById(deviceEl.value)
        .then(function () { deviceEl.value = viz.currentDeviceId(); })
        .catch(function (error) {
          // deviceIdx is only committed on a successful switch, so this is
          // the previously selected device, not one that is actually
          // connected: the failed attempt already released that stream.
          // Reverting the dropdown to it, rather than leaving it on the
          // device that failed to open, keeps the UI from claiming a switch
          // that did not happen.
          deviceEl.value = viz.currentDeviceId();
          reportDeviceError(error);
        });
    }
  });
  cycleEl.addEventListener('change', function () {
    if (cycleEl.checked !== viz.isCycling()) viz.toggleCycle();
  });
  guardEl.addEventListener('change', function () { setAudioGuard(guardEl.checked); });
  secsEl.addEventListener('change', function () {
    secsEl.value = viz.setCycleSecs(parseInt(secsEl.value, RADIX_DECIMAL));
  });

  document.addEventListener('keydown', function (e) {
    const tag = e.target.tagName;
    if (tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA') return;
    if (e.key.toLowerCase() === 'h') panel.classList.toggle('hidden');
    if (e.key.toLowerCase() === 'a') setAudioGuard(!viz.isAudioGuardArmed());
    if (e.key.toLowerCase() === 'i') diagnostics.toggle();
  });

  // Try to list devices early (labels only appear after permission on Start)
  if (navigator.mediaDevices) {
    viz.getDevices().then(refreshDeviceList).catch(reportDeviceError);
  }
  setStatus(keys.length + ' presets. Pick an input (or just hit Start for the default).');
})();
