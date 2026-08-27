# Template drift

This repository adopts the agent-instruction template from
[`abuzucom/agents`](https://github.com/abuzucom/agents). `scripts/sync.py`
keeps the AGENTS.md family in step; every file under `scripts/`, `hooks/`, and
`tests/` was copied by hand and is maintained here, so a local edit is
invisible upstream until somebody diffs the two repositories.

This file owns what differs locally and why. The template owns the rest:
`DRIFT.md` holds the policy and the three categories, and
`adopters/1a2n-web-visualizer.md` holds the adopted-at commit and the full list
of what this repository took versus declined. This file does not restate
either.

One part of this is mechanical. `scripts/sync.py --check-shared` compares the
seven files carrying gate decisions against `shared-files.json`, a manifest of
SHA-256 digests committed in both repositories, and it runs in CI here. A gate
fix landing upstream and not here fails this repository's check on the next
run.

Everything below that manifest is a convention. Nothing verifies it.

## What differs, and why

### `hooks/claude-code-settings.example.json`

Lists only the hooks this repository runs. The template's copy also registers
`enforce_branch_name.py` and `enforce_git_identity.py`, neither of which is
adopted here. Expected to differ.

### `tests/test_require_consent.py`

Deliberately outside the shared manifest, for the reason below.

Carries `HOOK_MATCHERS` and `test_configured_launcher_resolves_on_this_platform`,
which upstream live in `tests/test_enforce_branch_name.py`. That suite is not
adopted here, and dropping it would have dropped both assertions with it.

Losing them costs more than it looks. `HOOK_MATCHERS` fails when a registered
hook is not declared, so a hook can be wired to a matcher nobody reviewed. The
launcher test asserts that the `command` string in each settings file resolves
on the running platform, and Claude Code treats a hook that fails to start as a
non-blocking error, so a launcher that does not resolve makes every gate wave
its call through in silence. The behavioral tests launch hooks through
`sys.executable` and keep passing against exactly that configuration.

This is the one difference that reads as true drift without its cause attached.
It is not: it follows from a declined file.

### GitHub Actions pinning

This repository pins every action to a full commit SHA and enforces it with
`scripts/check_action_pins.py`. The template pins by released tag. Do not copy a
tag-pinned step from the template into a workflow here; read the SHA from the
action's own repository. Expected to differ.

### Checkers this repository holds alone

`scripts/check_action_pins.py`, `scripts/check_protected_files.py`, and
`scripts/jira_sync.py` have no template counterpart. Porting
`check_protected_files.py` upstream was raised and declined, so the template
ships no protected-file check. The server-side backstop for edits to `hooks/`
and `.claude/` is this repository's own, through
[`protected-file-review.md`](protected-file-review.md).

## When you change a template file here

Record the change in the table above, then open an issue in `abuzucom/agents`
naming the file, the change, and whether you recommend upstreaming it. A
difference nobody upstreams is a difference somebody re-derives later, which is
how three checker fixes in this repository sat unnoticed until a hand diff found
them.
