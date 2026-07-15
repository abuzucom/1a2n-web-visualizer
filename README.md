# Butterchurn Visualizer

Milkdrop-style audio visualizer pages built on
[butterchurn](https://github.com/jberg/butterchurn), intended for use as an
**OBS browser source** or as a **standalone fullscreen visualizer** in any
modern browser. Ships 14,770 deduplicated presets — 378 from the four
butterchurn preset packs plus ~15k from the
[tens-of-thousands-milkdrop-presets-for-butterchurn](https://github.com/ansorre/tens-of-thousands-milkdrop-presets-for-butterchurn)
collection, lazy-loaded in chunks — fully self-hosted (no CDN).

**Production Deployment:** <https://visualizer.1a2n.net/> (`/obs.html` and `/fullscreen.html`), automatically deployed from the `develop` branch.

Both entry points share a single controller module so visualizer logic stays consistent between them:

- `src/obs.html`: Provides an on-screen control panel for device selection, preset management, and auto-cycle configuration. Press <kbd>H</kbd> to hide the panel for capture.
- `src/fullscreen.html`: A keyboard-controlled interface with no visible UI. The cursor is hidden during operation. Auto-cycle shuffles presets by default. This mode is optimized for window capture or secondary display usage.

## Repository Structure

```text
butterchurn-visualizer/
├── README.md
├── LICENSE
├── CHANGELOG.md
├── .gitignore
├── package.json            # Development server configuration
├── preset-inventory.csv    # Every preset name, its pack, and chunk id
├── Caddyfile               # Caddy web server configuration
├── Dockerfile              # Container definition for local hosting
├── docker-compose.yml      # Docker Compose deployment configuration
├── .dockerignore
├── .github/
│   └── workflows/
│       └── deploy.yml      # GitHub Actions deployment workflow
├── src/
│   ├── index.html          # Landing page
│   ├── obs.html            # OBS browser source entry point
│   ├── fullscreen.html     # Standalone fullscreen entry point
│   ├── css/
│   │   ├── panel.css
│   │   └── fullscreen.css
│   ├── js/
│   │   ├── visualizer-core.js   # shared BCViz controller (the brains)
│   │   ├── obs-ui.js            # panel wiring
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
│   ├── import-nestdrop-presets.py       # imports supplied .milk archives as [EXP]
│   ├── compare-experimental-presets.py  # reports EXP/mainline equivalence
│   ├── remove-experimental-duplicates.py # removes approved EXP duplicates only
│   └── butterchurn-image-names.json
└── docs/
    ├── obs-setup.md
    ├── audio-routing.md
    └── local-hosting.md
```

### Experimental NestDrop presets

The experimental import pipeline accepts supplied NestDrop ZIP archives and
converts their raw `.milk` files into the same Butterchurn preset shape used
by the mainline lazy-loaded collection. Experimental runtime names receive a
reserved `[EXP] ` prefix so they are visually distinct.

Mainline logical chunk IDs remain contiguous and low. Experimental physical
chunk files begin at `chunk-9000.js` and are referenced through the optional
`index.js` `files` mapping. The `9000+` range is a physical filename
namespace, not a logical chunk ID; developers and agents must never advance
logical IDs into that range.

`tools/compare-experimental-presets.py` compares experimental data with the
baseline mainline chunks using canonical content hashes. It reports exact
duplicates, name conflicts, and EXP-only presets. Only entries with a
confirmed mainline counterpart can be supplied to
`tools/remove-experimental-duplicates.py`; EXP-only presets are ineligible.
The `[EXP] ` prefix is removed for analysis only and remains part of runtime
and exact curation names.

#### Experimental import methodology

The import is deliberately staged so supplied archives remain data, not code:

1. Preflight records the archive digest, member counts, duplicate basenames,
   textures, and ignored members. Extraction uses a whitelist of `.milk` files
   and approved image formats; archive executables and scripts are never
   extracted or invoked. ZIP traversal and symlink-like entries are rejected.
2. Conversion runs only the repository's trusted converter in the supported
   WSL Node 22 environment. Malformed EEL and unsupported shader programs are
   recorded as conversion failures rather than blocking the batch.
3. Texture references are checked before a preset is retained. DDS-dependent
   presets and presets with unresolved texture references are skipped and
   recorded in `experimental-presets.json`; DDS data is not placed in the
   browser image bundle.
4. Preset data is canonicalized and hashed. Exact mainline matches are
   eligible for removal only through an explicit approved decision file.
   Normalized-name matches are review information only and are never removed
   automatically.
5. Source basenames are not assumed to be globally unique. Byte-identical
   collisions are retained once; distinct-content collisions receive a
   deterministic `[variant N]` suffix. The archive-relative source path and
   collision information remain in the manifest.

Generated output must be regenerated, not hand-merged. If mainline preset
generation changes, start from the updated mainline `index.js`, rerun the
experimental importer, regenerate the inventory and reports, and then run
the browser and lint checks. Every generated chunk's
`window.__bcPresetChunk(logicalId, ...)` callback must match its logical
position in `index.js`; the physical `chunk-9000.js` filename does not change
that logical ID. Keep source archives and temporary conversion logs out of Git;
retain manifests and approval/report files when provenance or curation history
requires them.

## Quick Start

Browsers require a click or keypress before they'll grant audio capture permission, so click or press any key once the page loads.

**Standalone Browser:** Open `src/fullscreen.html`. Some browsers restrict audio access over the `file://` protocol — if the audio device list stays empty, use a local development server instead.

**Local Development Server:**

```bash
npm ci                # Install the pinned development dependencies
npm start             # Serves ./src via the pinned `serve` package
# Alternatively, using Python:
python3 -m http.server --directory src 8000
```

Open <http://localhost:8000/fullscreen.html> or <http://localhost:8000/obs.html>.

**OBS Integration:** See [`docs/obs-setup.md`](docs/obs-setup.md) for setup instructions.

## Hosted Deployment (GitHub Pages)

The production environment is hosted via GitHub Pages at **`visualizer.1a2n.net`**:

```text
https://visualizer.1a2n.net/obs.html
https://visualizer.1a2n.net/fullscreen.html
```

The GitHub Actions workflow located at `.github/workflows/deploy.yml` automatically publishes the `src/` directory upon any push to the `develop` branch. 

To deploy from a fork or new clone, go to **Settings → Pages → Source** and select **GitHub Actions**. The site will be available at `https://<user>.github.io/<repo>/`.

Because GitHub Pages serves content over HTTPS (a secure context), browser audio capture is permitted without local workarounds. When configuring OBS, create a Browser Source in URL mode and point it to the `obs.html` URL.

## Local Hosting

Three ways to run this without GitHub Pages: open `src/fullscreen.html` directly from the filesystem (`file://`), use a local development server, or run the included Docker configuration:

```bash
docker compose up -d --build
```

The application will be available at `http://localhost:8080`. Further configuration and security details are available in [`docs/local-hosting.md`](docs/local-hosting.md).

## Security Model

ButterChurn dynamically compiles its audited MilkDrop preset equations, so the
Content Security Policy intentionally permits `'unsafe-eval'`. Removing this
directive breaks core visualizer functionality. Presets are vendored or
generated from a pinned, hash-verified upstream archive, reviewed as executable
content, and are not fetched from users or remote sources at runtime.

The Docker/Caddy configuration is an internal deployment option only. Docker
binds it to `127.0.0.1:8080`; it is not intended to be exposed to a network or
the public internet.

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
| <kbd>D</kbd> | Switch audio input device |
| <kbd>F</kbd> | Toggle fullscreen mode |
| <kbd>?</kbd> | Show/hide the help menu |

### OBS Panel (`obs.html`)

Use the on-screen graphical controls. Press <kbd>H</kbd> to toggle the control panel's visibility.

## Audio Configuration

The application visualizes audio from a system input device (e.g., a microphone). To visualize system audio output (e.g., music playback), you must route the audio through a virtual audio cable and select that virtual device as the input. Platform-specific instructions are available in [`docs/audio-routing.md`](docs/audio-routing.md).

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

`src/presets-extra/` holds 14,775 mainline additional presets from
[ansorre/tens-of-thousands-milkdrop-presets-for-butterchurn](https://github.com/ansorre/tens-of-thousands-milkdrop-presets-for-butterchurn),
packed into 118 chunk files that are lazy-loaded via injected `<script>` tags
the first time one of their presets is selected (works from `file://` and
under the strict CSP; a small in-memory LRU keeps at most 16 chunks resident).
The 66 presets that duplicate a vendored pack name are skipped at startup —
vendored packs win — for 14,770 unique presets total. If the folder is
missing, the app silently falls back to the 378 vendored presets.

The experimental NestDrop import adds 44,253 `[EXP] ` presets in 377 physical
files (`chunk-9000.js` through `chunk-9376.js`). They occupy logical chunk IDs
after the mainline chunks, so the combined index currently contains 561 logical
chunks. The physical filename range is only a file namespace; the loader uses
the logical ID from `index.js` when registering each chunk.

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
