# Repository guide

Project orientation for agents and contributors. `docs/project-orientation.md`
sends every agent here. The assembled policy has a 64 KiB limit, so this
guide stays outside the injected policy. Read it before any change.

## Commands

- `npm ci --ignore-scripts` then `npm start`: dev server via the pinned
  `serve` package without building the native converter. `--ignore-scripts`
  also skips the `patch-package` postinstall that applies
  `patches/milkdrop-shader-converter+0.0.8.patch`; that patch matters only
  when building the native converter for the `.milk` conversion pipeline
  (see the header of `tools/convert-milk-presets.js`).
- `npm run dev`: alternative dev server via `python3 -m http.server --directory src 8000`.
- `npm run lint`: ESLint (`src/js/`, `tools/*.js`) plus ruff (`tools/*.py`). Run
  before presenting work as finished; fix everything it flags.
- Tests: `npm test` runs both Node (`npm run test:js`) and Python (`npm run test:py`) unit test suites.
- Preset validation: `npm run validate:presets` (`node tools/validate-preset-chunks.js`) and `npm run validate:exp` (`node tools/validate-experimental-presets.js`).
- `python3 scripts/sync.py`: assemble AGENTS.md, `docs/agent-policy/*.md`, and
  `docs/project-orientation.md` into the tool-specific copies; `--check` (run
  in CI) verifies without writing, and `--check-shared` verifies the gate files
  against `shared-files.json`.
- `docker compose up -d --build`: self-hosted deployment (see
  `docs/local-hosting.md`).
- Preset curation: `node tools/remove_presets.js --dry-run --names-file <file>`
  then without `--dry-run`; `node tools/analyze_curation_history.js`.
- Preset regeneration: `python3 tools/fetch-extra-presets-curated.py [--dry-run]`.
- EXP normalization: `python3 tools/import-nestdrop-presets.py --normalize-existing`.
- EXP validation: `node tools/validate-experimental-presets.js`.
- Texture parts: `python3 tools/split-extra-images.py [--dry-run]` re-splits
  and losslessly optimizes the experimental texture part files.
- Node and Python tests live in `tests/`; run both suites (see the test
  commands above) during the "Test-first" workflow. Browser behavior still
  requires loading the pages manually.

## Do not touch

- `src/vendor/butterchurnExtraImagesExp-part-N.js`: generated experimental
  texture parts. Regenerate only via `tools/split-extra-images.py` or the
  NestDrop importer; never hand-edit. The part callback format
  `window.__bcExtraImagesExpPart(N, TOTAL, {...})` must stay in sync between
  those tools and `visualizer-core.js`.
- `src/vendor/*.min.js`: vendored npm builds (butterchurn plus preset packs).
  Hand-editing breaks provenance; change preset content only via
  `tools/remove_presets.js`.
- `src/presets-extra/` (`index.js` plus `chunk-NNN.js`): generated, committed
  output. Edit only via `tools/remove_presets.js`, or regenerate wholesale
  with `tools/fetch-extra-presets*.py`. Never hand-edit a chunk file.
- Experimental NestDrop output is also generated output. Its logical chunk
  IDs remain contiguous after the mainline chunks, while its physical files
  use the reserved `chunk-9000.js` and higher namespace through the
  `index.js` `files` mapping. **Never use 9000+ as a logical chunk ID.** Each
  generated file's `window.__bcPresetChunk(logicalId, ...)` callback must match
  its logical position in `index.js`; changing the mainline index requires
  regenerating or reindexing all experimental output.
- `preset-inventory.csv`: generated inventory kept in sync by
  `tools/remove_presets.js`; do not hand-edit rows.
- `removed-presets.csv`: durable ledger of every preset ever curated out,
  appended to by `tools/remove_presets.js` at removal time; do not hand-edit
  rows. Fetch scripts consult it to avoid resurrecting removed presets.
- Presets already curated out are an intentional editorial choice (see
  README "Curation" section); never restore one as a "fix."

## Architecture

Static site, no build step or framework. `src/index.html` is a script-free
landing page linking to three visualizer entry points, `src/obs.html`,
`src/fullscreen.html`, and `src/mobile.html`, which share one controller
module, `src/js/visualizer-core.js` (the `BCViz` object). `obs-ui.js`,
`fullscreen-ui.js`, and `mobile-ui.js` wire up each page's UI on top of it;
`mobile-state.js` holds the mobile page's history/state helpers and
`hyperspeed.js` implements the rapid preset-shuffle mode.

- `src/vendor/`: vendored butterchurn plus preset packs, self-hosted (no
  CDN), and the generated `butterchurnExtraImagesExp-part-N.js` experimental
  texture parts, lazy-loaded via injected `<script>` tags on idle or before
  the first `[EXP]` preset.
