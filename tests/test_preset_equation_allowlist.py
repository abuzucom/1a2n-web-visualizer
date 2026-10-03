"""Test the preset equation allowlist checker.

Butterchurn compiles every preset equation with new Function. Equation text
is therefore executable code. The checker must reject anything outside the
vocabulary milkdrop-eel-parser emits. It must accept every preset the app
ships today.
"""

import importlib.util
import tempfile
import unittest
from pathlib import Path

CHECKER_PATH = Path(__file__).resolve().parent.parent / "tools" / "check_preset_equations.py"
MAX_REPORTED = 10


def _load_checker():
    spec = importlib.util.spec_from_file_location("check_preset_equations", CHECKER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


checker = _load_checker()

# Shapes taken from shipped chunks: chunk-000.js, chunk-9370.js, chunk-9380.js.
FRAME_SAMPLE = (
    "a['mv_g']=(1-(a['bass_att']*0.4)); "
    "a['beat']=((Math.abs(above((a['bass']*a['bass_att']), 4.5))>0.00001)?((1-a['beat'])):(a['beat'])); "
    "a['q2']=Math.min(a['amp'], 1); a['q3']=(a['trebcap']*2);"
)
LOOP_SAMPLE = (
    "for(var mdparser_idx3=0;mdparser_idx3<10000;mdparser_idx3++)"
    "{a['gmegabuf'][Math.floor(a['i'])]=0; a['i']=(a['i']+1);}"
)
WHILE_SAMPLE = (
    "(function(){var mdparser_idx128;var mdparser_count129=0;"
    "do{mdparser_count129+=1;mdparser_idx128=(function(){"
    "a['ran1']=div(rand(800),100); a['c1']=Math.cos(a['ran1']); "
    "return ((a['dist']<0.06)?1:0)})()}"
    "while(Math.abs(mdparser_idx128)>0.000010&&mdparser_count129<1048576);}());"
)

REJECTED = (
    "a.x=0;top.location='x'",
    "a['constructor']",
    "a['__proto__']=1",
    "a['toString']()",
    "Function('x')()",
    "this.y=1",
    "globalThis.z=1",
    "window.sqr(2)",
    "Math['constructor']",
    "(0,eval)(1)",
    "a['x']=`x`",
    "a['x']=new Date()",
    "a['x']=[]+{}",
    "a['x']=(Math.sin+1)[5]",
    "a['x'](1)",
    "a['x']=1..toString()",
    'a["\\x63"]=1',
    "var q=1",
    "Math.floor=Math.ceil",
    "a['x']=(a['y'])(1)",
    "a['megabuf']['constructor']",
    "a[ 'constructor' ]",
    "Math.a['x']",
)


class EquationAllowlistTests(unittest.TestCase):
    def test_accepts_the_shipped_equation_forms(self) -> None:
        for source in ("", FRAME_SAMPLE, LOOP_SAMPLE, WHILE_SAMPLE):
            with self.subTest(source=source):
                self.assertEqual(checker.find_equation_violations(source), [])

    def test_rejects_code_outside_the_equation_vocabulary(self) -> None:
        for source in REJECTED:
            with self.subTest(source=source):
                self.assertNotEqual(checker.find_equation_violations(source), [])

    def test_reports_the_offending_field(self) -> None:
        preset = {
            "init_eqs_str": "",
            "frame_eqs_str": FRAME_SAMPLE,
            "pixel_eqs_str": "",
            "shapes": [],
            "waves": [{"init_eqs_str": "", "frame_eqs_str": "", "point_eqs_str": "top.x=1"}],
        }
        problems = checker.preset_violations(preset)
        self.assertNotEqual(problems, [])
        for problem in problems:
            self.assertTrue(problem.startswith("waves[0].point_eqs_str: "), problem)

    def test_rejects_code_outside_the_chunk_wrapper(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            preset_dir = Path(directory)
            (preset_dir / "index.js").write_text(
                'window.BCExtraPresetIndex={"v":1,"chunks":[["p"]]};\n', encoding="utf-8")
            (preset_dir / "chunk-000.js").write_text(
                'window.__bcPresetChunk(0,{"p":{}});alert(1);\n', encoding="utf-8")
            with self.assertRaises(ValueError):
                checker.corpus_violations(preset_dir)

    def test_rejects_a_chunk_path_outside_the_preset_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            preset_dir = Path(directory)
            (preset_dir / "index.js").write_text(
                'window.BCExtraPresetIndex={"v":1,"chunks":[["p"]],"files":["../evil.js"]};\n',
                encoding="utf-8")
            with self.assertRaises(ValueError):
                checker.corpus_violations(preset_dir)

    def test_every_shipped_preset_passes(self) -> None:
        self.assertNotEqual(checker.chunk_files(checker.read_index()), [])
        offenders = checker.corpus_violations()
        self.assertEqual(
            offenders[:MAX_REPORTED], [],
            f"{len(offenders)} preset equations fall outside the allowlist (showing at most {MAX_REPORTED})",
        )


if __name__ == "__main__":
    unittest.main()
