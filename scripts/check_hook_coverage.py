#!/usr/bin/env python3
"""Fail when a hook statement no test reaches is not a recorded one.

The gates run as subprocesses, so ordinary in-process coverage sees
almost none of their decision code and reports the opposite of the truth.
This runs the suite with tools/coverage on PYTHONPATH, which traces every
interpreter, and compares what went unrun against a committed baseline.

The baseline is per function rather than per line, so an edit above a
function does not churn it. A function gaining unreached statements fails
the check, and so does a baseline that has gone stale: a gate nobody can
fail is the failure mode this whole check exists to avoid.

Regenerate with --write-baseline and commit the result.
"""
import ast
import io
import json
import os
import pickle
import shutil
import subprocess
import sys
import tempfile

BASELINE = "hook-coverage-baseline.json"
TARGET = "hooks"
TRACER_DIR = os.path.join("tools", "coverage")


def is_docstring(node, parent) -> bool:
    """Return True if `node` is `parent`'s docstring rather than code.

    A docstring compiles into __doc__ instead of executing, so it never
    appears in a trace count. Counting one as unreached measures the
    tracer, not the code.
    """
    return (bool(parent.body) and node is parent.body[0]
            and isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str))


def function_statements(path: str) -> dict:
    """Return {line: function name} for every real statement in a function."""
    with io.open(path, encoding="utf-8") as handle:
        tree = ast.parse(handle.read(), path)
    owned = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for child in ast.walk(node):
            if not isinstance(child, ast.stmt) or child is node:
                continue
            if is_docstring(child, node):
                continue
            owned.setdefault(child.lineno, node.name)
    return owned


def traced_lines(out_dir: str) -> set:
    """Return every (path, line) any traced interpreter executed."""
    hit = set()
    for name in os.listdir(out_dir):
        with open(os.path.join(out_dir, name), "rb") as handle:
            hit.update(pickle.load(handle))
    return hit


def unreached_counts(root: str, hit: set) -> dict:
    """Return {"file.py::function": unreached statement count}."""
    counts = {}
    target = os.path.join(root, TARGET)
    for name in sorted(os.listdir(target)):
        if not name.endswith(".py"):
            continue
        path = os.path.join(target, name)
        owned = function_statements(path)
        for line, function in owned.items():
            if (os.path.abspath(path), line) in hit:
                continue
            key = "%s::%s" % (name, function)
            counts[key] = counts.get(key, 0) + 1
    return counts


def measure(root: str) -> dict:
    """Run the suite under the tracer and return the unreached counts."""
    out_dir = tempfile.mkdtemp(prefix="hook-coverage-")
    try:
        environment = dict(os.environ)
        environment["PYTHONPATH"] = os.path.join(root, TRACER_DIR)
        environment["HOOK_COVERAGE_TARGET"] = os.path.join(root, TARGET)
        environment["HOOK_COVERAGE_OUT"] = out_dir
        result = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
            cwd=root, env=environment, capture_output=True, text=True,
            check=False)
        if result.returncode != 0:
            print("the suite failed under tracing, so coverage says nothing:",
                  file=sys.stderr)
            print(result.stderr[-2000:], file=sys.stderr)
            raise SystemExit(1)
        return unreached_counts(root, traced_lines(out_dir))
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


def compare(actual: dict, recorded: dict) -> list:
    """Return one line per disagreement between the run and the baseline."""
    problems = []
    for key in sorted(set(actual) | set(recorded)):
        now = actual.get(key, 0)
        was = recorded.get(key, 0)
        if now > was:
            problems.append(
                "%s: %d unreached statements, %d recorded. New code no test "
                "reaches." % (key, now, was))
        elif now < was:
            problems.append(
                "%s: %d unreached statements, %d recorded. The baseline is "
                "stale." % (key, now, was))
    return problems


def read_baseline(root: str) -> dict:
    """Return the committed baseline, or an empty mapping when absent."""
    path = os.path.join(root, BASELINE)
    if not os.path.isfile(path):
        return {}
    with io.open(path, encoding="utf-8") as handle:
        return json.load(handle).get("unreached", {})


def write_baseline(root: str, counts: dict) -> int:
    """Record `counts` as the baseline and return an exit code."""
    body = {
        "note": ("Statements in hooks/ that the suite, subprocesses included, "
                 "does not run, counted per function. Regenerate with "
                 "scripts/check_hook_coverage.py --write-baseline. Every entry "
                 "needs a reason in docs/gate-threat-model.md; an entry nobody "
                 "can explain is untested code, not a recorded limit."),
        "unreached": dict(sorted(counts.items())),
    }
    path = os.path.join(root, BASELINE)
    with io.open(path, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(body, indent=2) + "\n")
    print("recorded %d functions with unreached statements in %s"
          % (len(counts), BASELINE))
    return 0


def main(argv: list) -> int:
    """Measure, then either record the result or check it. Return an exit code."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    actual = measure(root)
    if "--write-baseline" in argv:
        return write_baseline(root, actual)
    problems = compare(actual, read_baseline(root))
    if not problems:
        print("hook coverage matches %s (%d functions recorded)"
              % (BASELINE, len(actual)))
        return 0
    for line in problems:
        print(line, file=sys.stderr)
    print("Add a test, or record the limit: run "
          "scripts/check_hook_coverage.py --write-baseline and say in "
          "docs/gate-threat-model.md why the statement is unreachable.",
          file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
