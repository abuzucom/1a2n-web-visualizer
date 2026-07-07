/* fullscreen-ui.js - keyboard-only wiring for fullscreen.html */
(function () {
  'use strict';

  const canvas  = document.getElementById('viz');
  const toast   = document.getElementById('toast');
  const help    = document.getElementById('help');
  const removeBtn      = document.getElementById('removeBtn');
  const excludedBtn    = document.getElementById('excludedBtn');
  const excludedPanel  = document.getElementById('excludedPanel');
  const excludedList   = document.getElementById('excludedList');
  const copyExcludedBtn  = document.getElementById('copyExcludedBtn');
  const closeExcludedBtn = document.getElementById('closeExcludedBtn');

  let toastTimer = null;
  function say(msg) {
    const s = msg.length > 60 ? msg.slice(0, 57) + '\u2026' : msg;
    toast.textContent = s;
    toast.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { toast.classList.remove('show'); }, 2400);
  }

  const viz = BCViz.create(canvas, { onToast: say, cycleSecs: 20, cycleOn: true, shuffle: true, randomFirst: true });

  if (!viz.keys().length) say('\u26A0 Preset library failed to load');

  function toggleFullscreen() {
    if (!document.fullscreenElement) {
      if (document.documentElement.requestFullscreen) document.documentElement.requestFullscreen();
    } else if (document.exitFullscreen) {
      document.exitFullscreen();
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
    if (viz.isStarted()) return;
    help.classList.add('hidden');
    try {
      await viz.start();
      document.body.classList.add('running');
      say('\u25B6 Running \u2014 press ? for controls');
    } catch (e) {
      help.classList.remove('hidden');
      say('Audio error: ' + e.message);
    }
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
      case 'd': case 'D': viz.nextDevice(); break;
      case 'f': case 'F': toggleFullscreen(); break;
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
