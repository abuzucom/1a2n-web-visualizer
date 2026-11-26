# Template drift

This repository adopts the agent-instruction template from
[`abuzucom/agents`](https://github.com/abuzucom/agents). The template's
`DRIFT.md` owns the drift policy and its three categories.
`adopters/1a2n-web-visualizer.md` in the template owns the adopted-at commit
and the taken and declined lists. This file owns the local differences and
the reason for each.

## Adopted revision

Template commit `e05985f`, tag `v2.50.0`. Every policy and shared file
matched the `2.50.0` digests in the template's `policy-digests.json` before
adoption. The upgrade takes `scripts/`, `hooks/`, `tests/`, `skills/`, the
three skill roots, `AGENTS.md`, `docs/agent-policy/*.md`, the client hook
registrations, and the template workflows. `scripts/complete_gate_adoption.py`
installed the gate set as one transaction.

`scripts/sync.py --check-shared` compares the local shared files with the
local `shared-files.json`. The check cannot read the template. A gate fix
that lands upstream and not here passes that check. Compare against the
template revision during each upgrade.

## Not adopted

These template files serve only the template repository:

- `scripts/release.py`, `.github/workflows/release.yml`, and the
  `tests/test_release_*.py` suites. This repository has its own publishing
  process.
- `DRIFT.md`, `adopters/`, `policy-digests.json`,
  `docs/agent-policy/source-orientation.md`, `CONTRIBUTING.md.example`,
  `SECURITY.md.example`, and `.github/FUNDING.yml`.
- The template `README.md`, `CHANGELOG.md`, `LICENSE`, `SECURITY.md`, and
  `docs/project-orientation.md` content.

## What differs, and why

### `docs/project-orientation.md` and `docs/repo-guide.md`

Expected to differ. `scripts/sync.py` caps the assembled policy at 64 KiB.
The template's `AGENTS.md` plus `docs/agent-policy/*.md` leave little room.
The orientation stub therefore names only the paths that must never be
hand-edited and points to `docs/repo-guide.md`. The guide holds the full
commands, protected paths, architecture, and gotchas outside the injected
policy.

### GitHub Actions pins

Expected to differ. Every action uses a full commit SHA with a release
comment. Two pin sets coexist:

- The adopted template workflows keep the template pins.
  `scripts/check_compliance_tree.py` trusts only the exact checkout and
  setup-python steps of `immutable-conflict-check.yml`. Template tests also
  assert the `github-script` pin in `gate-integrity.yml`.
- `checks.yml`, `protected-files.yml`, and `quality-review-pr.yml` keep this
  repository's pins.

`tests/test_action_version_pins.py` accepts both reviewed SHAs for
`actions/checkout`, `actions/setup-python`, and `actions/github-script`.
The template workflows drop the AgentLint step. AgentLint is an unapproved
third-party action.

### Prose file lists

Expected to differ. `sync-check.yml`, the `Makefile` `PROSE_FILES` list, and
`TARGET_FILES` in `scripts/check_agent_prose_gate.py` name this repository's
prose files instead of the template's.

### Repository configuration files

Expected to differ. `.pre-commit-config.yaml` extends the Python checks to
`tools/`. `.gitignore`, `.claudeignore`, `.editorconfig`, and
`.gitattributes` keep this repository's entries beside the template entries.

### `checks.yml`

Expected to differ. This repository's own workflow runs the application
tests, preset validation, and HTML checks. Its four checker installs pin
Python 3.14 and install hashed wheels only, like the template workflows.
`tests/test_scan_and_hash_wiring.py` counts nine checker installs instead of
the template's five.

### Persona review callers

Expected to differ. Every agents-personas caller pins 1.0.0 at `1649e5c`.
The template pins 0.22.0 at `c43f459`. `abuzucom/agents#182` tracks the
template pin. The affected files:

- `security-review-pr.yml`, `quality-review-pr.yml`, and
  `persona-review-labels.yml`.
- `.compliance-tree-exemptions.json`. The manifest records the SHA-256 of
  the re-pinned `persona-review-labels.yml` and its reusable workflow pins.
- `tests/test_security_review_wiring.py`,
  `tests/test_quality_review_wiring.py`, and
  `tests/test_persona_label_review_wiring.py`.

`quality-review-pr.yml` keeps this repository's `actions/github-script`
pin. The quality wiring test reads each upstream workflow trigger from its
workflow file and checks that the run lookup uses that event.

### `hooks/_gate_core.py`

True drift. The file keeps this repository's lexical UNC path classification
for infrastructure paths through `_is_unc_path`.
`tests/test_unc_infrastructure_paths.py` covers it. `shared-files.json`
records the local digest. Upstream review is pending.

### Declined wiring assertions

Two template tests assert files that only the template repository ships.
This adoption removes those two methods under recorded active human
sign-off. The other methods in each file still run.
`abuzucom/agents#187` tracks the upstream fix.

- `tests/test_policy_marker_names.py`,
  `MarkerNameTest.test_live_policy_uses_new_markers`. The method reads
  `docs/agent-policy/source-orientation.md`.
- `tests/test_source_publishing_scripts.py`,
  `SourcePublishingScriptListTest.test_local_list_supplies_release`. The
  method expects `scripts/release.py` entries in
  `hooks/workflow-scripts.local.txt`.

### Checkers and tests this repository holds alone

`scripts/check_protected_files.py` has no template counterpart.
The template declined `check_protected_files.py`. The
server-side backstop for edits to `hooks/`, `.claude/`, `.codex/`, `.gemini/`,
`.agents/`, and `docs/agent-policy/` is this repository's own, through
[`protected-file-review.md`](protected-file-review.md).

## Changing a template file here

Record the change above. Open an issue in `abuzucom/agents` naming the file,
the change, and whether it belongs upstream. The template adoption steps
require that issue. No check enforces it.
