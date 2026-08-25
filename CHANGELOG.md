# Changelog

All notable changes to this project are documented here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); this project aims to use
[Semantic Versioning](https://semver.org/).

## [1.9.0]

### Added
- Added `hooks/require_consent.py` and `.claude/settings.json`, wiring two Claude Code
  gates that run before a tool call. The only unprompted edit to an existing test file
  is a verified append at the end of it: the new text must begin with the old text, the
  addition must start on a new line, and the old text must sit at the end of the file.
  An earlier form of this check asked only whether the old text still appeared somewhere
  in the new text, which passed an assertion that had been commented out, wrapped in a
  string, moved into a branch that never runs, or extended on the same line. An edit that removes or rewrites existing test
  content, drops an assertion, or introduces a skip marker now goes to a permission
  prompt (AGENTS.md Rule 3), so the decision lands with a person at the act rather
  than with an agent that has talked itself into it. Adding a test, or appending one
  to an existing file, passes untouched, which keeps the mandated test-first workflow
  unprompted.
- Added `tests/test_require_consent.py` and `tests/test_block_destructive_bash.py`,
  27 tests covering every gate outcome and whether the settings files still register
  each hook.
- Added `tests/`, `hooks/`, and `.claude/` to `PROTECTED_PREFIXES` in
  `scripts/check_protected_files.py`. Pull requests touching a test, or touching the
  gates themselves, now need code-owner approval on the current commit. A local hook
  is defeatable by editing the settings it lives in; this check is not.
- Added four AGENTS.md lines, each backed by a check that now exists (Rule 13):
  approving a plan is not authorization for the acts inside it; Rule 2 carries no
  scope qualifier; disclosure is not a substitute for stopping; `--force-with-lease`
  is not an exception to the pushed-history rule.

### Changed
- Wired `hooks/block_destructive_bash.py` into `.claude/settings.json`. The repo has
  carried the script since adopting the template but never registered it, so it had
  never run. It also gained ask outcomes: a recursive `rm` against any target outside
  `/`, `~`, and `$HOME`; the `--force-with-lease` family, which its `--force` pattern
  never matched; `git push --mirror`; `git push --delete`; a forced `+` refspec;
  `git commit --amend`; `git rebase`; and `git filter-branch`.
- Rewrote that hook to tokenize and normalize the command before deciding. Matching
  the raw string matched spelling rather than meaning, so every equivalent spelling
  walked through: `rm -Rf` and `rm -r`, `git -C dir push --force` and other
  global-option forms, `--force-with-lease=main:<oid>`, and `git push origin
  +HEAD:main`. The `git -C dir push --force` form bypassed a deny, not just an ask.
  Ambiguity now fails closed, and quoted text such as `echo 'rm -rf /'` no longer
  reads as a command.
- Documented the new protected paths in `docs/protected-file-review.md` and both
  hooks in the README Security Model section.

## [1.8.1]

### Fixed
- Fixed switching the audio input device throwing `NotReadableError: Could not
  start audio source`. The device switch (`D` in `fullscreen.html`, the input
  dropdown in `obs.html`) requested the new device's stream before releasing
  the old one, which self-conflicted whenever the target device was already
  the active one, guaranteed whenever there is only one input device. It now
  releases the current stream first, skips the reopen entirely when the
  requested device is already active, and retries once on `NotReadableError`
  to absorb a driver that is briefly slow to free an exclusive-mode handle.
  See the new "Exclusive-mode devices (Windows)" section in
  `docs/unattended-operation.md`.

## [1.8.0]

### Added
- Kept the visualizer rendering while its window is covered, minimized, or in a
  background tab. A render driver (`src/js/render-driver.js`) drives frames from
  `requestAnimationFrame` while visible and from an `AudioWorkletProcessor`
  (`src/js/render-tick-processor.js`) while hidden, since the audio thread is
  not subject to page visibility throttling. A `setTimeout` clock is the
  fallback where the worklet is unavailable, such as on `file://` origins.
- Requested a screen wake lock so the display does not sleep under a visible but
  unfocused visualizer, re-acquiring it on return to visible.
- Added an audible-tab keepalive (`src/js/audible-keepalive.js`) that marks the
  tab audible to exempt it from background timer throttling. It runs on its own
  `AudioContext` and suppresses itself when the capture device looks like a
  loopback or monitor, so it can never feed back into the analysis input.
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

### Changed
- Stopped hyperspeed switching itself off when the page is hidden. The old
  behavior is still available through the new `pauseWhenHidden` option.

## [Unreleased]

### Added
- Added an `html-css-validation` job to `.github/workflows/checks.yml` that
  runs the [Nu Html Checker](https://github.com/validator/validator) against
  `src/*.html` and `src/css/*.css` on every pull request and push to
  `develop`, downloading its `vnu.jar` release asset pinned by a SHA-256
  checksum computed at adoption time.
- Added `SECURITY.md`: how to privately report a vulnerability (GitHub
  Security Advisories), scope, supported versions, and the accepted risks
  already documented elsewhere (CSP `unsafe-eval`, localhost-only Docker
  binding, vendored dependencies) linked rather than duplicated.
- Adopted the current `abuzucom/agents` template infrastructure: brought
  AGENTS.md's rule body to parity (rules 10-13, checker attribution
  clauses, two new Style bullets for American spelling and English-only
  prose), added the ten upstream `scripts/check_*.py` and `lint_style.py`
  checkers, wired them into `.github/workflows/checks.yml` and a new
  `.pre-commit-config.yaml`, and added `.editorconfig`, `.gitattributes`,
  `Makefile`, and `hooks/` (an inert Claude Code example hook), while
  preserving this repo's Commands, Do not touch, Architecture, Gotchas, and
  Read before touching orientation. Also added an explicit non-root `user:`
  to the Docker Compose service, matching the image's existing runtime user.
- `tools/split-extra-images.py` - splits the experimental texture bundle
  into deterministic lazy-loaded part files and losslessly optimizes the
  embedded images, verifying every optimized variant pixel-for-pixel.
- Added a touch-first mobile visualizer entry point with branded controls for
  shuffling, preset history, cycle intervals, and hyperspeed mode.
- Added the `T` fullscreen shortcut for toggling 100ms hyperspeed shuffle.
- Added `M`/`K` fullscreen shortcuts for favoriting the current preset and
  viewing/copying the session's favorites list, mirroring the excluded-
  presets workflow, for building a setlist during a live performance.

### Fixed
- Fixed an errant double `try-catch` block inside `tools/convert-milk-presets.js` and ensured exceptions are properly logged or handled instead of swallowed.
- Prevented potential zero-division crashes and eliminated slow/backtracking regular expressions during the preset parsing processes.
- Eliminated unreachable dead code segments across the tooling scripts.
- Randomized the initial fullscreen preset across the resident vendored
  collection while leaving the OBS startup behavior unchanged.
- Normalized equation strings with a trailing newline before load, so presets
  whose final statement lacks a semicolon compile in butterchurn's
  space-separated equation wrapper instead of being skipped.
- Detected warp/comp shader link failures during preset load and skipped the
  preset instead of rendering every frame with an unlinked program.
- Added runtime-detected broken presets (bad equations or shader link
  failures) to the exportable excluded-presets list for later curation.
- Reduced fullscreen startup blocking by selecting the initial vendored preset
  from a resident index and deferring experimental image loading until idle or
  lazy-preset selection.
- Stopped treating post-load WebGL error state as proof that a preset failed.
- Started the visualizer before microphone permission and device enumeration
  finish, so the first frame does not wait on audio input setup.
- Fixed equation validation for valid statements without trailing semicolons.
- Hardened workflow checkouts by disabling persisted GitHub credentials.

### Changed
- Reduced `checks.yml` CI minute usage: `validate-presets` now skips its two
  `npm run validate:*` steps (which otherwise parse all of
  `src/presets-extra/`) unless the diff touches preset data or the
  validator tooling; the Nu Html Checker jar and pip packages in
  `unit-tests` are now cached between runs; and `checks.yml` no longer
  also runs on push to `develop`, since a merge only lands after its PR's
  checks already passed (`deploy.yml`'s own push trigger is unaffected).
- Enforced strict `AGENTS.md` code style and quality guidelines across the entire codebase.
- Renamed all single-character and ambiguous variables in `src/js/` and `tools/` scripts to use descriptive, contextual names.
- Restored and completed comprehensive JSDoc annotations across `visualizer-core.js`, `fullscreen-ui.js`, `obs-ui.js`, and `mobile-ui.js`.
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
- Curated 661 additional presets from the supplied removal list and recorded
  the exact removals in the inventory and durable removal ledger; one further
  requested name (`Rovastar + Loadus + Geiss - FractalDrop (Triple Mix)`) lives
  in a vendored preset pack whose format the curation tool cannot auto-edit
  and was left in place.
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
- Extended Caddy cache headers to preset chunks and app js/css, and
  removed `immutable` from `/vendor/*` because curation rewrites those
  files in place; documented the rules in the local hosting guide.
- Documented the texture part layout and lazy-loading invariants in the
  agent instruction files and README.
- Curated 2,991 additional presets from a supplied removal list (580 further
  requested names were already removed by this pass) and recorded the exact
  removals in the inventory and durable removal ledger.
- Deduplicated the experimental collection against the mainline lazy-loaded
  presets: removed 15,739 `[EXP]` presets whose source presets already ship in
  the mainline collection (exact import-time content matches plus approved
  normalized-name matches) and 247 intra-experimental exact duplicate copies,
  shrinking `src/presets-extra/` from about 276 MB to about 209 MB.
- Pruned 38 stale index entries whose preset data was missing from their chunk
  files, which previously surfaced as unavailable presets at runtime.
- Added `tools/reconcile_preset_inventory.py` and restored 2,046 missing
  `preset-inventory.csv` rows so the inventory matches the shipped presets
  exactly; corrected README preset counts to the reconciled totals.
- Removed 575 presets whose names contained slurs, hate ideology, sexual
  violence, or explicit sexual content, identified by a full audit of all
  preset names (including obfuscated spellings) and recorded in the inventory
  and durable removal ledger; corrected the README preset counts to the
  post-curation totals.
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

## [1.7.1] - 2026-07-16

### Fixed
- Drained queued WebGL errors after failed shader loads so one invalid preset
  does not poison subsequent fallback presets.
- Loaded the initial preset during audio startup instead of waiting for later
  navigation or auto-cycle activity.

## [1.7.0] - 2026-07-15

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
- Added bounded protected-file pagination and trusted-default-branch execution
  for review checks and Jira workflows.
- Removed 131 invalid generated presets and kept generated indexes, chunks,
  inventories, and removal ledgers consistent.

### Security
- Jira secrets are used only by trusted `pull_request_target` and deployment
  workflows; fork pull requests skip cleanly when secrets are unavailable.
- Protected-file workflows never execute code from the pull request branch.
- Documented the single-maintainer branch protection model without requiring
  global GitHub Code Owner approval.

## [1.6.6] - 2026-07-15

### Changed
- Audited and simplified the README and local-hosting guide. Corrected current
  preset counts, commands, controls, tooling, security notes, and provenance.

## [1.6.5] - 2026-07-15

### Fixed
- Prevented Butterchurn equation compilation failures caused by missing empty
  equation fields in imported EXP presets.
- Added parser-based validation for generated equation JavaScript and removed
  250 malformed EXP presets from the shipped collection, with corresponding
  exclusion, inventory, and removal-ledger records.
- Added runtime diagnostics for broken preset loads, including the preset name,
  logical chunk ID, physical chunk file, and caught exception.

## [1.6.4] - 2026-07-15

### Security
- Added a lodash version override of `>=4.17.12` to prevent the known
  prototype-pollution vulnerability in the dependency tree.

### Fixed
- Corrected the logical IDs passed by all 377 experimental NestDrop preset
  chunks. Mainline chunk insertion had shifted the generated `index.js`
  mapping without updating the chunks' registration callbacks, causing valid
  `[EXP]` presets to be reported as unavailable at runtime.

## [1.6.3] - 2026-07-11

### Added
- `tools/remove_presets.js` - removes a given list of exact preset names
  from `src/presets-extra/index.js`, their backing chunk files, any
  vendored `.min.js` pack that contains them, and the matching
  `preset-inventory.csv` rows, with a pre-flight existence check (aborts
  with nothing written if any name isn't found) and a post-edit
  consistency check. Productionizes the manual curation procedure so it
  doesn't need to be reconstructed for each batch.
- `tools/analyze_curation_history.js` - reconstructs the full history of
  presets curated out of this repo from `git log` and prints neutral word
  /bigram/contributor-prefix frequency statistics over their names, with
  no built-in notion of "risky" content, so anyone using this repo can
  review the same data and make their own curation calls.

### Removed
- 186 more presets curated out for photosensitivity/seizure-risk content:
  185 via `tools/remove_presets.js` (21 self-labeled "epileptic", 14
  "strobe", 3 "flicker", 28 in the `recursion frustum`/"Ananda_Flash_Remix"
  series, 2 "eyepain", 9 "serpent", 44 "rainbow bubble", 56 in the "escape
  the worm"/"Worms 2003" series, and 8 individually named) plus 1
  presets-extra entry that duplicated an already-removed vendored-pack
  name (dead/shadowed data cleaned up alongside it). Spans
  `src/presets-extra/` (38 chunk files) and the vendored
  `butterchurnPresetsExtra`/`butterchurnPresetsExtra2` packs, with the
  matching `preset-inventory.csv` rows dropped. Same intentional editorial
  curation as prior batches - see the *Curation* section in the README.
  Ships 14,770 deduplicated presets now (378 vendored + 14,392
  lazy-loaded from 14,458 index names minus 66 that duplicate a vendored
  name).

## [1.6.2] - 2026-07-11

### Removed
- 32 more presets curated out of `src/presets-extra/` (removed from
  `index.js` and their backing chunk files, with the matching
  `preset-inventory.csv` rows dropped): 4 individually named presets
  (`Hampton GER - Randomnity (Adjustable Mix)`, `Shifter-openthelight`,
  `Eo.S. + Redi Jedi _Phat_Mexican_Insanity_Pepper_Crazy_mix(1.04) Eo.S.
  edit colors2`, `Optiks - Nerve`), plus every preset whose name contains
  "seizure" or "sezure" (28 presets, mostly `Eo.S. + Phat` /
  `Bdrv`/`beta106`/`bdrv + al` "recursion frustum" and "Let_go_Wana_Sezure"
  variants). Same intentional editorial curation as prior batches - see the
  *Curation* section in the README. Ships 14,954 deduplicated presets now
  (381 vendored + 14,573 lazy-loaded from 14,640 index names minus 67 that
  duplicate a vendored name).

## [1.6.1] - 2026-07-10

### Security
- The Docker + Caddy self-hosting container now also sends a
  `Strict-Transport-Security` header (`max-age=31536000; includeSubDomains`)
  alongside the existing OWASP header set, so the header is already in
  place if that Caddyfile is ever put behind TLS termination instead of
  served as plain HTTP on `localhost`.

## [1.6.0] - 2026-07-07

### Added
- `preset-inventory.csv` - a full inventory of every preset name and the pack
  that provides it (a vendored pack, or the lazy-loaded `presets-extra`
  collection with its chunk id), generated with the same dedup/precedence
  rules `visualizer-core.js` applies at runtime. Reflects the curated set
  (14,770 rows).
- `tools/fetch-extra-presets-curated.py` - regenerates `src/presets-extra/`
  like `fetch-extra-presets.py`, but diffs a fresh upstream pull against the
  currently committed `index.js` and re-excludes anything present upstream
  but missing from the current tree, so running it preserves curation
  instead of undoing it. Supports `--zip` and `--dry-run`.
  `fetch-extra-presets.py` was refactored to extract `collect_presets()` and
  `write_output()` out of `main()` (no behavior change) so both scripts
  share one source of truth for the texture-filter rule and the chunk/index
  JSON encoding.

### Removed
- 45 presets deleted from the `src/presets-extra/` collection (removed from
  `index.js` and their backing chunk files).
- 174 further presets curated out of this deployment: 171 from
  `src/presets-extra/` (`index.js` + backing chunk files) and 3 from the
  vendored bundles (2 from `butterchurnPresetsExtra2`, 1 from
  `butterchurnPresetsMD1`), with the matching `preset-inventory.csv` rows
  removed. These removals are an **intentional content-curation choice for
  this deployment**, independent of the upstream collection and the butterchurn
  libraries - not an upstream change. `tools/fetch-extra-presets-curated.py`
  (above) now re-applies this curation automatically on regeneration; the
  plain `fetch-extra-presets.py` still rebuilds `src/presets-extra/` from
  upstream verbatim and will reintroduce these presets (see the *Curation*
  section in the README).

### Fixed
- Corrected the documented preset counts to match the current curated packs:
  14,770 deduplicated presets total - 378 vendored (100 base + 135 new from
  Extra + 116 new from Extra2 + 27 new from MD1, after merge-order dedup)
  plus 14,392 lazy-loaded (14,458 index names minus 66 that duplicate a
  vendored name). Replaces the stale 15,330 / 15,264 totals and 387 / 385
  vendored figures, which no longer matched the regenerated and curated
  `Extra`/`Extra2`/`MD1` packs.
- A first-run bug in `fetch-extra-presets-curated.py`: an empty
  `current_names` set made `set(fresh_kept) - current_names` treat every
  freshly fetched preset as curated-out, so a first run with no prior
  `index.js` always produced an empty `src/presets-extra/`. Fixed by
  distinguishing "no prior curation state" from "current state is empty."

## [1.5.0] - 2026-07-05

### Added
- ~15k extra presets from
  [ansorre/tens-of-thousands-milkdrop-presets-for-butterchurn](https://github.com/ansorre/tens-of-thousands-milkdrop-presets-for-butterchurn),
  committed as 118 lazy-loaded chunk files in `src/presets-extra/` (15,375
  unique presets total after deduplication against the vendored packs;
  vendored packs win on name collisions). Chunks are injected as classic
  `<script>` tags on demand, so everything still works from `file://`,
  offline, and under the strict CSP; an in-memory LRU keeps at most 16
  chunks resident. If the folder is removed the app falls back to the 387
  vendored presets.
- `tools/fetch-extra-presets.py` - stdlib-only generator that downloads the
  pinned, sha256-verified upstream zip and regenerates `src/presets-extra/`,
  excluding presets that reference custom textures the app can't supply
  (`tools/butterchurn-image-names.json` lists the vendored textures).
- Preset filter box in the OBS panel (the dropdown now holds 15k+ entries),
  built off-DOM via a DocumentFragment; status line shows the preset count.
- Broken or unloadable presets are skipped automatically at runtime and
  removed from rotation for the session.

## [1.4.0] - 2026-07-04

### Added
- Internal-only self-hosting via Docker + Caddy: `Dockerfile`,
  `docker-compose.yml`, and `Caddyfile` serving plain HTTP on :80, bound to
  `127.0.0.1` only. `localhost` already counts as a secure context for mic
  capture, so no TLS is needed.
- `docs/local-hosting.md` covering all three local modes: `file://`, dev
  server, and the Docker container (including its security hardening).

## [1.3.1] - 2026-07-04

### Changed
- The GitHub Pages deploy workflow now retries the deployment step once
  (after a 30s pause) when the Pages backend rejects the first attempt with
  its transient "Deployment failed, try again later." error.
- Documentation refreshed to reflect the production deployment at
  `https://visualizer.1a2n.net/`, the vendored (CDN-free) libraries, and the
  `src/vendor/` layout.

## [1.3.0] - 2026-07-04

### Added
- Shuffle mode for the auto-cycle: picks a random preset (never the current
  one) each tick. On by default on the fullscreen page; toggle with
  <kbd>S</kbd>. The OBS page keeps sequential cycling.
- <kbd>R</kbd> (and the panel's Random button) now never re-picks the
  currently showing preset.

### Changed
- Fullscreen <kbd>[</kbd> / <kbd>]</kbd> adjust the cycle interval in 1s steps
  at/below 10s and 5s steps above, instead of a fixed 5s step.

## [1.2.0] - 2026-07-04

### Added
- Vendored three additional preset packs from `butterchurn-presets@2.4.7`
  (Extra, Extra2, MD1) and the `butterchurnExtraImages` texture pack from
  `butterchurn@2.6.7`.
- `visualizer-core.js` now merges all loaded preset packs at startup,
  skipping presets whose exact name already exists in an earlier pack
  (base pack wins collisions): 395 unique presets, up from 100.
- Custom textures are passed to butterchurn via `loadExtraImages` so the
  handful of texture-using presets render fully.

## [1.1.0] - 2026-07-04

### Changed
- Vendored `butterchurn` and `butterchurn-presets` into `src/vendor/` instead of
  loading them from unpkg, removing the runtime CDN dependency.
- Added a Content-Security-Policy meta tag to all pages.
- Fixed the malformed charset meta tag (`<meta charset="UTF-8">`).
- Moved `<script>` tags out of overlay divs to the end of `<body>`.
- Fullscreen page only hides the cursor once the visualizer is running.

### Fixed
- Concurrent `start()` calls (e.g. double-click on Start) could create multiple
  AudioContexts and render loops; starts are now guarded.
- A failed start (mic permission denied) no longer leaks an AudioContext per
  attempt.
- Switching audio devices now disconnects the previous audio source node.
- Pressing <kbd>H</kbd> while typing in a panel input no longer toggles the panel.
- Bare modifier keypresses no longer trigger start on the fullscreen page.

## [1.0.1] - 2026-06-27

### Added
- Cleaned up HTML
- Added `index.html` to avoid 404 when accessing the root folder on web

## [1.0.0] - 2026-06-26

### Added
- Shared `visualizer-core.js` controller (`window.BCViz`) holding all butterchurn
  setup, preset cycling, and audio-device handling.
- `obs.html` - OBS browser-source page with a hideable control panel.
- `fullscreen.html` - standalone keyboard-only fullscreen page.
- Per-page CSS (`panel.css`, `fullscreen.css`) and UI wiring
  (`obs-ui.js`, `fullscreen-ui.js`).
- Docs: OBS setup and audio-routing guides.
- `package.json` with a `start` script for a local static server.
- GitHub Actions workflow (`.github/workflows/deploy.yml`) to publish `src/`
  to GitHub Pages on push to `develop`.

### Notes
- Refactored from two standalone single-file HTML prototypes
  (`butterchurn-obs.html`, `butterchurn-fullscreen.html`) into a shared-core
  repository structure.
