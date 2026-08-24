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

  const deviceErrors = window.BCDeviceErrors;
  const audioPrefs = window.BCAudioPrefs;

  function setStatus(msg) { statusEl.textContent = msg; }

  function reportDeviceError(error) {
    setStatus('Audio device error: ' + deviceErrors.describe(error));
  }

  function labelFor(deviceId) {
    const match = viz.listDevices().find(function (d) { return d.deviceId === deviceId; });
    return match ? (match.label || '') : '';
  }

  /* An OBS browser source is rebuilt from scratch on a scene refresh, so
   * without this the operator's input is replaced by the OS default every
   * time the source reloads. */
  function rememberCurrentDevice() {
    const deviceId = viz.currentDeviceId();
    if (deviceId) audioPrefs.write(deviceId, labelFor(deviceId));
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
    // Show whichever input is actually connected. Rebuilding the options
    // otherwise leaves the dropdown on the first one, claiming a device that
    // may not be the one feeding the visualizer.
    const live = viz.currentDeviceId();
    if (live) deviceEl.value = live;
  }

  /* Before permission is granted every enumerated label is blank, so a saved
   * device can only be matched by id here. The second pass after the stream
   * opens is what recovers a device whose id changed, by label. */
  function requestedDeviceId() {
    if (deviceEl.value) return deviceEl.value;
    return audioPrefs.resolve(viz.listDevices(), audioPrefs.read()) || undefined;
  }

  async function reselectSavedDevice(requested) {
    const saved = audioPrefs.read();
    const wanted = audioPrefs.resolve(viz.listDevices(), saved);
    if (!wanted || wanted === requested || wanted === viz.currentDeviceId()) return;
    await viz.useDeviceById(wanted);
    refreshDeviceList();
  }

  function switchToSelectedDevice() {
    return viz.useDeviceById(deviceEl.value)
      .then(function (device) {
        deviceEl.value = viz.currentDeviceId();
        // useDeviceById resolves with null for an id that is no longer in the
        // device list, so without this the dropdown would just spring back
        // with no explanation.
        if (!device) {
          setStatus('That input is no longer present. Re-open the picker to rescan.');
          return;
        }
        rememberCurrentDevice();
      })
      .catch(function (error) {
        // deviceIdx is only committed on a successful switch, and the failed
        // attempt restored the stream that was already playing, so this is
        // the input actually connected. Reverting the dropdown to it keeps
        // the UI from claiming a switch that did not happen.
        deviceEl.value = viz.currentDeviceId();
        reportDeviceError(error);
      });
  }

  async function start() {
    try {
      const requested = requestedDeviceId();
      await viz.start(requested);
      refreshDeviceList();
      await reselectSavedDevice(requested);
      rememberCurrentDevice();
      setStatus('\u25B6 Running. Press H to hide this panel.');
    } catch (e) {
      setStatus('Audio error: ' + deviceErrors.describe(e));
    }
  }

  document.getElementById('startBtn').addEventListener('click', start);
  document.getElementById('nextBtn').addEventListener('click', function () { viz.next(); });
  document.getElementById('prevBtn').addEventListener('click', function () { viz.prev(); });
  document.getElementById('randBtn').addEventListener('click', function () { viz.random(); });
  presetEl.addEventListener('change', function () { viz.goto(parseInt(presetEl.value, RADIX_DECIMAL)); });
  deviceEl.addEventListener('change', function () {
    if (!deviceEl.value) return;
    if (!viz.isStarted()) {
      setStatus('Input selected. Press Start to use it.');
      return;
    }
    switchToSelectedDevice();
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
