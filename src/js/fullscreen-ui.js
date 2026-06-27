/* fullscreen-ui.js — keyboard-only wiring for fullscreen.html */
(function () {
  'use strict';

  const canvas = document.getElementById('viz');
  const toast  = document.getElementById('toast');
  const help   = document.getElementById('help');

  let toastTimer = null;
  function say(msg) {
    const s = msg.length > 60 ? msg.slice(0, 57) + '\u2026' : msg;
    toast.textContent = s;
    toast.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { toast.classList.remove('show'); }, 2400);
  }

  const viz = BCViz.create(canvas, { onToast: say, cycleSecs: 20, cycleOn: true });

  if (!viz.keys().length) say('\u26A0 Preset library failed to load (check internet)');

  function toggleFullscreen() {
    if (!document.fullscreenElement) {
      if (document.documentElement.requestFullscreen) document.documentElement.requestFullscreen();
    } else if (document.exitFullscreen) {
      document.exitFullscreen();
    }
  }

  async function start() {
    if (viz.isStarted()) return;
    help.classList.add('hidden');
    try {
      await viz.start();
      say('\u25B6 Running \u2014 press ? for controls');
    } catch (e) {
      help.classList.remove('hidden');
      say('Audio error: ' + e.message);
    }
  }

  document.addEventListener('keydown', function (e) {
    if (!viz.isStarted()) { start(); return; }
    switch (e.key) {
      case ' ': case 'n': case 'N': viz.next(); e.preventDefault(); break;
      case 'p': case 'P': viz.prev(); break;
      case 'r': case 'R': viz.random(); break;
      case 'c': case 'C': say(viz.toggleCycle() ? '\u21BB Auto-cycle on (' + viz.getCycleSecs() + 's)' : '\u23F8 Auto-cycle off'); break;
      case '[': say('Cycle: ' + viz.setCycleSecs(viz.getCycleSecs() - 5) + 's'); break;
      case ']': say('Cycle: ' + viz.setCycleSecs(viz.getCycleSecs() + 5) + 's'); break;
      case 'd': case 'D': viz.nextDevice(); break;
      case 'f': case 'F': toggleFullscreen(); break;
      case '?': help.classList.toggle('hidden'); break;
    }
  });
  document.addEventListener('click', function () { if (!viz.isStarted()) start(); });
})();
