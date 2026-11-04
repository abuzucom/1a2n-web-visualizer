#!/usr/bin/env node
/**
 * convert-milk-presets.js
 *
 * Converts raw MilkDrop .milk preset text into the JSON shape this repo's
 * lazy-loaded presets-extra chunks already use (baseVals, init_eqs_str,
 * frame_eqs_str, pixel_eqs_str, warp, comp, shapes, waves), using the same
 * jberg toolchain that produced the ansorre collection already vendored
 * here: milkdrop-preset-utils (parsing), milkdrop-eel-parser (EEL2 -> JS
 * equations), and milkdrop-shader-converter (HLSL -> GLSL warp/comp
 * shaders).
 *
 * The native shader-converter addon has been observed to hang indefinitely
 * on some inputs, so warp/comp conversion always runs in a short-lived
 * child process (convert-shader-worker.js) with a hard timeout -- a stuck
 * conversion is killed and that preset's shader falls back to "" rather
 * than blocking the whole batch.
 *
 * One-time setup (milkdrop-shader-converter ships a native C++ addon, not
 * pure JS -- see patches/milkdrop-shader-converter+*.patch for the fixes
 * this required against Node 22 / a modern bison):
 *   1. apt-get install -y flex bison cmake   (or your platform's equivalent)
 *   2. npm install --ignore-scripts   (recommended -- see warning below)
 *   3. npx patch-package               (applies patches/*.patch manually,
 *                                        since --ignore-scripts also skips
 *                                        the root postinstall that would
 *                                        otherwise do this automatically)
 *   4. cd node_modules/milkdrop-shader-converter && \
 *        npx cmake-js compile --std=c++17 -G "Unix Makefiles"
 * Step 4 (the actual native compile) is always manual regardless of which
 * install mode you used -- package-level "install" scripts like this
 * one's `cmake-js compile` are exactly the kind of arbitrary code
 * execution --ignore-scripts is meant to prevent, so it's never run
 * automatically.
 *
 * WARNING: a plain `npm install` (scripts enabled, no --ignore-scripts) is
 * NOT equivalent to steps 2-3 above and can fail outright: npm runs each
 * dependency's own "install" script -- including milkdrop-shader-converter's
 * `cmake-js compile` -- before the root project's own postinstall runs, so
 * the native addon would attempt to build from unpatched source (against
 * Node 22 headers it doesn't support) and fail before patch-package ever
 * gets a chance to apply the fix. Use --ignore-scripts and the manual
 * sequence above.
 *
 * Re-run step 4 whenever
 * node_modules/milkdrop-shader-converter is reinstalled.
 *
 * Usage (library):
 *   const { convertMilkText } = require('./convert-milk-presets');
 *   const { preset, warnings } = convertMilkText(fs.readFileSync('foo.milk', 'utf8'));
 *
 * Usage (CLI, one file, prints JSON to stdout):
 *   node tools/convert-milk-presets.js path/to/preset.milk
 *
 * Usage (CLI, batch mode -- every .milk file under a directory tree,
 * recursively; prints one JSON object of {presetName: preset} to stdout,
 * keyed by filename without extension, and a per-failure warning report to
 * stderr):
 *   node tools/convert-milk-presets.js --dir path/to/milk/files
 */

const { execFileSync } = require('child_process');
const fs = require('fs');
const osModule = require('os');
const path = require('path');
const utils = require('milkdrop-preset-utils');
const eel = require('milkdrop-eel-parser');
const acorn = require('acorn');

const SHADER_WORKER = path.join(__dirname, 'convert-shader-worker.js');
const SHADER_TIMEOUT_MS = 8000;
const LOG_INTERVAL = 200;
const ARGS_START = 2;
const JSON_INDENT = 2;

