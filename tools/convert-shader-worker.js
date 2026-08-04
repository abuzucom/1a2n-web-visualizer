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

/**
 * Listen for messages from the parent process and convert presets.
 */
function main() {
  const [, , inputPath] = process.argv;
  const shaderBody = fs.readFileSync(inputPath, 'utf8');

  const prepared = utils.prepareShader(shaderBody);
  // The native converter's entry point is hardcoded to "main" -- rename the
  // preset's shader_body function to match. optimize=true (glsl-optimizer)
  // has been observed to hang on valid input, so this uses the safe
  // unoptimized path and extracts just the function body, matching what
  // butterchurn's own runtime getShaderParts() extracts from "shader_body
  // { ... }" at load time -- the stored preset field is that same
  // convention, not a standalone compiled shader.
  const renamed = prepared.replace('shader_body (float2 uv', 'main (float2 uv');
  const compiled = converter.convertHLSLString(renamed, false).toString('utf8');
  // hlsl2glsl-fork always renames the translated entry function to
  // "xlat_main" internally and wraps it in its own "void main() {...}" that
  // calls it -- the real translated body lives in the xlat_main definition.
  const openIdx = compiled.indexOf('xlat_main(');
  if (openIdx === -1) throw new Error('could not locate compiled xlat_main() function');
  const braceOpen = compiled.indexOf('{', openIdx);
  if (braceOpen === -1) throw new Error('could not locate function body opening brace');
  let depth = 0;
  let braceClose = -1;
  for (let i = braceOpen; i < compiled.length; i++) {
    if (compiled[i] === '{') depth++;
    else if (compiled[i] === '}') {
      depth--;
      if (depth === 0) { braceClose = i; break; }
    }
  }
  if (braceClose === -1) throw new Error('could not locate matching closing brace');
  const body = compiled.slice(braceOpen + 1, braceClose).trim();
  const glsl = `shader_body\n{\n${body}\n}`;
  process.stdout.write(JSON.stringify({ ok: true, glsl }));
}

try {
  main();
} catch (err) {
  process.stdout.write(JSON.stringify({ ok: false, error: err.message }));
}
