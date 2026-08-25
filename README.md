# 1a2n Web Visualizer


MilkDrop-style audio visualizer pages built with [butterchurn](https://github.com/jberg/butterchurn). Use them as an **OBS browser source**, a **standalone fullscreen visualizer**, or a touch-first mobile experience. The application includes 18,013 deduplicated presets: 373 from four butterchurn preset packs, 14,408 mainline presets from the [tens-of-thousands](https://github.com/ansorre/tens-of-thousands-milkdrop-presets-for-butterchurn) collection, and 3,232 experimental NestDrop presets. It lazy-loads the mainline and experimental collections in chunks. The application is fully self-hosted and requires no CDN.

**Production Deployment:** <https://visualizer.1a2n.net/> (`/obs.html`,
`/fullscreen.html`, and `/mobile.html`). GitHub Actions deploys it from the
`develop` branch.

All entry points share one controller module:

- `src/obs.html`: Provides an on-screen control panel for device selection, preset management, and auto-cycle configuration. Press <kbd>H</kbd> to hide the panel.
- `src/fullscreen.html`: Provides a keyboard-controlled interface with no visible UI. It shows a five-second startup indicator, selects a random resident vendored preset, hides the cursor, and shuffles presets by default. Use it for window capture or secondary displays.
- `src/mobile.html`: Provides a touch-first browser interface with shuffle, visit history, interval, and hyperspeed controls. It does not request browser fullscreen or expose curation controls.

The UI follows the brand visual system across all entry points. The palette uses Pitch (`#0B0B0B`), Paper (`#EAE7E1`), Charcoal (`#242424`), Concrete (`#A6A39D`), and Dull Silver (`#74777A`). Libre Franklin provides display and editorial text, with Helvetica, Neue Haas Grotesk, and Arial fallbacks. Cousine provides utility text, with IBM Plex Mono and Courier New fallbacks.

## Repository Structure

```text
butterchurn-visualizer/
+-- README.md
+-- LICENSE
+-- CHANGELOG.md
+-- .gitignore
+-- package.json            # Development tools and server configuration
+-- preset-inventory.csv    # Every preset name, its pack, and chunk id
+-- Caddyfile               # Caddy web server configuration
+-- Dockerfile              # Container definition for local hosting
+-- docker-compose.yml      # Docker Compose deployment configuration
+-- .dockerignore
+-- .github/
|   +-- workflows/          # Deployment, Jira, lint, security, and pin checks
+-- patches/                # Native converter compatibility patch
+-- scripts/                # CI checks and instruction synchronization
+-- tests/                  # CI check tests
+-- src/
|   +-- index.html          # Landing page
|   +-- obs.html            # OBS browser source entry point
|   +-- fullscreen.html     # Standalone fullscreen entry point
|   +-- mobile.html         # Touch-first browser entry point
|   +-- css/
|   |   +-- brand.css            # shared brand palette and typography tokens
|   |   +-- landing.css          # landing page presentation
|   |   +-- panel.css
|   |   +-- fullscreen.css
|   |   +-- mobile.css
|   +-- js/
|   |   +-- visualizer-core.js   # shared BCViz controller (the brains)
|   |   +-- obs-ui.js            # panel wiring
|   |   +-- fullscreen-ui.js     # keyboard wiring
|   |   +-- mobile-ui.js         # touch wiring
|   |   +-- mobile-state.js      # in-memory mobile history and intervals
|   |   +-- hyperspeed.js        # shared hyperspeed scheduler
|   +-- vendor/                  # vendored butterchurn + preset/texture packs
|   |   +-- butterchurn.min.js
|   |   +-- butterchurnExtraImages.min.js
|   |   +-- butterchurnExtraImagesExp-part-N.js  # lazy-loaded texture parts
|   |   +-- butterchurnPresets.min.js
|   |   +-- butterchurnPresetsExtra.min.js
|   |   +-- butterchurnPresetsExtra2.min.js
|   |   +-- butterchurnPresetsMD1.min.js
|   +-- presets-extra/           # ~19k lazy-loaded presets (generated, committed)
|       +-- index.js             # preset name -> chunk mapping
|       +-- chunk-NNN.js         # generated logical/physical chunks
+-- tools/
|   +-- fetch-extra-presets.py           # regenerates src/presets-extra/ from upstream
|   +-- fetch-extra-presets-curated.py   # same, but re-applies prior curation
|   +-- import-nestdrop-presets.py       # imports supplied .milk archives as [EXP]
|   +-- compare-experimental-presets.py  # reports EXP/mainline equivalence
|   +-- remove-experimental-duplicates.py # removes approved EXP curation targets
|   +-- fetch-cream-of-the-crop-presets.py # adds raw MilkDrop source presets
|   +-- convert-milk-presets.js           # converts raw .milk to JSON
|   +-- convert-shader-worker.js          # isolated shader conversion worker
|   +-- remove_presets.js                 # removes exact curated names
|   +-- validate-experimental-presets.js  # checks generated equation JavaScript
|   +-- butterchurn-image-names.json
+-- docs/
    +-- obs-setup.md
    +-- audio-routing.md
    +-- local-hosting.md
    +-- jira-integration.md
    +-- protected-file-review.md
```

