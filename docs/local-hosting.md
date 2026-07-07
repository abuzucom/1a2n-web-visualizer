# Local usage & internal hosting

The primary deployment is GitHub Pages (<https://visualizer.1a2n.net/>), but
nothing here depends on it — every library and preset (including the ~15k
extra presets) is committed in the repo, so the site runs the same way
offline. Three local modes, from simplest to most capable:

## 1. Open directly in a browser (`file://`)

Just open `src/fullscreen.html` or `src/obs.html` from a clone of this repo.
No server, no internet.

> **Caveat:** microphone access over `file://` is up to browser policy.
> Chromium-based browsers generally allow it; others may show an empty device
> list or deny permission. If that happens, use mode 2 or 3.

## 2. Local dev server

```bash
npm start            # serves ./src via `npx serve`
# or, without Node:
python3 -m http.server --directory src 8000
```

Open `http://localhost:8000/fullscreen.html`. `localhost` counts as a secure
context, so mic capture always works — but only from the same machine.

## 3. Docker + Caddy (localhost only)

For a persistent local instance, the repo ships a hardened Caddy container:

```bash
docker compose up -d --build
```

Open `http://localhost:8080`. The port is bound to `127.0.0.1` only — it is
not reachable from other machines on the network. `localhost` is a secure
context, so microphone capture works without TLS.

### Security hardening

The compose file and Caddyfile apply the following measures:

- **Localhost binding** — `127.0.0.1:8080:80`, no network exposure.
- **Read-only filesystem** — the container cannot write to its own layers.
- **No new privileges** — blocks `setuid`/`setgid` escalation.
- **All capabilities dropped** — the container runs with zero Linux
  capabilities.
- **OWASP security headers** — `Content-Security-Policy`, `X-Frame-Options`,
  `X-Content-Type-Options`, `Referrer-Policy`, and `Permissions-Policy` are
  set by Caddy on every response (defense in depth with the HTML meta CSP).
- **Server fingerprint removed** — the `Server` header is stripped.

### Notes

- The image contains only `src/` and the Caddyfile (see `.dockerignore`);
  rebuilding after pulling new commits is just `docker compose up -d --build`.
- The public deployment is at <https://visualizer.1a2n.net/>. Do not expose
  this container to the internet — it has no authentication or rate limiting.
