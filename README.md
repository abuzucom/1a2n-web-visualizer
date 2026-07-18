# 1a2n Visualizer

Milkdrop-style audio visualizer pages built on
[butterchurn](https://github.com/jberg/butterchurn), intended for use as an
**OBS browser source** or as a **standalone fullscreen visualizer** in any
modern browser. Ships 14,986 deduplicated presets — 381 from the four
butterchurn preset packs plus ~15k from the
[tens-of-thousands-milkdrop-presets-for-butterchurn](https://github.com/ansorre/tens-of-thousands-milkdrop-presets-for-butterchurn)
collection, lazy-loaded in chunks — fully self-hosted (no CDN).

**Production Deployment:** <https://visualizer.1a2n.net/> (`/obs.html` and `/fullscreen.html`), automatically deployed from the `develop` branch.

Both entry points share a single controller module so visualizer logic stays consistent between them:

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
├── preset-inventory.csv    # Every preset name, its pack, and chunk id
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
│   ├── fetch-extra-presets.py           # regenerates src/presets-extra/ from upstream
│   ├── fetch-extra-presets-curated.py   # same, but re-applies prior curation
│   └── butterchurn-image-names.json
└── docs/
    ├── obs-setup.md
    ├── audio-routing.md
    └── local-hosting.md
```

## Quick Start

Browsers require a click or keypress before they'll grant audio capture permission, so click or press any key once the page loads.

**Standalone Browser:** Open `src/fullscreen.html`. Some browsers restrict audio access over the `file://` protocol — if the audio device list stays empty, use a local development server instead.

**Local Development Server:**

```bash
npm start            # Serves ./src via `npx serve`
# Alternatively, using Python:
python3 -m http.server --directory src 8000
```

Open <http://localhost:8000/fullscreen.html> or <http://localhost:8000/obs.html>.

**OBS Integration:** See [`docs/obs-setup.md`](docs/obs-setup.md) for setup instructions.

## Hosted Deployment (GitHub Pages)

The production environment is hosted via GitHub Pages at **`visualizer.1a2n.net`**:

```text
https://visualizer.1a2n.net/obs.html
https://visualizer.1a2n.net/fullscreen.html
```

The GitHub Actions workflow located at `.github/workflows/deploy.yml` automatically publishes the `src/` directory upon any push to the `develop` branch. 

To deploy from a fork or new clone, go to **Settings → Pages → Source** and select **GitHub Actions**. The site will be available at `https://<user>.github.io/<repo>/`.

Because GitHub Pages serves content over HTTPS (a secure context), browser audio capture is permitted without local workarounds. When configuring OBS, create a Browser Source in URL mode and point it to the `obs.html` URL.

## Local Hosting

Three ways to run this without GitHub Pages: open `src/fullscreen.html` directly from the filesystem (`file://`), use a local development server, or run the included Docker configuration:

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

Use the on-screen graphical controls. Press <kbd>H</kbd> to toggle the control panel's visibility.

## Audio Configuration

The application visualizes audio from a system input device (e.g., a microphone). To visualize system audio output (e.g., music playback), you must route the audio through a virtual audio cable and select that virtual device as the input. Platform-specific instructions are available in [`docs/audio-routing.md`](docs/audio-routing.md).

## Dependencies

butterchurn (`butterchurn@2.6.7`) and its presets (`butterchurn-presets@2.4.7`)
are vendored in `src/vendor/` and served from the site itself — no CDN. Four
preset packs are loaded (base, Extra, Extra2,
MD1) plus the extra-images texture pack; `visualizer-core.js` merges them at
startup, skipping any preset whose name already exists in an earlier pack
(381 unique presets). To upgrade, replace the `.min.js` files with the
corresponding `lib/` builds from the npm packages. A few presets have been
intentionally curated out of the vendored packs for this deployment (see
[Curation](#curation) below), so these bundles differ slightly from the
stock npm builds.

## Extra Presets (~15k)

`src/presets-extra/` holds 14,775 additional presets from
[ansorre/tens-of-thousands-milkdrop-presets-for-butterchurn](https://github.com/ansorre/tens-of-thousands-milkdrop-presets-for-butterchurn),
packed into 118 chunk files that are lazy-loaded via injected `<script>` tags
the first time one of their presets is selected (works from `file://` and
under the strict CSP; a small in-memory LRU keeps at most 16 chunks resident).
The 67 presets that duplicate a vendored pack name are skipped at startup —
vendored packs win — for 14,986 unique presets total. If the folder is
missing, the app silently falls back to the 381 vendored presets.

The folder is generated (and committed) output. To refresh it after an
upstream update, use the curation-preserving script (see
[Curation](#curation) below for why):

```bash
python3 tools/fetch-extra-presets-curated.py           # download + regenerate, keeping curation
python3 tools/fetch-extra-presets-curated.py --zip P   # use an already-downloaded zip
python3 tools/fetch-extra-presets-curated.py --dry-run # preview the diff, write nothing
```

`tools/fetch-extra-presets.py` is the same generator without curation —
useful for a clean reset from upstream, or as the one both scripts import
their fetch/filter/write logic from. Both pin the upstream commit and verify
the zip's sha256 (constants at the top of `fetch-extra-presets.py` — bump
them when upstream grows), and exclude any preset referencing custom
textures that neither butterchurn nor the vendored extra-images pack can
supply, so everything shipped renders correctly. The upstream collection has
**no license file**; the presets are community-created MilkDrop content
redistributed as-is.

## Curation

This deployment ships a **deliberately curated** subset of the upstream
content. Selected presets have been removed from **both** the vendored preset
packs (`src/vendor/butterchurnPresets*.min.js`) and the lazy-loaded upstream
collection (`src/presets-extra/`), with the matching rows dropped from
`preset-inventory.csv`. These deletions are an intentional editorial choice
for this deployment — they are **not** upstream or library changes, and are
not bugs to be "fixed" by restoring the presets.

Two things to know if you're regenerating presets:

- **`presets-extra` regeneration is curation-safe by default.**
  `tools/fetch-extra-presets-curated.py` diffs a fresh upstream pull against
  the currently committed `index.js` and re-excludes anything that's present
  upstream but missing from the current tree — so running it preserves this
  curation instead of undoing it. Its plain counterpart,
  `tools/fetch-extra-presets.py`, has no such memory: it rebuilds
  `src/presets-extra/` verbatim from the pinned upstream zip and will
  reintroduce every curated-out preset, so only use it for a clean reset.
  Neither script touches the vendored `.min.js` packs — replacing one with a
  stock npm build restores the presets removed from that pack, and that
  curation has to be re-applied by hand.
- **The removal lists come from the app.** The `fullscreen.html` interface can
  remove the current preset from rotation and export the list of presets
  excluded during a session (the &#128683; / &#128203; controls), which is the
  source of the names curated out of the codebase here.

## License

This project is licensed under the MIT License. See [`LICENSE`](LICENSE) for details. The `butterchurn` library is also MIT-licensed. Preset authors are credited within the preset names.
