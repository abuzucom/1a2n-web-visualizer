# Template drift

This repository adopts the agent-instruction template from
[`abuzucom/agents`](https://github.com/abuzucom/agents). The template's
`DRIFT.md` owns the drift policy and its three categories.
`adopters/1a2n-web-visualizer.md` in the template owns the adopted-at commit
and the taken and declined lists. This file owns the local differences and
the reason for each.

## Adopted revision

Template commit `b452348`, re-adopted from `848d069`. One commit carries
`scripts/`, `hooks/`, `AGENTS.md`, `docs/agent-policy/*.md`,
`shared-files.json`, `hook-coverage-baseline.json`, the four client hook
registrations, and the template tests for every adopted hook and checker.
`scripts/complete_gate_adoption.py` installed the gate files as one
transaction.

The `848d069` installer selects files from its own required-path lists.
Those lists lack `hooks/_command_execution_gate.py` and
`.local-path-allowlist`, which the `b452348` checker requires. Both files
landed before the transaction ran. Neither file acts until the new hooks
and checker load it.

Every shared file except five matches the upstream `shared-files.json`
digest:
- `hooks/_cmd_parser.py`, `hooks/_platform_policy.py`,
  `tests/json_line_worker_child.py`, and `tests/test_platform_policy.py`
  carry the lint fixes listed below. Upstream left them unchanged since
  `848d069`.
- `hooks/_gate_core.py` is a three-way merge of upstream onto the local file.
  It keeps every local fix, the UNC path rule, and the fsmonitor rule below.

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
- `scripts/check_hook_coverage.py` `run_test_shard` takes the root and
  environment as one `location` argument. `tests/test_shard_priority.py`
  follows that signature.
- Test files move `sys.path` imports to `importlib.import_module` and wrap two
  long lines. No assertion changes.
- `_MarkedMapping` in `check_dockerfile_root.py` and
  `check_persist_credentials.py` defines `__eq__` over its contents.

Every gate verdict over the 3,900 string literals in `tests/` matches the
pre-change verdicts. `shared-files.json` and `hook-coverage-baseline.json`
record the changed files. `scripts/check_pr_review_response.py`, `ci/call_model.py`, and
`ci/run_model_command.py` also differ from foucault 3.3.14 by named constants.
`tests/test_foucault_review_wiring.py` pins the current digest of each file.
Upstreaming these fixes to `abuzucom/agents` needs a separate issue.

The `b452348` re-adoption takes the upstream file whole wherever upstream
rewrote code that carried a local fix. The local fixes in those files are
gone:
- `hooks/enforce_branch_name.py`, `hooks/block_destructive_bash.py`, and
  `hooks/block_destructive_cmd.py`
- `scripts/trusted_git.py`, `scripts/trusted_gh.py`,
  `scripts/check_changelog.py`, and `scripts/check_gate_pr_integrity.py`

CI runs ruff on `tools/` only, so no check depends on those fixes.

### fsmonitor rule in `hooks/_gate_core.py`

True drift. `tests/test_builtin_fsmonitor_gate.py` and
`tests/test_fsmonitor_version_compatibility.py` exist only here. On Git
2.35.2 or later, a boolean `core.fsmonitor` value selects the built-in daemon
rather than a program path. The local rule lets `git status` run without a
prompt in that case. Every other `core.fsmonitor` value still prompts.

### Dependabot changelog automation

Declined removal. Upstream removed
`.github/workflows/dependabot-changelog.yml`,
`scripts/create_dependabot_changelog_pr.py`, and
`tests/test_dependabot_changelog.py` after `848d069`. This repository keeps
all three.

### `actions/github-script` pin in `gate-integrity.yml`

Expected to differ. Upstream pins `actions/github-script` 7.1.0.
`tests/test_action_version_pins.py` allows only the reviewed 9.0.0 pin. The
approval-timeline step uses that pin. `tests/test_gate_pr_integrity_timeline.py`
expects the 9.0.0 SHA here, with active-human approval of that specification
change.

### Checkers and tests this repository holds alone

`scripts/check_protected_files.py` and `scripts/jira_sync.py` have no template
counterpart. The template declined `check_protected_files.py`. The
server-side backstop for edits to `hooks/`, `.claude/`, `.codex/`, `.gemini/`,
`.agents/`, and `docs/agent-policy/` is this repository's own, through
[`protected-file-review.md`](protected-file-review.md).

### `tests/test_foucault_review_wiring.py`

Expected to differ. The template's `tests/test_security_review_wiring.py`
pins that repository's foucault revision and trigger workflow. This
repository adapts it under a new name with its own pin, its `Checks`
trigger, and digest checks for the copied adapters. The template file is
not adopted.

## Changing a template file here

Record the change above. Open an issue in `abuzucom/agents` naming the file,
the change, and whether it belongs upstream. The template adoption steps
require that issue. No check enforces it.
