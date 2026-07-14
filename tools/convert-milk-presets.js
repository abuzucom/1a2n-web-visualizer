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
 *   2. npm install                            (applies the patch via
 *                                               postinstall: patch-package)
 *   3. cd node_modules/milkdrop-shader-converter && \
 *        npx cmake-js compile --std=c++17 -G "Unix Makefiles"
 * `npm install` deliberately runs with scripts disabled elsewhere in this
 * repo's workflow, so this native build step is manual, not automatic --
 * re-run step 3 whenever node_modules/milkdrop-shader-converter is
 * reinstalled.
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
const os = require('os');
const path = require('path');
const utils = require('milkdrop-preset-utils');
const eel = require('milkdrop-eel-parser');

const SHADER_WORKER = path.join(__dirname, 'convert-shader-worker.js');
const SHADER_TIMEOUT_MS = 8000;

/** Runs convert-shader-worker.js on one HLSL shader body with a hard timeout. */
function convertShader(shaderBody) {
  if (!shaderBody || !shaderBody.trim()) return { ok: true, glsl: '' };

  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'shader-conv-'));
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

/** Best-effort per-wave/shape conversion: only equations that actually look
 * like non-trivial EEL text are converted; anything else is left as bare
 * baseVals (matching the common "disabled, no custom equations" case). */
function convertWaveOrShape(item, kind, index, presetVersion) {
  // splitPreset() can leave the raw (unconverted) equation text sitting in
  // baseVals under keys like "init"/"per_frame"/"per_point" -- it tries to
  // parse them as numbers, which fails to NaN (JSON.stringify renders NaN
  // as null). Strip those so they don't pollute the output as bogus "null"
  // baseVals (real baseVals are always finite numbers).
  const baseVals = Object.fromEntries(
    Object.entries(item.baseVals || {}).filter(([, v]) => typeof v !== 'number' || Number.isFinite(v)),
  );
  const hasCustomEqs =
    (item.init_eqs_str && item.init_eqs_str.trim()) ||
    (item.frame_eqs_str && item.frame_eqs_str.trim()) ||
    (kind === 'wave' && item.point_eqs_str && item.point_eqs_str.trim());

  if (!hasCustomEqs) return { baseVals };

  try {
    const converted = eel.convert_preset_wave_and_shape(
      kind,
      index,
      presetVersion,
      item.init_eqs_str || '',
      item.frame_eqs_str || '',
      kind === 'wave' ? (item.point_eqs_str || '') : '',
    );
    const result = { baseVals };
    if (converted.perFrameInitEQs && converted.perFrameInitEQs.trim()) {
      result.init_eqs_str = converted.perFrameInitEQs.trim();
    }
    if (converted.perFrameEQs && converted.perFrameEQs.trim()) {
      result.frame_eqs_str = converted.perFrameEQs.trim();
    }
    if (kind === 'wave' && converted.perPixelEQs && converted.perPixelEQs.trim()) {
      result.point_eqs_str = converted.perPixelEQs.trim();
    }
    return result;
  } catch {
    // Conversion of this item's custom equations failed -- fall back to
    // just its baseVals rather than dropping the whole preset.
    return { baseVals };
  }
}

/** Converts raw .milk preset text into the target preset-object shape.
 * Returns { preset, warnings } -- warnings lists any shader that failed to
 * convert and was replaced with "" (empty = no custom warp/comp effect). */
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
    waves: (split.waves || []).map((w, i) => convertWaveOrShape(w, 'wave', i, split.presetVersion)),
    shapes: (split.shapes || []).map((s, i) => convertWaveOrShape(s, 'shape', i, split.presetVersion)),
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

function runBatch(rootDir) {
  const files = findMilkFiles(rootDir);
  const results = {};
  let failCount = 0;

  files.forEach((filePath, i) => {
    const name = path.basename(filePath, path.extname(filePath));
    if (i % 200 === 0) console.error(`converting ${i}/${files.length}...`);
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

  console.error(`converted ${Object.keys(results).length}/${files.length} (${failCount} failed)`);
  console.log(JSON.stringify(results));
}

function main() {
  const args = process.argv.slice(2);
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
  console.log(JSON.stringify(preset, null, 2));
}

module.exports = { convertMilkText };

if (require.main === module) main();
