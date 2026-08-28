# Changelog

All notable changes to this project are documented here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); this project aims to use
[Semantic Versioning](https://semver.org/).

## [1.10.0]

### Added
- Remembered the selected audio input across reloads
  (`src/js/audio-prefs.js`). An OBS browser source is rebuilt from scratch on a
  scene refresh, which previously dropped the visualizer back to the system
  default input every time. The device is matched back by id first and by label
  second, so it also survives a Voicemeeter restart handing the same device
  back under a new id. This is the only state the pages persist.

### Fixed
- Fixed `NotAllowedError: Permission denied` when selecting an audio input
  giving no indication of the cause. The error wording now distinguishes a page
  or embedder block, which in OBS means a **Local file** browser source that
  has to become a **URL** source, from an operating-system privacy block, and
  covers `SecurityError` as well. The wording moved out of the two
  byte-identical copies in `src/js/obs-ui.js` and `src/js/fullscreen-ui.js`
  into `src/js/device-errors.js`. See the new troubleshooting entries in
  `docs/audio-routing.md` and the expanded note in `docs/obs-setup.md`.
- Fixed a failure to open the audio input at startup collapsing into one
  generic message, so a permission denial looked the same as an unplugged
  cable. The initial connect is also awaited now, so the device picker is
  rebuilt from the list enumerated under permission rather than the
  pre-permission list, where every label is blank.
- Fixed a start that fails after the audio input connects leaving the capture
  device held and the page unable to retry. Awaiting the initial connect means
  the stream is attached before `started` is set, so `startAudio`'s failure
  path now releases the stream and clears `prepared` and `started` as well as
  closing the context. It previously kept the microphone open, and left the
  retry guard believing the visualizer was running, so every later attempt
  returned silently over a dead context.
- Fixed a failure in the second-pass device reselect being reported as a
  failure to start. That pass runs after the visualizer is already running on
  the default input, so `src/js/obs-ui.js` now reports why the saved input was
  skipped alongside the running status instead of replacing it with
  `Audio error`.
- Fixed a remembered device name shared by more than one input resolving to
  whichever enumerated first. Two identical interfaces report one label, and
  reconnecting to the wrong one still looks healthy, so `resolve` now declines
  an ambiguous label and falls back to the system default.

### Changed
- Guarded `window.BCDeviceErrors` and `window.BCAudioPrefs` in
  `src/js/obs-ui.js` and `src/js/fullscreen-ui.js`, matching the guard
  `visualizer-core.js` already applies to the same globals. Both arrive as
  separate deferred scripts, and a missing one turned every device-error path
  into a `TypeError`, in the code whose job is reporting failures.

## [1.9.0]

### Changed
- Replaced pickle hook-coverage trace files with validated JSON. Test processes
  influence the trace directory, so loading those files with `pickle.load`
  allowed a crafted test artifact to execute code in the coverage checker.
- Classified command strings passed to Bash `eval`, treated `exec` as a command
  prefix, and routed unresolved `eval` expansions to the user. These builtins
  previously hid destructive commands from the gate.
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
- Imported `unittest.mock` in `tests/test_require_consent.py` rather than
  importing `unittest` twice, once plainly and once with `from`, which a
  code-quality bot flagged on this pull request.

### Added
- Measured the coverage baseline where CI measures it. A mode 000 file is
  readable for root, so the two `OSError` branches in `require_consent.py`
  that a permission denial takes never fire in a root shell and do fire in
  CI. The tool now refuses to write a baseline as root rather than
  producing one that cannot match.
- Named the tracer directory `tools/hook-trace`. `coverage/` is one of the
  commonest `.gitignore` entries and this repo carries it, so the first
  commit of the gate silently left the tracer out. Without it the gate
  reads no traced lines and reports every statement in `hooks/` as
  unreached, which arrives as a wall of noise rather than as the one
  missing file it is. Fixed upstream too, since any adopter with that line
  would have hit it.
- Added `scripts/check_hook_coverage.py`, `tools/hook-trace/sitecustomize.py`
  and `hook-coverage-baseline.json`, run in CI. The gates execute as
  subprocesses, so ordinary in-process coverage sees almost none of their
  decision code; Python imports `sitecustomize` in every interpreter it
  starts, which is the stdlib way to reach them. The gate fails both when a
  function gains unreached statements and when the baseline goes stale,
  since a recorded limit nobody maintains stops being a limit.
- The baseline is per repository, and this one records 211 unreached
  statements across 64 functions where the template records 118 across 59.
  This repo declined `test_enforce_branch_name.py` and
  `test_enforce_git_identity.py`, which exercise the template's Git write
  context paths. `docs/template-drift.md` records it.
- Covered the digest-bound form of `AGENTS_CONSENT_GRANTED`, which no test
  had ever run. The bare `path` grant was covered; `path@sha256:<digest>`
  was not, so the binding the gate's docstring promises had never been
  shown to hold. Four tests cover it, including a stale digest and a digest
  belonging to another file. Found by a reachability pass that traces every
  interpreter the suite launches, since the gates run as subprocesses and
  in-process coverage sees almost none of their decision code.
- Wired `scripts/check_ascii.py` into CI against `README.md`,
  `CHANGELOG.md`, `SECURITY.md`, and `docs/`, and fixed the 37 spaced
  hyphens it found. Version headings parenthesize their date,
  `## [1.2.3] (2026-01-01)`, and definition bullets use a colon. The
  checker had been available and unwired, so the repo failed a rule it
  ships.
- Added `tests/test_check_ascii.py`, 13 tests shared with
  `abuzucom/agents`. Six pin what the dash rule still catches, since a fix
  to a linter's false positives is one edit away from a fix to its true
  ones.
- Fixed a crash in the PowerShell gate's `-ArgumentList` handler, which
  called `unparseable_verdict` with one argument against a two-parameter
  function. A payload that would not tokenize raised `TypeError` rather
  than denying, and a raise is a non-zero exit that is not 2, which Claude
  Code treats as non-blocking: the gate failed open on exactly the input it
  exists to catch. `tests/gate_corpus.py` carries the case.
- Removed two duplicate test methods from `tests/test_require_consent.py`.
  Merging the template's copy with this repo's local wiring assertions
  produced a second definition of `test_entries_use_the_exec_form` and
  `test_destructive_bash_hook_is_registered`. Python keeps the later
  definition silently, so both assertions had stopped running.
- Added `shared-files.json` and `scripts/sync.py --check-shared`, run in
  CI. `sync.py` copies the AGENTS.md family and can copy nothing living in
  a repository it cannot see, which is how this repo's `check_ascii.py` and
  `lint_style.py` improvements sat unnoticed upstream for weeks. The seven
  files carrying gate decisions are now compared against SHA-256 digests
  committed in both repositories, so a fix landing in one and not the other
  fails the other's check. `tests/test_require_consent.py` stays off the
  list: it holds two wiring assertions moved from a suite this repo
  declined, recorded in `docs/template-drift.md`.
- Added `tests/gate_corpus.py`, shared byte-identical with
  `abuzucom/agents`: one table of every known gate bypass with the verdict
  it must reach and the reason the row exists, imported by the Bash,
  PowerShell, and consent suites. A fix landing in one repository and not
  the other fails the other's suite.
- Closed five gate bypasses the corpus found. Each gate knew only its own
  shell's interpreters, so `powershell -Command 'Remove-Item -Recurse
  -Force /etc'` crossed the Bash gate and `bash -c 'rm -rf /etc'` crossed
  the PowerShell gate, both untouched; on Windows both lines run. A
  PowerShell script block put a brace where a program name goes, so
  `& { Remove-Item -Recurse -Force /etc }` was read as a program named `{`.
  `Start-Process -ArgumentList` handed a CMD line to a program through a
  parameter no gate recognized. All three delete readings, POSIX `rm`,
  PowerShell `Remove-Item`, and the CMD verbs, now live in
  `hooks/_gate_core.py` and are tried together, so neither gate can learn a
  spelling the other does not.
- Named the unrecognized `permission_mode` in the deny reason the shell
  gates emit. An interactive mode Claude Code adds later denies here, and
  the reason read identically to a genuinely unattended session.
- Added `docs/template-drift.md`, recording what this repository's copies of
  the `abuzucom/agents` template files differ in and why. `sync.py` keeps only
  the AGENTS.md family in step, so every `scripts/`, `hooks/`, and `tests/`
  file is maintained here and drifts unwatched. Two files differ today, both
  following from a template file this repository declined rather than from an
  independent edit. The template owns the policy in `DRIFT.md` and the
  taken-versus-declined list in `adopters/1a2n-web-visualizer.md`; neither side
  restates the other's fields. Nothing verifies any of it.
- Added a demo build (`src/demo.html`) that drives the visualizer from a
  synthetic audio track generated in the page, so the presets react with no
  microphone permission, no virtual audio cable, and no input device. It shares
  `css/fullscreen.css` and `js/fullscreen-ui.js` with the fullscreen build and
  is selected by `data-demo="1"` on `<body>`; `?demo=1` turns `fullscreen.html`
  into the same build. Listed as a fourth card on the landing page.
- Added `src/js/demo-audio.js`, the track generator: kick, snare, bass, chord
  pad and filtered-noise hats on a two-second lookahead scheduler, with a slow
  filter LFO running as an audio-thread modulation edge so the drift continues
  while the page is hidden. Three tempos, each its own pattern rather than the
  same loop played faster: house at 87, trance at 140, and liquid drum and bass
  at 174, the last a two-step break over half-time harmony.
- Made the generated audio silent. It reaches `destination` only through a gain
  of exactly zero, which is bit-exact digital silence. That tap exists because
  butterchurn's analyser chain never connects to the destination itself, so the
  synthetic sources would otherwise depend on an engine's automatic-pull
  behavior for an output-unconnected `AnalyserNode`.
- Added <kbd>B</kbd> to cycle genre and tempo, <kbd>,</kbd>/<kbd>.</kbd> to
  nudge tempo, and <kbd>-</kbd>/<kbd>=</kbd> for intensity, plus a `Demo` row in
  the diagnostics overlay that stays hidden on the other three pages.
- Added the `demo` option to `BCViz.create` and six methods to its API:
  `isDemo`, `getDemoTempo`, `setDemoTempo`, `cycleDemoTempo`,
  `getDemoIntensity`, and `setDemoIntensity`. All are additive and report `0`
  rather than throwing when demo mode is off.

### Fixed
- Removed the replayable `AGENTS_CONSENT_GRANTED` grant override. Fixed Bash
  brace and command-substitution parsing, PowerShell backtick and encoded-command
  handling, Git config execution detection, and hard-link scan failures.
- Fixed the watchdog reporting a lost audio input, and reconnecting to a device
  when armed, on a page that never opened a stream. `visualizer-core.js` passed
  a `handleLostInput` option that `audio-watchdog.js` does not read; the option
  it honors is `isMonitoring`, which was never passed and so defaulted to
  monitoring everything. The `hadStream` guard the code intended was dead. This
  already misfired whenever `getUserMedia` failed, and an armed guard would
  escalate it into a device reconnect.
- Fixed the audio source not being reconnected after a WebGL context recovery.
  `recoverVisualizer` builds a fresh butterchurn instance with a fresh internal
  analyser chain, and nothing called `connectAudio` again, so a recovered
  visualizer rendered against dead audio for the rest of the session.
- Added `hooks/require_consent.py` and `.claude/settings.json`, wiring two Claude Code
  gates that run before a tool call. The only unprompted edit to an existing test file
  is a verified append at the end of it: the new text must begin with the old text, the
  addition must start on a new line, and the old text must sit at the end of the file.
  An earlier form of this check asked only whether the old text still appeared somewhere
  in the new text, which passed an assertion that had been commented out, wrapped in a
  string, moved into a branch that never runs, or extended on the same line. Paths are
  resolved before classification, so a symlink with an innocuous name cannot carry an
  edit into a test file, and any test file resolving outside the project root is gated
  whether a link redirected it there or the caller named it directly. The `AGENTS_CONSENT_GRANTED` override for headless runs
  is compared on the canonical path, so one grant releases one file rather than every
  file whose path ends the same way. An edit that removes or rewrites existing test
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
- Split the newly mirrored Git option, repository-config, alias, and nested
  interpreter parsing into focused helpers so all shared gate files pass this
  repository's strict ruff rules without changing decisions.
- Removed `find_reason` and `find_consent_reason` from the Bash gate. Both
  were defined and called by nothing, here or upstream.
- Closed three false positives in `check_ascii.py` and `lint_style.py`.
  A Markdown table delimiter row tripped the dash rule, so did a list
  marker opening its own line, and an inline code span opening on one line
  and closing on the next leaked its contents. The last one flagged the
  preset name `Optiks - Nerve` in a 1.6.2 entry, where satisfying the
  checker would have meant rewriting the name and falsifying the record of
  which preset was removed.
- Brought the shared gates under this repository's ruff ruleset. `lint` had
  been red on every commit of this branch: `npx eslint .` passes, and the
  `astral-sh/ruff-action` install step runs `ruff check` over the whole
  repository before the explicit `ruff check tools/` step is reached.
  Seven magic values are named, `git_verdict` splits into a resolution
  reading, a per-subcommand table and a flag reading, and the three
  `_program_verdict` functions split so each returns at most six times.
- Rewrote the README hook section and dropped a contradicting sentence from
  AGENTS.md rule 3. Both described the gates two revisions back: two hooks
  where there are three, `git push --force` as a refusal after it moved to
  a prompt, the append carve-out as live after it came out, and the Bash
  redirect as an open gap after the shell gate closed it. Rule 3 carried
  both the corrected sentence and the stale one, which disagreed.
- Excluded merge commits from `scripts/check_commit_message.py`, and returned it to the template's advisory
  behavior so a subject violation reports rather than blocks. `git merge` writes `Merge branch 'x' into y`,
  which no author chose and which no `type: description` subject can express, so every ordinary branch update
  failed the check. Added `tests/test_check_commit_message.py` covering the merge case, a real violation, and
  the advisory exit code.
- Registered both hooks in the exec form (`command` plus `args`) instead of a shell string. In shell form an
  unquoted `${CLAUDE_PROJECT_DIR}` splits a project path containing a space, and the gate silently never runs.
- Made both hooks fail closed on their own inputs. An unparseable payload or a malformed `tool_input` is denied
  rather than treated as a SessionStart or crashing, and a test file that cannot be read or decoded is gated
  rather than read as an empty string, which had let a non-UTF-8 test file be overwritten with no prompt.
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
- Added `hooks/_gate_core.py`, which both shell gates and the consent gate import, so a decision has one definition rather than one per gate.
- Added `hooks/block_destructive_powershell.py` under a `PowerShell` matcher. The Bash matcher covered only Bash, so `Remove-Item -Recurse -Force` on a Windows session met no gate at all.
- Added `tests/test_gate_parity.py`, which feeds both gates an equivalent corpus and fails when their verdicts differ, and asserts neither gate defines a decision function of its own.
- Added a `windows-latest` job. No Linux job can show that the configured launcher resolves on Windows, and the gates had never run there.
- Added `tools/run-python.js`, which probes `python3`, `python`, then `py -3` by running each rather than trusting the name. `npm run test:py` and `dev` named `python3`, which does not exist on Windows, while `lint` named `python`, which may be absent or Python 2 on Debian.
- Added the data-destruction policy: drive roots, system directories, formatting and repair tools, `dd`, `hdparm`, truncating redirects, pipes into interpreters, alias definitions, `crontab -r`, recovery destruction, and `gh repo delete` are refused; recursive deletes, privilege escalation, process termination, shell profile writes, and forced pushes route to the user.
- Added an `html-css-validation` job to `.github/workflows/checks.yml` that
  runs the [Nu Html Checker](https://github.com/validator/validator) against
  `src/*.html` and `src/css/*.css` on every pull request and push to
  `develop`. Upstream attaches release assets only to a moving `latest` tag,
  which silently replaces the jar and breaks any checksum pinned against it,
  so the job takes `vnu.jar` from the immutable `vnu-jar` npm tarball the
  same project publishes, pinned by version and verified by SHA-256 on both
  the tarball and the extracted jar. Moving to a new checker version is now
  a deliberate change rather than whatever upstream published last.
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
- `tools/split-extra-images.py`: splits the experimental texture bundle
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
- Removed the end-of-file append carve-out from the consent gate. Every edit to a test file that already exists now asks. A textual append check cannot tell a new test from a statement that neutralizes every test above it.
- Launched hooks as `python` rather than `python3`, and added a test asserting the configured string resolves. The behavioral tests run hooks through `sys.executable`, so they passed against a configuration that never started on Windows.
- Gated Bash writes that reach a test file through a redirect, a here-document, `tee`, `sed -i`, `cp`, or `mv`. Rule 3 applied to the same act through one tool and not the other.
- Rendered every value reaching a permission prompt or stderr as printable ASCII. A filename carrying newlines or terminal control could rewrite the prompt the user reads to decide.
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

## [1.6.6] (2026-07-15)

### Changed
- Audited and simplified the README and local-hosting guide. Corrected current
  preset counts, commands, controls, tooling, security notes, and provenance.

## [1.6.5] (2026-07-15)

### Fixed
- Prevented Butterchurn equation compilation failures caused by missing empty
  equation fields in imported EXP presets.
- Added parser-based validation for generated equation JavaScript and removed
  250 malformed EXP presets from the shipped collection, with corresponding
  exclusion, inventory, and removal-ledger records.
- Added runtime diagnostics for broken preset loads, including the preset name,
  logical chunk ID, physical chunk file, and caught exception.

## [1.6.4] (2026-07-15)

### Security
- Added a lodash version override of `>=4.17.12` to prevent the known
  prototype-pollution vulnerability in the dependency tree.

### Fixed
- Corrected the logical IDs passed by all 377 experimental NestDrop preset
  chunks. Mainline chunk insertion had shifted the generated `index.js`
  mapping without updating the chunks' registration callbacks, causing valid
  `[EXP]` presets to be reported as unavailable at runtime.

## [1.6.3] (2026-07-11)

### Added
- `tools/remove_presets.js`: removes a given list of exact preset names
  from `src/presets-extra/index.js`, their backing chunk files, any
  vendored `.min.js` pack that contains them, and the matching
  `preset-inventory.csv` rows, with a pre-flight existence check (aborts
  with nothing written if any name isn't found) and a post-edit
  consistency check. Productionizes the manual curation procedure so it
  doesn't need to be reconstructed for each batch.
- `tools/analyze_curation_history.js`: reconstructs the full history of
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
  curation as prior batches; see the *Curation* section in the README.
  Ships 14,770 deduplicated presets now (378 vendored + 14,392
  lazy-loaded from 14,458 index names minus 66 that duplicate a vendored
  name).

## [1.6.2] (2026-07-11)

### Removed
- 32 more presets curated out of `src/presets-extra/` (removed from
  `index.js` and their backing chunk files, with the matching
  `preset-inventory.csv` rows dropped): 4 individually named presets
  (`Hampton GER - Randomnity (Adjustable Mix)`, `Shifter-openthelight`,
  `Eo.S. + Redi Jedi _Phat_Mexican_Insanity_Pepper_Crazy_mix(1.04) Eo.S.
  edit colors2`, `Optiks - Nerve`), plus every preset whose name contains
  "seizure" or "sezure" (28 presets, mostly `Eo.S. + Phat` /
  `Bdrv`/`beta106`/`bdrv + al` "recursion frustum" and "Let_go_Wana_Sezure"
  variants). Same intentional editorial curation as prior batches; see the
  *Curation* section in the README. Ships 14,954 deduplicated presets now
  (381 vendored + 14,573 lazy-loaded from 14,640 index names minus 67 that
  duplicate a vendored name).

## [1.6.1] (2026-07-10)

### Security
- The Docker + Caddy self-hosting container now also sends a
  `Strict-Transport-Security` header (`max-age=31536000; includeSubDomains`)
  alongside the existing OWASP header set, so the header is already in
  place if that Caddyfile is ever put behind TLS termination instead of
  served as plain HTTP on `localhost`.

## [1.6.0] (2026-07-07)

### Added
- `preset-inventory.csv`: a full inventory of every preset name and the pack
  that provides it (a vendored pack, or the lazy-loaded `presets-extra`
  collection with its chunk id), generated with the same dedup/precedence
  rules `visualizer-core.js` applies at runtime. Reflects the curated set
  (14,770 rows).
- `tools/fetch-extra-presets-curated.py`: regenerates `src/presets-extra/`
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
  libraries, not an upstream change. `tools/fetch-extra-presets-curated.py`
  (above) now re-applies this curation automatically on regeneration; the
  plain `fetch-extra-presets.py` still rebuilds `src/presets-extra/` from
  upstream verbatim and will reintroduce these presets (see the *Curation*
  section in the README).

### Fixed
- Corrected the documented preset counts to match the current curated packs:
  14,770 deduplicated presets total: 378 vendored (100 base + 135 new from
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

## [1.5.0] (2026-07-05)

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
- `tools/fetch-extra-presets.py`: stdlib-only generator that downloads the
  pinned, sha256-verified upstream zip and regenerates `src/presets-extra/`,
  excluding presets that reference custom textures the app can't supply
  (`tools/butterchurn-image-names.json` lists the vendored textures).
- Preset filter box in the OBS panel (the dropdown now holds 15k+ entries),
  built off-DOM via a DocumentFragment; status line shows the preset count.
- Broken or unloadable presets are skipped automatically at runtime and
  removed from rotation for the session.

## [1.4.0] (2026-07-04)

### Added
- Internal-only self-hosting via Docker + Caddy: `Dockerfile`,
  `docker-compose.yml`, and `Caddyfile` serving plain HTTP on :80, bound to
  `127.0.0.1` only. `localhost` already counts as a secure context for mic
  capture, so no TLS is needed.
- `docs/local-hosting.md` covering all three local modes: `file://`, dev
  server, and the Docker container (including its security hardening).

## [1.3.1] (2026-07-04)

### Changed
- The GitHub Pages deploy workflow now retries the deployment step once
  (after a 30s pause) when the Pages backend rejects the first attempt with
  its transient "Deployment failed, try again later." error.
- Documentation refreshed to reflect the production deployment at
  `https://visualizer.1a2n.net/`, the vendored (CDN-free) libraries, and the
  `src/vendor/` layout.

## [1.3.0] (2026-07-04)

### Added
- Shuffle mode for the auto-cycle: picks a random preset (never the current
  one) each tick. On by default on the fullscreen page; toggle with
  <kbd>S</kbd>. The OBS page keeps sequential cycling.
- <kbd>R</kbd> (and the panel's Random button) now never re-picks the
  currently showing preset.

### Changed
- Fullscreen <kbd>[</kbd> / <kbd>]</kbd> adjust the cycle interval in 1s steps
  at/below 10s and 5s steps above, instead of a fixed 5s step.

## [1.2.0] (2026-07-04)

### Added
- Vendored three additional preset packs from `butterchurn-presets@2.4.7`
  (Extra, Extra2, MD1) and the `butterchurnExtraImages` texture pack from
  `butterchurn@2.6.7`.
- `visualizer-core.js` now merges all loaded preset packs at startup,
  skipping presets whose exact name already exists in an earlier pack
  (base pack wins collisions): 395 unique presets, up from 100.
- Custom textures are passed to butterchurn via `loadExtraImages` so the
  handful of texture-using presets render fully.

## [1.1.0] (2026-07-04)

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
- Docs: OBS setup and audio-routing guides.
- `package.json` with a `start` script for a local static server.
- GitHub Actions workflow (`.github/workflows/deploy.yml`) to publish `src/`
  to GitHub Pages on push to `develop`.

### Notes
- Refactored from two standalone single-file HTML prototypes
  (`butterchurn-obs.html`, `butterchurn-fullscreen.html`) into a shared-core
  repository structure.
