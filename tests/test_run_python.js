"use strict";
const assert = require("node:assert");
const { test } = require("node:test");
const { execFileSync, spawnSync } = require("node:child_process");
const path = require("node:path");

const SHIM = path.join(__dirname, "..", "tools", "run-python.js");
const { findInterpreter } = require("../tools/run-python.js");

test("forwards arguments to the interpreter", () => {
  const out = execFileSync(process.execPath, [SHIM, "-c", "print('hello')"], {
    encoding: "utf8",
  });
  assert.strictEqual(out.trim(), "hello");
});

test("forwards the interpreter exit code", () => {
  const result = spawnSync(process.execPath, [SHIM, "-c", "raise SystemExit(3)"]);
  assert.strictEqual(result.status, 3);
});

test("rejects a candidate that is not Python 3", () => {
  // A stand-in for the Windows Store alias and for Python 2: it runs, and
  // it fails the version probe.
  assert.strictEqual(findInterpreter([["false"]]), null);
});

test("reports every candidate when none resolves", () => {
  const result = spawnSync(process.execPath, [SHIM, "-c", "pass"], {
    env: { ...process.env, PATH: path.join(__dirname, "does-not-exist") },
    encoding: "utf8",
  });
  assert.strictEqual(result.status, 1);
  assert.match(result.stderr, /no Python 3 interpreter found/);
  assert.match(result.stderr, /python3/);
  assert.match(result.stderr, /py -3/);
});