- `src/presets-extra/`: tens of thousands of lazy-loaded presets from the
  mainline and experimental collections, packed into `chunk-NNN.js` files
  injected as `<script>` tags on demand. Chunk and preset counts change
  with every curation PR; `src/presets-extra/index.js` is the source of
  truth for what exists.
- `tools/`: Python generators (`fetch-extra-presets*.py`,
  `fetch-cream-of-the-crop-presets.py`) that build `src/presets-extra/` from
  upstream, Node curation utilities (`remove_presets.js`,
  `analyze_curation_history.js`), and the raw `.milk` to JSON conversion
  pipeline (`convert-milk-presets.js`, `convert-shader-worker.js`) used by
  fetch scripts pulling from sources that do not ship pre-converted presets.
  Further utilities: `validate-preset-chunks.js` and
  `validate-experimental-presets.js` (validation),
  `compare-experimental-presets.py` and `remove-experimental-duplicates.py`
  (EXP dedup analysis), `reconcile_preset_inventory.py` (inventory repair).
  Root JSON files (`experimental-presets.json`,
  `experimental-exclusions.json`, `experimental-textures.json`,
  `tools/butterchurn-image-names.json`) are generated records consumed by
  the import/validation pipeline.
- `scripts/`: repo automation run by CI, not the app. The `abuzucom/agents`
  template supplies `scripts/` and `hooks/` whole (see
  `docs/template-drift.md`); `sync.py` assembles the policy copies,
  `check_action_pins.py` enforces
  commit-pinned GitHub Actions, `check_protected_files.py` backs the
  protected-file review gate, `jira_sync.py` links PRs and deploys to Jira.
- Deployed via `.github/workflows/deploy.yml` to GitHub Pages on push to
  `develop`; alternatively self-hosted via the included Docker/Caddy config.
  Other workflows: `checks.yml` (AGENTS.md sync, action pins, ESLint, ruff,
  HTML/CSS validation via the Nu Html Checker), `protected-files.yml`
  (code-owner approval gate, see `docs/protected-file-review.md`),
  `security-review-pr.yml` (foucault model review of each pull request, see
  `docs/pr-security-review.md`), and
  `jira.yml` (creates and references issues in the Jira `VID` project, see
  `docs/jira-integration.md`).

## Gotchas

- `file://` usage blocks `fetch()` of local JSON; that is why preset chunks
  are injected as `<script>` tags rather than fetched directly.
- A strict CSP is enforced; anything added must work under it.
- Experimental textures are not resident at startup. They load lazily
  (idle prefetch, and `ensureExperimentalImages()` gates every `[EXP]`
  preset load); a missing part resolves without blocking preset loads.
  All page `<script>` tags use `defer`; execution order is load-bearing.
- The `tests/` suites (see Commands) cover the tooling and page logic, but
  rendering behavior still requires loading the page(s) in a browser (see
  README "Quick Start"). `npm run lint` exists and must pass.
- AGENTS.md is the single source for agent instructions. CLAUDE.md,
  GEMINI.md, CONVENTIONS.md, `.cursorrules`, `.clinerules`, `.windsurfrules`,
  `.copilot-instructions`, and `.github/copilot-instructions.md` are copies of
  AGENTS.md plus `docs/agent-policy/*.md` and `docs/project-orientation.md`,
  produced by `python3 scripts/sync.py`. Edit those sources only, then run the
  sync script; CI (`scripts/sync.py --check`) fails if any copy drifts. The
  assembled copy must stay under 64 KiB, which is why this guide lives
  outside it.
- `preset-inventory.csv` and `removed-presets.csv` must always change in
  lockstep with `index.js`, the affected chunk files, and any vendored pack;
  never one without the others (this is exactly what
  `tools/remove_presets.js` does for you). **Both CSVs are bookkeeping/audit
  records, not the source of truth the app reads from.** The running app
  only ever loads `src/vendor/*.min.js` and `src/presets-extra/index.js` plus
  `chunk-NNN.js`. Hand-editing either CSV changes nothing about what users
  see; it just leaves the ledger lying about what is actually in the app.
  `tools/remove_presets.js` is the only sanctioned way to change presets,
  precisely because it updates the real data files and both CSVs together,
  atomically.
- Experimental names use `[EXP] `. Analysis strips it; runtime and curation
  names retain it. EXP-only presets are never duplicate-removal targets.
- Each distinct import batch gets its own sequential prefix passed via
  `tools/import-nestdrop-presets.py --exp-prefix`: the original NestDrop
  import is `[EXP] `, the next batch is `[EXP2] `, and so on (`[EXP3] `,
  `[EXP4] `, ...). Never reuse an earlier batch's prefix for a new source.
  This keeps batches visually distinguishable during curation and keeps the
  importer's own name-collision check (which only compares within a single
  prefix) scoped to genuine re-imports of the same batch rather than
  masking a new batch's presets as false-positive duplicates of an earlier
  one.
