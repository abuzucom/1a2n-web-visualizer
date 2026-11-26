# Pull request reviews

This repository calls the `abuzucom/agents-personas` foucault security review
and euler quality review. The `docs/` and `reviewers/` directories of
agents-personas own the architecture and the trust boundary. This document
records only the local wiring.

## What runs

`.github/workflows/security-review-pr.yml` triggers on completion of the
`Immutable Compliance` workflow. It resolves the pull request from the
workflow run head. It then calls the agents-personas
`foucault-security-review.yml` wrapper. The wrapper loads the engine, the
foucault prompt, and the model adapter from the pinned revision. It builds the
review case without the provider key. It sends each envelope to the
configured provider, posts a fenced report, and publishes a
`foucault / security` check run.

`.github/workflows/quality-review-pr.yml` calls the
`euler-quality-review.yml` wrapper at the same revision. The review starts
after `Convention Sync Check` and `Immutable Compliance` both pass for the
same head. It publishes a `euler / quality` check run. The euler review skips
`tests/**`. The test suite holds destructive command fixtures for the gates.

Both callers pin the reusable workflow and `personas_ref` to agents-personas
commit `1649e5c9710fd85d6cca12006e344af27a5404a6`, version 1.0.0. One
revision for both keeps the policy and its runner together. Change the pin
only on purpose. Record the change in `CHANGELOG.md`.

Both callers set `fail_on_block: true`. A `BLOCK` verdict fails the check. A
`NEEDS-HUMAN` verdict warns and concludes neutral.

A pull request from a fork receives a skipped check from the engine and no
provider secret.

Each caller skips a head with a GitHub Actions check run that already carries
a `VERDICT:` title. The caller trusts that check only when its check suite
belongs to a `workflow_run` execution of the same caller file. A run that ends
before a verdict carries another title. The next event for that head then
retries the review.

The `workflow_run` trigger keeps each caller on default branch code. A caller
change takes effect only after it reaches `main`. The review appears on a
pull request only after the upstream runs finish for that head. Find the
`security-review-pr` and `quality-review-pr` runs under the default branch in
the Actions tab.

This repository vendors no adapter or response validator. The engine
supplies both from the pinned revision.

## Tests

- `tests/test_security_review_wiring.py` covers the foucault caller.
- `tests/test_quality_review_wiring.py` covers the euler caller.
- `tests/test_review_verdict_producer.py` covers the verdict producer check
  in both callers.

## Required repository secret

The review stays idle until an active human adds the provider API key as a
repository secret. No agent sets it, and no agent commits it.

The active profile in the pinned `engine/model_providers.json` selects the
provider. The callers map `secrets.OLLAMA_API_KEY` to the reusable workflow's
`MODEL_API_KEY`. Neither caller uses `secrets: inherit`.

Add the key under Settings, Secrets and variables, Actions, as
`OLLAMA_API_KEY`. Until the secret exists, the `foucault / security` and
`euler / quality` checks fail. That failure reflects the absent secret. It
reports no finding against the diff.

## Required checks

The `main` ruleset requires the `security-review` check from the former
foucault caller. The caller on `main` reviews the promotion pull request from
`develop` to `main`. The former caller publishes only `security-review`.
Keep that requirement until the promotion pull request merges. Then replace
it with `foucault / security` and `euler / quality`. An administrator
fast-forward runs no required check. That path permits the swap at any time.
Repository files cannot change a ruleset.
