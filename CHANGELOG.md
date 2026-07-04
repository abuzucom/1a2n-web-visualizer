# Changelog

All notable changes to this project are documented here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); this project aims to use
[Semantic Versioning](https://semver.org/).

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
