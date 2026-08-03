(function (global) {
  'use strict';

  const DEFAULT_INTERVAL_MS = 100;

  function create(options) {
    const opts = options || {};
    const shuffle = typeof opts.shuffle === 'function' ? opts.shuffle : function () {};
    const onChange = typeof opts.onChange === 'function' ? opts.onChange : function () {};
    const intervalMs = Number(opts.intervalMs) > 0 ? Number(opts.intervalMs) : DEFAULT_INTERVAL_MS;
    const visibilityTarget = opts.visibilityTarget;
    let enabled = false;
    let timer = null;

    function clearTimer() {
      if (timer !== null) {
        global.clearInterval(timer);
        timer = null;
      }
    }

    function setEnabled(nextEnabled) {
      const next = Boolean(nextEnabled);
      if (next === enabled) return enabled;
      enabled = next;
      clearTimer();
      onChange(enabled);
      if (enabled) {
        shuffle();
        timer = global.setInterval(shuffle, intervalMs);
      }
      return enabled;
    }

    /* Hyperspeed used to switch itself off whenever the page was hidden,
     * because rendering stopped there anyway. The render driver now keeps
     * frames coming while hidden, so the default is to keep shuffling. Callers
     * that still want the old behavior opt in with pauseWhenHidden. */
    if (opts.pauseWhenHidden && visibilityTarget && visibilityTarget.addEventListener) {
      visibilityTarget.addEventListener('visibilitychange', function () {
        if (visibilityTarget.hidden) setEnabled(false);
      });
    }

    return {
      toggle: function () { return setEnabled(!enabled); },
      setEnabled: setEnabled,
      stop: function () { setEnabled(false); },
      isEnabled: function () { return enabled; },
    };
  }

  global.BCHyperspeed = { create: create, DEFAULT_INTERVAL_MS: DEFAULT_INTERVAL_MS };
})(window);
