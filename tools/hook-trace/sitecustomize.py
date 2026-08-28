"""Trace every interpreter the test suite starts, the hooks included.

Python imports `sitecustomize` at startup in every process, which is the
only stdlib way to reach a subprocess the suite launches. The gates run
that way, so in-process coverage sees almost none of their decision code
and reports the opposite of the truth.

Inert unless both environment variables are set, so putting this
directory on PYTHONPATH for other work costs nothing.
"""
import atexit
import json
import os
import sys
import threading
import trace
import uuid

TARGET_DIR = os.environ.get("HOOK_COVERAGE_TARGET", "")
OUT_DIR = os.environ.get("HOOK_COVERAGE_OUT", "")

if TARGET_DIR and OUT_DIR:
    _tracer = trace.Trace(count=1, trace=0, ignoredirs=[sys.prefix])

    def _dump() -> None:
        """Write this process's counts for the target directory."""
        # Stop tracing before reading. atexit runs with tracing still on,
        # so the counts dict grows while it is being iterated.
        sys.settrace(None)
        threading.settrace(None)
        snapshot = list(_tracer.results().counts)
        counts = {
            (os.path.abspath(filename), line)
            for filename, line in snapshot
            if os.path.abspath(filename).startswith(TARGET_DIR)
        }
        if not counts:
            return
        path = os.path.join(OUT_DIR, "%s.json" % uuid.uuid4().hex)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(sorted(counts), handle)

    atexit.register(_dump)
    sys.settrace(_tracer.globaltrace)
    threading.settrace(_tracer.globaltrace)
