# Local usage & internal hosting

The primary deployment is GitHub Pages (<https://visualizer.1a2n.net/>), but
the site is fully self-contained — every library and preset pack is vendored
in `src/vendor/` — so it also runs entirely offline. Three local modes, from
simplest to most capable:

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

## 3. Internal hosting with Docker + Caddy

For a persistent, LAN-reachable instance (e.g. an OBS machine pointing at a
small server), the repo ships a Caddy-based container:

```bash
docker compose up -d --build
```

This serves the site two ways:

| URL | Transport | Mic capture works from |
| --- | --- | --- |
| `http://<host>:8080` | plain HTTP | the Docker host only (via `http://localhost:8080`) |
| `https://<host>:8443` | HTTPS, Caddy internal CA | any machine on the network |

The HTTPS listener exists because browsers only allow microphone capture in a
**secure context** — HTTPS or `localhost`. Plain HTTP from another machine
loads the page fine but gets no audio.

### The self-signed certificate

Caddy generates its own internal certificate authority (`local_certs`) on
first start; the compose file persists it in the `caddy_data` volume so the
CA survives container rebuilds.

**Prefer connecting by hostname** (`https://myserver.lan:8443`, mDNS name,
etc.): the config uses on-demand issuance, so Caddy mints a certificate
matching whatever name you connect with. Connecting by raw IP works too, but
serves a fallback certificate whose name won't match, so you'll always get a
warning even after trusting the CA.

Clients have two options:

- **Click through the browser warning** once per client — fine for casual use.
- **Trust the CA properly** (no warnings, needed for some locked-down
  browsers): export the root certificate and import it into the client's
  trust store:

  ```bash
  docker compose exec visualizer cat /data/caddy/pki/authorities/local/root.crt > caddy-root.crt
  ```

  Then install `caddy-root.crt` as a trusted root CA on each client
  (Windows: certmgr; macOS: Keychain Access; Linux: `update-ca-certificates`;
  or import it in the browser's own certificate settings).

### Notes

- The container is intended for **internal use only** — nothing in the config
  does auth or rate limiting. Don't port-forward it to the internet; the
  public deployment already exists for that.
- The image contains only `src/` and the Caddyfile (see `.dockerignore`);
  rebuilding after pulling new commits is just `docker compose up -d --build`.
- OBS on another machine: use a Browser Source in URL mode pointing at
  `https://<host>:8443/obs.html` (trust the CA on that machine first).
