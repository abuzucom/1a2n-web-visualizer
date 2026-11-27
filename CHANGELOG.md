# Changelog

This file records all notable changes to this project. The format loosely
follows [Keep a Changelog](https://keepachangelog.com/). This project aims to
use [Semantic Versioning](https://semver.org/).

## [1.25.1] (2026-11-27)

### Added
- Adopt the `abuzucom/agents` template at `e05985f` (v2.50.0). The upgrade
  adds the new hooks, checkers, tests, and skills, the template issue and
  pull request templates, `persona-review-labels.yml`,
  `policy-size-report.yml`, and `.compliance-tree-exemptions.json`.
  `docs/template-drift.md` lists each difference.
- Add `hooks/workflow-scripts.local.txt` for this repository's checker
  scripts and trust `abuzucom` in `hooks/trusted-owners.txt`.

### Changed
- Correct the branch protection notes in `docs/repo-guide.md`. A classic
  branch protection rule also covers `develop` and blocks force pushes. The
  `develop` reset in the promotion process needs force pushes allowed for
  the reset only.
- Reword `README.md`, `SECURITY.md`, `docs/repo-guide.md`, and
  `CHANGELOG.md` to satisfy the template prose checkers. The agent prose gate
  scans each file whole on every pull request with agent trailers. Facts
  stay the same. The README handoff paragraph keeps its wording. A current
  test pins that wording until the template upgrade replaces the test.
- Reword the README handoff paragraph. The adopted template test pins the
  new wording.
- Merge same-day `CHANGELOG.md` entries under the newest version of each
  day. Correct the 1.14.0 date to 2026-09-29.
- The template gate workflows follow the template trigger model.
  `Immutable Compliance` runs on `pull_request_target` with the base branch
  checker. The gate workflows drop the branch filters and push triggers.
  `quality-review-pr.yml` looks up `Immutable Compliance` under
  `pull_request_target`.
- The branch checker exempts `develop`. The attribution checker accepts the
  signed GitHub web-flow committer of a web merge.
- The template workflows keep the template action pins. The repository
  workflows keep the repository pins. `tests/test_action_version_pins.py`
  accepts both reviewed releases.
- `checks.yml` installs checker dependencies as hashed wheels on Python
  3.14.
- The Windows job in `checks.yml` runs the Python suite before `npm ci`. A
  template test copies the whole working tree, and `node_modules` pushed
  that copy past the 30-second shard timeout.
- Record the dismissed CodeQL alerts in template files in
  `docs/template-drift.md`.
- Rename 91 local tests to at most five words after `test_`. Each renamed
  test keeps its description in a docstring.

### Removed
- Remove the retained foucault 3.3.14 adapter copies under `ci/`,
  `scripts/check_pr_review_response.py`, and the matching tests, including
  `tests/test_review_adapter_digests.py` and
  `tests/test_protected_review_adapters.py`.
- Remove the Dependabot changelog companion workflow, its script, and its
  test. The template removed it. Dependabot pull requests need manual
  changelog entries.
- Remove `.agents/skills/github-draft`. The template skill
  `commit-and-draft-pr` replaces it.
- Remove the local built-in fsmonitor allowance and its tests. `git
  status` with any `core.fsmonitor` value prompts again.

## [1.24.0] (2026-11-26)

### Added
- Add `.github/workflows/quality-review-pr.yml`. It runs the
  `abuzucom/agents-personas` euler quality review after `Convention Sync
  Check` and `Immutable Compliance` both pass. The review publishes a
  `euler / quality` check and skips `tests/**`.
- Add `tests/test_security_review_wiring.py`,
  `tests/test_quality_review_wiring.py`, and
  `tests/test_review_verdict_producer.py` from the `abuzucom/agents`
  template at `e05985f`. Each pins agents-personas 1.0.0.
- Add `tests/test_review_adapter_digests.py`. It pins the retained foucault
  3.3.14 adapter copies until the template upgrade removes the copies.
- Document branch promotion in `docs/repo-guide.md`. A pull request promotes
  `develop` to `main`. A forced reset then returns `develop` to `main`. An
  administrator fast-forward remains the fallback.

### Changed
- `.github/workflows/security-review-pr.yml` calls the agents-personas
  `foucault-security-review.yml` wrapper. It runs after `Immutable
  Compliance` and publishes a `foucault / security` check.
- Both review callers pin `uses:` and `personas_ref` to agents-personas
  commit `1649e5c9710fd85d6cca12006e344af27a5404a6` (1.0.0).
- The engine publishes the skipped check for a fork pull request. The caller
  drops its fork job.
- A review caller trusts a prior `VERDICT:` check only from its own
  `workflow_run` execution.
- Describe both reviews in `docs/pr-security-review.md`, `README.md`,
  `docs/repo-guide.md`, and `docs/template-drift.md`.

### Removed
- Remove the `abuzucom/foucault` 3.3.14 pin.
- Delete `tests/test_foucault_review_wiring.py`. The new wiring tests and
  `tests/test_review_adapter_digests.py` replace it.

### Fixed
- Set the root version in `package-lock.json` to match `package.json`. The
  lockfile still recorded 1.22.5.

## [1.23.1] (2026-11-24)

### Changed
- Correct the staging hostname. The staging environment serves the `develop`
  branch at `develop.visualizer.1a2n.net`.
- Deploy the site through Vercel instead of GitHub Pages. `vercel.json`
  publishes `src/` as a static site, and `.vercelignore` keeps the rest of
  the repository out of the deployment payload.
- `main` publishes the production environment at `visualizer.1a2n.net`.
  `develop` publishes the staging environment at `test.visualizer.1a2n.net`.
  Every other branch receives a preview deployment.
- Run the `Checks`, `Convention Sync Check`, `AGENTS.md Compliance`, `Gate
  Integrity`, and `Immutable Compliance` workflows on `main` as well as on
  `develop`.
- Target `develop` in `.github/dependabot.yml`. Dependency pull requests land
  on the staging branch.
- Describe the Vercel deployment in `README.md`, `SECURITY.md`,
  `docs/local-hosting.md`, `docs/repo-guide.md`, `docs/protected-file-review.md`,
  and `docs/pr-security-review.md`.

### Removed
- Delete `.github/workflows/deploy.yml`. Vercel deploys through its Git
  integration. No GitHub Actions workflow publishes the site.
- Delete `tests/test_pages_deployment_boundary.py`. Add
  `tests/test_vercel_deployment_boundary.py` to assert the Vercel deployment
  boundary.

## [1.22.5] (2026-11-18)

### Changed
- `docs/repo-guide.md` states that both preset validators parse every
  converted equation with acorn and catch a JS `SyntaxError`. Both still
  miss shader link failures and errors that appear only at run time.
- Correct the docstrings of `runBatch` and `main` in
  `tools/convert-milk-presets.js`, `main` in
  `tools/convert-shader-worker.js`, and `readChunk` and
  `findInvalidPresets` in `tools/validate-preset-chunks.js`.
- `main` in `tools/convert-milk-presets.js` is no longer `async`. It
  awaits nothing.
- Drop the unused `index` parameter from `readChunk` in
  `tools/validate-preset-chunks.js`.
- Correct seven comments in `src/js/visualizer-core.js` that contradicted
  the code: the file header, `unplayedNames`, `removeCurrent`,
  `favoriteCurrent`, `createPlaybackController`, `loadExtraImages`, and
  `createAudioController`.
- `start()` in `src/js/fullscreen-ui.js` is no longer `async`. It awaits
  nothing, and no caller awaits it.
- Drop a check in `src/js/performance-ui.js` that can never fail. Every
  name in a category cycle already has a runtime index.
- `src/js/obs-ui.js` lowercases the preset names once at load instead of
  on every filter rebuild.
- Share one bracket matcher and one `index.js` reader between
  `tools/remove_presets.js` and `tools/analyze_curation_history.js`
  through the new `tools/preset_source.js`. The chunk reader moves there
  too. `analyze_curation_history.js` now rejects an `index.js` with an
  unexpected wrapper instead of slicing it blindly.
- The removal and history tool test fixtures copy
  `tools/preset_source.js` beside the tool under test.
- Use the shared `BCViz` helpers in `obs-ui.js`, `fullscreen-ui.js`,
  and `performance-ui.js`. The page scripts no longer carry separate
  `describeDeviceError`, audio-prefs fallback, or shortcut filter copies.
  Behavior stays the same.
- Give the page-script unit tests the real shared `BCViz` helpers. The
  new `tests/support/bcviz-stub.js` loads the helpers from
  `visualizer-core.js` beside each test's own `create()`. No assertion
  changes.

### Added
- Cover the case-insensitive OBS preset filter in
  `tests/test_obs_preset_filter.js`.
- Cover the shared matcher and wrapper readers in
  `tests/test_preset_source.js`.
- Fail the test suite when a page script defines its own copy of a
  shared `BCViz` helper. The check covers declarations, function
  expressions, and arrow functions.
- Expose `describeDeviceError`, `audioPrefs`, and `shouldIgnoreShortcut`
  on `BCViz`. Each page script carries its own copy of these helpers
  today. `audioPrefs` returns an inert store when `audio-prefs.js` is
  absent. `describeDeviceError` keeps its fallback for a missing
  `device-errors.js`. The existing `create` and `createPlayedSession`
  properties stay unchanged.
- Fail the test suite when a `tools/*.py` file carries a `noqa`
  suppression.

## [1.21.1] (2026-11-17)

### Fixed
- Warn on stderr when the `--names-file` path of
  `tools/remove_presets.js` resolves outside the repository. The check
  follows symlinks. The run continues. Callers that keep a names file
  elsewhere keep working.

### Changed
- Pin the `lodash` override to the locked version, 4.18.1.
- Pull the Caddy base image by digest instead of the moving
  `caddy:2-alpine` tag.
- Install ruff 0.16.9 in CI from `requirements-ruff.txt` with
  `--require-hashes`. The unversioned `astral-sh/ruff-action` step is gone.
  The lint rules in `pyproject.toml` stay the same.

### Added
- A report-only CI step that runs the organization ruff baseline from
  `.github/ruff-baseline/` and prints finding counts. It never fails the
  build.

## [1.20.5] (2026-11-15)

### Fixed
- Stop `tools/import-nestdrop-presets.py` from appending duplicate
  `skipped` and `collisions` records to `experimental-presets.json` on
  every re-run over the same archive. Existing records stay unchanged.
- Split the importer's `extract_source` and `main` into stages, name its
  file-mode and marker constants, remove an unreachable path check, and
  drop its inline lint suppressions.
- Escape the `--reason` text in the ledger row that
  `tools/remove-experimental-duplicates.py` writes. A reason with a comma
  split the row into extra columns.
- Clear the energy and performance catalog entries of removed experimental
  presets, and rewrite both runtime bundles. A removed preset left its
  catalog entries behind.
- Split the removal tool's `main` into stages and drop its file-wide lint
  suppression.

## [1.20.3] (2026-11-13)

### Fixed
- Remove only the inventory row of the resolved pack in
  `tools/remove_presets.js`. A name held by two packs lost both rows, and
  the run aborted.
- Count only names gone from every chunk as removals in
  `tools/analyze_curation_history.js`. A preset that moved to another
  chunk counted as removed.
- Remove the temporary directory after a failed write in
  `tools/remove_presets.js` and `tools/convert-milk-presets.js`.
- Warn on stderr about an unrecognized argument to
  `tools/remove_presets.js`. A misspelled `--dry-run` no longer passes
  without notice.
- Exit with an error when `--name` or `--names-file` has no value.
- Complete a removal on a re-run after a failed run rewrote a chunk file.
  The re-run skips a name that the ledger records and the chunk no longer
  holds.
- Name the physical chunk file, such as `chunk-9000.js`, in chunk error
  messages.
- Describe the tool's write order and checks accurately in its header.
- Skip already indexed names in `tools/import-nestdrop-presets.py`. A
  re-run after a stop past the index write indexed the batch twice.
- Write the vendored textures first in `tools/import-nestdrop-presets.py`.
  A texture failure left presets indexed without the matching textures.
- Finish an interrupted removal on a re-run in
  `tools/remove-experimental-duplicates.py`. The index now goes first and
  the manifest last. Ledger rows and exclusions skip names already
  recorded.
- Build every texture part before any write in
  `tools/split-extra-images.py`. A failure partway left parts that
  disagreed on the part total.
- Close the inventory file and replace it atomically in
  `tools/reconcile_preset_inventory.py`.
- Write LF line endings on every platform in
  `tools/import-nestdrop-presets.py`. Its writer copy wrote CRLF on
  Windows.
- Remove the temporary file after a failed write in
  `tools/fetch-cream-of-the-crop-presets.py`.
- Report counts in `tools/fetch-cream-of-the-crop-presets.py` that add up
  to the converted count. The inventory count ignores case, the way the
  filter does. A name in both ledgers counts once.
- Fail `npm run validate:exp` when an experimental preset carries an
  invalid equation. The CI step now blocks such a preset.
- Accept a preset index without a `files` map in both preset validators.
  The chunk validator reads the padded chunk names the runtime falls back
  to.
- Disconnect the audio source from the old visualizer before a WebGL
  rebuild. The old analyser chain stayed connected after every recovery.
- Reload the experimental textures for a rebuilt visualizer. `[EXP]`
  presets loaded without textures after a recovery.
- Rebuild the visualizer on the next watchdog restart after a render
  failure. A plain driver restart left rendering off while the driver
  reported healthy ticks.
- Discard a worklet module load that finishes after the render driver
  stops. The late load connected a node with no owner.
- Clear the failed mark for presets in a chunk that arrives after its
  timeout. Those presets stayed ineligible for the whole session.
- Start the fullscreen and performance pages on the remembered audio
  input. The pages resolved the saved input against an empty device list.
  The fullscreen page then replaced the saved choice with the system
  default.
- Stop reporting a released input after a failed device switch. The core
  and the OBS panel named the old input while the visualizer had none.
- Record each appended chunk in the index `files` map in
  `tools/fetch-cream-of-the-crop-presets.py`. Index readers reject an index
  with differing chunk and file counts.
- Create a new index in `tools/fetch-cream-of-the-crop-presets.py` when none
  exists.
- Refuse a full regeneration in `tools/fetch-extra-presets.py` and
  `tools/fetch-extra-presets-curated.py` when the index has a `files` map. The
  wipe would delete every experimental chunk.
- Bound the upstream download in `tools/fetch-extra-presets.py` with a
  timeout.
- Close the upstream archive and read the texture name list as UTF-8 in the
  three fetch tools.

### Changed
- Move the atomic file writer and the preset hash into the shared
  `tools/preset_io.py` module. Four tools carried a separate writer copy.
  Two tools carried a separate hash copy. The duplicate-content report
  compares against hashes that the importer recorded.

## [1.19.5] (2026-11-09)

### Changed
- Update ESLint to 10.14.0.
- Use the hosted runner's default Java for HTML and CSS validation.

## [1.19.4] (2026-11-07)

### Added
- Record the energy category of 84 curated presets in the energy catalog.

### Removed
- Remove 8 presets on request. The batch covers 6 mainline presets and 2
  experimental presets.

### Fixed
- Restart the preset cycle timer after an energy curation key. The keys
  reset the timer now, the way the shuffle removal key does.
- Drop every requested preset in one curation run. The removal pass rebuilt
  the catalog from the original list. Only the last removal survived.
- Record the pack the runtime plays in a catalog entry. A name that exists
  in two packs plays from the vendored pack.
- Load a missing performance catalog as an empty list. The shared default
  had the wrong shape and crashed the curation tool.
- Replace the category of the same preset when an assignment names another
  pack. The catalog and the validator now agree on one category per preset.
- Reject an assignment for a pack that holds no preset. The validator
  rejected such a catalog after the curation tool wrote it.
- Keep a catalog entry for a pack that the removal did not target. The
  removal tool now matches the pack that the removal removed.
- Copy the bare preset names when the clipboard write fails. The manual
  fallback now copies the same text as the button.
- Follow the page attribute for the curation feature. The panel markup no
  longer decides whether the curation keys work.
- Load the shared catalog helpers without a lint suppression.
- Wrap the long removal tool test fixture line. The CI lint job checks
  every Python file, and that fixture line ran past the line limit.
- Assert the played session pick by exclusion. The old assertion named one
  preset from a pool of two. It passed or failed at random.

## [1.19.0] (2026-11-06)

### Added
- Add an energy catalog that gives each preset one low, medium, or high
  category.
- Add a performance catalog that lists the presets curated for performance
  playback.
- Add the energy curation keys to the fullscreen build. The keys record the
  category for the current preset and move on to a preset that has not
  played yet.
- Add an assigned-presets panel to the fullscreen build. It lists the
  session assignments under low, medium, and high. The panel copies the
  preset names for a later removal session. The panel copies the catalog
  assignment block separately.
- Add a performance page. The keys play the next preset of the pressed
  energy from the performance catalog. Every eligible preset plays once per
  category cycle. Each following cycle uses an order that differs from the
  previous one.
- Add `tools/curate_catalogs.py` for the energy and performance catalogs.
- Add `tools/validate_catalogs.py` for the catalog checks.

### Changed
- Clear the removed presets from both catalogs in the removal tool.
- Report the catalog changes in the dry-run output of the removal tool.

## [1.18.2] (2026-11-04)

### Removed
- Remove 19 curated presets from PR 173 across the current collections.
  The batch covers 14 mainline presets, four original experimental presets,
  and one vendored preset. The inventory contains 18,155 presets.
- Preserve the EXP4 import, converter repairs, Jira removal, and newer curation records.
- Remove the remaining Jira integration and deployment publishing step.
- Remove the sync script, dedicated tests, integration guide, and current documentation references.

### Documentation
- Remove obsolete integration references from the repository guide and template drift notes.

### Tests
- Preserve Pages permissions, pinned deployment actions, and failure retry behavior.

### Added
- Import 228 curated `[EXP4] ` presets across five sources in two lazy-loaded chunks.
- Record pinned source paths, content hashes, upstream license notices, and unresolved rights.
- Preserve current curation and PR 173 exclusions. The inventory contains 18,174 presets.

### Fixed
- Correct custom wave and shape parser calls and preserve wave point equations.
- Require runtime equation fields and report custom equation conversion failures.
- Separate converted expressions from the runtime return statement.
- Adapt optimized native shaders with the matching upstream postprocessor.
  Preserve helper declarations and bound shader size and delimiter nesting.

## [1.16.11] (2026-11-01)

### Removed
- Removed 38 presets on request. The removals cover 26 mainline presets
  from `src/presets-extra/`, 11 `[EXP] ` presets, and 1 `[EXP3] ` preset.
  `tools/remove_presets.js` handled the mainline removals.
  `tools/remove-experimental-duplicates.py` handled the experimental
  removals. The preset inventory now holds 17,946 rows across 582 logical
  chunks.

### Security
- Bumped `fast-uri` from 3.1.8 to 3.1.9. The release fixes four URI parsing
  and normalization advisories. The fixed defects cover percent-encoded
  scheme spoofing, host confusion in domain canonicalization, incorrect
  relative-reference normalization, and scheme injection in suffix
  references.
  `fast-uri` reaches this repository only as a development dependency of
  `serve`.

### Fixed
- Load non-EXP lazy presets without waiting for the experimental texture
  parts. R and X no longer stall for the whole texture download, or
  forever when a texture part never answers.
- Stop waiting for experimental textures after 10 seconds. A stalled
  texture part no longer blocks EXP presets.
- Skip EXP presets in random picks until the matching textures are ready.
- Prefetch the next random preset from the first rendered frame onward.
  R, X, and shuffle cycling apply an already loaded preset.
- Mark a lazy preset missing from its loaded chunk as unavailable.
  Fallback no longer retries it in a loop.
- Count each broken preset once when deciding whether a fallback can
  still find a working preset.
- Pick random presets in constant time in the common case instead of
  scanning the whole library on every pick.
- Log lazy preset load failures with the preset name instead of leaving
  an unhandled rejection.

## [1.16.8] (2026-10-31)

### Fixed
- Set the `package.json` and `package-lock.json` version to match the
  changelog. Both files read 1.16.3 before this change.
- Start the mobile visualizer from a native button. Keyboard users can
  now reach and activate it.
- Keep mobile controls visible while keyboard focus stays inside the
  controls. Focus and key presses wake the faded controls.
- Keep the mobile audio error visible in the help box after a failed
  start.
- Remove hidden fullscreen and demo list panels from the tab order and
  the accessibility tree. Closing a panel returns focus to its opener.
- Give the excluded and favorites panels dialog semantics. Label each
  panel's text area with the panel heading.
- Keep the fullscreen corner buttons out of the tab order before
  startup and while a list panel covers the buttons. Name each emoji button.
- Leave Space and Enter on focused buttons to native activation. Typing
  in a text field and Ctrl, Cmd, or Alt combinations no longer trigger
  shortcuts.
- Announce fullscreen and demo toasts through a polite live region.
  Keep a failed start reason visible in the help box.
- Announce OBS status updates through a polite live region.
- Label the OBS preset filter and the auto-cycle interval field. The
  interval label states the unit in seconds.
- Remove the hidden OBS panel from the tab order.
- Raise small text contrast to at least 4.5:1. The landing subtitle and
  footer use charcoal. The demo card uses pitch text on paper with a
  pitch outline. OBS hints use concrete.

## [1.16.6] (2026-10-26)

### Dependencies
- Combined Dependabot bumps:
  - `eslint` 10.12.0 to 10.13.0 (dev dependency)
  - `actions/setup-python` 7.0.0 to 7.1.0
- Moved the reviewed `actions/setup-python` pin to the 7.1.0 commit in the
  immutable compliance scanner and the action pin test.

## [1.16.5] (2026-10-21)

### Fixed
- Keep each landing page card title on one line by sizing the title for
  each card layout.
- Place each landing page card description directly under its title at a
  consistent height.
- Loosen the landing page heading letter spacing so adjacent glyphs no
  longer touch, and enable font kerning.
- Tighten the "1a" and "li" pairs in the landing page heading.

### Dependencies
- Combined Dependabot bumps:
  - `acorn` 8.18.0 to 8.19.0 (dev dependency)
  - `eslint` 10.11.0 to 10.12.0 (dev dependency)
  - `actions/setup-node` 7.0.0 to 7.1.0
  - `actions/upload-artifact` 7.0.1 to 7.0.2
  - `actions/setup-java` 6.0.1 to 6.1.0
  - `actions/download-artifact` 8.0.1 to 8.0.2
- Recorded the full release version in the `checks.yml` pin comments for
  `actions/setup-node` and `actions/upload-artifact`.
- Added a test that holds each reused action in `checks.yml` to one revision.

## [1.16.3] (2026-10-08)

### Fixed
- Require Git 2.35.2 or newer before treating `core.fsmonitor` boolean
  spellings as non-executable.
- Separate appended removal records when the existing ledger lacks a final
  line ending.
- Avoid resolving external UNC write targets against a local repository path.
- Inspect UNC infrastructure paths lexically without opening remote manifests.
- Run slow remediation, branch-review, and branch-context coverage in
  isolation with the resource timeout.

### Changed
- Tightened the hook coverage baseline after fsmonitor regression coverage
  reached another Git config parser statement.
- Updated the shared gate manifest after the fsmonitor correction.

## [1.16.0] (2026-10-07)

### Changed
- Extended experimental curation to numbered prefixes and approved unmatched
  targets. Preserved existing removal-ledger bytes when appending records.
- Classified built-in `core.fsmonitor` boolean values as non-executable.

### Dependencies
- Combined Dependabot bumps:
  - `actions/checkout` 4.2.2 to 7.0.1
  - `actions/setup-python` 5.6.0 to 7.0.0
  - `actions/github-script` 7.1.0 to 9.0.0
  - `actions/upload-code-coverage` 1.4.2 to 1.4.4
  - `brace-expansion` 1.1.16 to 1.1.21 and 5.0.7 to 5.0.12 (dev dependency)
- Updated the immutable workflow validator's trusted action pins to match the
  upgraded `actions/checkout` and `actions/setup-python` versions.

## [1.15.0] (2026-10-03)

### Security
- Added `src/presets-extra/` to the protected paths in
  `scripts/check_protected_files.py` and `.github/CODEOWNERS`. The pages load
  every chunk as a script. A chunk change now needs owner approval like
  `src/js/` and `src/vendor/`.
- Added `tools/check_preset_equations.py`. It tokenizes every compiled preset
  equation and rejects anything outside the converter vocabulary. It also
  rejects code outside the JSON payload of each chunk and `index.js`.
  `npm run validate:equations` runs it. All shipped presets pass.
- Pinned `lcov_cobertura` 2.1.1 and `coverage` 7.16.2 in
  `.github/workflows/checks.yml`.

### Added
- Added `tests/test_protected_preset_chunks.py` and
  `tests/test_preset_equation_allowlist.py`.

### Removed
- Removed the committed `comments.json` GitHub API dump. `.gitignore` now
  lists it.

### Changed
- `docs/repo-guide.md` records known vendored provenance and the accepted
  risks from the security review. It drops the missing `jira.yml` workflow.
- `docs/jira-integration.md` states that only the deployment sync runs.
- `docs/protected-file-review.md` names the `pull_request` trigger that
  `protected-files.yml` uses.

## [1.14.2] (2026-10-02)

### Changed
- Added a `push` trigger scoped to `develop` in `.github/workflows/checks.yml`
  so the default branch produces a Cobertura coverage baseline for
  comparison. Gated the jobs unrelated to coverage
  (`tests-windows`, `agents-md-sync`, `static-checks`, `lint`,
  `validate-presets`, `html-css-validation`) to `pull_request` only so the
  push trigger runs only the coverage-producing `unit-tests` and
  `upload-coverage-*` jobs.
- Untracked the stale committed coverage artifacts (`.coverage`,
  `coverage.lcov`, `coverage-js.xml`, `coverage-js-new.lcov`,
  `coverage-python.xml`) that predated this change. `.gitignore` already
  listed most of the files. Added the missing `coverage-js-new.lcov` entry.

## [1.14.1] (2026-09-29)

### Security
- Bumped `fast-uri` from 3.1.5 to 3.1.8. The releases fix several host
  confusion, authority injection, and server-side request forgery
  advisories. `fast-uri` reaches this repository only as a development
  dependency of `serve`.
- Stopped expanding `github.head_ref` into the `branch-name` job's shell
  script in `.github/workflows/checks.yml`. A branch name with shell syntax
  could run commands on the runner. `scripts/check_branch_name.py` reads
  `GITHUB_HEAD_REF` from the environment instead.
- Added `tests/test_workflow_script_injection.py`. The test rejects pull
  request controlled expressions inside any workflow `run:` script.

### Changed
- Bumped `eslint` from 10.9.1 to 10.11.0. `npx eslint .` stays clean.
- Bumped `actions/setup-java` from 6.0.0 to 6.0.1 in
  `.github/workflows/checks.yml` and `actions/deploy-pages` from 5.0.0 to
  5.0.1 in `.github/workflows/deploy.yml`, both pinned to full commit SHAs.
- Added `tests/test_workflow_action_pins.py`. It runs the action pin checker
  over every real workflow and requires the Pages deploy retry to use the
  same `actions/deploy-pages` revision as the first attempt.
- Replaced a `--` dash substitute in a `.github/workflows/checks.yml`
  comment with a sentence break.

### Added
- Added the `abuzucom/foucault` pull request security review:
  `.github/workflows/security-review-pr.yml` runs after `Checks` and calls
  the reusable foucault workflow pinned to release 3.3.14. `BLOCK` and
  `NEEDS-HUMAN` verdicts fail the `security-review` check. Fork pull
  requests get no provider secret.
- Added the foucault adapters under `ci/`, with named-constant lint fixes in
  `ci/call_model.py` and `ci/run_model_command.py`. Added
  `tests/test_foucault_review_wiring.py`. The test checks the pins, the secret
  mapping, and each adapter's digest.
- Added `ci/` to the protected-file review and `CODEOWNERS`. Documented the
  wiring in `docs/pr-security-review.md`.

## [1.13.6] (2026-09-28)

### Fixed
- Gated Python unit tests on `scripts/run_tests.py` and measured coverage in
  one process. Subprocess coverage tracing conflicted with the hook coverage
  tracer-scope test.
- Scoped the `tempfile.tempdir` override in `tests/test_trusted_gh.py` to
  that module.
- Restored full gate decision reasons in hook prompts and denials.
- Removed the Jira pull request workflow.
- Moved protected-file review to an unprivileged pull request trigger.
- Bound immutable scanner bootstrap to the approved pinned source checkout.
- Bootstrapped immutable compliance from the pinned `abuzucom/agents` scanner
  while the target base lacks the scanner.
- Preserved the fixed protected-value diagnostic for malformed CMD payloads.
- Moved immutable compliance to an unprivileged pull request trigger and kept
  checker setup pinned without reading a pull request dependency manifest.
- Replaced untrusted gate diagnostics with fixed safe labels while preserving
  branch-correction and unsafe Git configuration diagnostics.
- Prevented keyboard shortcut keys from wrapping onto multiple lines in the
  fullscreen and demo help dialogs.

### Changed
- Re-adopted the `abuzucom/agents` template whole at commit `848d069`:
  `AGENTS.md`, `docs/agent-policy/*.md`, every file under `scripts/` and
  `hooks/`, the matching tests, `shared-files.json`, and the hook-coverage
  baseline. `scripts/sync.py` now assembles the eight policy copies from
  `AGENTS.md`, `docs/agent-policy/*.md`, and `docs/project-orientation.md`.
- Moved the repository orientation (commands, protected paths, architecture,
  gotchas) from `AGENTS.md` to `docs/repo-guide.md`. The assembled policy has
  a 64 KiB limit that the template alone nearly fills.
  `docs/project-orientation.md` points agents at the guide and names the
  generated paths that must never be hand-edited.
- Replaced `scripts/check_action_pins.py` and its tests with the template
  versions.
- Dated the version headings from 1.8.0 through 1.12.1 and versioned the
  orphaned unreleased block as 1.7.2, as `scripts/check_changelog.py`
  requires.

### Added
- Registered the branch, identity, gate-adoption, infrastructure, CMD, and
  policy-reinjection hooks for Claude Code, Codex, Gemini, and Antigravity
  (`.claude/settings.json`, `.codex/`, `.gemini/settings.json`,
  `.agents/hooks.json`), installed as one transaction by
  `scripts/complete_gate_adoption.py`.
- Added `requirements-checkers.txt` pinning `PyYAML==6.0.3` for the YAML-based
  checkers, and CI steps for gate adoption, hook launchers, policy size,
  changelog versioning, commit identity, commit attribution, and external
  repository references.
- Added `plan/HANDOFF.md.example` and `docs/gate-threat-model.md` from the
  template.
- Added the template workflows (`sync-check.yml`, `agents-compliance.yml`,
  `agents-md-compliance.yml`, `immutable-conflict-check.yml`,
  `gate-integrity.yml`, `dependabot-changelog.yml`) retargeted to `develop`.
  Added the Makefile and pre-commit wiring that the workflows check, and the
  13 wiring tests.
- Ran the Python suite through `scripts/run_tests.py`. The runner isolates
  each test class. Measured coverage across the runner's subprocesses.
- Fixed the 152 ruff findings and the code-scanning findings in the template
  files as recorded drift. Every gate verdict over the test corpus stayed the
  same.

## [1.12.1] (2026-09-01)

### Removed
- 2,134 more presets curated out via `tools/remove_presets.js`: 1,991
  `[EXP2] ` presets, 129 `[EXP3] ` presets, 13 mainline presets, and 1
  `[EXP] ` preset. Spans `src/presets-extra/` (35 chunk files) with the
  matching `preset-inventory.csv` rows dropped and `removed-presets.csv`
  appended. Same intentional editorial curation as prior batches; see the
  *Curation* section in the README. Ships 18,224 deduplicated presets now
  (373 vendored + 17,851 from `src/presets-extra/`).

## [1.12.0] (2026-08-30)

### Added
- Imported 421 presets from
  [projectM-visualizer/presets-milkdrop-original](https://github.com/projectM-visualizer/presets-milkdrop-original)
  (pinned commit `e03b83e`), the official "Original Milkdrop Preset Pack",
  tagged `[EXP3] ` per the repo's per-batch prefix convention. Of 552
  source `.milk` files, 544 converted. Eight failed on malformed source
  equations (parse errors in corrupted custom EEL2 code). The import
  recorded each failure. The import skipped 123 files as already curated
  out, already imported, or duplicate content. One retained preset
  needed the `clouds` texture, pulled from the same
  [projectM-visualizer/presets-milkdrop-texture-pack](https://github.com/projectM-visualizer/presets-milkdrop-texture-pack)
  pin already vendored for the `[EXP2] ` batch. Five "martin"-authored source
  presets convert with a blank warp or comp shader. The source `.milk`
  files use undeclared `double2`/`double3` HLSL identifiers. The curation
  ledger already excluded all five names. The import added none of the five.
- Documented the per-batch `[EXP2]`, `[EXP3]`, ... exp-prefix convention
  in AGENTS.md so future preset-import batches stay visually
  distinguishable during curation.

### Fixed
- `tools/import-nestdrop-presets.py` now fills absent equation fields on
  newly imported presets too. Before, only already-committed chunks reached
  by `--normalize-existing` got the fill. Butterchurn compiles equations as
  `"".concat(field, " return a;")`. A missing field stringified to the
  literal `undefined` and raised `SyntaxError: Unexpected token 'return'`.
  The loader then skipped the preset. visualizer-core.js could not catch
  the error. Its `normalizeEquation` only rewrites existing strings.
  `validateEquation` returns early on a falsy value. The defect affected
  232 of this batch's 421 presets without any warning before the fix. The
  normalization runs after the importer takes the dedup digest. Duplicate
  detection therefore still compares the same canonical content that
  earlier imports recorded.
- `tools/import-nestdrop-presets.py`'s texture-bundling step now merges a
  new batch's textures with the vendored set instead of replacing the
  bundle outright. Before, an import archive without a full copy of every
  vendored experimental texture deleted the missing textures from
  `src/vendor/butterchurnExtraImagesExp-part-N.js` and
  `experimental-textures.json` without any warning.

## [1.11.0] (2026-08-29)

### Added
- Imported 2,173 presets from the "Flexis Mildrop preset collection" folder
  of [LeetCodes/milkdrop-preset-collection](https://github.com/LeetCodes/milkdrop-preset-collection)
  (pinned commit `65ea61e`), tagged `[EXP2] ` instead of the existing
  `[EXP] `. The separate tag keeps this batch visually distinct while
  curating. Of 3,008 source `.milk` files, 2,926 converted. 82 failed on
  malformed source content, mostly one corrupted equation shared across 67
  mix variants of `TonyMilkdrop - Dawning The Peacocks`. The import
  recorded each failure. The import skipped 753 files as already curated
  out, already imported, missing a texture, or duplicate content within
  this batch. The build required the native `milkdrop-shader-converter`
  addon. This environment lacked a compiled copy. See the new `--exp-prefix` flag on
  `tools/import-nestdrop-presets.py` below.
- Added 7 textures new to the experimental image bundle from
  [projectM-visualizer/presets-milkdrop-texture-pack](https://github.com/projectM-visualizer/presets-milkdrop-texture-pack)
  (pinned commit `b6e4610`), needed by a handful of the newly imported
  presets. 60 of that pack's 67 textures were already carried.
- Added `--exp-prefix` to `tools/import-nestdrop-presets.py`. The flag
  defaults to the existing `[EXP] ` string. Every prior invocation keeps
  the same behavior. A batch that should stay visually distinct from
  earlier imports while curating can now pass `--exp-prefix "[EXP2] "`.

## [1.10.0] (2026-08-28)

### Added
- Remembered the selected audio input across reloads
  (`src/js/audio-prefs.js`). OBS rebuilds a browser source from scratch on
  a scene refresh. Each refresh previously dropped the visualizer back to
  the system default input. The page matches the device by id first and by
  label second. The choice therefore also survives a Voicemeeter restart
  that hands the same device back under a new id. This is the only state
  the pages persist.

### Fixed
- Fixed `NotAllowedError: Permission denied` giving no indication of the
  cause when selecting an audio input. The error wording now tells a page
  or embedder block apart from an operating-system privacy block. In OBS, a
  page block means a **Local file** browser source that has to become a
  **URL** source. The wording also covers `SecurityError`. The wording moved
  out of the two byte-identical copies in `src/js/obs-ui.js` and
  `src/js/fullscreen-ui.js` into `src/js/device-errors.js`. See the new
  troubleshooting entries in `docs/audio-routing.md` and the expanded note
  in `docs/obs-setup.md`.
- Fixed a failure to open the audio input at startup collapsing into one
  generic message. A permission denial looked the same as an unplugged
  cable. The page now also awaits the initial connect. The device picker
  therefore rebuilds from the list enumerated under permission. The
  pre-permission list shows every label blank.
- Fixed a start that fails after the audio input connects leaving the capture
  device held and the page unable to retry. Awaiting the initial connect
  attaches the stream before the code sets `started`. `startAudio`'s failure
  path now releases the stream and clears `prepared` and `started`. It also
  closes the context. The old path kept the microphone open. It also left
  the retry guard believing the visualizer was running. Every later attempt
  then returned without a message over a dead context.
- Fixed the start status reporting a failure in the second-pass device
  reselect as a failure to start. That pass runs after the visualizer is
  already running on the default input. `src/js/obs-ui.js` now reports why
  the page skipped the saved input next to the running status. The status no
  longer changes to `Audio error`.
- Fixed a remembered device name shared by more than one input resolving to
  whichever enumerated first. Two identical interfaces report one label. A
  connection to the wrong one still looks healthy. `resolve` now declines an
  ambiguous label and falls back to the system default.

### Changed
- Guarded `window.BCDeviceErrors` and `window.BCAudioPrefs` in
  `src/js/obs-ui.js` and `src/js/fullscreen-ui.js`, matching the guard
  `visualizer-core.js` already applies to the same globals. Both arrive as
  separate deferred scripts. A missing one turned every device-error path
  into a `TypeError` inside the failure-reporting code.

## [1.9.0] (2026-08-25)

### Changed
- Replaced pickle hook-coverage trace files with validated JSON. Test
  processes influence the trace directory. Loading those files with
  `pickle.load` let a crafted test artifact execute code in the coverage
  checker.
- Classified command strings passed to Bash `eval`, treated `exec` as a command
  prefix, and sent unresolved `eval` expansions to the permission prompt.
  These builtins previously hid destructive commands from the gate.
- Treated Bash `builtin` as a command prefix and retained the enclosing command
  around backtick substitutions. Prefixing `eval` with `builtin`, or building
  its command name through a substitution, previously bypassed classification.
- Included `scripts/` in the shell-write consent paths because repository hooks
  execute branch-name and identity checkers from that directory.
- Named the two-field JSON trace-record length required by this repository's
  stricter repo-wide Ruff configuration.
- Replaced the spaced hyphen in `require_consent.py`'s `# pragma: no cover` and
  `# noqa: BLE001` comments with parentheses, matching the template. The house
  style reads a spaced hyphen as an em-dash substitute.
- Imported `unittest.mock` in `tests/test_require_consent.py` instead of
  importing `unittest` twice, once plainly and once with `from`. A code
  quality bot flagged the double import on this pull request.

- Split the newly mirrored Git option, repository-config, alias, and nested
  interpreter parsing into focused helpers so all shared gate files pass this
  repository's strict ruff rules without changing decisions.
- Removed `find_reason` and `find_consent_reason` from the Bash gate.
  Nothing here or upstream called either function.
- Closed three false positives in `check_ascii.py` and `lint_style.py`.
  A Markdown table delimiter row tripped the dash rule. A list marker
  opening its own line tripped it too. An inline code span opening on one
  line and closing on the next leaked its contents. The last case flagged
  the preset name `Optiks - Nerve` in a 1.6.2 entry. Satisfying the checker
  would have meant rewriting the name and falsifying the record of the
  removed preset.
- Brought the shared gates under this repository's ruff ruleset. `lint` had
  failed on every commit of this branch. `npx eslint .` passes. The
  `astral-sh/ruff-action` install step runs `ruff check` over the whole
  repository before the explicit `ruff check tools/` step. The change names
  seven magic values. `git_verdict` splits into a resolution reading, a
  per-subcommand table, and a flag reading. The three `_program_verdict`
  functions split so each returns at most six times.
- Rewrote the README hook section and dropped a contradicting sentence from
  AGENTS.md rule 3. Both described the gates two revisions back. The text
  named two hooks where three exist. It called `git push --force` a refusal
  after it moved to a prompt. It described the append exemption as live
  after its removal. It called the Bash redirect an open gap after the shell
  gate closed it. Rule 3 carried both the corrected sentence and the stale
  one, and the two disagreed.
- Excluded merge commits from `scripts/check_commit_message.py`. Returned the
  checker to the template's advisory behavior. A subject violation now
  reports and no longer blocks. `git merge` writes `Merge branch 'x' into y`.
  No author chose that subject, and no `type: description` subject can
  express it. Every ordinary branch update therefore failed the check. Added
  `tests/test_check_commit_message.py` covering the merge case, a real
  violation, and the advisory exit code.
- Registered both hooks in the exec form (`command` plus `args`) instead of a
  shell string. In shell form an unquoted `${CLAUDE_PROJECT_DIR}` splits a
  project path containing a space. The gate then fails to start without any
  notice.
- Made both hooks fail closed on malformed input. An unparseable payload or a
  malformed `tool_input` now gets a denial. Before, the hook treated it as a
  SessionStart or crashed. A test file that the hook cannot read or decode
  now goes to the prompt. Before, the hook read it as an empty string. That
  path let a tool overwrite a non-UTF-8 test file with no prompt.
- Wired `hooks/block_destructive_bash.py` into `.claude/settings.json`. The repo has
  carried the script since adopting the template but never registered it. The gate
  had therefore never run. It also gained ask outcomes for a recursive `rm` against
  any target outside `/`, `~`, and `$HOME`, and for the `--force-with-lease` family.
  The old `--force` pattern never matched that family. Further ask outcomes cover
  `git push --mirror`, `git push --delete`, a forced `+` refspec,
  `git commit --amend`, `git rebase`, and `git filter-branch`.
- Rewrote that hook to split the command into tokens and normalize it before
  deciding. Matching the raw string matched spelling instead of meaning. Every
  equivalent spelling therefore walked through. Examples include `rm -Rf` and
  `rm -r`, `git -C dir push --force` and other global-option forms,
  `--force-with-lease=main:<oid>`, and `git push origin +HEAD:main`. The
  `git -C dir push --force` form bypassed a deny as well as an ask. Ambiguity
  now fails closed. Quoted text such as `echo 'rm -rf /'` no longer reads as a
  command.
- Documented the new protected paths in `docs/protected-file-review.md` and both
  hooks in the README Security Model section.

### Added
- Measured the coverage baseline where CI measures it. Root can read a mode
  000 file. The two `OSError` branches in `require_consent.py` that a
  permission denial takes therefore never fire in a root shell. Both fire in
  CI. The tool now refuses to write a baseline as root. A root baseline could
  never match CI.
- Named the tracer directory `tools/hook-trace`. `coverage/` is one of the
  commonest `.gitignore` entries, and this repo carries it. The first commit
  of the gate therefore left the tracer out without any warning. Without the
  tracer, the gate reads no traced lines and reports every statement in
  `hooks/` as unreached. The report then shows a wall of noise in place of
  the one missing file. Fixed upstream too. Any adopter with that ignore
  line would have hit the same failure.
- Added `scripts/check_hook_coverage.py`, `tools/hook-trace/sitecustomize.py`
  and `hook-coverage-baseline.json`, run in CI. The gates execute as
  subprocesses. Ordinary in-process coverage therefore sees almost none of the
  gate decision code. Python imports `sitecustomize` in every interpreter it
  starts. That import is the stdlib way to reach the gates. The gate fails when
  a function gains unreached statements. It also fails when the baseline goes
  stale. An unmaintained recorded limit stops being a limit.
- The baseline is per repository. This one records 211 unreached
  statements across 64 functions. The template records 118 across 59.
  This repo declined `test_enforce_branch_name.py` and
  `test_enforce_git_identity.py`. Those suites exercise the template's Git
  write context paths. `docs/template-drift.md` records the difference.
- Covered the digest-bound form of `AGENTS_CONSENT_GRANTED`. No test had ever
  run it. Tests covered the bare `path` grant but not
  `path@sha256:<digest>`. Nothing had shown that the binding promised in the
  gate's docstring holds. Four tests now cover it, including a stale digest and
  a digest belonging to another file. A reachability pass found the gap. The
  pass traces every interpreter the suite launches. The gates run as
  subprocesses, and in-process coverage sees almost none of the gate decision
  code.
- Wired `scripts/check_ascii.py` into CI against `README.md`,
  `CHANGELOG.md`, `SECURITY.md`, and `docs/`. Fixed the 37 spaced hyphens it
  found. Version headings parenthesize the date,
  `## [1.2.3] (2026-01-01)`. Definition bullets use a colon. The checker had
  been available and unwired. The repo therefore failed a rule it ships.
- Added `tests/test_check_ascii.py`, 13 tests shared with
  `abuzucom/agents`. Six pin what the dash rule still catches, since a fix
  to a linter's false positives is one edit away from a fix to its true
  ones.
- Fixed a crash in the PowerShell gate's `-ArgumentList` handler. The handler
  called `unparseable_verdict` with one argument against a two-parameter
  function. A payload that failed to split into tokens raised `TypeError`
  instead of denying. A raise is a non-zero exit other than 2. Claude Code
  treats such an exit as non-blocking. The gate therefore failed open on
  exactly the input it exists to catch. `tests/gate_corpus.py` carries the
  case.
- Removed two duplicate test methods from `tests/test_require_consent.py`.
  Merging the template's copy with this repo's local wiring assertions
  produced a second definition of `test_entries_use_the_exec_form` and
  `test_destructive_bash_hook_is_registered`. Python keeps the later
  definition without a warning. Both earlier assertions had stopped running.
- Added `shared-files.json` and `scripts/sync.py --check-shared`, run in
  CI. `sync.py` copies the AGENTS.md family. It cannot copy anything from a
  repository it cannot see. This repo's `check_ascii.py` and `lint_style.py`
  improvements therefore sat unnoticed upstream for weeks. Both repositories
  now commit SHA-256 digests for the seven files that carry gate decisions. A
  fix that lands in one repository and not the other fails the other's check.
  `tests/test_require_consent.py` stays off the list. It holds two wiring
  assertions moved from a suite this repo declined. `docs/template-drift.md`
  records that choice.
- Added `tests/gate_corpus.py`, shared byte-identical with
  `abuzucom/agents`. The file holds one table of every known gate bypass. Each
  row names the required verdict and the reason for the row. The Bash,
  PowerShell, and consent suites import it. A fix that lands in one repository
  and not the other fails the other's suite.
- Closed five gate bypasses the corpus found. Each gate knew only its own
  shell's interpreters. `powershell -Command 'Remove-Item -Recurse
  -Force /etc'` therefore crossed the Bash gate untouched. `bash -c 'rm -rf
  /etc'` crossed the PowerShell gate untouched. On Windows both lines run. A
  PowerShell script block put a brace where a program name goes. The gate
  read `& { Remove-Item -Recurse -Force /etc }` as a program named `{`.
  `Start-Process -ArgumentList` handed a CMD line to a program through a
  parameter no gate recognized. All three delete readings, POSIX `rm`,
  PowerShell `Remove-Item`, and the CMD verbs, now live in
  `hooks/_gate_core.py`. The core tries all three together. Neither gate can
  learn a spelling the other lacks.
- Named the unrecognized `permission_mode` in the deny reason the shell
  gates emit. A later interactive mode from Claude Code denies here. The old
  reason read the same as the reason for a truly unattended session.
- Added `docs/template-drift.md`. It records how this repository's copies of
  the `abuzucom/agents` template files differ and why. `sync.py` keeps only
  the AGENTS.md family in step. Every `scripts/`, `hooks/`, and `tests/` file
  gets local maintenance and drifts unwatched. Two files differ today. Both
  differences follow from a template file this repository declined. Neither
  comes from an independent edit. The template owns the policy in `DRIFT.md`
  and the taken and declined list in `adopters/1a2n-web-visualizer.md`.
  Neither side restates the other's fields. No check verifies the records.
- Added a demo build (`src/demo.html`). It drives the visualizer from a
  synthetic audio track generated in the page. The presets react with no
  microphone permission, no virtual audio cable, and no input device. It shares
  `css/fullscreen.css` and `js/fullscreen-ui.js` with the fullscreen build.
  `data-demo="1"` on `<body>` selects it. `?demo=1` turns `fullscreen.html`
  into the same build. The landing page lists it as a fourth card.
- Added `src/js/demo-audio.js`, the track generator. It plays kick, snare,
  bass, chord pad, and filtered-noise hats on a two-second lookahead
  scheduler. A slow filter LFO runs as an audio-thread modulation edge. The
  drift therefore continues in a hidden page. Each of the three tempos plays
  its own pattern. House plays at 87, trance at 140, and liquid drum and bass
  at 174. The last plays a two-step break over half-time harmony.
- Made the generated audio silent. It reaches `destination` only through a gain
  of exactly zero. That gain produces bit-exact digital silence. The tap exists
  because butterchurn's analyser chain never connects to the destination
  itself. Without the tap, the synthetic sources would depend on an engine's
  automatic-pull behavior for an output-unconnected `AnalyserNode`.
- Added <kbd>B</kbd> to cycle genre and tempo, <kbd>,</kbd>/<kbd>.</kbd> to
  nudge tempo, and <kbd>-</kbd>/<kbd>=</kbd> for intensity, plus a `Demo` row in
  the diagnostics overlay that stays hidden on the other three pages.
- Added the `demo` option to `BCViz.create` and six methods to its API:
  `isDemo`, `getDemoTempo`, `setDemoTempo`, `cycleDemoTempo`,
  `getDemoIntensity`, and `setDemoIntensity`. All are additive. Each reports
  `0` without throwing when demo mode is off.

### Fixed
- Removed the replayable `AGENTS_CONSENT_GRANTED` grant override. Fixed Bash
  brace and command-substitution parsing, PowerShell backtick and
  encoded-command handling, Git config execution detection, and hard link scan
  failures.
- Fixed the watchdog reporting a lost audio input, and reconnecting to a device
  when armed, on a page that never opened a stream. `visualizer-core.js` passed
  a `handleLostInput` option that `audio-watchdog.js` does not read. The
  watchdog honors `isMonitoring`. The core never passed that option, and the
  default monitored everything. The intended `hadStream` guard was dead code.
  The watchdog already misfired whenever `getUserMedia` failed. An armed guard
  would escalate the misfire into a device reconnect.
- Fixed the missing audio source reconnect after a WebGL context recovery.
  `recoverVisualizer` builds a fresh butterchurn instance with a fresh internal
  analyser chain. Nothing called `connectAudio` again. A recovered visualizer
  therefore rendered against dead audio for the rest of the session.
- Added `hooks/require_consent.py` and `.claude/settings.json`. The pair wires two
  Claude Code gates that run before a tool call. The only unprompted edit to an
  existing test file is a verified append at the end of the file. The new text must
  begin with the old text. The addition must start on a new line. The old text must
  sit at the end of the file. An earlier form of this check asked only whether the
  old text still appeared somewhere in the new text. That form passed an assertion
  commented out, wrapped in a string, moved into an unreachable branch, or extended
  on the same line. The gate resolves each path before classification. A symlink
  with a harmless name therefore cannot carry an edit into a test file. The gate
  also gates every test file that resolves outside the project root. The same rule
  applies to a link redirect and to a directly named path. The gate compares the
  `AGENTS_CONSENT_GRANTED` override for headless runs on the canonical path. One
  grant therefore releases one file. Other files with the same path ending stay
  gated. An edit that removes or rewrites existing test content, drops an
  assertion, or introduces a skip marker now goes to a permission prompt (AGENTS.md
  Rule 3). A person then decides at the act. An agent can no longer talk itself
  into the edit. Adding a test, or appending one to an existing file, passes
  untouched. The mandated test-first workflow therefore stays unprompted.
- Added `tests/test_require_consent.py` and `tests/test_block_destructive_bash.py`,
  27 tests covering every gate outcome and whether the settings files still register
  each hook.
- Added `tests/`, `hooks/`, and `.claude/` to `PROTECTED_PREFIXES` in
  `scripts/check_protected_files.py`. Pull requests touching a test, or touching the
  gate files, now need code-owner approval on the current commit. An edit to the
  settings file can defeat a local hook. That edit cannot defeat this check.
- Added four AGENTS.md lines. A check now backs each line (Rule 13). Approving a
  plan grants no authorization for the acts inside it. Rule 2 carries no scope
  qualifier. Disclosure does not replace stopping. `--force-with-lease` is no
  exception to the pushed-history rule.

## [1.8.1] (2026-08-03)

### Fixed
- Fixed switching the audio input device throwing `NotReadableError: Could not
  start audio source`. The device switch (`D` in `fullscreen.html`, the input
  dropdown in `obs.html`) requested the new device's stream before releasing
  the old one. The request conflicted with itself whenever the target device
  was already active. A single input device always triggered the conflict.
  The switch now releases the current stream first. It skips the reopen when
  the requested device is already active. It retries once on
  `NotReadableError`. The retry absorbs a driver that frees an exclusive-mode
  handle slowly. See the new "Exclusive-mode devices (Windows)" section in
  `docs/unattended-operation.md`.
- Fixed an errant double `try-catch` block inside `tools/convert-milk-presets.js`. Exceptions now reach a log or a handler. The old block swallowed each exception.
- Prevented potential zero-division crashes and eliminated slow/backtracking regular expressions during the preset parsing processes.
- Eliminated unreachable dead code segments across the tooling scripts.
- Randomized the initial fullscreen preset across the resident vendored
  collection while leaving the OBS startup behavior unchanged.
- Normalized equation strings with a trailing newline before load. A preset with
  a final statement that lacks a semicolon now compiles in butterchurn's
  space-separated equation wrapper. Before the fix, the loader skipped such a
  preset.
- Detected warp/comp shader link failures during preset load and skipped the
  preset instead of rendering every frame with an unlinked program.
- Added runtime-detected broken presets (bad equations or shader link
  failures) to the exportable excluded-presets list for later curation.
- Reduced fullscreen startup blocking by selecting the initial vendored preset
  from a resident index and deferring experimental image loading until idle or
  lazy-preset selection.
- Stopped treating post-load WebGL error state as proof that a preset failed.
- Started the visualizer before microphone permission and device enumeration
  finish. The first frame no longer waits on audio input setup.
- Fixed equation validation for valid statements without trailing semicolons.
- Hardened workflow checkouts by disabling persisted GitHub credentials.

### Added
- Kept the visualizer rendering under another window, in a minimized window, and
  in a background tab. A render driver (`src/js/render-driver.js`) drives frames
  from `requestAnimationFrame` while visible. While hidden, an
  `AudioWorkletProcessor` (`src/js/render-tick-processor.js`) drives frames.
  Page visibility throttling does not apply to the audio thread. A `setTimeout`
  clock is the fallback where the worklet is unavailable, such as on `file://`
  origins.
- Requested a screen wake lock. The display stays awake under a visible but
  unfocused visualizer. The page acquires the lock again on return to visible.
- Added an audible-tab keepalive (`src/js/audible-keepalive.js`). It marks the
  tab audible to exempt it from background timer throttling. It runs on a
  separate `AudioContext`. It suppresses itself when the capture device looks
  like a loopback or monitor. It therefore never feeds back into the analysis
  input.
- Added a watchdog (`src/js/audio-watchdog.js`) that restarts a stalled render
  loop and resumes a suspended `AudioContext`. Both checks are always on.
- Added an opt-in audio guard that reconnects a lost capture device after a
  20 second grace window, ranking candidates Voicemeeter-first and never falling
  back to a physical microphone. It starts disarmed, arms with `A` or the OBS
  checkbox or `?guard=1`, and never treats silence as a lost input.
- Added a diagnostics overlay (`src/js/diagnostics.js`) showing frame rate, tick
  source, visibility, wake lock, keepalive, input device, track state, and
  watchdog counters. Toggles with `I` or `?diag=1`.
- Added `docs/background-rendering.md` and `docs/unattended-operation.md`.
- Added `hooks/_gate_core.py`. Both shell gates and the consent gate import it. Each decision now has one definition instead of one per gate.
- Added `hooks/block_destructive_powershell.py` under a `PowerShell` matcher. The Bash matcher covered only Bash. `Remove-Item -Recurse -Force` on a Windows session therefore met no gate at all.
- Added `tests/test_gate_parity.py`. It feeds both gates an equivalent corpus and fails when the verdicts differ. It also asserts that neither gate defines a separate decision function.
- Added a `windows-latest` job. No Linux job can show that the configured launcher resolves on Windows, and the gates had never run there.
- Added `tools/run-python.js`. It probes `python3`, `python`, then `py -3` by running each candidate instead of trusting the name. `npm run test:py` and `dev` named `python3`. Windows lacks that name. `lint` named `python`. Debian may lack that name or map it to Python 2.
- Added the data-destruction policy. The gates refuse drive roots, system directories, formatting and repair tools, `dd`, `hdparm`, truncating redirects, pipes into interpreters, alias definitions, `crontab -r`, recovery destruction, and `gh repo delete`. Recursive deletes, privilege escalation, process termination, shell profile writes, and forced pushes go to the permission prompt.
- Added an `html-css-validation` job to `.github/workflows/checks.yml`. The job
  runs the [Nu Html Checker](https://github.com/validator/validator) against
  `src/*.html` and `src/css/*.css` on every pull request and push to
  `develop`. Upstream attaches release assets only to a moving `latest` tag.
  Each new upstream build replaces the jar and breaks any checksum pinned
  against it. The job therefore takes `vnu.jar` from the immutable `vnu-jar`
  npm tarball that the same project publishes. A version pin and SHA-256
  checks on both the tarball and the extracted jar guard it. A move to a new
  checker version now requires an intended change.
- Added `SECURITY.md`. It covers private vulnerability reports through GitHub
  Security Advisories, scope, and supported versions. It links the accepted
  risks documented elsewhere (CSP `unsafe-eval`, localhost-only Docker
  binding, vendored dependencies) without duplicating the text.
- Adopted the current `abuzucom/agents` template infrastructure. Brought
  AGENTS.md's rule body to parity (rules 10-13, checker attribution
  clauses, two new Style bullets for American spelling and English-only
  prose). Added the ten upstream `scripts/check_*.py` and `lint_style.py`
  checkers. Wired the checkers into `.github/workflows/checks.yml` and a new
  `.pre-commit-config.yaml`. Added `.editorconfig`, `.gitattributes`,
  `Makefile`, and `hooks/` (an inert Claude Code example hook). Kept this
  repo's Commands, Do not touch, Architecture, Gotchas, and Read before
  touching orientation. Also added an explicit non-root `user:` to the
  Docker Compose service, matching the image's existing runtime user.
- `tools/split-extra-images.py`: splits the experimental texture bundle
  into deterministic lazy-loaded part files and losslessly optimizes the
  embedded images, verifying every optimized variant pixel-for-pixel.
- Added a touch-first mobile visualizer entry point with branded controls for
  shuffling, preset history, cycle intervals, and hyperspeed mode.
- Added the `T` fullscreen shortcut for toggling 100ms hyperspeed shuffle.
- Added `M`/`K` fullscreen shortcuts for favoriting the current preset and
  viewing/copying the session's favorites list, mirroring the excluded-
  presets workflow, for building a setlist during a live performance.

### Changed
- Stopped hyperspeed switching itself off in a hidden page. The new
  `pauseWhenHidden` option restores the old behavior.
- Removed the end-of-file append exemption from the consent gate. Every edit to a test file that already exists now asks. A text-level append check cannot tell a new test from a statement that neutralizes every test above it.
- Launched hooks as `python` instead of `python3`. Added a test that asserts the configured string resolves. The behavioral tests run hooks through `sys.executable`. Those tests therefore passed against a configuration that never started on Windows.
- Gated Bash writes that reach a test file through a redirect, a here-document, `tee`, `sed -i`, `cp`, or `mv`. Rule 3 applied to the same act through one tool and not the other.
- Rendered every value reaching a permission prompt or stderr as printable ASCII. A filename carrying newlines or terminal control could rewrite the prompt that a person reads to decide.
- Reduced `checks.yml` CI minute usage. `validate-presets` now skips its two
  `npm run validate:*` steps unless the diff touches preset data or the
  validator tooling. Those steps parse all of `src/presets-extra/`.
  `unit-tests` now caches the Nu Html Checker jar and pip packages between
  runs. `checks.yml` no longer also runs on push to `develop`. A merge only
  lands after the PR's checks pass. The push trigger of `deploy.yml` stays the
  same.
- Enforced strict `AGENTS.md` code style and quality guidelines across the entire codebase.
- Renamed all single-character and ambiguous variables in `src/js/` and `tools/` scripts to use descriptive, contextual names.
- Restored and completed the JSDoc annotations across `visualizer-core.js`, `fullscreen-ui.js`, `obs-ui.js`, and `mobile-ui.js`.
- Hardened Python tooling scripts by enforcing explicit types (e.g. `typing.Any`) and resolving Ruff complexity lint checks.
- Pinned devDependencies in `package.json` to exact versions instead of caret
  ranges, matching the current `package-lock.json` resolutions and the
  pin-all-versions policy in AGENTS.md.
- Curated 53 additional presets from the supplied removal list and recorded
  the exact removals in the inventory and durable removal ledger.
- Curated 12 additional presets from the supplied removal list and recorded
  the exact removals in the inventory and durable removal ledger.
- Curated 153 additional presets from the supplied removal list and recorded
  the exact removals in the inventory and durable removal ledger.
- Updated AGENTS.md (and its synced copies) to match the repo: documented
  the Node and Python test commands, `npm run validate:presets`, the
  `scripts/` automation and `sync.py` single-source rule, all four GitHub
  workflows including the `VID` Jira integration, the mobile entry point
  and remaining `src/js` modules, the previously unlisted tools and
  generated root JSON records, the `patch-package` interaction with
  `--ignore-scripts`, and replaced hard preset/chunk counts with a pointer
  to `src/presets-extra/index.js`.
- Curated 661 additional presets from the supplied removal list. Recorded
  the exact removals in the inventory and durable removal ledger. One further
  requested name (`Rovastar + Loadus + Geiss - FractalDrop (Triple Mix)`)
  lives in a vendored preset pack. The curation tool cannot auto-edit that
  pack format. The preset stays in place.
- Curated 211 additional presets from the supplied removal list and recorded
  the exact removals in the inventory and durable removal ledger.
- Curated 15,458 additional presets from the supplied removal list and recorded
  the exact removals in the inventory and durable removal ledger.
- Curated 280 additional presets from the supplied removal list and recorded
  the exact removals in the inventory and durable removal ledger.
- Curated 62 additional presets from the supplied removal list and recorded
  the exact removals in the inventory and durable removal ledger.
- Curated 2,959 additional presets from the supplied removal list and recorded
  the exact removals in the inventory and durable removal ledger.
- Replaced the 53.7 MB blocking experimental texture bundle with eight
  lazy-loaded part files injected on idle or before the first `[EXP]`
  preset, cutting startup transfer by about 54 MB; a legacy single-file
  bundle still loads if present.
- Losslessly recompressed the 1,230 embedded experimental textures
  (JPEG via jpegtran, BMP and static GIF to PNG, PNG via optipng),
  saving 6.9 MB with pixel-identical output.
- Added `defer` to all page scripts so parsing no longer blocks on
  script execution order.
- Extended Caddy cache headers to preset chunks and app js/css. Removed
  `immutable` from `/vendor/*`. Curation rewrites those files in place.
  Documented the rules in the local hosting guide.
- Documented the texture part layout and lazy-loading invariants in the
  agent instruction files and README.
- Curated 2,991 additional presets from a supplied removal list (580 further
  requested names were already removed by this pass) and recorded the exact
  removals in the inventory and durable removal ledger.
- Deduplicated the experimental collection against the mainline lazy-loaded
  presets. Removed 15,739 `[EXP]` presets with source presets that already ship
  in the mainline collection (exact import-time content matches plus approved
  normalized-name matches). Removed 247 intra-experimental exact duplicate
  copies. `src/presets-extra/` shrank from about 276 MB to about 209 MB.
- Pruned 38 stale index entries with preset data missing from the matching
  chunk files. Each entry surfaced as an unavailable preset at runtime.
- Added `tools/reconcile_preset_inventory.py` and restored 2,046 missing
  `preset-inventory.csv` rows. The inventory now matches the shipped presets
  exactly. Corrected README preset counts to the reconciled totals.
- Removed 575 presets with names containing slurs, hate ideology, sexual
  violence, or explicit sexual content. A full audit of all preset names
  (including obfuscated spellings) found the names. The inventory and durable
  removal ledger record each removal. Corrected the README preset counts to
  the post-curation totals.
- Curated 2,706 additional presets from the shipped collections and recorded
  the exact removals in the inventory and durable removal ledger.
- Added the mobile visualizer to the landing-page navigation and documented its
  browser-viewport behavior without curation controls or browser fullscreen.
- Refreshed the landing page, OBS panel, and fullscreen overlays with the
  shared brand palette, typography system, responsive layouts, and accessible
  focus states.
- Curated 2,606 additional presets from the shipped collections and recorded
  the exact removals in the inventory and durable removal ledger.
- Curated 301 additional presets from the shipped collections and recorded the
  exact removals in the inventory and durable removal ledger.
- Synced the AI agent instruction files from the authoritative `abuzucom/agents`
  template while preserving this repo's Commands, Do not touch, Architecture,
  Gotchas, and Read before touching orientation.
- Curated 2,498 additional presets from the shipped collections and recorded
  the exact removals in the inventory and durable removal ledger.
- Curated 1,625 additional presets from the shipped collections and recorded
  the exact removals in the inventory and durable removal ledger.
- Made preset curation recoverable after partial writes and Windows file-lock
  replacement failures, while resolving generated chunks from the authoritative
  index instead of stale inventory metadata.

## [1.7.1] (2026-07-16)

### Fixed
- Drained queued WebGL errors after failed shader loads so one invalid preset
  does not poison subsequent fallback presets.
- Loaded the initial preset during audio startup instead of waiting for later
  navigation or auto-cycle activity.

## [1.7.0] (2026-07-15)

### Added
- Jira Cloud synchronization for approved pull requests and successful GitHub
  Pages deployments. The integration links `VID-*` issues and can create a
  `Task` only when maintainers apply the `jira-create` label.
- Protected-file review checks for agent instructions, GitHub Actions,
  automation scripts, dependencies, deployment configuration, runtime code, and
  vendored code. See [`docs/protected-file-review.md`](docs/protected-file-review.md).
- Current-commit approval enforcement for protected files changed by agents,
  while owner-authored pull requests avoid the impossible self-approval case.
- GitHub Actions pin, instruction synchronization, lint, and protected-file
  checks as documented repository gates.

### Changed
- Renamed the README heading to `1a2n Web Visualizer` to match the repository
  name.
- Made curation output writes atomic and guarded audio-device recovery against
  asynchronous failures and leaked resources.
- Split the BCViz controller responsibilities and hardened preset loading,
  rendering, WebGL context recovery, and render-loop failure handling.
- Added favicon links to the visualizer pages.
- Added known-good preset recovery and random fallback behavior when a preset
  fails to compile or render.
- Added bounded protected-file pagination and execution from the trusted
  default branch for review checks and Jira workflows.
- Removed 131 invalid generated presets and kept generated indexes, chunks,
  inventories, and removal ledgers consistent.
- Audited and simplified the README and local-hosting guide. Corrected current
  preset counts, commands, controls, tooling, security notes, and provenance.

### Security
- Only trusted `pull_request_target` and deployment workflows use Jira
  secrets. Fork pull requests skip cleanly when secrets are unavailable.
- Protected-file workflows never execute code from the pull request branch.
- Documented the single-maintainer branch protection model without requiring
  global GitHub Code Owner approval.
- Added a lodash version override of `>=4.17.12` to prevent the known
  prototype-pollution vulnerability in the dependency tree.

### Fixed
- Prevented Butterchurn equation compilation failures caused by missing empty
  equation fields in imported EXP presets.
- Added parser-based validation for generated equation JavaScript and removed
  250 malformed EXP presets from the shipped collection, with corresponding
  exclusion, inventory, and removal-ledger records.
- Added runtime diagnostics for broken preset loads, including the preset name,
  logical chunk ID, physical chunk file, and caught exception.
- Corrected the logical IDs passed by all 377 experimental NestDrop preset
  chunks. Mainline chunk insertion had shifted the generated `index.js`
  mapping without updating the chunk registration callbacks. The runtime then
  reported valid `[EXP]` presets as unavailable.

## [1.6.3] (2026-07-11)

### Added
- Added `tools/remove_presets.js`. It removes a given list of exact preset
  names from `src/presets-extra/index.js`, the backing chunk files, any
  vendored `.min.js` pack that contains the names, and the matching
  `preset-inventory.csv` rows. A pre-flight existence check aborts with
  nothing written if any name is missing. A post-edit consistency check
  follows each run. The tool turns the manual curation procedure into a
  repeatable command for each batch.
- Added `tools/analyze_curation_history.js`. It reconstructs the full history
  of presets curated out of this repo from `git log`. It prints neutral word,
  bigram, and contributor-prefix frequency statistics over the removed names.
  It has no built-in notion of "risky" content. Anyone using this repo can
  review the same data and make separate curation calls.

### Removed
- Curated 186 more presets out for photosensitivity and seizure-risk content.
  `tools/remove_presets.js` removed 185: 21 self-labeled "epileptic", 14
  "strobe", 3 "flicker", 28 in the `recursion frustum`/"Ananda_Flash_Remix"
  series, 2 "eyepain", 9 "serpent", 44 "rainbow bubble", 56 in the "escape
  the worm"/"Worms 2003" series, and 8 individually named. One more
  presets-extra entry duplicated an already-removed vendored-pack name. The
  batch cleaned up that dead, shadowed data too. The removals span
  `src/presets-extra/` (38 chunk files) and the vendored
  `butterchurnPresetsExtra`/`butterchurnPresetsExtra2` packs. The matching
  `preset-inventory.csv` rows are gone. Same intentional editorial curation
  as prior batches. See the *Curation* section in the README. The app now
  ships 14,770 deduplicated presets (378 vendored + 14,392 lazy-loaded from
  14,458 index names minus 66 that duplicate a vendored name).
- Curated 32 more presets out of `src/presets-extra/`. The batch removed
  each one from `index.js` and the backing chunk file and dropped the
  matching `preset-inventory.csv` row. The batch covers 4 individually named
  presets (`Hampton GER - Randomnity (Adjustable Mix)`, `Shifter-openthelight`,
  `Eo.S. + Redi Jedi _Phat_Mexican_Insanity_Pepper_Crazy_mix(1.04) Eo.S.
  edit colors2`, `Optiks - Nerve`). It also covers every preset with a name
  containing "seizure" or "sezure". Those 28 presets are mostly
  `Eo.S. + Phat` / `Bdrv`/`beta106`/`bdrv + al` "recursion frustum" and
  "Let_go_Wana_Sezure" variants. Same intentional editorial curation as prior
  batches. See the *Curation* section in the README. The app now ships 14,954
  deduplicated presets (381 vendored + 14,573 lazy-loaded from 14,640 index
  names minus 67 that duplicate a vendored name).

## [1.6.1] (2026-07-10)

### Security
- The Docker + Caddy self-hosting container now also sends a
  `Strict-Transport-Security` header (`max-age=31536000; includeSubDomains`)
  next to the existing OWASP header set. The header is already in place if
  that Caddyfile ever moves behind TLS termination. Today it serves plain
  HTTP on `localhost`.

## [1.6.0] (2026-07-07)

### Added
- `preset-inventory.csv`: a full inventory of every preset name and the pack
  that provides it (a vendored pack, or the lazy-loaded `presets-extra`
  collection with its chunk id), generated with the same dedup/precedence
  rules `visualizer-core.js` applies at runtime. Reflects the curated set
  (14,770 rows).
- Added `tools/fetch-extra-presets-curated.py`. It regenerates
  `src/presets-extra/` like `fetch-extra-presets.py`. It also diffs a fresh
  upstream pull against the currently committed `index.js`. It re-excludes
  anything present upstream but missing from the current tree. A run
  therefore preserves curation. It supports `--zip` and `--dry-run`. A
  refactor moved `collect_presets()` and `write_output()` out of `main()` in
  `fetch-extra-presets.py` without a behavior change. Both scripts now share
  one source of truth for the texture-filter rule and the chunk/index JSON
  encoding.

### Removed
- Deleted 45 presets from the `src/presets-extra/` collection, from both
  `index.js` and the backing chunk files.
- Curated 174 further presets out of this deployment. 171 came from
  `src/presets-extra/` (`index.js` + backing chunk files). Three came from the
  vendored bundles (2 from `butterchurnPresetsExtra2`, 1 from
  `butterchurnPresetsMD1`). The matching `preset-inventory.csv` rows are
  gone. These removals are an **intentional content-curation choice for this
  deployment**. The removals are independent of the upstream collection and the
  butterchurn libraries. `tools/fetch-extra-presets-curated.py` (above) now
  re-applies this curation automatically on regeneration. The plain
  `fetch-extra-presets.py` still rebuilds `src/presets-extra/` exactly from
  upstream and reintroduces these presets. See the *Curation* section in the
  README.

### Fixed
- Corrected the documented preset counts to match the current curated packs.
  The total is 14,770 deduplicated presets. That covers 378 vendored (100 base
  + 135 new from Extra + 116 new from Extra2 + 27 new from MD1, after
  merge-order dedup) plus 14,392 lazy-loaded (14,458 index names minus 66
  that duplicate a vendored name). The new figures replace the stale 15,330 /
  15,264 totals and the 387 / 385 vendored figures. The old figures no longer
  matched the regenerated and curated `Extra`/`Extra2`/`MD1` packs.
- Fixed a first-run bug in `fetch-extra-presets-curated.py`. An empty
  `current_names` set made `set(fresh_kept) - current_names` treat every
  freshly fetched preset as curated-out. A first run with no prior
  `index.js` therefore always produced an empty `src/presets-extra/`. The fix
  tells "no prior curation state" apart from "current state is empty."

## [1.5.0] (2026-07-05)

### Added
- Added about 15k extra presets from
  [ansorre/tens-of-thousands-milkdrop-presets-for-butterchurn](https://github.com/ansorre/tens-of-thousands-milkdrop-presets-for-butterchurn)
  as 118 lazy-loaded chunk files in `src/presets-extra/`. The total is 15,375
  unique presets after deduplication against the vendored packs. Vendored
  packs win on name collisions. The app injects chunks as classic `<script>`
  tags on demand. Everything still works from `file://`, offline, and under
  the strict CSP. An in-memory LRU keeps at most 16 chunks resident. Without
  the folder, the app falls back to the 387 vendored presets.
- `tools/fetch-extra-presets.py`: stdlib-only generator that downloads the
  pinned, sha256-verified upstream zip and regenerates `src/presets-extra/`,
  excluding presets that reference custom textures the app can't supply
  (`tools/butterchurn-image-names.json` lists the vendored textures).
- Added a preset filter box to the OBS panel. The dropdown now holds 15k+
  entries. The panel builds the list off-DOM through a DocumentFragment. The
  status line shows the preset count.
- The runtime now skips broken or unloadable presets and removes each one
  from rotation for the session.

## [1.4.0] (2026-07-04)

### Added
- Added internal-only self-hosting through Docker + Caddy. `Dockerfile`,
  `docker-compose.yml`, and `Caddyfile` serve plain HTTP on :80, bound to
  `127.0.0.1` only. Browsers treat `localhost` as a secure context for mic
  capture. The setup needs no TLS.
- `docs/local-hosting.md` covering all three local modes: `file://`, dev
  server, and the Docker container (including its security hardening).
- Shuffle mode for the auto-cycle: picks a random preset (never the current
  one) each tick. On by default on the fullscreen page; toggle with
  <kbd>S</kbd>. The OBS page keeps sequential cycling.
- <kbd>R</kbd> (and the panel's Random button) now never re-picks the
  currently showing preset.
- Vendored three additional preset packs from `butterchurn-presets@2.4.7`
  (Extra, Extra2, MD1) and the `butterchurnExtraImages` texture pack from
  `butterchurn@2.6.7`.
- `visualizer-core.js` now merges all loaded preset packs at startup. It
  skips a preset if an earlier pack already holds the exact name. The base
  pack wins collisions. The app now holds 395 unique presets, up from 100.
- Passed custom textures to butterchurn through `loadExtraImages`. The few
  texture-using presets now render fully.

### Changed
- The GitHub Pages deploy workflow now retries the deployment step once
  (after a 30s pause) when the Pages backend rejects the first attempt with
  its transient "Deployment failed, try again later." error.
- Documentation refreshed to reflect the production deployment at
  `https://visualizer.1a2n.net/`, the vendored (CDN-free) libraries, and the
  `src/vendor/` layout.
- Fullscreen <kbd>[</kbd> / <kbd>]</kbd> now adjust the cycle interval in 1s
  steps up to 10s and in 5s steps above. The old step was a fixed 5s.
- Vendored `butterchurn` and `butterchurn-presets` into `src/vendor/` instead of
  loading both from unpkg. The app no longer depends on a runtime CDN.
- Added a Content-Security-Policy meta tag to all pages.
- Fixed the malformed charset meta tag (`<meta charset="UTF-8">`).
- Moved `<script>` tags out of overlay divs to the end of `<body>`.
- Fullscreen page only hides the cursor once the visualizer is running.

### Fixed
- Guarded concurrent `start()` calls. A double-click on Start could create
  multiple AudioContexts and render loops.
- A failed start (mic permission denied) no longer leaks an AudioContext per
  attempt.
- Switching audio devices now disconnects the previous audio source node.
- Pressing <kbd>H</kbd> while typing in a panel input no longer toggles the panel.
- Bare modifier keypresses no longer trigger start on the fullscreen page.

## [1.0.1] (2026-06-27)

### Added
- Cleaned up HTML
- Added `index.html` to avoid 404 when accessing the root folder on web

## [1.0.0] (2026-06-26)

### Added
- Shared `visualizer-core.js` controller (`window.BCViz`) holding all butterchurn
  setup, preset cycling, and audio-device handling.
- `obs.html`: OBS browser-source page with a hideable control panel.
- `fullscreen.html`: standalone keyboard-only fullscreen page.
- Per-page CSS (`panel.css`, `fullscreen.css`) and UI wiring
  (`obs-ui.js`, `fullscreen-ui.js`).
- Added documentation for OBS setup and audio routing.
- `package.json` with a `start` script for a local static server.
- GitHub Actions workflow (`.github/workflows/deploy.yml`) to publish `src/`
  to GitHub Pages on push to `develop`.

### Notes
- Refactored from two standalone single-file HTML prototypes
  (`butterchurn-obs.html`, `butterchurn-fullscreen.html`) into a shared-core
  repository structure.
