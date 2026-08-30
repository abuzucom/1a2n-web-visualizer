"""Guard the equation-field invariant on generated experimental output.

Butterchurn compiles preset equations with
``new Function("a", "".concat(field, " return a;"))``. A field missing from the
JSON stringifies to the literal ``undefined``, which is a hard SyntaxError, so
the preset dies at load time. visualizer-core.js does not catch this: its
``normalizeEquation`` only rewrites values that are already strings, and
``validateEquation`` returns early on a falsy value.

The top-level ``init_eqs_str``/``frame_eqs_str`` are compiled unconditionally.
Shape and wave equations are compiled only when that item's merged
``baseVals.enabled`` is non-zero (butterchurn's shape/wave defaults both carry
``enabled: 0``), so only enabled items are load-bearing.

Neither validate-experimental-presets.js nor validate-preset-chunks.js covers
this, since both only check JSON shape.
"""

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "src" / "presets-extra"
INDEX_PATH = OUT_DIR / "index.js"
INDEX_PREFIX = "window.BCExtraPresetIndex="
EXPERIMENTAL_FILE_PREFIX = "chunk-9"

TOP_REQUIRED = ("init_eqs_str", "frame_eqs_str")
SHAPE_REQUIRED = ("init_eqs_str", "frame_eqs_str")
WAVE_REQUIRED = ("init_eqs_str", "frame_eqs_str")


def read_index():
    """Return the experimental preset index mapping and its file list."""
    text = INDEX_PATH.read_text(encoding="utf-8").strip()
    data = json.loads(text[len(INDEX_PREFIX):-1])
    files = data.get("files") or [
        f"chunk-{cid:03d}.js" for cid in range(len(data["chunks"]))
    ]
    return data, files


def read_chunk(cid, filename):
    """Return the preset mapping stored in one generated chunk file."""
    text = (OUT_DIR / filename).read_text(encoding="utf-8").strip()
    prefix = f"window.__bcPresetChunk({cid},"
    if not text.startswith(prefix) or not text.endswith(");"):
        raise ValueError(f"unexpected chunk wrapper in {filename}")
    return json.loads(text[len(prefix):-2])


def is_enabled(item):
    """Return whether butterchurn would compile this shape's or wave's equations."""
    return (item.get("baseVals") or {}).get("enabled", 0) != 0


def missing_fields(preset):
    """Return the load-bearing equation fields absent from the given preset."""
    missing = []
    for field in TOP_REQUIRED:
        if not isinstance(preset.get(field), str):
            missing.append(field)
    for index, shape in enumerate(preset.get("shapes") or []):
        if not is_enabled(shape):
            continue
        missing.extend(
            f"shapes[{index}].{field}"
            for field in SHAPE_REQUIRED
            if not isinstance(shape.get(field), str)
        )
    for index, wave in enumerate(preset.get("waves") or []):
        if not is_enabled(wave):
            continue
        missing.extend(
            f"waves[{index}].{field}"
            for field in WAVE_REQUIRED
            if not isinstance(wave.get(field), str)
        )
    return missing


class ExperimentalEquationFieldTests(unittest.TestCase):
    def test_enabled_shapes_and_waves_define_equation_fields(self):
        """Every reachable equation field is a string, including an empty one."""
        data, files = read_index()
        offenders = []
        for cid, filename in enumerate(files):
            if not filename.startswith(EXPERIMENTAL_FILE_PREFIX):
                continue
            chunk = read_chunk(cid, filename)
            for name in data["chunks"][cid]:
                missing = missing_fields(chunk[name])
                if missing:
                    offenders.append((name, missing))
        self.assertEqual(
            offenders[:10], [],
            f"{len(offenders)} experimental presets omit equation fields that "
            f"butterchurn compiles unconditionally; they raise SyntaxError and "
            f"are skipped at load time (showing at most 10)",
        )

    def test_batch_prefixes_stay_within_the_documented_scheme(self):
        """Experimental display names use the [EXP], [EXP2], [EXP3], ... scheme."""
        data, files = read_index()
        pattern = re.compile(r"^\[EXP\d*\] ")
        bad = []
        for cid, filename in enumerate(files):
            if not filename.startswith(EXPERIMENTAL_FILE_PREFIX):
                continue
            bad.extend(
                name for name in data["chunks"][cid] if not pattern.match(name)
            )
        self.assertEqual(bad[:10], [], "experimental presets must carry an [EXPn] prefix")


if __name__ == "__main__":
    unittest.main()
