#!/usr/bin/env node
"use strict";
// npm scripts named python3, which does not exist on Windows, while lint in
// the same file named python, which may be absent or Python 2 on Debian. No
// single spelling works everywhere, so selection happens here.
const { spawn, spawnSync } = require("node:child_process");

// Ordered by how likely each is to be a working Python 3 on a given host.
const CANDIDATES = [["python3"], ["python"], ["py", "-3"]];
const VERSION_PROBE = "import sys; sys.exit(0 if sys.version_info[0] == 3 else 1)";
// process.argv[0] is the node binary and [1] is this script. Everything the
// caller wants handed to Python starts after those two.
const FORWARDED_ARGUMENT_START = 2;

function findInterpreter(candidates = CANDIDATES) {
  // Each candidate is run rather than looked up. That is what rejects the
  // two traps: the Windows Store alias named python.exe, which opens the
  // Store and exits 9009, and a python that is still Python 2.
  for (const candidate of candidates) {
    const [program, ...prefix] = candidate;
    const probe = spawnSync(program, [...prefix, "-c", VERSION_PROBE], {
      stdio: "ignore",
    });
    if (!probe.error && probe.status === 0) {
      return candidate;
    }
  }
  return null;
}

function main(argv) {
  const candidate = findInterpreter();
  if (candidate === null) {
    const names = CANDIDATES.map((entry) => entry.join(" ")).join(", ");
    process.stderr.write(`no Python 3 interpreter found. Tried: ${names}\n`);
    return 1;
  }
  const [program, ...prefix] = candidate;
  const child = spawn(program, [...prefix, ...argv], { stdio: "inherit" });
  child.on("exit", (code, signal) => {
    process.exit(signal ? 1 : code === null ? 1 : code);
  });
  return null;
}

if (require.main === module) {
  const status = main(process.argv.slice(FORWARDED_ARGUMENT_START));
  if (status !== null) {
    process.exit(status);
  }
}

module.exports = { findInterpreter, CANDIDATES };