### Experimental NestDrop presets

The experimental import pipeline accepts supplied NestDrop ZIP archives and
converts their raw `.milk` files into the same Butterchurn preset shape used
by the mainline lazy-loaded collection. Experimental runtime names receive a
reserved `[EXP] ` prefix so they are visually distinct.

Experimental textures ship as generated
`src/vendor/butterchurnExtraImagesExp-part-N.js` files (losslessly
optimized). They are not loaded at startup: `visualizer-core.js` injects the
parts as `<script>` tags on idle, and `ensureExperimentalImages()` awaits
them before the first `[EXP]` preset loads. Regenerate the parts only with
`python3 tools/split-extra-images.py` or the NestDrop importer.

Mainline logical chunk IDs remain contiguous and low. Experimental physical
chunk files begin at `chunk-9000.js` and are referenced through the optional
`index.js` `files` mapping. The `9000+` range is a physical filename
namespace, not a logical chunk ID; developers and agents must never advance
logical IDs into that range.

`tools/compare-experimental-presets.py` compares experimental data with the
baseline mainline chunks using canonical content hashes. It reports exact
duplicates, name conflicts, and EXP-only presets. Confirmed mainline matches
can be supplied to `tools/remove-experimental-duplicates.py` for duplicate
removal; parser-invalid EXP presets may also be supplied with the explicit
invalid-equation option and are recorded separately.
The `[EXP] ` prefix is removed for analysis only and remains part of runtime
and exact curation names.

#### Experimental import methodology

Treat supplied archives as data, not code:

1. Record the archive digest, member counts, duplicate basenames, textures, and
   ignored members. Extract only `.milk` files and approved image formats.
   Never extract or invoke archive executables or scripts. Reject ZIP traversal
   paths.
2. Run the trusted converter in the supported WSL Node 22 environment. Record
   malformed EEL, unsupported shaders, and invalid JavaScript equations as
   conversion failures.
3. Check texture references before retaining a preset. Skip DDS-dependent and
   unresolved-texture presets. Record skips in `experimental-presets.json` and
   exclude DDS data from the browser image bundle.
4. Canonicalize and hash preset data. Remove exact mainline matches only with
   an approved decision file. Treat normalized-name matches as review data; do
   not remove them automatically.
5. Handle source basenames independently. Keep byte-identical collisions once
   and suffix distinct-content collisions with deterministic `[variant N]`
   names. Record archive-relative source paths and collision data in the
   manifest.

Regenerate generated output; do not merge it by hand. If mainline preset
generation changes, start with the updated mainline `index.js`, rerun the
experimental importer, regenerate the inventory and reports, and run the
browser and lint checks. Every generated chunk's
`window.__bcPresetChunk(logicalId, ...)` callback must match its logical
position in `index.js`; the physical `chunk-9000.js` filename does not change
that logical ID. Keep source archives and temporary conversion logs out of Git;
retain manifests and approval/report files when provenance or curation history
requires them.

The generated equation fields are always present, even when empty, because
Butterchurn compiles them into function bodies. To repair an existing EXP
collection after updating the converter, run:

```bash
python3 tools/import-nestdrop-presets.py --normalize-existing
node tools/validate-experimental-presets.js
```

