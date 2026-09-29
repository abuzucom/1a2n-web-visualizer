# Project orientation

Read `docs/repo-guide.md` before any change. It holds commands, protected
paths, architecture, and gotchas.

Never hand-edit `src/vendor/*.min.js`, `src/presets-extra/`, the
`butterchurnExtraImagesExp-part-N.js` files, `preset-inventory.csv`, or
`removed-presets.csv`. Change presets only through `tools/remove_presets.js`.
Never restore a curated-out preset.
