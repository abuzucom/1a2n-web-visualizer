/**
 * preset_source.js
 *
 * Shared readers for the generated preset sources that the JS curation
 * tools parse. The index.js and chunk files wrap one JSON payload in a
 * fixed callback. The vendored packs embed preset maps in minified
 * JavaScript, so the tools locate a map's end with a bracket matcher.
 */

const INDEX_PREFIX = 'window.BCExtraPresetIndex=';
const INDEX_SUFFIX = ';';
const CHUNK_SUFFIX = ');';
const CLOSERS = { '{': '}', '[': ']' };

/**
 * Return the index of the bracket that closes the one at openIdx, or -1.
 * Brackets inside single- or double-quoted strings do not count.
 */
function findMatchingCloser(text, openIdx) {
  const open = text[openIdx];
  const close = CLOSERS[open];
  if (!close) throw new Error(`no bracket at index ${openIdx}`);
  let depth = 0;
  let quote = null;
  let escaped = false;
  for (let i = openIdx; i < text.length; i++) {
    const character = text[i];
    if (quote) {
      if (escaped) escaped = false;
      else if (character === '\\') escaped = true;
      else if (character === quote) quote = null;
      continue;
    }
    if (character === '"' || character === "'") quote = character;
    else if (character === open) depth++;
    else if (character === close && --depth === 0) return i;
  }
  return -1;
}

/**
 * Strip a known wrapper from raw source and return the parsed payload.
 * Throws with the given message when either end of the wrapper is absent.
 */
function parseWrapped(raw, prefix, suffix, message) {
  const trimmed = raw.trimEnd();
  if (!raw.startsWith(prefix) || !trimmed.endsWith(suffix)) throw new Error(message);
  return JSON.parse(trimmed.slice(prefix.length, trimmed.length - suffix.length));
}

/**
 * Parse src/presets-extra/index.js source.
 * Returns { data, prefix, suffix } so a writer can restore the wrapper.
 */
function parseIndexSource(raw) {
  const data = parseWrapped(raw, INDEX_PREFIX, INDEX_SUFFIX, 'unexpected index.js wrapper format');
  return { data: data, prefix: INDEX_PREFIX, suffix: INDEX_SUFFIX };
}

/**
 * Parse one chunk file whose callback must name the given logical chunk id.
 * Returns { data, prefix, suffix } so a writer can restore the wrapper.
 */
function parseChunkSource(raw, id, label) {
  const prefix = `window.__bcPresetChunk(${id},`;
  const data = parseWrapped(raw, prefix, CHUNK_SUFFIX, `unexpected wrapper format in ${label}`);
  return { data: data, prefix: prefix, suffix: CHUNK_SUFFIX };
}

module.exports = {
  findMatchingCloser: findMatchingCloser,
  parseIndexSource: parseIndexSource,
  parseChunkSource: parseChunkSource,
};
