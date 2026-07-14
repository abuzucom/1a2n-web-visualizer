# Butterchurn Visualizer

Milkdrop-style audio visualizer built on
[butterchurn](https://github.com/jberg/butterchurn), for **DJ set playback**:
a fullscreen, keyboard-controlled page that streams a DJ set from a
Cloudflare CDN playlist and visualizes it live. Ships 14,770 deduplicated
presets — 378 from the four butterchurn preset packs plus ~15k from the
[tens-of-thousands-milkdrop-presets-for-butterchurn](https://github.com/ansorre/tens-of-thousands-milkdrop-presets-for-butterchurn)
collection, lazy-loaded in chunks — fully self-hosted (no CDN for presets).

> **Fork direction:** this repository is a functional fork of
> `1a2n-web-visualizer`. Changes that materially alter behavior and UX to make
> the app better for DJ set playback are intentional in this codebase.
> Contributors and coding agents should not "correct" those differences back to
> upstream behavior unless maintainers explicitly request it. Notably: the
> OBS browser-source entry point and live-input-device routing have been
> removed entirely in favor of CDN-streamed track playback (see
> [`docs/audio-routing.md`](docs/audio-routing.md)), and Docker/local
> container hosting has been dropped in favor of Cloudflare Pages.
>
> **Syncing from upstream:** future changes pulled from `1a2n-web-visualizer`
> are expected to be **preset additions/removals only**. Conform to those,
> but do not reintroduce the OBS build, live-input-device audio, or Docker
> hosting if a sync/merge brings them back — see AGENTS.md's "Syncing from
> upstream" section for the full policy.

**Production Deployment:** <https://visualizer.1a2n.net/>, automatically deployed to Cloudflare Pages from the `develop` branch.

`src/fullscreen.html` is the sole entry point: a keyboard-controlled interface with no visible UI. The cursor is hidden during operation, and it plays a CDN-hosted DJ set playlist automatically on start. Auto-cycle shuffles presets by default. `src/js/visualizer-core.js` holds the shared `BCViz` controller (preset rotation, playlist playback) that `src/js/fullscreen-ui.js` wires up to the keyboard.

## Repository Structure

```text
butterchurn-visualizer/
├── README.md
├── LICENSE
├── CHANGELOG.md
├── .gitignore
├── package.json            # Development server configuration
├── preset-inventory.csv    # Every preset name, its pack, and chunk id
├── .github/
│   └── workflows/
│       └── deploy.yml      # GitHub Actions deployment workflow (Cloudflare Pages)
├── src/
│   ├── index.html          # Landing page
│   ├── fullscreen.html     # Sole entry point: fullscreen visualizer
│   ├── tracks.js           # DJ set playlist (window.BCTracks, CDN URLs)
│   ├── css/
│   │   └── fullscreen.css
│   ├── js/
│   │   ├── visualizer-core.js   # shared BCViz controller (the brains)
│   │   └── fullscreen-ui.js     # keyboard wiring
│   ├── vendor/                  # vendored butterchurn + preset/texture packs
│   │   ├── butterchurn.min.js
│   │   ├── butterchurnExtraImages.min.js
│   │   ├── butterchurnPresets.min.js
│   │   ├── butterchurnPresetsExtra.min.js
│   │   ├── butterchurnPresetsExtra2.min.js
│   │   └── butterchurnPresetsMD1.min.js
│   └── presets-extra/           # ~15k lazy-loaded presets (generated, committed)
│       ├── index.js             # preset name → chunk mapping
│       └── chunk-NNN.js         # 118 chunks (~128 presets each)
├── tools/
│   ├── fetch-extra-presets.py           # regenerates src/presets-extra/ from upstream
│   ├── fetch-extra-presets-curated.py   # same, but re-applies prior curation
│   └── butterchurn-image-names.json
└── docs/
    ├── audio-routing.md
    └── local-hosting.md
```

## Quick Start

Browsers require a click or keypress before audio can play, so click or press any key once the page loads.

**Standalone Browser:** Open `src/fullscreen.html`. It plays the playlist configured in `src/tracks.js`.

**Local Development Server:**

```bash
npm ci                # Install the pinned development dependencies
npm start             # Serves ./src via the pinned `serve` package
# Alternatively, using Python:
python3 -m http.server --directory src 8000
```

Open <http://localhost:8000/fullscreen.html>.

**Configuring tracks:** See [`docs/audio-routing.md`](docs/audio-routing.md) for the `src/tracks.js` playlist format and the CORS setup required on your Cloudflare CDN origin.

## Hosted Deployment (Cloudflare Pages)

The production environment is hosted via Cloudflare Pages at **`visualizer.1a2n.net`**:

```text
https://visualizer.1a2n.net/fullscreen.html
```

The GitHub Actions workflow located at `.github/workflows/deploy.yml` automatically publishes the `src/` directory to Cloudflare Pages upon any push to the `develop` branch.

One-time setup in GitHub:

1. Add repository secrets `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID`.
2. Optionally add repository variable `CLOUDFLARE_PAGES_PROJECT` (if omitted, the workflow uses the repository name).

One-time setup in Cloudflare Pages:

1. Create a Pages project.
2. Set its production branch to `develop`.

Cloudflare Pages serves content over HTTPS (a secure context), which is required for audio playback and the analyser graph to work reliably.

## Local Hosting

Two ways to run this locally: open `src/fullscreen.html` directly from the filesystem (`file://`), or use a local development server. See [`docs/local-hosting.md`](docs/local-hosting.md) for details. This fork does not ship a Docker/container hosting option.

## Security Model

ButterChurn dynamically compiles its audited MilkDrop preset equations, so the
Content Security Policy intentionally permits `'unsafe-eval'`. Removing this
directive breaks core visualizer functionality. Presets are vendored or
generated from a pinned, hash-verified upstream archive, reviewed as executable
content, and are not fetched from users or remote sources at runtime.

The CSP also allows `media-src` from the configured Cloudflare CDN origin
(`media.1a2n.net`) so `src/tracks.js` can stream DJ sets from it; see
[`docs/audio-routing.md`](docs/audio-routing.md) for the required CORS setup
on that origin.

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
| <kbd>A</kbd> | Previous track |
| <kbd>D</kbd> | Next track |
| <kbd>K</kbd> | Play / pause the current track |
| <kbd>F</kbd> | Toggle fullscreen mode |
| <kbd>?</kbd> | Show/hide the help menu |

## Audio Configuration

The application plays a DJ set playlist streamed from a Cloudflare CDN and visualizes that stream — no microphone or live input device, and no virtual audio cable routing, is used. Configure the playlist in `src/tracks.js` and the CDN's CORS headers as described in [`docs/audio-routing.md`](docs/audio-routing.md).

## Dependencies

butterchurn (`butterchurn@2.6.7`) and its presets (`butterchurn-presets@2.4.7`)
are vendored in `src/vendor/` and served from the site itself — no CDN. Four
preset packs are loaded (base, Extra, Extra2,
MD1) plus the extra-images texture pack; `visualizer-core.js` merges them at
startup, skipping any preset whose name already exists in an earlier pack
(378 unique presets). To upgrade, replace the `.min.js` files with the
corresponding `lib/` builds from the npm packages. A few presets have been
intentionally curated out of the vendored packs for this deployment (see
[Curation](#curation) below), so these bundles differ slightly from the
stock npm builds.

## Extra Presets (~15k)

`src/presets-extra/` holds 14,775 additional presets from
[ansorre/tens-of-thousands-milkdrop-presets-for-butterchurn](https://github.com/ansorre/tens-of-thousands-milkdrop-presets-for-butterchurn),
packed into 118 chunk files that are lazy-loaded via injected `<script>` tags
the first time one of their presets is selected (works from `file://` and
under the strict CSP; a small in-memory LRU keeps at most 16 chunks resident).
The 66 presets that duplicate a vendored pack name are skipped at startup —
vendored packs win — for 14,770 unique presets total. If the folder is
missing, the app silently falls back to the 378 vendored presets.

The folder is generated (and committed) output. To refresh it after an
upstream update, use the curation-preserving script (see
[Curation](#curation) below for why):

```bash
python3 tools/fetch-extra-presets-curated.py           # download + regenerate, keeping curation
python3 tools/fetch-extra-presets-curated.py --zip P   # use an already-downloaded zip
python3 tools/fetch-extra-presets-curated.py --dry-run # preview the diff, write nothing
```

`tools/fetch-extra-presets.py` is the same generator without curation —
useful for a clean reset from upstream, or as the one both scripts import
their fetch/filter/write logic from. Both pin the upstream commit and verify
the zip's sha256 (constants at the top of `fetch-extra-presets.py` — bump
them when upstream grows), and exclude any preset referencing custom
textures that neither butterchurn nor the vendored extra-images pack can
supply, so everything shipped renders correctly. The upstream collection has
**no license file**; the presets are community-created MilkDrop content
redistributed as-is.

## Curation

This deployment ships a **deliberately curated** subset of the upstream
content. Selected presets have been removed from **both** the vendored preset
packs (`src/vendor/butterchurnPresets*.min.js`) and the lazy-loaded upstream
collection (`src/presets-extra/`), with the matching rows dropped from
`preset-inventory.csv` and recorded in `removed-presets.csv`. These deletions
are an intentional editorial choice for this deployment — they are **not**
upstream or library changes, and are not bugs to be "fixed" by restoring the
presets.

`removed-presets.csv` is the durable "never re-add this" ledger: every name
ever curated out of this repo, with its pack, chunk, and (when known) the
commit/date/subject that removed it. Like `preset-inventory.csv`, it's a
generated bookkeeping record, not the source of truth the app reads from —
only `tools/remove_presets.js` should ever write to it.

Three things to know if you're regenerating presets:

- **`presets-extra` regeneration is curation-safe by default.**
  `tools/fetch-extra-presets-curated.py` diffs a fresh upstream pull against
  the currently committed `index.js` *and* against `removed-presets.csv`,
  excluding anything caught by either check — so running it preserves this
  curation instead of undoing it. Its plain counterpart,
  `tools/fetch-extra-presets.py`, has no such memory: it rebuilds
  `src/presets-extra/` verbatim from the pinned upstream zip and will
  reintroduce every curated-out preset, so only use it for a clean reset.
  Neither script touches the vendored `.min.js` packs — replacing one with a
  stock npm build restores the presets removed from that pack, and that
  curation has to be re-applied by hand.
- **The removal lists come from the app.** The `fullscreen.html` interface can
  remove the current preset from rotation and export the list of presets
  excluded during a session (the &#128683; / &#128203; controls), which is the
  source of the names curated out of the codebase here.
- **New upstream sources should consult `removed-presets.csv` too.** A fetch
  script pulling presets from a different collection should exclude names
  present in the ledger, the same way `fetch-extra-presets-curated.py` does —
  not just names absent from the current `index.js` snapshot, since a
  different source could coincidentally share a name with something removed
  from an entirely different collection.

### Removing presets

`tools/remove_presets.js` performs an actual curation removal: given a list of
exact preset names, it drops each one from `src/presets-extra/index.js`, its
owning `chunk-NNN.js` file, any vendored `.min.js` pack that contains it, and
the matching `preset-inventory.csv` row, and appends a row for each to
`removed-presets.csv` — the same mechanical steps described above, without
reconstructing them by hand each time. Matching is exact-name only, and
nothing is written unless every requested name is found and every edited file
passes a post-edit consistency check.

```bash
node tools/remove_presets.js --names-file names.txt   # one exact name per line
node tools/remove_presets.js --name "Foo" --name "Bar"
node tools/remove_presets.js --names-file names.txt --dry-run
```

It does not update the preset counts documented in this README/CHANGELOG —
recompute those by hand after a removal (see the numbers in the "Extra
Presets" section above for the formula).

`tools/analyze_curation_history.js` reconstructs the full history of presets
curated out via `git log` — auto-discovering every commit that ever touched
`src/presets-extra/` or `src/vendor/*.min.js`, so it stays correct across
history rewrites instead of relying on a hand-maintained commit list — and
prints neutral frequency statistics (top words, bigrams, and likely
contributor-name prefixes) over their names. It has no built-in notion of
what's "risky" or unwanted, just the raw data, so anyone using this repo can
review the same history and make their own curation decisions. This is also
the tool that originally generated `removed-presets.csv`'s `--csv` output;
`tools/remove_presets.js` keeps it current from here on, so you shouldn't
normally need to regenerate it:

```bash
node tools/analyze_curation_history.js
node tools/analyze_curation_history.js --csv history.csv   # also write the full table
```

## License

This project is licensed under the MIT License. See [`LICENSE`](LICENSE) for details. The `butterchurn` library is also MIT-licensed. Preset authors are credited within the preset names.