The validator parses generated equation text without executing it. Presets
that fail validation must be removed through the curation/removal tooling and
recorded in the exclusion and removal ledgers.

## Quick Start

Click the page or press a key after it loads to grant audio-capture permission.

**Standalone Browser:** Open `src/fullscreen.html`. Some browsers restrict audio access over `file://`. If the device list stays empty, use a local development server.

**Local Development Server:**

```bash
npm ci --ignore-scripts # Install dependencies without building the native converter
npm start             # Serves ./src via the pinned `serve` package
# Alternatively, using Python:
python3 -m http.server --directory src 8000
```

Open <http://localhost:8000/fullscreen.html>, <http://localhost:8000/mobile.html>,
or <http://localhost:8000/obs.html>.

**OBS Integration:** See [`docs/obs-setup.md`](docs/obs-setup.md) for setup instructions.

**Background rendering:** The visualizer keeps rendering when its window is
covered, minimized, or in a background tab. See
[`docs/background-rendering.md`](docs/background-rendering.md), and
[`docs/unattended-operation.md`](docs/unattended-operation.md) for running a set
you are not watching. Serve over HTTP for the full behavior; a `file://` origin
cannot use the AudioWorklet frame clock and falls back to about 1 fps while
hidden.

## Hosted Deployment (GitHub Pages)

GitHub Pages hosts the production environment at **`visualizer.1a2n.net`**:

```text
https://visualizer.1a2n.net/obs.html
https://visualizer.1a2n.net/fullscreen.html
https://visualizer.1a2n.net/mobile.html
```

On every push to `develop`, `.github/workflows/deploy.yml` publishes `src/`.

To deploy from a fork or new clone, select **Settings -> Pages -> Source -> GitHub Actions**. The site will be available at `https://<user>.github.io/<repo>/`.

GitHub Pages serves content over HTTPS, so browser audio capture needs no local workaround. In OBS, create a Browser Source in URL mode and use the `obs.html` URL.

## Local Hosting

Run without GitHub Pages in one of three ways: open `src/fullscreen.html` from the filesystem (`file://`), use a local development server, or run Docker:

```bash
docker compose up -d --build
```

The application runs at `http://localhost:8080`. See [`docs/local-hosting.md`](docs/local-hosting.md) for configuration and security details.

## Security Model

ButterChurn dynamically compiles its audited MilkDrop preset equations. The Content Security Policy intentionally allows `'unsafe-eval'`. Removing this directive breaks the visualizer. The ansorre collection is pinned and SHA-256 verified. Supplied archives record their digests. The Cream of the Crop source is pinned to a commit; verify its ZIP checksum before full trust. The project reviews all shipped presets as executable content and never fetches them from remote sources at runtime.

Use the Docker/Caddy configuration only for internal deployment. Docker binds
it to `127.0.0.1:8080`; do not expose it to a network or the public internet.

