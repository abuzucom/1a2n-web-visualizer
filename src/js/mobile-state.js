(function (global) {
  'use strict';

  function createHistory(limit) {
    const maxEntries = limit > 0 ? limit : 20;
    let currentIndex = null;
    let pendingRestore = null;
    const entries = [];

    function visit(index) {
      const restored = pendingRestore === index;
      pendingRestore = null;
      if (currentIndex !== null && currentIndex !== index && !restored) {
        entries.push(currentIndex);
        if (entries.length > maxEntries) entries.shift();
      }
      currentIndex = index;
    }

    return {
      visit: visit,
      back: function () {
        if (!entries.length) return null;
        pendingRestore = entries.pop();
        return pendingRestore;
      },
      cancelPendingRestore: function () { pendingRestore = null; },
      canGoBack: function () { return entries.length > 0; },
      size: function () { return entries.length; },
    };
  }

  function createIntervalCycle(values, initialIndex) {
    const options = values.slice();
    let index = initialIndex || 0;
    if (index < 0 || index >= options.length) index = 0;
    return {
      current: function () { return options[index]; },
      next: function () {
        index = (index + 1) % options.length;
        return options[index];
      },
    };
  }

  global.BCMobileState = {
    createHistory: createHistory,
    createIntervalCycle: createIntervalCycle,
  };
})(window);
