# Changelog

All notable changes to this project are documented here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); this project aims to use
[Semantic Versioning](https://semver.org/).

## [1.4.0] - 2026-07-04

### Added
- Internal-only self-hosting via Docker + Caddy: `Dockerfile`,
  `docker-compose.yml`, and `Caddyfile` serving plain HTTP on :80 and HTTPS
  on :443 through Caddy's internal CA (mic capture needs a secure context,
  so HTTPS makes audio work from other LAN machines).
- `docs/local-hosting.md` covering all three local modes: `file://`, dev
  server, and the Docker container (including how to trust the self-signed
  CA).

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
