# Butterchurn Visualizer

Milkdrop-style audio visualizer pages built on
[butterchurn](https://github.com/jberg/butterchurn), intended for use as an
**OBS browser source** or as a **standalone fullscreen visualizer** in any
modern browser.

Two entry points share a single controller module, so visualizer logic lives in
one place:

- `src/obs.html` — has an on-screen control panel (device picker, preset picker,
  auto-cycle). Press <kbd>H</kbd> to hide the panel for capture.
- `src/fullscreen.html` — no visible UI; keyboard-only controls, hidden cursor.
  Cleaner to window-capture or run on a second display.

## Repository layout

```
butterchurn-visualizer/
├── README.md
├── LICENSE
├── CHANGELOG.md
├── .gitignore
├── package.json            # optional local dev server
├── .github/
│   └── workflows/
│       └── deploy.yml      # auto-deploy src/ to GitHub Pages
├── src/
│   ├── index.html          # web landing page
│   ├── obs.html            # OBS browser-source entry point
│   ├── fullscreen.html     # standalone fullscreen entry point
│   ├── css/
│   │   ├── panel.css
│   │   └── fullscreen.css
│   └── js/
│       ├── visualizer-core.js   # shared BCViz controller (the brains)
│       ├── obs-ui.js            # panel wiring
│       └── fullscreen-ui.js     # keyboard wiring
└── docs/
    ├── obs-setup.md
    └── audio-routing.md
```

## Quick start

A user gesture (click or keypress) is required before the browser will grant
audio access, so just open a page and click once.

**Standalone browser:** open `src/fullscreen.html`. If the audio device list
stays empty (some browsers block audio access over `file://`), serve it over
localhost instead — see below.

**Local dev server (recommended):**

```bash
npm start            # serves ./src via `npx serve`
# or, without Node:
python3 -m http.server --directory src 8000
```

Then open <http://localhost:8000/fullscreen.html> or `/obs.html`.

**OBS:** see [`docs/obs-setup.md`](docs/obs-setup.md).

## Hosted (GitHub Pages)

A workflow at `.github/workflows/deploy.yml` publishes `src/` to GitHub Pages on
every push to `develop`. One-time setup: in the repo go to **Settings → Pages**
and set **Source** to **GitHub Actions**. After the first deploy your pages are
at:

```
https://<user>.github.io/<repo>/obs.html
https://<user>.github.io/<repo>/fullscreen.html
```

Because Pages serves over HTTPS (a secure context), audio capture works directly
— no `localhost` workaround needed. In OBS, use a Browser Source in **URL** mode
pointing at the `obs.html` link above.

## Controls

### Fullscreen (`fullscreen.html`)

| Key | Action |
| --- | --- |
| <kbd>Space</kbd> / <kbd>N</kbd> | Next preset |
| <kbd>P</kbd> | Previous preset |
| <kbd>R</kbd> | Random preset |
| <kbd>C</kbd> | Toggle auto-cycle |
| <kbd>[</kbd> / <kbd>]</kbd> | Cycle interval − / + |
| <kbd>D</kbd> | Switch audio input |
| <kbd>F</kbd> | Toggle fullscreen |
| <kbd>?</kbd> | Show/hide help |

### OBS panel (`obs.html`)

Use the on-screen controls; press <kbd>H</kbd> to hide the panel.

## Audio

The page can only "hear" an **audio input device**. To visualize music rather
than your microphone, route audio through a virtual cable and select that device
(press <kbd>D</kbd> in fullscreen, or use the dropdown in the panel). Full
instructions per platform are in [`docs/audio-routing.md`](docs/audio-routing.md).

## Dependencies

butterchurn (`butterchurn@2.6.7`) and its presets (`butterchurn-presets@2.4.7`)
are vendored in `src/vendor/` and served from the site itself — no CDN, no
internet access needed. Four preset packs are loaded (base, Extra, Extra2,
MD1) plus the extra-images texture pack; `visualizer-core.js` merges them at
startup, skipping any preset whose name already exists in an earlier pack
(395 unique presets total). To upgrade, replace the `.min.js` files with the
corresponding `lib/` builds from the npm packages.

## License

MIT — see [`LICENSE`](LICENSE). butterchurn is also MIT-licensed; preset authors
are credited within the preset names.
