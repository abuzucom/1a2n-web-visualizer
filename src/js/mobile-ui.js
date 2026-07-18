(function () {
  'use strict';

  const canvas = document.getElementById('viz');
  const toast = document.getElementById('toast');
  const help = document.getElementById('help');
  const startPrompt = document.getElementById('startPrompt');
  const startupStatus = document.getElementById('startupStatus');
  const shuffleBtn = document.getElementById('shuffleBtn');
  const backBtn = document.getElementById('backBtn');
  const intervalBtn = document.getElementById('intervalBtn');
  const intervalValue = document.getElementById('intervalValue');
  const hyperspeedBtn = document.getElementById('hyperspeedBtn');
  const hyperspeedValue = document.getElementById('hyperspeedValue');
  const INTERVALS = [15, 30, 60];
  let toastTimer = null;
  let startupPending = false;
  let idleTimer = null;
  const history = window.BCMobileState.createHistory(20);
  const intervalCycle = window.BCMobileState.createIntervalCycle(INTERVALS, 1);

  function say(msg) {
    toast.textContent = msg.length > 60 ? msg.slice(0, 57) + '\u2026' : msg;
    toast.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { toast.classList.remove('show'); }, 2400);
  }

  function formatInterval(seconds) { return seconds === 60 ? '1m' : seconds + 's'; }

  function updateBackState() { backBtn.disabled = !history.canGoBack(); }

  function onPreset(index) {
    history.visit(index);
    updateBackState();
  }

  const viz = BCViz.create(canvas, {
    onToast: say,
    onPreset: onPreset,
    cycleSecs: intervalCycle.current(),
    cycleOn: true,
    shuffle: true,
    randomFirst: true,
  });

  function wakeControls() {
    if (!viz.isStarted()) return;
    document.body.classList.remove('controls-idle');
    clearTimeout(idleTimer);
    idleTimer = setTimeout(function () {
      document.body.classList.add('controls-idle');
    }, 4000);
  }

  function shufflePreset() {
    history.cancelPendingRestore();
    viz.random();
    wakeControls();
  }

  function goBack() {
    const previousIndex = history.back();
    if (previousIndex === null) return;
    viz.goto(previousIndex);
    updateBackState();
    wakeControls();
  }

  function changeInterval() {
    const seconds = intervalCycle.next();
    viz.setCycleSecs(seconds);
    const label = formatInterval(seconds);
    intervalValue.textContent = label;
    intervalBtn.setAttribute('aria-label', 'Change preset interval. Current ' + seconds + ' seconds');
    say('Preset interval: ' + label);
    wakeControls();
  }

  function updateHyperspeed(enabled) {
    document.body.classList.toggle('hyperspeed', enabled);
    hyperspeedValue.textContent = enabled ? 'On' : 'Off';
    hyperspeedBtn.setAttribute('aria-pressed', String(enabled));
    say('Hyperspeed ' + (enabled ? 'on' : 'off'));
  }

  function bindAction(button, action) {
    button.addEventListener('click', function (event) {
      event.stopPropagation();
      action();
    });
  }

  const hyperspeed = window.BCHyperspeed.create({
    shuffle: shufflePreset,
    intervalMs: 100,
    visibilityTarget: document,
    onChange: updateHyperspeed,
  });

  async function start() {
    if (viz.isStarted() || startupPending) return;
    startupPending = true;
    startPrompt.hidden = true;
    startupStatus.hidden = false;
    try {
      await viz.start();
      startupStatus.hidden = true;
      help.classList.add('hidden');
      document.body.classList.add('running');
      wakeControls();
      say('Running');
    } catch (error) {
      startupStatus.hidden = true;
      startPrompt.hidden = false;
      say('Audio error: ' + error.message);
    } finally {
      startupPending = false;
    }
  }

  bindAction(shuffleBtn, shufflePreset);
  bindAction(backBtn, goBack);
  bindAction(intervalBtn, changeInterval);
  bindAction(hyperspeedBtn, function () { hyperspeed.toggle(); wakeControls(); });
  help.addEventListener('click', start);
  canvas.addEventListener('click', function () {
    if (!viz.isStarted()) start();
    else wakeControls();
  });
  canvas.addEventListener('pointerdown', wakeControls);
  if (window.visualViewport) {
    window.visualViewport.addEventListener('resize', function () { viz.resize(); });
  }
  if (!viz.keys().length) say('Preset library failed to load');
})();
