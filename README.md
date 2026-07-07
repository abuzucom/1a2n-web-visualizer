# Butterchurn Visualizer

Milkdrop-style audio visualizer pages built on
[butterchurn](https://github.com/jberg/butterchurn), intended for use as an
**OBS browser source** or as a **standalone fullscreen visualizer** in any
modern browser. Ships 15,090 deduplicated presets — 382 from the four
butterchurn preset packs plus ~15k from the
[tens-of-thousands-milkdrop-presets-for-butterchurn](https://github.com/ansorre/tens-of-thousands-milkdrop-presets-for-butterchurn)
collection, lazy-loaded in chunks — fully self-hosted (no CDN).

**Production Deployment:** <https://visualizer.1a2n.net/> (`/obs.html` and `/fullscreen.html`), automatically deployed from the `develop` branch.

Both entry points utilize a shared controller module to maintain consistent visualizer logic:

- `src/obs.html`: Provides an on-screen control panel for device selection, preset management, and auto-cycle configuration. Press <kbd>H</kbd> to hide the panel for capture.
- `src/fullscreen.html`: A keyboard-controlled interface with no visible UI. The cursor is hidden during operation. Auto-cycle shuffles presets by default. This mode is optimized for window capture or secondary display usage.

## Repository Structure

```text
butterchurn-visualizer/
├── README.md
├── LICENSE
├── CHANGELOG.md
├── .gitignore
├── package.json            # Development server configuration
├── Caddyfile               # Caddy web server configuration
├── Dockerfile              # Container definition for local hosting
├── docker-compose.yml      # Docker Compose deployment configuration
├── .dockerignore
├── .github/
│   └── workflows/
│       └── deploy.yml      # GitHub Actions deployment workflow
├── src/
│   ├── index.html          # Landing page
│   ├── obs.html            # OBS browser source entry point
│   ├── fullscreen.html     # Standalone fullscreen entry point
│   ├── css/
│   │   ├── panel.css
│   │   └── fullscreen.css
│   ├── js/
│   │   ├── visualizer-core.js   # shared BCViz controller (the brains)
│   │   ├── obs-ui.js            # panel wiring
│   │   └── fullscreen-ui.js     # keyboard wiring
│   ├── vendor/                  # vendored butterchurn + preset/texture packs
│   │   ├── butterchurn.min.js
│   │   ├── butterchurnExtraImages.min.js
│   │   ├── butterchurnPresets.min.js
│   │   ├── butterchurnPresetsExtra.min.js
│   │   ├── butterchurnPresetsExtra2.min.js
│   │   └── butterchurnPresetsMD1.min.js
│   └── presets-extra/           # ~15k lazy-loaded presets (generated, committed)
│       ├── index.js             # preset name → chunk mapping
│       └── chunk-NNN.js         # 118 chunks (~128 presets each)
├── tools/
│   ├── fetch-extra-presets.py   # regenerates src/presets-extra/ from upstream
│   └── butterchurn-image-names.json
└── docs/
    ├── obs-setup.md
    ├── audio-routing.md
    └── local-hosting.md
```

## Quick Start

Modern browsers require a user interaction (click or keypress) before granting audio capture permissions. Please interact with the page once upon loading.

**Standalone Browser:** Open `src/fullscreen.html`. Note that some browsers restrict audio access over the `file://` protocol. If the audio device list does not populate, use a local development server.

**Local Development Server:**

```bash
npm start            # Serves ./src via `npx serve`
# Alternatively, using Python:
python3 -m http.server --directory src 8000
```

Navigate to <http://localhost:8000/fullscreen.html> or <http://localhost:8000/obs.html>.

**OBS Integration:** Refer to [`docs/obs-setup.md`](docs/obs-setup.md) for configuration instructions.

## Hosted Deployment (GitHub Pages)

The production environment is hosted via GitHub Pages at **`visualizer.1a2n.net`**:

```text
https://visualizer.1a2n.net/obs.html
https://visualizer.1a2n.net/fullscreen.html
```

The GitHub Actions workflow located at `.github/workflows/deploy.yml` automatically publishes the `src/` directory upon any push to the `develop` branch. 

To configure deployment on a fork or new clone, navigate to **Settings → Pages → Source** and select **GitHub Actions**. The site will be available at `https://<user>.github.io/<repo>/`.

Because GitHub Pages serves content over HTTPS (a secure context), browser audio capture is permitted without local workarounds. When configuring OBS, create a Browser Source in URL mode and point it to the `obs.html` URL.

## Local Hosting

The project is fully vendored and can operate offline. You may open `src/fullscreen.html` directly from the filesystem (`file://`), use a local development server, or utilize the included Docker configuration:

```bash
docker compose up -d --build
```

The application will be available at `http://localhost:8080`. Further configuration and security details are available in [`docs/local-hosting.md`](docs/local-hosting.md).

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
| <kbd>?</kbd> | Show/hide the help menu |

### OBS Panel (`obs.html`)

Utilize the on-screen graphical controls. Press <kbd>H</kbd> to toggle the visibility of the control panel.

## Audio Configuration

The application visualizes audio from a system input device (e.g., a microphone). To visualize system audio output (e.g., music playback), you must route the audio through a virtual audio cable and select that virtual device as the input. Platform-specific instructions are available in [`docs/audio-routing.md`](docs/audio-routing.md).

## Dependencies

butterchurn (`butterchurn@2.6.7`) and its presets (`butterchurn-presets@2.4.7`)
are vendored in `src/vendor/` and served from the site itself — no CDN, no
internet access needed. Four preset packs are loaded (base, Extra, Extra2,
MD1) plus the extra-images texture pack; `visualizer-core.js` merges them at
startup, skipping any preset whose name already exists in an earlier pack
(382 unique presets). To upgrade, replace the `.min.js` files with the
corresponding `lib/` builds from the npm packages. A few presets have been
intentionally curated out of the vendored packs for this deployment (see
[Curation](#curation) below), so these bundles differ slightly from the
stock npm builds.

## Extra presets (~15k)

`src/presets-extra/` holds 14,775 additional presets from
[ansorre/tens-of-thousands-milkdrop-presets-for-butterchurn](https://github.com/ansorre/tens-of-thousands-milkdrop-presets-for-butterchurn),
packed into 118 chunk files that are lazy-loaded via injected `<script>` tags
the first time one of their presets is selected (works from `file://` and
under the strict CSP; a small in-memory LRU keeps at most 16 chunks resident).
The 67 presets that duplicate a vendored pack name are skipped at startup —
vendored packs win — for 15,090 unique presets total. If the folder is
missing, the app silently falls back to the 382 vendored presets.

The folder is generated (and committed) output. To refresh it after an
upstream update:

```bash
python3 tools/fetch-extra-presets.py           # download + regenerate
python3 tools/fetch-extra-presets.py --zip P   # use an already-downloaded zip
```

The script pins the upstream commit and verifies the zip's sha256 (both
constants are at the top of the script — bump them when upstream grows), and
excludes any preset referencing custom textures that neither butterchurn nor
the vendored extra-images pack can supply, so everything shipped renders
correctly. Note that the upstream collection has **no license file**; the
presets are community-created MilkDrop content redistributed as-is.

## Curation

This deployment ships a **deliberately curated** subset of the upstream
content. Selected presets have been removed from **both** the vendored preset
packs (`src/vendor/butterchurnPresets*.min.js`) and the lazy-loaded upstream
collection (`src/presets-extra/`), with the matching rows dropped from
`preset-inventory.csv`. These deletions are an intentional editorial choice
for this deployment — they are **not** upstream or library changes, and are
not bugs to be "fixed" by restoring the presets.

Two consequences to keep in mind:

- **Regeneration re-adds them.** `tools/fetch-extra-presets.py` rebuilds
  `src/presets-extra/` verbatim from the pinned upstream zip, so it will
  reintroduce any curated-out `presets-extra` presets. After regenerating,
  the curation must be re-applied. Likewise, replacing a vendored `.min.js`
  with a stock npm build restores the presets removed from that pack.
- **The removal lists come from the app.** The `fullscreen.html` interface can
  remove the current preset from rotation and export the list of presets
  excluded during a session (the &#128683; / &#128203; controls), which is the
  source of the names curated out of the codebase here.

## License

This project is licensed under the MIT License. See [`LICENSE`](LICENSE) for details. The `butterchurn` library is also MIT-licensed. Preset authors are credited within the preset names.
