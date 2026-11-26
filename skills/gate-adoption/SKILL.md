---
name: gate-adoption
description: Atomic adoption procedure for the shared gate set.
---

# Gate adoption

Rule 18 makes adoption atomic across every client.

## Steps

1. Pin the source to one full commit SHA. Do not adopt from a branch.
2. Verify each shared file digest against the source `policy-digests.json`
   entry for that release. Stop on any mismatch.
3. Show the human the full diff of every shared skill and hook.
4. Generate adoptable policy with `python scripts/sync.py --print-adoptable`.
5. Stage the candidate under `.gate-staging/<candidate>`.
6. Run `python scripts/complete_gate_adoption.py --candidate .gate-staging/<candidate>`.
7. Fill adopter files:
   - `docs/project-orientation.md` with the canonical revision
   - `hooks/primary-branch.txt` when the primary branch is not `main`
   - `hooks/trusted-owners.txt`, asking for each owner in its own prompt.
     An empty or absent list keeps every test runner at ask.
   - `hooks/workflow-scripts.local.txt` for adopter scripts, confirming each
     entry in its own prompt. An entry may not repeat a shared entry.
8. Run `python scripts/check_local_paths.py --report`. Show each finding.
   Get a separate decision per proposed allowlist entry.
9. Run the verification list:
   - `python scripts/check_gate_adoption.py`
   - `python scripts/check_hook_launchers.py`
   - `python scripts/check_hook_coverage.py`
   - `python scripts/sync.py --check`
   - `python scripts/sync.py --check-shared`
10. Before the first push, follow the template upgrade merge order below.
    Run `python scripts/plan_template_upgrade.py --base <revision>`.

A failed step keeps the last verified set.

## Template upgrade merge order
Base branch consumers judge a template upgrade pull request. A local pass
cannot predict the consumer verdicts. These consumers read the base branch:

- `immutable-conflict-check.yml` with `scripts/check_compliance_tree.py`
- `gate-integrity.yml` with `scripts/check_gate_pr_integrity.py` and
  `scripts/check_pr_base.py`
- the agent prose gate in `agents-compliance.yml`. It scans whole gate
  target files.
- the CodeQL configuration named by the `github-codeql-config-file` property
- every adopter `workflow_run` review caller
- branch protection and rulesets on the base branch

Before the first push:

- Run `python scripts/plan_template_upgrade.py --base <revision>` with
  `--message <path>` for each planned commit message and pull request body.
- Run each base branch checker from a base checkout against the candidate.
- Run the prose checkers on every gate target file of the candidate.
- Report each expected failure to the active human with its owner action and
  the planned order. Push nothing before that report.

Merge the stack in this order:

1. Prose fixes for the gate target files, against the base branch.
2. Review caller changes, against the base branch.
3. The template upgrade, on top.

Rule 18 forbids a partial gate set. A base branch checker change lands only
through one of these paths:

- An owner merges past `immutable-compliance` after review.
- A template release keeps the previous workflow schema valid for one
  revision.

Keep one `CHANGELOG.md` entry per UTC date across the stack. Each rebased
layer merges its lines into the same-day entry under the highest version.

## Source publishing tooling
The source repository keeps `scripts/release.py`,
`.github/workflows/release.yml`, and the release tests. Its
`hooks/workflow-scripts.local.txt` lists the release forms. Each adopter
supplies its own publishing process. The release wording rule of the agent
prose gate applies to every adopter.

## Client map

- In every client, the transaction hook allows only fixed checks, reads,
  and `.gate-staging/` writes while adoption stays incomplete.

## Enforcement

Tier 1 for the required files through `check_gate_adoption.py` in CI.
Tier 3 for the digest and diff review steps.

Tiers: `docs/enforcement-matrix.md`.
