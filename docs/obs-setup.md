# OBS setup

## Add the visualizer as a Browser Source

1. Save/clone this repo somewhere permanent (OBS references the file by path).
2. In OBS: **Sources → + → Browser**.
3. Choose **Local file** and point it at `src/obs.html`.
   - Set **Width**/**Height** to your canvas size (e.g. 1920 × 1080).
4. Click **OK**.

> If audio access fails over a local file, run a dev server instead
> (`npm start`) and use **URL** mode pointing at
> `http://localhost:3000/obs.html` (port depends on the server).
>
> **Hosted option:** if you deployed via GitHub Pages (see the workflow in
> `.github/workflows/deploy.yml`), use **URL** mode pointing at
> `https://<user>.github.io/<repo>/obs.html`. HTTPS means audio capture works
> with no extra setup.

## Grant audio and start

1. Right-click the source → **Interact**.
2. Pick your audio input from the dropdown (see
   [audio-routing.md](audio-routing.md) to feed it music instead of a mic).
3. Click **Start visualizer**, then press <kbd>H</kbd> to hide the panel.

## Clean capture tips

- Press <kbd>H</kbd> to hide the control panel before going live.
- For the keyboard-only build, use `src/fullscreen.html` in a separate browser
  window and add a **Window Capture** instead.
- If the visualizer pauses when not visible, that is expected behavior for
  background browser sources; keep it on an active scene.

## Notes / gotchas

- The CDN scripts require internet on first load. To run offline, vendor the
  libraries locally (see the README "Dependencies" section).
- The butterchurn build is unaffiliated with OBS; no plugin install is needed —
  it is just a web page.