Dependency security is reinforced with a lodash version override in
`package.json`. Pull requests and pushes to `develop` run `scripts/sync.py --check`,
pinned GitHub Actions checks, ESLint, Ruff, Node & Python unit tests (`npm test`),
preset chunk & experimental preset validation (`npm run validate:presets`, `npm run validate:exp`),
and HTML/CSS validation against `src/*.html` and `src/css/*.css` via the
[Nu Html Checker](https://github.com/validator/validator)
through `.github/workflows/checks.yml`. Pull requests also run a banned-agent
authorship check, branch-name and commit-message shape checks (skipped for
Dependabot, whose own naming does not follow this repo's conventions), and
static checks for `persist-credentials: false` on checkout steps, unjustified
MD5/SHA-1, non-root containers, and likely secrets.

These checks come from the `abuzucom/agents` AI-agent-instructions template
(see AGENTS.md's own history for the adoption). `make sync` (or
`python3 scripts/sync.py`) regenerates the tool-specific copies after editing
`AGENTS.md`; `make check` verifies them without writing; `make lint` runs the
AGENTS.md-specific style checks below, additive to `npm run lint` (ESLint and
Ruff), not a replacement for it. Running `pre-commit install` after cloning
also wires most of the same checks in as local git hooks (`.pre-commit-config.yaml`).

`hooks/` holds two Claude Code hooks, wired through `.claude/settings.json`,
that run before a tool call rather than after a commit.
`block_destructive_bash.py` denies a recursive `rm` aimed at `/`, `~`, or
`$HOME`, a bare `git push --force`, and `git reset --hard`, and routes every
other recursive delete, the `--force-with-lease` family, `git push --mirror`,
`git push --delete`, a forced (`+`) refspec, `git commit --amend`,
`git rebase`, and `git filter-branch` to a permission prompt. It tokenizes the
command first, so equivalent spellings (`rm -Rf`, `git -C dir push --force`,
`--force-with-lease=main:<oid>`) are caught rather than read past, and a
command it cannot parse is gated rather than cleared.
`require_consent.py` sends any write to an existing test file to the same
prompt, except a verified append at the end of it: the new text must begin
with the old text, the addition must start on a new line, and the old text
must sit at the end of the file. A new test file passes untouched. Edits that
keep the old text are still gated, because an assertion that is commented
out, wrapped in a string, or moved into a branch that never runs keeps its
text and loses its effect. Paths are resolved before classification, so a
symlink with an innocuous name cannot carry an edit into a test file, and any
test file resolving outside the project root is gated whether a link
redirected it there or the caller named it directly. Both are heuristics rather than a
sandbox, and neither sees a file written through a Bash redirect, which is
what the protected-file review in `docs/protected-file-review.md` covers.

| Script | Backs | Blocking? |
|---|---|---|
| `scripts/lint_style.py` | No run-on sentences/dashes; no non-ASCII characters (in `AGENTS.md`) | Yes |
| `scripts/check_us_spelling.py` | American English spelling | No, warns only |
| `scripts/check_english_only.py` | English only | No, warns only |
| `scripts/check_banned_agents.py` | Banned agents | Yes |
| `scripts/check_branch_name.py` | Branch naming conventions | Yes |
| `scripts/check_commit_message.py` | Commit message style | Yes |
| `scripts/check_persist_credentials.py` | No persisted git credentials in CI workflows | Yes |
| `scripts/check_weak_hashing.py` | No weak hashing in security-sensitive contexts | Yes |
| `scripts/check_dockerfile_root.py` | No root containers without explicit consent | Yes |
| `scripts/check_secrets_heuristic.py` | No secrets in version control (heuristic, not entropy-based) | Yes |
| `scripts/check_ascii.py` | Same rule as `lint_style.py`, portable to any file glob | Available, not wired into CI: this repo's existing prose (`CHANGELOG.md`, `README.md`) uses spaced hyphens outside the scope the rule targets |

Protected-file review runs from the trusted default branch through
`.github/workflows/protected-files.yml`. It covers agent instructions,
automation, dependencies, deployment files, runtime code, and vendored code.
Changes from `@itsjustatank` do not require self-approval; changes from agent
or bot identities require approval from `@itsjustatank` on the current commit.
See [`docs/protected-file-review.md`](docs/protected-file-review.md) for the
branch protection and agent identity requirements.

Jira synchronization is opt-in through the `needs-jira` label and uses the
`JIRA_EMAIL` and `JIRA_API_TOKEN` repository secrets. See
[`docs/jira-integration.md`](docs/jira-integration.md) for the maintainer
workflow and deployment linking behavior.

## Controls

### Fullscreen (`fullscreen.html`)

| Key | Action |
| --- | --- |
| <kbd>Space</kbd> / <kbd>N</kbd> | Next preset |
| <kbd>P</kbd> | Previous preset |
| <kbd>R</kbd> | Random preset |
| <kbd>C</kbd> | Toggle auto-cycle |
| <kbd>S</kbd> | Toggle between shuffle and sequential auto-cycle (default is shuffle) |
| <kbd>[</kbd> / <kbd>]</kbd> | Adjust cycle interval (1s increments up to 10s, 5s increments above 10s) |
| <kbd>D</kbd> | Switch audio input device |
| <kbd>F</kbd> | Toggle fullscreen mode |
| <kbd>T</kbd> | Toggle hyperspeed shuffle at 100ms intervals |
| <kbd>X</kbd> | Remove current preset from this session's shuffle |
| <kbd>L</kbd> | Show presets excluded this session |
| <kbd>M</kbd> | Favorite the current preset this session |
| <kbd>K</kbd> | Show presets favorited this session |
| <kbd>A</kbd> | Arm/disarm the audio guard (reconnects a lost input; see [`docs/unattended-operation.md`](docs/unattended-operation.md)) |
| <kbd>I</kbd> | Show/hide the diagnostics overlay (also `?diag=1`) |
| <kbd>Escape</kbd> | Close the excluded-presets or favorites panel |
| <kbd>?</kbd> | Show/hide the help menu |

### OBS Panel (`obs.html`)

Use the on-screen graphical controls. Press <kbd>H</kbd> to toggle the control panel's visibility.
Press <kbd>A</kbd>, or use the "Audio guard" checkbox, to arm the audio guard.
Press <kbd>I</kbd> for the diagnostics overlay.

### Mobile (`mobile.html`)

Use the touch dock to shuffle, return to the previous displayed preset, cycle
through the `15s`, `30s`, and `1m` intervals, or toggle hyperspeed shuffle. The
mobile page keeps visit history in memory for the current session only.

## Audio Configuration

The application visualizes audio from a system input device, such as a
microphone. To visualize system output, route it through a virtual audio cable
and select that device as the input. See [`docs/audio-routing.md`](docs/audio-routing.md)
for platform-specific instructions.

## Dependencies

The project vendors butterchurn (`butterchurn@2.6.7`) and its presets (`butterchurn-presets@2.4.7`) in `src/vendor/`. It uses no CDN. `visualizer-core.js` merges four preset packs (base, Extra, Extra2, MD1) and the extra-images pack at startup. It skips duplicate names to yield 373 unique presets. To upgrade, replace the `.min.js` files with the `lib/` builds from the npm packages. This deployment intentionally curates vendored presets (see [Curation](#curation)). The bundles differ slightly from stock npm builds.

Development tools include `serve`, `patch-package`, `acorn`, the MilkDrop
EEL/preset parsers, and the native `milkdrop-shader-converter`. Raw `.milk`
imports need the native converter; local serving does not. Use
`npm ci --ignore-scripts` for serving and follow `tools/convert-milk-presets.js`
to build the converter.

### Preset Converter Architecture

The `.milk` to JSON pipeline (`tools/convert-milk-presets.js`) prioritizes stability, correctness, and batch safety.

- **Isolated Shader Compilation:** The native `milkdrop-shader-converter` (HLSL to GLSL) can hang on malformed inputs. The pipeline dispatches shader translation to a child process (`tools/convert-shader-worker.js`). A strict timeout kills stuck shaders and yields an empty shader instead of halting the batch.
- **Strict Equation Validation:** The pipeline checks all generated JavaScript equations using `acorn.parse()`. This guarantees valid math equations before writing to disk and prevents runtime browser errors.
- **Graceful Degradation:** If EEL equations for a wave or shape fail to translate, the converter retains the static `baseVals` instead of discarding the preset.
- **Correctness Over Minification:** The pipeline ships the generated JavaScript exactly as emitted. It avoids JS minifiers, which can rename dynamic global state variables like `time` or `bass`. Browser JIT compilers optimize these loops automatically.
- **Robust Batching:** The pipeline recursively walks source directories, detects duplicate basenames, and outputs a unified JSON dictionary to `stdout`. It routes warnings and errors to `stderr`.

## Extra Presets (~19k total)

`src/presets-extra/` holds 14,411 mainline index names from [ansorre/tens-of-thousands-milkdrop-presets-for-butterchurn](https://github.com/ansorre/tens-of-thousands-milkdrop-presets-for-butterchurn). These pack into 184 logical chunks that load lazily through injected `<script>` tags when selected. This works from `file://` under the strict CSP. An in-memory LRU keeps at most 16 chunks resident. The mainline index contains 14,408 unique presets. If the folder is missing, the app falls back to the 373 vendored presets.

The experimental NestDrop import adds 3,232 `[EXP] ` presets in 377 physical files (`chunk-9000.js` through `chunk-9376.js`). They occupy logical chunk IDs after the mainline chunks. The combined index contains 561 logical chunks. The physical filename range is only a file namespace; the loader uses the logical ID from `index.js` when registering each chunk. The overall total is 18,013 presets.

The folder contains generated, committed output. After an upstream update,
refresh it with the curation-preserving script (see
[Curation](#curation) below for why):

```bash
python3 tools/fetch-extra-presets-curated.py           # download + regenerate, keeping curation
python3 tools/fetch-extra-presets-curated.py --zip P   # use an already-downloaded zip
python3 tools/fetch-extra-presets-curated.py --dry-run # preview the diff, write nothing
```

`tools/fetch-extra-presets.py` runs the same generator without curation. Use it for a clean reset from upstream. Both scripts pin the upstream commit and verify the zip's SHA-256 (update the constants in `fetch-extra-presets.py` when upstream grows). They exclude presets referencing missing custom textures. The upstream collection has **no license file**; it redistributes community-created MilkDrop content as-is.

`tools/fetch-cream-of-the-crop-presets.py` is a separate additive importer for
raw `.milk` files from the pinned Cream of the Crop commit. Its upstream ZIP
checksum is not yet verified, and it requires the native converter build.

## Curation

This deployment ships a **deliberately curated** subset of the upstream
content. It removes selected presets from **both** the vendored preset packs
(`src/vendor/butterchurnPresets*.min.js`) and the lazy-loaded upstream
collection (`src/presets-extra/`). It drops matching `preset-inventory.csv`
rows and records removals in `removed-presets.csv`. These are editorial
choices, not upstream or library changes. Do not restore them as fixes.

`removed-presets.csv` permanently records presets that must never be re-added,
including their pack, chunk, and known removal commit, date, and subject. Like
`preset-inventory.csv`, it is bookkeeping, not runtime source. Use
`tools/remove_presets.js` for vendored/mainline curation; experimental tools
also update it for EXP decisions.

Follow these rules when regenerating presets:

- **`presets-extra` regeneration is curation-safe by default.** `tools/fetch-extra-presets-curated.py` diffs a fresh upstream pull against the committed `index.js` and `removed-presets.csv`. It excludes presets caught by either check, preserving curation. Its plain counterpart, `tools/fetch-extra-presets.py`, has no memory. It rebuilds `src/presets-extra/` verbatim from the upstream zip and reintroduces every curated-out preset. Use it only for a clean reset. Neither script touches the vendored `.min.js` packs. Replacing a pack with a stock npm build restores removed presets; reapply curation manually.
- **The removal lists come from the app.** The `fullscreen.html` interface can remove the current preset from rotation and export the list of excluded presets. This exported list supplies the names curated out of the codebase. The app automatically adds presets that fail at runtime (due to broken equations or shader link failures) to the exported list.
- **New upstream sources must consult `removed-presets.csv`.** A fetch script pulling presets from a different collection must exclude names present in the ledger, exactly as `fetch-extra-presets-curated.py` does. Do not merely rely on names absent from `index.js`; a different source might coincidentally share a name with a preset removed from another collection.

### Removing presets

`tools/remove_presets.js` removes exact preset names from `src/presets-extra/index.js`, their owning `chunk-NNN.js` file, matching vendored `.min.js` packs, and `preset-inventory.csv`. It appends a record for each removal to `removed-presets.csv`. Matching is exact-name only. The tool writes nothing unless it finds every requested name and every edited file passes a post-edit consistency check.

```bash
node tools/remove_presets.js --names-file names.txt   # one exact name per line
node tools/remove_presets.js --name "Foo" --name "Bar"
node tools/remove_presets.js --names-file names.txt --dry-run
```

It does not update the preset counts documented in this README/CHANGELOG -
recompute those by hand after a removal (see the numbers in the "Extra
Presets" section above for the formula).

`tools/analyze_curation_history.js` reconstructs the history of removed presets via `git log`. It auto-discovers commits touching `src/presets-extra/` or `src/vendor/*.min.js`, remaining correct across history rewrites. It prints frequency statistics (top words, bigrams, and likely contributor prefixes) over the removed names. It provides raw data without classifying presets as risky or unwanted. This script originally generated `removed-presets.csv`. Use `tools/remove_presets.js` to maintain the ledger going forward:

```bash
node tools/analyze_curation_history.js
node tools/analyze_curation_history.js --csv history.csv   # also write the full table
```

## License

This project is licensed under the MIT License. See [`LICENSE`](LICENSE) for details. The `butterchurn` library is also MIT-licensed. Preset authors are credited within the preset names.