- Generated equation fields must be present as strings, including empty
  strings. Validate generated equations with
  `tools/validate-experimental-presets.js`; never execute preset text during
  validation.
- Every equation field butterchurn reaches must exist as a string. It
  compiles them as `new Function("a", "".concat(field, " return a;"))`, so a
  field absent from the JSON stringifies to the literal `undefined` and
  raises `SyntaxError: Unexpected token 'return'` at load time.
  visualizer-core.js does not catch this: `normalizeEquation` only rewrites
  values that are already strings, and `validateEquation` returns early on a
  falsy value. Top-level `init_eqs_str`/`frame_eqs_str` are compiled
  unconditionally; `pixel_eqs_str` and a wave's `point_eqs_str` are guarded
  by a non-empty check; a shape's or wave's equations are compiled only when
  that item's merged `baseVals.enabled` is non-zero (butterchurn's shape and
  wave defaults both carry `enabled: 0`). `tests/test_experimental_equation_fields.py`
  enforces this over the generated experimental chunks.
- `validate-experimental-presets.js` and `validate-preset-chunks.js` only
  check JSON shape. Neither one catches a WebGL shader link failure or a
  JS `SyntaxError` in a converted equation, since both only surface when
  butterchurn actually compiles and runs the preset; a batch can pass both
  validators, lint, and `npm test` while a large fraction of it is broken
  at runtime. Before treating an import batch as done, load
  `src/demo.html` in a real browser (`data-demo="1"` gives synthetic
  audio, so no microphone is needed) or force `BCViz.create()`'s
  `opts.demo = true` when driving `obs.html`/`fullscreen.html` instead,
  then walk the batch's presets through the returned instance's
  `keys()` / `goto(index, announce)` / `currentName()` /
  `isChunkLoading()`. Pass `cycleOn: false`, or the auto-cycle timer
  navigates mid-walk and misattributes failures. Watch the console for
  `Preset load failed; skipping: {...}` warnings: that is
  visualizer-core.js's graceful-degradation path (see "Graceful
  Degradation" in the README), and it auto-advances past a broken preset
  without throwing, so a broken import looks clean unless the console is
  actually checked. A failure also makes the controller fall forward
  through neighboring presets, so attribute a warning to a preset only
  when its own name appears in the warning after that preset was
  requested. Screenshotting a small hand-picked sample (as prior import
  PRs did) is not enough to catch a systemic conversion bug that affects
  most of a batch; walk the whole batch's presets, not a sample.
- A software WebGL renderer (headless Chromium with swiftshader, as in a
  CI or agent sandbox) fails to link most converted MilkDrop-2 warp/comp
  shaders, reporting `shader program link failed: Fragment shader is not
  compiled.` This is an artifact of that renderer, not evidence the
  presets are broken. Mainline and `[EXP]` carry no custom shaders at all,
  so their passing says nothing here; split the batch by whether a preset
  has non-empty `warp`/`comp` and compare the shader-bearing half against
  an already-shipped shader-heavy batch (`[EXP2]`) as the control. When
  both fail at the same rate the result is environmental and shader
  validity simply cannot be judged in that sandbox; say so rather than
  reporting the batch as broken. The equation checks above stay valid
  there, because they are pure JS and never touch the GPU.
- Imports whitelist `.milk` and approved images; never extract or invoke
  archive executables/scripts. Reject traversal and symlinks; record ignored
  members and the archive digest. Convert with trusted WSL Node 22 tooling.
- Record conversion, missing-texture, and DDS exclusions; DDS-dependent
  presets remain excluded. Deduplicate identical basename content; suffix
  distinct variants `[variant N]` and record archive-relative paths.
- Remove exact canonical matches only from approved decisions. Normalized-name
  matches require review. If mainline output changes, regenerate EXP output;
  never hand-merge generated chunks. Verify callback IDs against the index
  before committing generated output.

## Read before touching

- Preset curation: README "Curation" section, `tools/remove_presets.js`,
  `tools/analyze_curation_history.js`.
- Deployment: README "Hosted Deployment" and "Local Hosting" sections,
  `docs/local-hosting.md`.
- Audio setup: `docs/audio-routing.md`, `docs/obs-setup.md`.
- CI and automation: `docs/protected-file-review.md` before touching
  protected files (workflows, scripts, deployment config, runtime pages);
  `docs/jira-integration.md` for the `VID` Jira project integration.


## Local policy notes

- `tests/` is a protected path. A pull request touching it needs code-owner
  approval through `docs/protected-file-review.md`, in addition to the Rule 3
  consent prompt from `hooks/require_consent.py`.
- `scripts/check_protected_files.py` is the server-side backstop for edits to
  `hooks/`, `.claude/`, and the other client hook configurations, since a local
  hook cannot vouch for itself.
