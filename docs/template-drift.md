# Template drift

This repository adopts the agent-instruction template from
[`abuzucom/agents`](https://github.com/abuzucom/agents). The template's
`DRIFT.md` owns the drift policy and its three categories.
`adopters/1a2n-web-visualizer.md` in the template owns the adopted-at commit
and the taken and declined lists. This file owns the local differences and
the reason for each.

## Adopted revision

Template commit `848d069`. One commit copies `scripts/` and `hooks/` whole,
together with `AGENTS.md`, `docs/agent-policy/*.md`,
`shared-files.json`, `hook-coverage-baseline.json`, the four client hook
registrations, and the template tests for every adopted hook and checker.
`scripts/complete_gate_adoption.py` installed the registrations as one
transaction.

`scripts/sync.py --check-shared` compares the gate files against
`shared-files.json` in CI. A gate fix landing upstream and not here fails that
check on the next run. Everything outside the manifest is a convention that
no check verifies.

## What differs, and why

### `docs/project-orientation.md` and `docs/repo-guide.md`

Expected to differ. `scripts/sync.py` caps the assembled policy at 64 KiB.
The template's `AGENTS.md` plus `docs/agent-policy/*.md` already fill all but
about 600 bytes of it. The orientation stub therefore names only the paths
that must never be hand-edited and points to `docs/repo-guide.md`. The guide
holds the full commands, protected paths, architecture, and gotchas outside
the injected policy.

### GitHub Actions pinning

Expected to differ. This repository pins every action to a full commit SHA
with a release comment and enforces it with `scripts/check_action_pins.py`.
Copy a template workflow step only after confirming its SHA pin.

### Workflow wiring

Expected to differ. The template's own workflows are not copied. The adopted
checks run from `.github/workflows/checks.yml` instead. This adoption
holds back the template tests that assert the template's own workflow files,
Makefile, and pre-commit wiring. Those tests arrive with that wiring.

### Lint and code-scanning fixes in template files

True drift. The repository lints every Python file under `pyproject.toml`
(`E`, `F`, `W`, `B`, `C90`, `PLR`, `FIX`, `RET`, `BLE`). The template files at
`848d069` carry 152 findings under those rules. This repository carries local
fixes:

- Named constants replace magic values.
- Complex functions split into named helpers. Decision tables replace long
  `if` chains in the gates.
- Blind `except` clauses name the exception types each handler covers.
- `scripts/trusted_git.py` `run_git` takes its keyword options through one
  validated mapping. Every existing call keeps working.
- `scripts/check_hook_coverage.py` `run_test_shard` takes the root and
  environment as one `location` argument. `tests/test_shard_priority.py`
  follows that signature.
- Test files move `sys.path` imports to `importlib.import_module` and wrap two
  long lines. No assertion changes.
- `_MarkedMapping` in `check_dockerfile_root.py` and
  `check_persist_credentials.py` defines `__eq__` over its contents.

Every gate verdict over the 3,900 string literals in `tests/` matches the
pre-change verdicts. `shared-files.json` and `hook-coverage-baseline.json`
record the changed files. `scripts/check_pr_review_response.py` also differs
from foucault 3.3.14 and carries this repository's digest in
`tests/test_foucault_review_wiring.py`. An `abuzucom/agents` issue proposes the
same fixes upstream.

### Checkers and tests this repository holds alone

`scripts/check_protected_files.py` and `scripts/jira_sync.py` have no template
counterpart. The template declined `check_protected_files.py`. The
server-side backstop for edits to `hooks/`, `.claude/`, `.codex/`, `.gemini/`,
`.agents/`, and `docs/agent-policy/` is this repository's own, through
[`protected-file-review.md`](protected-file-review.md).

## Changing a template file here

Record the change above. Open an issue in `abuzucom/agents` naming the file,
the change, and whether it belongs upstream. The template adoption steps
require that issue. No check enforces it.
