#!/usr/bin/env node
/** Report generated presets whose equations cannot be parsed as JavaScript. */

const fs = require('fs');
const path = require('path');
const { validatePresetEquations } = require('./convert-milk-presets');

const ROOT = path.join(__dirname, '..');
const INDEX_PREFIX = 'window.BCExtraPresetIndex=';
const outputPath = process.argv[2] || path.join(ROOT, 'preset-invalid-equations.json');
const namesPath = process.argv[3] || null;

function readIndex() {
  const indexPath = path.join(ROOT, 'src', 'presets-extra', 'index.js');
  const text = fs.readFileSync(indexPath, 'utf8').trim();
  return JSON.parse(text.slice(INDEX_PREFIX.length, -1));
}

function readChunk(index, cid, filename) {
  const chunkPath = path.join(ROOT, 'src', 'presets-extra', filename);
  const text = fs.readFileSync(chunkPath, 'utf8').trim();
  const prefix = `window.__bcPresetChunk(${cid},`;
  if (!text.startsWith(prefix) || !text.endsWith(');')) {
    throw new Error(`invalid chunk wrapper: ${chunkPath}`);
  }
  return JSON.parse(text.slice(prefix.length, -2));
}

function findInvalidPresets(index) {
  const invalid = [];
  index.chunks.forEach(function (_, cid) {
    const filename = index.files[cid];
    const chunk = readChunk(index, cid, filename);
    Object.entries(chunk).forEach(function ([name, preset]) {
      try {
        validatePresetEquations(preset);
      } catch (error) {
        invalid.push({
          name: name,
          logicalChunk: cid,
          physicalFile: filename,
          reason: 'invalid generated JavaScript equation',
          error: error.message,
        });
      }
    });
  });
  return invalid;
}

const invalid = findInvalidPresets(readIndex());
fs.writeFileSync(outputPath, `${JSON.stringify({ presets: invalid }, null, 2)}\n`);
if (namesPath) fs.writeFileSync(namesPath, invalid.map(function (item) { return item.name; }).join('\n') + '\n');
console.log(`invalid generated presets: ${invalid.length}`);
if (invalid.length) process.exitCode = 1;