/** Runs convert-shader-worker.js on one HLSL shader body with a hard timeout. */
function convertShader(shaderBody) {
  if (!shaderBody || !shaderBody.trim()) return { ok: true, glsl: '' };

  const dir = fs.mkdtempSync(path.join(osModule.tmpdir(), 'shader-conv-'));
  const inputPath = path.join(dir, 'shader.txt');
  fs.writeFileSync(inputPath, shaderBody);
  try {
    const out = execFileSync(process.execPath, [SHADER_WORKER, inputPath], {
      timeout: SHADER_TIMEOUT_MS,
      encoding: 'utf8',
    });
    return JSON.parse(out);
  } catch (err) {
    return { ok: false, error: err.message };
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
}

/** Convert custom equations and report failures without omitting required fields. */
function convertWaveOrShape(item, kind, index, presetVersion, warnings) {
  // splitPreset() can leave the raw (unconverted) equation text sitting in
  // baseVals under keys like "init"/"per_frame"/"per_point" -- it tries to
  // parse them as numbers, which fails to NaN (JSON.stringify renders NaN
  // as null). Strip those so they don't pollute the output as bogus "null"
  // baseVals (real baseVals are always finite numbers).
  const baseVals = Object.fromEntries(
    Object.entries(item.baseVals || {}).filter(([, v]) => typeof v !== 'number' || Number.isFinite(v)),
  );
  const result = {
    baseVals,
    init_eqs_str: '',
    frame_eqs_str: '',
    ...(kind === 'wave' ? { point_eqs_str: '' } : {}),
  };
  const hasCustomEqs =
    (item.init_eqs_str && item.init_eqs_str.trim()) ||
    (item.frame_eqs_str && item.frame_eqs_str.trim()) ||
    (kind === 'wave' && item.point_eqs_str && item.point_eqs_str.trim());
  if (!hasCustomEqs) return result;
  try {
    const converted = kind === 'wave'
      ? eel.make_wave_map(presetVersion, item)
      : eel.make_shape_map(presetVersion, item);
    if (converted.perFrameInitEQs && converted.perFrameInitEQs.trim()) {
      result.init_eqs_str = converted.perFrameInitEQs.trim();
    }
    if (converted.perFrameEQs && converted.perFrameEQs.trim()) {
      result.frame_eqs_str = converted.perFrameEQs.trim();
    }
    if (kind === 'wave' && converted.perPointEQs && converted.perPointEQs.trim()) {
      result.point_eqs_str = converted.perPointEQs.trim();
    }
    return result;
  } catch (error) {
    warnings.push(`${kind}[${index}]: ${error.message.replace(/[\r\n]/g, ' ')}`);
    return result;
  }
}

/** Reject generated equation text that Butterchurn cannot compile. */
function validateEquation(source, label) {
  if (typeof source !== 'string') throw new TypeError(`${label}: expected an equation string`);
  if (!source.trim()) return;
  try {
    acorn.parse(`function __bcEquation(a) {${source}\nreturn a;}`, {
      ecmaVersion: 'latest',
      sourceType: 'script',
    });
  } catch (error) {
    throw new Error(`${label}: ${error.message}`, { cause: error });
  }
}

/** Validate every generated JavaScript equation without executing it. */
function validatePresetEquations(preset) {
  for (const field of ['init_eqs_str', 'frame_eqs_str']) {
    validateEquation(preset[field], field);
  }
  if (preset.pixel_eqs_str !== undefined) validateEquation(preset.pixel_eqs_str, 'pixel_eqs_str');
  for (const [kind, items] of [['shape', preset.shapes], ['wave', preset.waves]]) {
    items.forEach((item, index) => {
      validateItemEquations(item, kind, index);
    });
  }
}

/** Match runtime guards for disabled items and optional wave point equations. */
function validateItemEquations(item, kind, index) {
  const enabled = Boolean(item.baseVals && item.baseVals.enabled);
  for (const field of ['init_eqs_str', 'frame_eqs_str']) {
    if (enabled || item[field] !== undefined) validateEquation(item[field], `${kind}[${index}].${field}`);
  }
  if (kind === 'wave' && item.point_eqs_str !== undefined) {
    validateEquation(item.point_eqs_str, `${kind}[${index}].point_eqs_str`);
  }
}

/** Separate generated statements from Butterchurn's appended return statement. */
function terminatePresetEquations(preset) {
  const items = [preset, ...preset.shapes, ...preset.waves];
  const fields = ['init_eqs_str', 'frame_eqs_str', 'pixel_eqs_str', 'point_eqs_str'];
  for (const item of items) {
    for (const field of fields) {
      const source = item[field];
      if (typeof source === 'string' && source.trim() && !source.trimEnd().endsWith(';')) {
        item[field] = `${source}\n;`;
      }
    }
  }
}

/** Converts raw .milk preset text into the target preset-object shape.
 * Return { preset, warnings } with explicit shader and custom equation failures. */
function convertMilkText(text) {
  const split = utils.splitPreset(text);
  const warnings = [];

  const basic = eel.convert_basic_preset(
    split.presetVersion,
    split.presetInit || '',
    split.perFrame || '',
    split.perVertex || '',
  );

  const warpResult = convertShader(split.warp);
  if (!warpResult.ok) warnings.push(`warp: ${warpResult.error}`);
  const compResult = convertShader(split.comp);
  if (!compResult.ok) warnings.push(`comp: ${compResult.error}`);

  const preset = {
    baseVals: split.baseVals || {},
    warp: warpResult.ok ? warpResult.glsl : '',
    comp: compResult.ok ? compResult.glsl : '',
    init_eqs_str: '',
    frame_eqs_str: '',
    pixel_eqs_str: '',
    waves: (split.waves || []).map((w, i) => convertWaveOrShape(w, 'wave', i, split.presetVersion, warnings)),
    shapes: (split.shapes || []).map((s, i) => convertWaveOrShape(s, 'shape', i, split.presetVersion, warnings)),
  };
  if (basic.perFrameInitEQs && basic.perFrameInitEQs.trim()) {
    preset.init_eqs_str = basic.perFrameInitEQs.trim();
  }
  if (basic.perFrameEQs && basic.perFrameEQs.trim()) {
    preset.frame_eqs_str = basic.perFrameEQs.trim();
  }
  if (basic.perPixelEQs && basic.perPixelEQs.trim()) {
    preset.pixel_eqs_str = basic.perPixelEQs.trim();
  }

  terminatePresetEquations(preset);
  validatePresetEquations(preset);
  return { preset, warnings };
}

/** Recursively lists every .milk file under `dir`, returning absolute paths. */
function findMilkFiles(dir) {
  const out = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) out.push(...findMilkFiles(full));
    else if (entry.isFile() && entry.name.toLowerCase().endsWith('.milk')) out.push(full);
  }
  return out;
}

