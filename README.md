# Butterchurn Visualizer

Milkdrop-style audio visualizer pages built on [butterchurn](https://github.com/jberg/butterchurn). This project is designed for use as an **OBS browser source** or as a **standalone fullscreen visualizer** in any modern web browser. It includes 395 deduplicated presets from four preset packs and is fully self-hosted without reliance on external Content Delivery Networks (CDNs).

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
│   │   ├── visualizer-core.js   # Shared visualizer controller logic
│   │   ├── obs-ui.js            # OBS interface event bindings
│   │   └── fullscreen-ui.js     # Fullscreen keyboard event bindings
│   └── vendor/                  # Vendored dependencies and presets
│       ├── butterchurn.min.js
│       ├── butterchurnExtraImages.min.js
│       ├── butterchurnPresets.min.js
│       ├── butterchurnPresetsExtra.min.js
│       ├── butterchurnPresetsExtra2.min.js
│       └── butterchurnPresetsMD1.min.js
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

The `butterchurn` library (v2.6.7) and associated presets (v2.4.7) are vendored within the `src/vendor/` directory. The application does not require a CDN or internet access to function.

Four preset packs are included (Base, Extra, Extra2, MD1) alongside the `extra-images` texture pack. `visualizer-core.js` merges these packs at initialization and deduplicates them based on preset name, yielding 395 unique presets.

To update these dependencies, replace the `.min.js` files with the corresponding compiled `lib/` artifacts from the upstream npm packages.

## License

This project is licensed under the MIT License. See [`LICENSE`](LICENSE) for details. The `butterchurn` library is also MIT-licensed. Preset authors are credited within the preset names.
