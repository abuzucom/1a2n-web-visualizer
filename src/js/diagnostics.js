/* Operator diagnostics overlay.
 *
 * Everything the anti-throttling stack does is invisible by design, which is
 * useless during a live show. This overlay is the confirmation: it says which
 * tick source is driving frames, whether the page is hidden, whether the
 * keepalive was suppressed, and above all whether the audio guard is armed.
 *
 * Shown with ?diag=1 on any page, and with the I key on fullscreen.html.
 */
(function (global) {
  'use strict';

  const REFRESH_MS = 500;

  const ROWS = [
    { key: 'FPS', read: function (s) { return String(s.fps || 0) + ' fps'; } },
    { key: 'Tick source', read: function (s) { return s.tickSource || 'idle'; } },
    { key: 'Page', read: function (s) { return s.hidden ? 'hidden' : 'visible'; } },
    { key: 'Wake lock', read: function (s) { return s.wakeLock ? 'held' : 'none'; } },
    { key: 'Keepalive', read: function (s) { return s.keepalive || 'off'; } },
    { key: 'Input', read: function (s) { return s.device || 'unknown'; } },
    { key: 'Track', read: function (s) { return s.trackState || 'unknown'; } },
    { key: 'Recoveries', read: function (s) { return String(s.recoveries || 0); } },
  ];

  /** True for ?name, ?name=1, ?name=true. Anything else is off.
   * Compares key names literally rather than building a RegExp around the
   * caller's name, so metacharacters in it cannot alter the match or throw. */
  function hasFlag(search, name) {
    if (typeof search !== 'string' || !search || !name) return false;
    const query = search.charAt(0) === '?' ? search.slice(1) : search;
    const parts = query.split('&');
    for (let i = 0; i < parts.length; i += 1) {
      const separator = parts[i].indexOf('=');
      const key = separator === -1 ? parts[i] : parts[i].slice(0, separator);
      if (key !== name) continue;
      const value = separator === -1 ? '' : parts[i].slice(separator + 1);
      return value === '' || value === '1' || value.toLowerCase() === 'true';
    }
    return false;
  }

  function addRow(state, key) {
    const row = state.doc.createElement('div');
    const keyEl = state.doc.createElement('span');
    const valueEl = state.doc.createElement('span');
    row.className = 'diag-row';
    keyEl.className = 'diag-key';
    valueEl.className = 'diag-value';
    keyEl.textContent = key;
    row.appendChild(keyEl);
    row.appendChild(valueEl);
    state.root.appendChild(row);
    return { row: row, key: keyEl, value: valueEl };
  }

  function build(state) {
    if (state.root) return;
    state.root = state.doc.createElement('div');
    state.root.className = 'diag-overlay';
    state.root.setAttribute('aria-hidden', 'true');
    state.guard = addRow(state, 'Audio guard');
    state.guard.row.className = 'diag-row diag-guard';
    state.countdown = addRow(state, '');
    state.countdown.row.className = 'diag-row diag-countdown';
    state.cells = ROWS.map(function (definition) {
      return { definition: definition, cell: addRow(state, definition.key) };
    });
    state.doc.body.appendChild(state.root);
  }

  function renderGuard(state, stats) {
    const armed = Boolean(stats.armed);
    state.guard.value.textContent = armed ? 'ARMED' : 'DISARMED';
    state.guard.row.className = 'diag-row diag-guard ' + (armed ? 'is-armed' : 'is-disarmed');
  }

  function renderCountdown(state, stats) {
    const secs = Number(stats.recoverInSecs) || 0;
    state.countdown.key.textContent = secs > 0 ? 'Reconnect in' : '';
    state.countdown.value.textContent = secs > 0 ? String(secs) + 's' : '';
  }

  function render(state) {
    if (!state.root || !state.visible) return;
    const stats = state.getStats() || {};
    renderGuard(state, stats);
    renderCountdown(state, stats);
    state.cells.forEach(function (entry) {
      entry.cell.value.textContent = entry.definition.read(stats);
    });
  }

  function startRefresh(state) {
    if (state.timer !== null) return;
    state.timer = state.win.setInterval(function () { render(state); }, REFRESH_MS);
  }

  function stopRefresh(state) {
    if (state.timer === null) return;
    state.win.clearInterval(state.timer);
    state.timer = null;
  }

  function show(state) {
    build(state);
    state.visible = true;
    state.root.hidden = false;
    state.root.setAttribute('aria-hidden', 'false');
    render(state);
    startRefresh(state);
  }

  function hide(state) {
    state.visible = false;
    stopRefresh(state);
    if (!state.root) return;
    state.root.hidden = true;
    state.root.setAttribute('aria-hidden', 'true');
  }

  function create(options) {
    const opts = options || {};
    const win = opts.window || global;
    const state = {
      win: win,
      doc: opts.document || win.document,
      getStats: typeof opts.getStats === 'function' ? opts.getStats : function () { return {}; },
      root: null,
      guard: null,
      countdown: null,
      cells: [],
      visible: false,
      timer: null,
    };
    return {
      show: function () { show(state); },
      hide: function () { hide(state); },
      toggle: function () {
        if (state.visible) hide(state);
        else show(state);
        return state.visible;
      },
      update: function () { render(state); },
      isVisible: function () { return state.visible; },
    };
  }

  global.BCDiagnostics = { create: create, hasFlag: hasFlag };
}(window));
