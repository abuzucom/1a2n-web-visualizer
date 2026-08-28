# OBS setup

## Add the visualizer as a Browser Source

1. Save/clone this repo somewhere permanent (OBS references the file by path).
2. In OBS: **Sources -> + -> Browser**.
3. Choose **Local file** and point it at `src/obs.html`.
   - Set **Width**/**Height** to your canvas size (e.g. 1920 x 1080).
4. Click **OK**.

> If audio access fails over a local file, run a dev server instead
> (`npm start`) and use **URL** mode pointing at
> `http://localhost:3000/obs.html` (port depends on the server).
>
> **Hosted option (simplest):** use **URL** mode pointing at the production
> deployment, `https://visualizer.1a2n.net/obs.html`. HTTPS means audio
> capture works with no extra setup.
>
> **Internal option:** if you run the Docker + Caddy container (see
> [local-hosting.md](local-hosting.md)) on the same machine as OBS, point
> **URL** mode at `http://localhost:8080/obs.html` instead; the container
> only binds to `localhost`, so this doesn't work from a different machine.

## Grant audio and start

1. Right-click the source -> **Interact**.
2. Pick your audio input from the dropdown (see
   [audio-routing.md](audio-routing.md) to feed it music instead of a mic).
3. Click **Start visualizer**, then press <kbd>H</kbd> to hide the panel.

## Clean capture tips

- Press <kbd>H</kbd> to hide the control panel before going live.
- For the keyboard-only build, use `src/fullscreen.html` in a separate browser
  window and add a **Window Capture** instead.
- The visualizer keeps rendering on an inactive scene, so it no longer has to
  stay on an active one. Uncheck "Shutdown source when not visible" and "Refresh
  browser when scene becomes active" in the source properties, or OBS tears the
  page down on a scene change regardless. See
  [background-rendering.md](background-rendering.md).
- For an unattended stream, arm the audio guard once the set is running. See
  [unattended-operation.md](unattended-operation.md).

## Notes / gotchas

- Runs fully offline from a local clone; see [local-hosting.md](local-hosting.md)
  for how the vendoring works.
- The butterchurn build is unaffiliated with OBS; no plugin install is needed -
  it is just a web page.
