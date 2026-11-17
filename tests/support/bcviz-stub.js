/* Builds the BCViz global that a page script sees in a unit test. The shared
 * page helpers come from the real visualizer-core.js. The test supplies only
 * create(), which hands back its fake controller. */
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const CORE_PATH = path.join(__dirname, '..', '..', 'src', 'js', 'visualizer-core.js');
const CORE_SOURCE = fs.readFileSync(CORE_PATH, 'utf8');

/**
 * Return a BCViz object with the real shared helpers and the given create().
 * The helpers read support globals such as BCAudioPrefs from the page window
 * at call time. A child scope keeps the core's own BCViz global off it.
 */
function createBCVizStub(window, create) {
  const scope = Object.create(window);
  vm.runInNewContext(CORE_SOURCE, { window: scope, console: console });
  return Object.assign({}, scope.BCViz, { create: create });
}

module.exports = { createBCVizStub: createBCVizStub };
