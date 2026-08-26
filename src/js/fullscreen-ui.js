/* fullscreen-ui.js - keyboard-only wiring for fullscreen.html */
(function () {
  'use strict';

  const canvas  = document.getElementById('viz');
  const toast   = document.getElementById('toast');
  const help    = document.getElementById('help');
  const startPrompt = document.getElementById('startPrompt');
  const startupStatus = document.getElementById('startupStatus');
  const startupStatusText = document.getElementById('startupStatusText');
  const startupProgressBar = document.getElementById('startupProgressBar');
  const removeBtn      = document.getElementById('removeBtn');
  const excludedBtn    = document.getElementById('excludedBtn');
  const excludedPanel  = document.getElementById('excludedPanel');
  const excludedList   = document.getElementById('excludedList');
  const copyExcludedBtn  = document.getElementById('copyExcludedBtn');
  const closeExcludedBtn = document.getElementById('closeExcludedBtn');
  const favoriteBtn       = document.getElementById('favoriteBtn');
  const favoritesBtn      = document.getElementById('favoritesBtn');
  const favoritesPanel    = document.getElementById('favoritesPanel');
  const favoritesTextEl   = document.getElementById('favoritesListText');
  const copyFavoritesBtn  = document.getElementById('copyFavoritesBtn');
  const closeFavoritesBtn = document.getElementById('closeFavoritesBtn');

  let toastTimer = null;
  let startupPending = false;
  let startupTimer = null;
  const STARTUP_COUNTDOWN = 5;
  const MAX_TOAST_LENGTH = 60;
  const TRUNCATED_TOAST_LENGTH = 57;
  const TOAST_DURATION_MS = 2400;
  const PERCENT_MULTIPLIER = 100;
  const ONE_SECOND_MS = 1000;
  const CYCLE_STEP_THRESHOLD = 10;
  const CYCLE_STEP_SMALL = 1;
  const CYCLE_STEP_LARGE = 5;
  const TEMPO_STEP_BPM = 4;
  const INTENSITY_STEP = 0.1;
  function say(msg) {
    const s = msg.length > MAX_TOAST_LENGTH ? msg.slice(0, TRUNCATED_TOAST_LENGTH) + '\u2026' : msg;
    toast.textContent = s;
    toast.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { toast.classList.remove('show'); }, TOAST_DURATION_MS);
  }

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

  /* demo.html sets the attribute; ?demo=1 turns any fullscreen page into the
   * same synthetic-audio build, following the ?diag and ?guard convention. */
  const DEMO_MODE = document.body.getAttribute('data-demo') === '1'
    || window.BCDiagnostics.hasFlag(location.search, 'demo');
  const viz = BCViz.create(canvas, {
    onToast: say, cycleSecs: 20, cycleOn: true, shuffle: true, randomFirst: true, demo: DEMO_MODE,
  });
  const hyperspeed = window.BCHyperspeed.create({
    shuffle: function () { if (viz.isStarted() && !viz.isChunkLoading()) viz.random(); },
    intervalMs: 100,
    onChange: function (enabled) {
      document.body.classList.toggle('hyperspeed', enabled);
      say('Hyperspeed ' + (enabled ? 'on' : 'off'));
    },
  });
  const diagnostics = window.BCDiagnostics.create({
    window: window,
    document: document,
    getStats: function () { return viz.diagnostics(); },
  });
  if (window.BCDiagnostics.hasFlag(location.search, 'diag')) diagnostics.show();
  if (window.BCDiagnostics.hasFlag(location.search, 'guard')) viz.setAudioGuard(true);

  /* Finer steps near the bottom of the range: 1s at or below 10s, 5s above.
   * Stepping down tests <= and stepping up tests <, so 10s steps down by 1s
   * but up by 5s. That asymmetry is deliberate; keep it. */
  function stepCycle(direction) {
    const current = viz.getCycleSecs();
    const nearBottom = direction < 0
      ? current <= CYCLE_STEP_THRESHOLD
      : current < CYCLE_STEP_THRESHOLD;
    const step = nearBottom ? CYCLE_STEP_SMALL : CYCLE_STEP_LARGE;
    say('Cycle: ' + viz.setCycleSecs(current + direction * step) + 's');
  }

  function sayDemo() {
    say('\u266A ' + viz.diagnostics().demo);
  }

  function cycleDemoGenre() {
    if (!viz.isDemo()) return;
    viz.cycleDemoTempo();
    sayDemo();
  }

  function nudgeDemoTempo(delta) {
    if (!viz.isDemo()) return;
    viz.setDemoTempo(viz.getDemoTempo() + delta);
    sayDemo();
  }

  function nudgeDemoIntensity(delta) {
    if (!viz.isDemo()) return;
    viz.setDemoIntensity(viz.getDemoIntensity() + delta);
    sayDemo();
  }

  function toggleAudioGuard() {
    say(viz.toggleAudioGuard()
      ? '🛡 Audio guard armed'
      : '⚠ Audio guard disarmed');
  }

  function updateStartupStatus(secondsRemaining) {
    if (secondsRemaining > 0) {
      startupStatusText.textContent = 'Loading visualizer... ' + secondsRemaining + 's';
      if (!STARTUP_COUNTDOWN) throw new Error('STARTUP_COUNTDOWN cannot be zero');
      startupProgressBar.style.width = (secondsRemaining / STARTUP_COUNTDOWN * PERCENT_MULTIPLIER) + '%';
      startupProgressBar.parentElement.setAttribute('aria-valuenow', secondsRemaining);
      return;
    }
    startupStatusText.textContent = 'Still loading...';
    startupProgressBar.style.width = '0%';
    startupProgressBar.parentElement.removeAttribute('aria-valuenow');
  }

  function showStartupStatus() {
    startPrompt.hidden = true;
    startupStatus.hidden = false;
    help.classList.add('loading');
    updateStartupStatus(STARTUP_COUNTDOWN);
    startupTimer = window.setInterval(function () {
      const remaining = Number(startupProgressBar.parentElement.getAttribute('aria-valuenow')) - 1;
      updateStartupStatus(Number.isNaN(remaining) ? 0 : remaining);
    }, ONE_SECOND_MS);
  }

  function clearStartupStatus(showPrompt) {
    window.clearInterval(startupTimer);
    startupTimer = null;
    startupStatus.hidden = true;
    help.classList.remove('loading');
    startPrompt.hidden = !showPrompt;
  }

  if (!viz.keys().length) say('\u26A0 Preset library failed to load');

  function toggleFullscreen() {
    if (!document.fullscreenElement) {
      if (document.documentElement.requestFullscreen) {
        document.documentElement.requestFullscreen().catch(function (error) {
          say('Fullscreen failed: ' + error.message);
        });
      }
    } else if (document.exitFullscreen) {
      document.exitFullscreen().catch(function (error) {
        say('Fullscreen exit failed: ' + error.message);
      });
    }
  }

  function removeCurrent() {
    if (!viz.isStarted()) return;
    const removed = viz.removeCurrentFromShuffle();
    if (removed) say('\uD83D\uDEAB Removed from shuffle: ' + removed);
  }

  function showExcludedPanel() {
    if (!viz.isStarted()) return;
    const list = viz.excludedList();
    excludedList.value = list.length ? list.join('\n') : '(none excluded yet)';
    excludedPanel.classList.remove('hidden');
    excludedList.focus();
    excludedList.select();
  }

  function hideExcludedPanel() {
    excludedPanel.classList.add('hidden');
  }

  function copyExcludedList() {
    const list = viz.excludedList();
    const text = list.join('\n');
    excludedList.select();
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(function () {
        say('Copied ' + list.length + ' preset name(s)');
      }, function () {
        say('Copy failed \u2014 text is selected, use Ctrl/Cmd+C');
      });
    } else {
      say('Text is selected \u2014 use Ctrl/Cmd+C to copy');
    }
  }

  function favoriteCurrent() {
    if (!viz.isStarted()) return;
    const favorited = viz.favoriteCurrentPreset();
    if (favorited) say('\u2b50 Favorited: ' + favorited);
  }

  function showFavoritesPanel() {
    if (!viz.isStarted()) return;
    const list = viz.favoritesList();
    favoritesTextEl.value = list.length ? list.join('\n') : '(none favorited yet)';
    favoritesPanel.classList.remove('hidden');
    favoritesTextEl.focus();
    favoritesTextEl.select();
  }

  function hideFavoritesPanel() {
    favoritesPanel.classList.add('hidden');
  }

  function copyFavoritesList() {
    const list = viz.favoritesList();
    const text = list.join('\n');
    favoritesTextEl.select();
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(function () {
        say('Copied ' + list.length + ' preset name(s)');
      }, function () {
        say('Copy failed \u2014 text is selected, use Ctrl/Cmd+C');
      });
    } else {
      say('Text is selected \u2014 use Ctrl/Cmd+C to copy');
    }
  }

  async function start() {
    if (viz.isStarted() || startupPending) return;
    startupPending = true;
    showStartupStatus();
    window.setTimeout(async function () {
      try {
        await viz.start();
        clearStartupStatus(false);
        help.classList.add('hidden');
        document.body.classList.add('running');
        say('\u25B6 Running \u2014 press ? for controls');
      } catch (e) {
        clearStartupStatus(true);
        say('Audio error: ' + e.message);
      } finally {
        startupPending = false;
      }
    }, 0);
  }

  document.addEventListener('keydown', function (e) {
    if (!viz.isStarted()) {
      if (e.key.length === 1 || e.key === 'Enter') start();  // ignore bare modifier presses
      return;
    }
    switch (e.key) {
      case ' ': case 'n': case 'N': viz.next(); e.preventDefault(); break;
      case 'p': case 'P': viz.prev(); break;
      case 'r': case 'R': viz.random(); break;
      case 'c': case 'C':
        say(viz.toggleCycle()
          ? '\u21BB Auto-cycle on (' + viz.getCycleSecs() + 's)'
          : '\u23F8 Auto-cycle off');
        break;
      case 's': case 'S':
        say(viz.toggleShuffle()
          ? '\uD83D\uDD00 Shuffle cycle on'
          : '\u27A1 Sequential cycle');
        break;
      case '[': stepCycle(-1); break;
      case ']': stepCycle(1); break;
      // Demo build only; no-ops elsewhere. Shifted variants included so the
      // keys work without checking the modifier.
      case 'b': case 'B': cycleDemoGenre(); break;
      case ',': case '<': nudgeDemoTempo(-TEMPO_STEP_BPM); break;
      case '.': case '>': nudgeDemoTempo(TEMPO_STEP_BPM); break;
      case '-': case '_': nudgeDemoIntensity(-INTENSITY_STEP); break;
      case '=': case '+': nudgeDemoIntensity(INTENSITY_STEP); break;
      case 'd': case 'D':
        if (viz.isDemo()) { say('Demo mode: synthetic audio, no input device'); break; }
        viz.nextDevice().catch(function (error) { say('Audio device error: ' + describeDeviceError(error)); });
        break;
      case 'f': case 'F': toggleFullscreen(); break;
      case 't': case 'T':
        if (!e.repeat) hyperspeed.toggle();
        e.preventDefault();
        break;
      case 'x': case 'X': removeCurrent(); break;
      case 'l': case 'L': showExcludedPanel(); break;
      case 'm': case 'M': favoriteCurrent(); break;
      case 'k': case 'K': showFavoritesPanel(); break;
      case 'a': case 'A': toggleAudioGuard(); break;
      case 'i': case 'I': diagnostics.toggle(); break;
      case 'Escape': hideExcludedPanel(); hideFavoritesPanel(); break;
      case '?': help.classList.toggle('hidden'); break;
    }
  });
  document.addEventListener('click', function () { if (!viz.isStarted()) start(); });

  removeBtn.addEventListener('click', function (e) { e.stopPropagation(); removeCurrent(); });
  excludedBtn.addEventListener('click', function (e) { e.stopPropagation(); showExcludedPanel(); });
  copyExcludedBtn.addEventListener('click', function (e) { e.stopPropagation(); copyExcludedList(); });
  closeExcludedBtn.addEventListener('click', function (e) { e.stopPropagation(); hideExcludedPanel(); });
  favoriteBtn.addEventListener('click', function (e) { e.stopPropagation(); favoriteCurrent(); });
  favoritesBtn.addEventListener('click', function (e) { e.stopPropagation(); showFavoritesPanel(); });
  copyFavoritesBtn.addEventListener('click', function (e) { e.stopPropagation(); copyFavoritesList(); });
  closeFavoritesBtn.addEventListener('click', function (e) { e.stopPropagation(); hideFavoritesPanel(); });

  /* -- idle-fade: hide corner buttons after 3 s of inactivity ------ */
  let idleTimer = null;
  const IDLE_MS = 3000;

  function goIdle() { document.body.classList.add('idle'); }
  function wakeUp() {
    document.body.classList.remove('idle');
    clearTimeout(idleTimer);
    idleTimer = setTimeout(goIdle, IDLE_MS);
  }

  document.addEventListener('mousemove', wakeUp);
  document.addEventListener('keydown', wakeUp);
  document.addEventListener('click', wakeUp);
  // start the first idle countdown
  idleTimer = setTimeout(goIdle, IDLE_MS);
})();
