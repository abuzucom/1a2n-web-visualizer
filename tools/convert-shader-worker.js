#!/usr/bin/env node
/**
 * convert-shader-worker.js
 *
 * Converts one HLSL warp/comp shader body to GLSL. Run as a short-lived
 * child process (never required in-process) because the underlying native
 * milkdrop-shader-converter addon has been observed to hang indefinitely on
 * some inputs -- isolating it per-call lets the caller enforce a hard
 * timeout and kill a stuck conversion without losing the rest of a batch.
 *
 * Usage: node convert-shader-worker.js <shaderBodyFile>
 * Prints JSON {ok:true, glsl} or {ok:false, error} to stdout.
 */

const fs = require('fs');
const utils = require('milkdrop-preset-utils');
const converter = require('milkdrop-shader-converter');
const MAX_SHADER_BYTES = 1048576;
const MAX_SHADER_DEPTH = 128;

/** Reject malformed compiler output before upstream text transformations. */
function validateCompiledShader(source) {
  if (!source.trim()) throw new Error('native converter returned empty output');
  if (Buffer.byteLength(source) > MAX_SHADER_BYTES) throw new Error('compiled shader exceeds size limit');
  const stack = [];
  const pairs = { ')': '(', ']': '[', '}': '{' };
  for (let index = 0; index < source.length; index++) {
    const character = source[index];
    const next = source[index + 1];
    if (character === '/' && next === '/') {
      const end = source.indexOf('\n', index);
      index = end === -1 ? source.length : end;
      continue;
    }
    if (character === '/' && next === '*') {
      const end = source.indexOf('*/', index + 1);
      if (end === -1) throw new Error('unterminated shader comment');
      index = end + 1;
      continue;
    }
    if ('([{'.includes(character)) stack.push(character);
    if (stack.length > MAX_SHADER_DEPTH) throw new Error('compiled shader exceeds nesting limit');
    if (Object.hasOwn(pairs, character) && stack.pop() !== pairs[character]) {
      throw new Error('unbalanced compiled shader delimiters');
    }
  }
  if (stack.length) throw new Error('unbalanced compiled shader delimiters');
  const entryPoints = source.match(/\bvoid main \(\)/g) || [];
  if (entryPoints.length !== 1) throw new Error('expected one optimized shader entry point');
  if (!source.includes('_glesFragData[0] = ')) throw new Error('compiled shader has no fragment output');
}

/**
 * Listen for messages from the parent process and convert presets.
 */
function main() {
  const [, , inputPath] = process.argv;
  const shaderBody = fs.readFileSync(inputPath, 'utf8');
  if (Buffer.byteLength(shaderBody) > MAX_SHADER_BYTES) throw new Error('input shader exceeds size limit');

  const prepared = utils.prepareShader(shaderBody);
  // The matching upstream postprocessor requires optimized native output.
  // The parent process enforces the deadline around translation and optimization.
  const renamed = prepared.replace('shader_body (float2 uv', 'main (float2 uv');
  const output = converter.convertHLSLString(renamed, true);
  if (!Buffer.isBuffer(output)) throw new Error('native converter returned no shader buffer');
  const compiled = output.toString('utf8');
  validateCompiledShader(compiled);
  const glsl = utils.processOptimizedShader(compiled);
  if (!glsl.includes('shader_body') || /\bvoid main\b|_glesFragData|xlv_TEXCOORD0/.test(glsl)) {
    throw new Error('optimized shader adaptation left unsupported entry-point symbols');
  }
  process.stdout.write(JSON.stringify({ ok: true, glsl }));
}

try {
  main();
} catch (err) {
  process.stdout.write(JSON.stringify({ ok: false, error: err.message }));
}
