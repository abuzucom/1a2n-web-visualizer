# Security Policy

This is a static, no-backend visualizer: a browser page, a bundle of vendored
libraries and preset content, and an optional self-hosted Docker/Caddy
deployment. There is no server-side application logic, no database, and no
user accounts. Most of what would be a "security model" for a typical web
app does not apply here; what remains is documented below.

## Reporting a vulnerability

Report privately through GitHub's
[Security Advisories](https://github.com/abuzucom/1a2n-web-visualizer/security/advisories/new)
("Report a vulnerability" on the repository's Security tab). Do not open a
public issue or pull request for a suspected vulnerability before it has
been triaged.

Include what you found, the affected file(s) or URL, reproduction steps, and
the impact you believe it has. You should get an acknowledgment within a few
days. A fix timeline depends on severity; you'll be kept updated on the
advisory thread.

If you believe GitHub's private reporting is not available for this
repository, note that in an issue without describing the vulnerability
itself, and a maintainer will follow up with an alternative channel.

## Scope

**In scope:**

- XSS, CSP bypass, or other client-side injection in `src/*.html` or
  `src/js/**`.
- Anything that lets untrusted preset content execute code outside the
  audited MilkDrop-equation compilation path (see "Accepted risks" below for
  what is intentional here).
- Supply-chain issues in vendored bundles (`src/vendor/*.min.js`) or in the
  build/CI pipeline (`.github/workflows/**`, `scripts/**`, `tools/**`),
  including anything that could let a malicious dependency or GitHub Action
  run with repo-write access.
- Misconfiguration in the Docker/Caddy self-hosting path
  (`Dockerfile`, `docker-compose.yml`, `Caddyfile`) that weakens its
  documented localhost-only posture.
- Anything that could let a pull request bypass
  [protected-file review](docs/protected-file-review.md) or land unreviewed
  changes to protected files.

**Out of scope:**

- Reports about the content or quality of individual MilkDrop presets
  (visual glitches, GPU load, artistic disagreement). Presets are reviewed
  as executable content before being shipped; see "Accepted risks."
  Preset removal requests are a curation matter, not a security report; use
  a regular issue.
- Denial of service against your own local instance (e.g. a pathological
  preset causing a slow frame) unless it demonstrates a real vulnerability
  (e.g. a way to execute arbitrary code, not just render badly).
- Findings that require physical access to a machine already running the
  visualizer, or that assume the operator has ignored this document's
  deployment guidance (e.g. exposing the Docker port beyond `127.0.0.1`).
- Vulnerabilities in GitHub Pages, Docker, Caddy, or Node/npm/Python
  themselves; report those upstream.

## Supported versions

This project does not maintain multiple release branches. Only the code
currently on `develop` (what GitHub Pages deploys, and what
`docker compose up -d --build` builds from `HEAD` of your checkout) is
supported. There is no backport policy for older tags.

## Accepted risks

A few things look like findings but are deliberate, documented trade-offs:

- **`script-src` includes `'unsafe-eval'`.** ButterChurn dynamically compiles
  MilkDrop preset equations at runtime; this directive cannot be removed
  without breaking the visualizer. All shipped presets are reviewed as
  executable content before being added, and the app never fetches preset
  content from a remote source at runtime. See README's
  [Security Model](README.md#security-model) section.
- **The Docker deployment binds to `127.0.0.1:8080` only.** It is documented
  as internal-only; exposing it beyond localhost is an operator
  misconfiguration, not a vulnerability in the default config.
- **`src/vendor/*.min.js` is vendored, not fetched from a CDN at runtime**,
  specifically to avoid a third-party supply-chain compromise affecting
  deployed instances directly; updates go through the normal PR and
  protected-file review process instead.

## Security measures already in place

Documented in more detail elsewhere, linked here rather than duplicated:

- README's [Security Model](README.md#security-model) section: CSP
  rationale, preset integrity verification (SHA-256 pinning, commit-pinned
  sources), CI checks, and the checker scripts backing them.
- [`docs/protected-file-review.md`](docs/protected-file-review.md):
  code-owner approval requirements for agent instructions, automation,
  dependencies, deployment config, and runtime code.
- `AGENTS.md`: the rules governing how changes (including AI-agent-authored
  ones) are made to this repo, including no untrusted input in
  queries/commands/code, no secrets in version control, no weak hashing in
  security-sensitive contexts, pinned GitHub Actions with
  `persist-credentials: false`, and non-root containers by default.
- Dependabot (`.github/dependabot.yml`) for npm and GitHub Actions
  dependency updates.

## Disclosure policy

Coordinated disclosure: please give a reasonable window to investigate and
ship a fix before any public disclosure. Credit is offered by default in the
published advisory unless you ask to stay anonymous.
