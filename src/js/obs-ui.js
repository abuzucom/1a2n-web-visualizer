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

  function setStatus(msg) { statusEl.textContent = msg; }

  const viz = BCViz.create(canvas, {
    onToast: setStatus,
    onPreset: function (i) { presetEl.value = i; },
    cycleSecs: parseInt(secsEl.value, 10) || 20,
    cycleOn: cycleEl.checked
  });

  // Populate preset dropdown
  const keys = viz.keys();
  if (keys.length) {
    keys.forEach(function (name, i) {
      const o = document.createElement('option');
      o.value = i; o.textContent = name;
      presetEl.appendChild(o);
    });
  } else {
    setStatus('\u26A0 Preset library failed to load.');
  }

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
  presetEl.addEventListener('change', function () { viz.goto(parseInt(presetEl.value, 10)); });
  deviceEl.addEventListener('change', function () {
    if (viz.isStarted() && deviceEl.value) viz.useDeviceById(deviceEl.value);
  });
  cycleEl.addEventListener('change', function () {
    if (cycleEl.checked !== viz.isCycling()) viz.toggleCycle();
  });
  secsEl.addEventListener('change', function () {
    secsEl.value = viz.setCycleSecs(parseInt(secsEl.value, 10));
  });

  document.addEventListener('keydown', function (e) {
    const tag = e.target.tagName;
    if (tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA') return;
    if (e.key.toLowerCase() === 'h') panel.classList.toggle('hidden');
  });

  // Try to list devices early (labels only appear after permission on Start)
  if (navigator.mediaDevices) viz.getDevices().then(refreshDeviceList);
  setStatus('Pick an input (or just hit Start for the default), then Start.');
})();
