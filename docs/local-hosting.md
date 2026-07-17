# Local Usage and Internal Hosting

The primary deployment uses GitHub Pages (<https://visualizer.1a2n.net/>), but
the site does not depend on it. The repository includes every library and
preset, including about 60,000 presets, so the site runs offline the same way.
Use one of three local modes:

## 1. Open directly in a browser (`file://`)

Open `src/fullscreen.html` or `src/obs.html` from a repository clone. This mode
requires neither a server nor an internet connection.

> **Caveat:** microphone access over `file://` is up to browser policy.
> Chromium-based browsers generally allow it; others may show an empty device
> list or deny permission. If that happens, use mode 2 or 3.

## 2. Local dev server

```bash
npm ci --ignore-scripts   # install the pinned development dependencies
npm start                 # serves ./src via the pinned `serve` package
# or, without Node:
python3 -m http.server --directory src 8000
```

Use `--ignore-scripts`: the `milkdrop-shader-converter` devDependency, which
the preset-curation tools use, includes a native addon. Its install script
would otherwise compile the addon against the repository's pinned Node version
and fail before the server starts. See `tools/convert-milk-presets.js` to build
the addon when needed.

Open `http://localhost:8000/fullscreen.html`. Because `localhost` is a secure
context, microphone capture works from that machine without extra configuration.

## 3. Docker + Caddy (localhost only)

For a persistent local instance, run the hardened Caddy container included in
the repository:

```bash
docker compose up -d --build
```

Open `http://localhost:8080`. The configuration binds the port to `127.0.0.1`,
so other machines cannot reach it. `localhost` is a secure context, so
microphone capture works without TLS.

### Security hardening

The compose file and Caddyfile apply the following measures:

- **Localhost binding** - `127.0.0.1:8080:80`, no network exposure.
- **Read-only filesystem** - the container cannot write to its own layers.
- **No new privileges** - blocks `setuid`/`setgid` escalation.
- **All capabilities dropped** - the container runs with zero Linux
  capabilities.
- **OWASP security headers** - Caddy sets `Content-Security-Policy`, `X-Frame-Options`,
  `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy`, and
  `Strict-Transport-Security` are set by Caddy on every response (defense
  in depth with the HTML meta CSP). Note that `Strict-Transport-Security`
  is only enforced by browsers when a response is served over HTTPS; this
  container serves plain HTTP on `localhost` by design (see top of file),
  so the header has no effect here but takes effect if this Caddyfile runs
  behind TLS termination.
- **Server fingerprint removed** - the `Server` header is stripped.
- **Asset caching** - `/vendor/*` and `/presets-extra/*` are cached for a
  day and `/js/*` plus `/css/*` for an hour, all with ETag revalidation;
  HTML stays `no-store`. Nothing is marked `immutable` because curation
  rewrites vendored packs and preset chunks in place under the same
  filenames.

### Accepted CSP exception

The application CSP allows `'unsafe-eval'` because ButterChurn dynamically
compiles the MilkDrop equations used by its presets. This is required for the
visualizer to function and is an intentional exception, not a disabled CSP.
The project vendors presets or generates them from reviewed sources. The
ansorre source is pinned and SHA-256 verified; supplied archives record their
digests. The app does not fetch presets from users or remote sources at runtime.

Use this Docker/Caddy configuration only for local hosting. Docker binds the
service to `127.0.0.1:8080`; do not expose it to a network or the public
internet.

### Notes

- The image contains only `src/` and the Caddyfile (see `.dockerignore`).
  Rebuild after pulling new commits with `docker compose up -d --build`.
- The public deployment is at <https://visualizer.1a2n.net/>. Do not expose
  this container to the internet; it provides neither authentication nor rate
  limiting.
