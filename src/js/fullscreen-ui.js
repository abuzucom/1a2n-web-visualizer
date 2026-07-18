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

  let toastTimer = null;
  let startupPending = false;
  let startupTimer = null;
  const STARTUP_COUNTDOWN = 5;
  function say(msg) {
    const s = msg.length > 60 ? msg.slice(0, 57) + '\u2026' : msg;
    toast.textContent = s;
    toast.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { toast.classList.remove('show'); }, 2400);
  }

  const viz = BCViz.create(canvas, { onToast: say, cycleSecs: 20, cycleOn: true, shuffle: true, randomFirst: true });
  const hyperspeed = window.BCHyperspeed.create({
    shuffle: function () { if (viz.isStarted() && !viz.isChunkLoading()) viz.random(); },
    intervalMs: 100,
    visibilityTarget: document,
    onChange: function (enabled) {
      document.body.classList.toggle('hyperspeed', enabled);
      say('Hyperspeed ' + (enabled ? 'on' : 'off'));
    },
  });

  function updateStartupStatus(secondsRemaining) {
    if (secondsRemaining > 0) {
      startupStatusText.textContent = 'Loading visualizer... ' + secondsRemaining + 's';
      startupProgressBar.style.width = (secondsRemaining / STARTUP_COUNTDOWN * 100) + '%';
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
    }, 1000);
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
      // finer steps near the bottom of the range: 1s at/below 10s, 5s above
      case '[':
        say('Cycle: ' + viz.setCycleSecs(
          viz.getCycleSecs() - (viz.getCycleSecs() <= 10 ? 1 : 5)) + 's');
        break;
      case ']':
        say('Cycle: ' + viz.setCycleSecs(
          viz.getCycleSecs() + (viz.getCycleSecs() < 10 ? 1 : 5)) + 's');
        break;
      case 'd': case 'D':
        viz.nextDevice().catch(function (error) { say('Audio device error: ' + error.message); });
        break;
      case 'f': case 'F': toggleFullscreen(); break;
      case 't': case 'T':
        if (!e.repeat) hyperspeed.toggle();
        e.preventDefault();
        break;
      case 'x': case 'X': removeCurrent(); break;
      case 'l': case 'L': showExcludedPanel(); break;
      case 'Escape': hideExcludedPanel(); break;
      case '?': help.classList.toggle('hidden'); break;
    }
  });
  document.addEventListener('click', function () { if (!viz.isStarted()) start(); });

  removeBtn.addEventListener('click', function (e) { e.stopPropagation(); removeCurrent(); });
  excludedBtn.addEventListener('click', function (e) { e.stopPropagation(); showExcludedPanel(); });
  copyExcludedBtn.addEventListener('click', function (e) { e.stopPropagation(); copyExcludedList(); });
  closeExcludedBtn.addEventListener('click', function (e) { e.stopPropagation(); hideExcludedPanel(); });

  /* -- idle-fade: hide corner buttons after 3 s of inactivity ------ */
  var idleTimer = null;
  var IDLE_MS = 3000;

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