/**
 * Distribute conversion tasks across worker processes and return a promise array.
 */
function runBatch(rootDir) {
  const files = findMilkFiles(rootDir);
  const results = {};
  let failCount = 0;

  let collisionCount = 0;

  files.forEach((filePath, i) => {
    const name = path.basename(filePath, path.extname(filePath));
    if (i % LOG_INTERVAL === 0) console.error(`converting ${i}/${files.length}...`);
    if (Object.prototype.hasOwnProperty.call(results, name)) {
      // The name is the sole identity key everywhere downstream (index.js,
      // chunk files, preset-inventory.csv) -- keep the first occurrence
      // (stable directory-walk order) rather than silently letting a later
      // file win with no signal.
      collisionCount += 1;
      console.error(`warning: duplicate basename ${JSON.stringify(name)} at ${filePath} -- keeping first occurrence`);
      return;
    }
    try {
      const text = fs.readFileSync(filePath, 'utf8');
      const { preset, warnings } = convertMilkText(text);
      if (warnings.length) console.error(`warning: ${JSON.stringify(name)}: ${warnings.join('; ')}`);
      results[name] = preset;
    } catch (err) {
      failCount += 1;
      console.error(`failed: ${JSON.stringify(name)}: ${err.message}`);
    }
  });

  if (collisionCount) console.error(`duplicate basenames skipped: ${collisionCount}`);

  console.error(`converted ${Object.keys(results).length}/${files.length} (${failCount} failed)`);
  console.log(JSON.stringify(results));
}

/**
 * Prepare paths and start the conversion pipeline for presets.
 */
async function main() {
  const args = process.argv.slice(ARGS_START);
  if (args[0] === '--dir') {
    if (!args[1]) {
      console.error('Usage: node convert-milk-presets.js --dir <path/to/milk/files>');
      process.exit(1);
    }
    runBatch(args[1]);
    return;
  }

  const [inputPath] = args;
  if (!inputPath) {
    console.error('Usage: node convert-milk-presets.js <path/to/preset.milk>');
    console.error('       node convert-milk-presets.js --dir <path/to/milk/files>');
    process.exit(1);
  }
  const text = fs.readFileSync(inputPath, 'utf8');
  const { preset, warnings } = convertMilkText(text);
  if (warnings.length) console.error('warnings:', warnings.join('; '));
  console.log(JSON.stringify(preset, null, JSON_INDENT));
}

module.exports = { convertMilkText, validatePresetEquations };

if (require.main === module) main();
