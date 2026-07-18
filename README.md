# 1a2n Web Visualizer

MilkDrop-style audio visualizer pages built with
[butterchurn](https://github.com/jberg/butterchurn), intended for use as an
**OBS browser source**, a **standalone fullscreen visualizer**, or a touch-first
mobile browser experience. Includes 34,784 deduplicated presets: 374 from the four
butterchurn preset packs, 18,896 mainline lazy-loaded presets from the
[tens-of-thousands-milkdrop-presets-for-butterchurn](https://github.com/ansorre/tens-of-thousands-milkdrop-presets-for-butterchurn)
collection, and 15,514 experimental NestDrop presets; the latter two
collections are lazy-loaded in chunks - fully self-hosted (no CDN).

**Production Deployment:** <https://visualizer.1a2n.net/> (`/obs.html`,
`/fullscreen.html`, and `/mobile.html`). GitHub Actions deploys it from the
`develop` branch.

All entry points share one controller module:

- `src/obs.html`: Provides an on-screen control panel for device selection, preset management, and auto-cycle configuration. Press <kbd>H</kbd> to hide the panel.
- `src/fullscreen.html`: Provides a keyboard-controlled interface with no visible UI. It shows a five-second startup indicator, selects a random resident vendored preset, hides the cursor, and shuffles presets by default. Use it for window capture or secondary displays.
- `src/mobile.html`: Provides a touch-first browser interface with shuffle, visit history, interval, and hyperspeed controls. It does not request browser fullscreen or expose curation controls.

The UI follows the brand visual system across the landing page, OBS panel,
fullscreen overlays, and mobile controls. The palette uses Pitch (`#0B0B0B`), Paper (`#EAE7E1`),
Charcoal (`#242424`), Concrete (`#A6A39D`), and Dull Silver (`#74777A`).
Libre Franklin is used for display and editorial text, with Helvetica, Neue Haas
Grotesk, and Arial fallbacks. Cousine is used for utility text, with IBM Plex
Mono and Courier New fallbacks.

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
|   +-- presets-extra/           # ~37k lazy-loaded presets (generated, committed)
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

## Hosted Deployment (GitHub Pages)

The production environment is hosted via GitHub Pages at **`visualizer.1a2n.net`**:

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

ButterChurn dynamically compiles its audited MilkDrop preset equations, so the
Content Security Policy intentionally allows `'unsafe-eval'`. Removing this
directive breaks the visualizer. The ansorre collection is
pinned and SHA-256 verified; supplied archives record their digests, while the
Cream of the Crop source is pinned to a commit but its ZIP checksum is not yet
verified. The project reviews all shipped presets as executable content and
never fetches them from users or remote sources at runtime.

Use the Docker/Caddy configuration only for internal deployment. Docker binds
it to `127.0.0.1:8080`; do not expose it to a network or the public internet.

Dependency security is reinforced with a lodash version override in
`package.json`. Pull requests also run `scripts/sync.py --check`, the pinned
GitHub Actions check, ESLint, and Ruff through `.github/workflows/checks.yml`.

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
| <kbd>Escape</kbd> | Close the excluded-presets panel |
| <kbd>?</kbd> | Show/hide the help menu |

### OBS Panel (`obs.html`)

Use the on-screen graphical controls. Press <kbd>H</kbd> to toggle the control panel's visibility.

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

The project vendors butterchurn (`butterchurn@2.6.7`) and its presets
(`butterchurn-presets@2.4.7`) in `src/vendor/` and serves them from the site;
it uses no CDN. The application loads four preset packs (base, Extra, Extra2,
and MD1) plus the extra-images texture pack; `visualizer-core.js` merges them at
startup, skipping any preset whose name already exists in an earlier pack
(374 unique presets). To upgrade, replace the `.min.js` files with the
corresponding `lib/` builds from the npm packages. This deployment intentionally
curates some vendored presets; see [Curation](#curation). The bundles therefore
differ slightly from the stock npm builds.

Development tools include `serve`, `patch-package`, `acorn`, the MilkDrop
EEL/preset parsers, and the native `milkdrop-shader-converter`. Raw `.milk`
imports need the native converter; local serving does not. Use
`npm ci --ignore-scripts` for serving and follow `tools/convert-milk-presets.js`
to build the converter.

## Extra Presets (~34k total)

`src/presets-extra/` holds 18,896 mainline index names from
[ansorre/tens-of-thousands-milkdrop-presets-for-butterchurn](https://github.com/ansorre/tens-of-thousands-milkdrop-presets-for-butterchurn),
packed into 184 logical chunks that load lazily through injected `<script>` tags
when a user first selects one of their presets (works from `file://` and
under the strict CSP; a small in-memory LRU keeps at most 16 chunks resident).
The mainline index contains 18,896 unique presets. If the folder is
missing, the app silently falls back to the 374 vendored presets.

The experimental NestDrop import adds 15,514 `[EXP] ` presets in 377 physical
files (`chunk-9000.js` through `chunk-9376.js`). They occupy logical chunk IDs
after the mainline chunks, so the combined index currently contains 561 logical
chunks. The physical filename range is only a file namespace; the loader uses
the logical ID from `index.js` when registering each chunk. Together with the
374 vendored presets and 18,896 mainline presets, the current total is 34,784.

The folder contains generated, committed output. After an upstream update,
refresh it with the curation-preserving script (see
[Curation](#curation) below for why):

```bash
python3 tools/fetch-extra-presets-curated.py           # download + regenerate, keeping curation
python3 tools/fetch-extra-presets-curated.py --zip P   # use an already-downloaded zip
python3 tools/fetch-extra-presets-curated.py --dry-run # preview the diff, write nothing
```

`tools/fetch-extra-presets.py` is the same generator without curation -
useful for a clean reset from upstream, or as the one both scripts import
their fetch/filter/write logic from. Both pin the upstream commit and verify
the zip's sha256 (constants at the top of `fetch-extra-presets.py` - bump
them when upstream grows), and exclude any preset referencing custom
textures that neither butterchurn nor the vendored extra-images pack can
supply. The upstream collection has
**no license file**; the presets are community-created MilkDrop content
redistributed as-is.

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

Three things to know if you're regenerating presets:

- **`presets-extra` regeneration is curation-safe by default.**
  `tools/fetch-extra-presets-curated.py` diffs a fresh upstream pull against
  the currently committed `index.js` *and* against `removed-presets.csv`,
  excluding anything caught by either check - so running it preserves this
  curation instead of undoing it. Its plain counterpart,
  `tools/fetch-extra-presets.py`, has no such memory: it rebuilds
  `src/presets-extra/` verbatim from the pinned upstream zip and will
  reintroduce every curated-out preset, so only use it for a clean reset.
  Neither script touches the vendored `.min.js` packs - replacing one with a
  stock npm build restores the presets removed from that pack, and that
  curation has to be re-applied by hand.
- **The removal lists come from the app.** The `fullscreen.html` interface can
  remove the current preset from rotation and export the list of presets
  excluded during a session (the &#128683; / &#128203; controls), which is the
  source of the names curated out of the codebase here. Presets that fail at
  runtime - broken equations or shader link failures - are added to that
  exported list automatically when the app skips them.
- **New upstream sources should consult `removed-presets.csv` too.** A fetch
  script pulling presets from a different collection should exclude names
  present in the ledger, the same way `fetch-extra-presets-curated.py` does -
  not just names absent from the current `index.js` snapshot, since a
  different source could coincidentally share a name with something removed
  from an entirely different collection.

### Removing presets

`tools/remove_presets.js` removes exact preset names from
`src/presets-extra/index.js`, their
owning `chunk-NNN.js` file, any vendored `.min.js` pack that contains it, and
the matching `preset-inventory.csv` row, and appends a row for each to
`removed-presets.csv`. Matching is exact-name only. The tool writes nothing
unless it finds every requested name and every edited file passes a post-edit
consistency check.

```bash
node tools/remove_presets.js --names-file names.txt   # one exact name per line
node tools/remove_presets.js --name "Foo" --name "Bar"
node tools/remove_presets.js --names-file names.txt --dry-run
```

It does not update the preset counts documented in this README/CHANGELOG -
recompute those by hand after a removal (see the numbers in the "Extra
Presets" section above for the formula).

`tools/analyze_curation_history.js` reconstructs the full history of presets
curated out via `git log` - auto-discovering every commit that ever touched
`src/presets-extra/` or `src/vendor/*.min.js`, so it stays correct across
history rewrites instead of relying on a hand-maintained commit list - and
prints neutral frequency statistics (top words, bigrams, and likely
contributor-name prefixes) over their names. It has no built-in notion of
what's "risky" or unwanted, just the raw data, so anyone using this repo can
review the same history and make their own curation decisions. This is also
the tool that originally generated `removed-presets.csv`'s `--csv` output;
`tools/remove_presets.js` keeps it current from here on, so you shouldn't
normally need to regenerate it:

```bash
node tools/analyze_curation_history.js
node tools/analyze_curation_history.js --csv history.csv   # also write the full table
```

## License

This project is licensed under the MIT License. See [`LICENSE`](LICENSE) for details. The `butterchurn` library is also MIT-licensed. Preset authors are credited within the preset names.
