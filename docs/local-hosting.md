# Local usage & internal hosting

The primary deployment is Cloudflare Pages (<https://visualizer.1a2n.net/>), but
nothing here depends on it — every library and preset (including the ~15k
extra presets) is committed in the repo, so the site runs the same way
offline. Two local modes, from simplest to most capable:

This repo is a functional fork of `1a2n-web-visualizer`; changes that make it
more suitable for DJ set playback are intentional and should not be treated as
accidental drift from upstream. This fork does not ship a Docker/container
hosting option — it is deployed via Cloudflare Pages or run locally with the
modes below.

## 1. Open directly in a browser (`file://`)

Just open `src/fullscreen.html` from a clone of this repo. No server, no
internet. Audio is streamed from the CDN playlist in `src/tracks.js`
(see [`audio-routing.md`](audio-routing.md)), so no local audio permissions
are involved.

## 2. Local dev server

```bash
npm ci --ignore-scripts   # install the pinned development dependencies
npm start                 # serves ./src via the pinned `serve` package
# or, without Node:
python3 -m http.server --directory src 8000
```

`--ignore-scripts` is required here, not optional: one devDependency
(`milkdrop-shader-converter`, used only by the preset-curation tools in
`tools/`) ships a native addon whose own install script would otherwise try
to compile against this repo's pinned Node version and fail before serving
the app needs anything from it. See `tools/convert-milk-presets.js`'s header
comment if you actually need that addon built.

Open `http://localhost:8000/fullscreen.html`.

### Accepted CSP exception

The application CSP includes `'unsafe-eval'` because ButterChurn dynamically
compiles the MilkDrop equations used by its presets. This is required for the
visualizer to function and is an intentional exception, not a disabled CSP.
Presets are vendored or generated from a pinned, SHA-256-verified upstream
archive and reviewed as executable content; they are not fetched from users or
remote sources at runtime.
