# PR security review

`.github/workflows/security-review-pr.yml` runs the `abuzucom/foucault`
security reviewer against every same-repository pull request. The reviewer
loads `AUDIT.md` as the model's system prompt and returns a verdict of
`APPROVE`, `BLOCK`, or `NEEDS-HUMAN`.

## Event flow

1. A pull request event starts the `Checks` workflow.
2. `Checks` completes and starts `security-review-pr.yml` through
   `workflow_run`. That event runs the caller from `develop`. A pull request
   therefore cannot edit the reviewer that judges it.
3. The `resolve-pr` job maps the run's head commit to exactly one pull
   request. It skips a head that already carries a `security-review` check
   run with a verdict.
4. A fork pull request gets the `fork-review-skipped` job and no secret.
5. A same-repository pull request calls the reusable
   `abuzucom/foucault/.github/workflows/security-review.yml`.
6. The reusable workflow checks out the base commit and fetches the head
   object without checking it out. It never executes pull request content.
7. The workflow posts a fenced review comment and a `security-review` check
   run on the head commit. `BLOCK` and `NEEDS-HUMAN` fail the check.

## Pins

Both `uses:` and `audit_ref` pin foucault release 3.3.14 at
`06d74fba4d9013654cdaf9896bb7535724385186`. Update both together, never to a
tag or branch.

The reusable workflow runs these files from this repository's own base
checkout. Each file is a verbatim copy from the pinned foucault revision:

- `ci/build_pr_case.py`
- `ci/run_model_command.py`
- `ci/call_model.py`
- `ci/model_providers.json`
- `scripts/check_pr_review_response.py`, part of the template `scripts/` set

`tests/test_foucault_review_wiring.py` checks the pins, the secret mapping,
the fork skip, and the SHA-256 digest of each copied file. A foucault upgrade
updates the pins, the copies, and the recorded digests in one change.

## Provider and secret

`ci/model_providers.json` selects Ollama with `kimi-k2.7-code`. The caller
maps only the `OLLAMA_API_KEY` repository secret to `MODEL_API_KEY`. It never
uses `secrets: inherit`, since the job sends an untrusted diff to a provider.

## Setup

- Add the `OLLAMA_API_KEY` repository secret. The review fails until it
  exists.
- After the first successful run, optionally require the `security-review`
  check in branch protection for `develop`.
- `workflow_run` runs appear under `develop` in the Actions tab, not on the
  pull request branch.
