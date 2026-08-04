#!/usr/bin/env node
/** Report EXP presets whose generated equations cannot be parsed as JavaScript. */

const fs = require('fs');
const path = require('path');
const { validatePresetEquations } = require('./convert-milk-presets');

const root = path.join(__dirname, '..');
const ARGS_OUTPUT = 2;
const SUFFIX_LENGTH = -2;
const JSON_INDENT = 2;
const outputPath = process.argv[ARGS_OUTPUT] || path.join(root, 'experimental-invalid-equations.json');
const indexPath = path.join(root, 'src', 'presets-extra', 'index.js');
const indexText = fs.readFileSync(indexPath, 'utf8').trim();
const index = JSON.parse(indexText.slice('window.BCExtraPresetIndex='.length, -1));
const invalid = [];

for (let cid = 0; cid < index.chunks.length; cid += 1) {
  const filename = index.files[cid];
  if (!filename.startsWith('chunk-9')) continue;
  const chunkPath = path.join(root, 'src', 'presets-extra', filename);
  const text = fs.readFileSync(chunkPath, 'utf8').trim();
  const prefix = `window.__bcPresetChunk(${cid},`;
  if (!text.startsWith(prefix) || !text.endsWith(');')) {
    throw new Error(`invalid chunk wrapper: ${chunkPath}`);
  }
  const chunk = JSON.parse(text.slice(prefix.length, SUFFIX_LENGTH));
  for (const [name, preset] of Object.entries(chunk)) {
    try {
      validatePresetEquations(preset);
    } catch (error) {
      invalid.push({
        experimentalName: name,
        logicalChunk: cid,
        physicalFile: filename,
        reason: 'invalid generated JavaScript equation',
        error: error.message,
      });
    }
  }
}

fs.writeFileSync(outputPath, `${JSON.stringify({ presets: invalid }, null, JSON_INDENT)}\n`);
console.log(`invalid experimental presets: ${invalid.length}`);
