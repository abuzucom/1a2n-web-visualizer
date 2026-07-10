# Changelog

All notable changes to this project are documented here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); this project aims to use
[Semantic Versioning](https://semver.org/).

## [1.6.1] - 2026-07-10

### Security
- The Docker + Caddy self-hosting container now also sends a
  `Strict-Transport-Security` header (`max-age=31536000; includeSubDomains`)
  alongside the existing OWASP header set, so the header is already in
  place if that Caddyfile is ever put behind TLS termination instead of
  served as plain HTTP on `localhost`.

## [1.6.0] - 2026-07-07

### Added
- `preset-inventory.csv` — a full inventory of every preset name and the pack
  that provides it (a vendored pack, or the lazy-loaded `presets-extra`
  collection with its chunk id), generated with the same dedup/precedence
  rules `visualizer-core.js` applies at runtime. Reflects the curated set
  (14,986 rows).
- `tools/fetch-extra-presets-curated.py` — regenerates `src/presets-extra/`
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
  libraries — not an upstream change. `tools/fetch-extra-presets-curated.py`
  (above) now re-applies this curation automatically on regeneration; the
  plain `fetch-extra-presets.py` still rebuilds `src/presets-extra/` from
  upstream verbatim and will reintroduce these presets (see the *Curation*
  section in the README).

### Fixed
- Corrected the documented preset counts to match the current curated packs:
  14,986 deduplicated presets total — 381 vendored (100 base + 138 new from
  Extra + 117 new from Extra2 + 26 new from MD1, after merge-order dedup)
  plus 14,605 lazy-loaded (14,672 index names minus 67 that duplicate a
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
- `tools/fetch-extra-presets.py` — stdlib-only generator that downloads the
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
- `obs.html` — OBS browser-source page with a hideable control panel.
- `fullscreen.html` — standalone keyboard-only fullscreen page.
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
