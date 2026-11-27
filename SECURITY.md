# Security Policy

This is a static, no-backend visualizer. It consists of a browser page, a
bundle of vendored libraries and preset content, and an optional self-hosted
Docker/Caddy deployment. There is no server-side application logic, no
database, and no user accounts. Most of a typical web app security model
does not apply here. This document covers the remaining parts.

## Reporting a vulnerability

Report privately through GitHub's
[Security Advisories](https://github.com/abuzucom/1a2n-web-visualizer/security/advisories/new)
("Report a vulnerability" on the repository's Security tab). Do not open a
public issue or pull request for a suspected vulnerability before a
maintainer triages it.

Include the finding, the affected file(s) or URL, reproduction steps, and the
expected impact. A maintainer acknowledges each report within a few days.
The fix timeline depends on severity. The advisory thread carries every
update.

When GitHub's private reporting is unavailable for this repository, open an
issue that states only that fact. Leave the vulnerability details out. A
maintainer then follows up with an alternative channel.

## Scope

**In scope:**

- XSS, CSP bypass, or other client-side injection in `src/*.html` or
  `src/js/**`.
- Anything that lets untrusted preset content execute code outside the
  audited MilkDrop-equation compilation path. "Accepted risks" below
  describes the intended behavior.
- Supply-chain issues in vendored bundles (`src/vendor/*.min.js`) or in the
  build/CI pipeline (`.github/workflows/**`, `scripts/**`, `tools/**`). This
  includes any path for a malicious dependency or GitHub Action to run with
  repo-write access.
- Misconfiguration in the Docker/Caddy self-hosting path
  (`Dockerfile`, `docker-compose.yml`, `Caddyfile`) that weakens its
  documented localhost-only posture.
- Anything that could let a pull request bypass
  [protected-file review](docs/protected-file-review.md) or land unreviewed
  changes to protected files.

**Out of scope:**

- Reports about the content or quality of individual MilkDrop presets
  (visual glitches, GPU load, artistic disagreement). Maintainers review
  every preset as executable content before it ships. See "Accepted risks."
  Preset removal requests belong in a regular issue as a curation matter.
- Denial of service against a local instance, such as a pathological preset
  that slows a frame. A report qualifies only when it demonstrates a real
  vulnerability, such as arbitrary code execution.
- Findings that require physical access to a machine already running the
  visualizer. The same applies to findings that assume an operator ignored
  this document's deployment guidance, such as exposing the Docker port
  beyond `127.0.0.1`.
- Vulnerabilities in the Vercel, Docker, Caddy, Node, npm, or Python
  projects. Report those upstream.

## Supported versions

This project does not maintain multiple release branches. Support covers only
the code currently on `main` and on `develop`. The Vercel production
environment deploys `main`. The Vercel staging environment deploys `develop`.
`docker compose up -d --build` builds from `HEAD` of the local checkout.
There is no backport policy for older tags.

## Accepted risks

A few items look like findings. Each one is a documented trade-off:

- **`script-src` includes `'unsafe-eval'`.** ButterChurn compiles MilkDrop
  preset equations at runtime. The visualizer stops working without this
  directive. Maintainers review every shipped preset as executable content
  before adding it. The app never fetches preset content from a remote
  source at runtime. See README's
  [Security Model](README.md#security-model) section.
- **The Docker deployment binds to `127.0.0.1:8080` only.** The
  documentation describes it as internal-only. Exposing it beyond localhost
  is an operator misconfiguration. The default config carries no such
  vulnerability.
- **`src/vendor/*.min.js` ships vendored instead of from a CDN at
  runtime.** Vendoring keeps a third-party supply-chain compromise from
  reaching deployed instances directly. Updates go through the normal PR and
  protected-file review process.

## Security measures already in place

Other documents describe these measures in more detail:

- README's [Security Model](README.md#security-model) section covers the CSP
  rationale, preset integrity verification (SHA-256 pinning, commit-pinned
  sources), CI checks, and the checker scripts that back the checks.
- [`docs/protected-file-review.md`](docs/protected-file-review.md) covers
  code-owner approval requirements for agent instructions, automation,
  dependencies, deployment config, and runtime code.
- `AGENTS.md` holds the rules for every change to this repo, including
  changes from AI agents. The rules cover untrusted input in
  queries/commands/code, secrets in version control, weak hashing in
  security-sensitive contexts, pinned GitHub Actions with
  `persist-credentials: false`, and non-root containers by default.
- Dependabot (`.github/dependabot.yml`) proposes npm and GitHub Actions
  dependency updates.

## Disclosure policy

This project follows coordinated disclosure. Allow a reasonable window to
investigate and ship a fix before any public disclosure. The published
advisory credits the reporter by default. A reporter can ask to stay
anonymous.
