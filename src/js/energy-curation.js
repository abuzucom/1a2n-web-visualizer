/* energy-curation.js - session energy classification for the curation keys */
(function (global) {
  'use strict';

  const CATEGORIES = ['low', 'medium', 'high'];
  const BLOCK_VERSION = 1;

  function isCategory(value) {
    return CATEGORIES.indexOf(value) !== -1;
  }

  /**
   * Create one session of energy assignments.
   *
   * A preset holds at most one category. A new assignment replaces the
   * previous category for that preset and keeps the preset in the
   * collection.
   */
  function create() {
    const assignments = new Map();

    function groups() {
      return CATEGORIES.map(function (category) {
        const names = [];
        assignments.forEach(function (value, name) {
          if (value === category) names.push(name);
        });
        return { category: category, names: names };
      });
    }

    return {
      assign: function (name, category) {
        if (!name) return '';
        if (!isCategory(category)) throw new Error('unknown energy category: ' + category);
        assignments.set(name, category);
        return category;
      },
      categoryOf: function (name) {
        return assignments.get(name) || '';
      },
      groups: groups,
      names: function () {
        const names = [];
        assignments.forEach(function (value, name) { names.push(name); });
        return names;
      },
      assignmentBlock: function () {
        const presets = {};
        assignments.forEach(function (value, name) { presets[name] = value; });
        return { version: BLOCK_VERSION, presets: presets };
      },
    };
  }

  global.BCEnergyCuration = { create: create, CATEGORIES: CATEGORIES };
})(window);
