# V2 icon system validation

Validated locally on 2026-10-13. This report covers the icon asset pipeline;
Windows screenshots, native DPI and packaged-app validation are separate gates.

## Implemented

- Replaced the custom Pillow-drawn glyphs in `modules/ui_icons.py` with authentic
  [Lucide](https://lucide.dev/) SVGs from the
  [official upstream revision](https://github.com/lucide-icons/lucide/tree/dab294f313897bacaa968b725b3259fa37c17bd1/icons).
- Vendored only the 11 required SVGs, their local 96px RGBA PNG renders, the
  complete upstream license, source URLs and SHA-256 manifests.
- Retained the `make_icon(name, color, size)` API, local asset resolution for
  source and PyInstaller execution, and the midnight-blue/gold palette.
- Resurrection uses `assets/panacea_icon.png`, including its original gold
  gradients and border. It is resized, never recolored or replaced by Lucide.
- Repeated icon loads are cached, file handles close immediately, and returned
  images can be modified without altering cached source art.
- `Panacea.spec` already includes the entire `assets` directory; no packaging
  path change or application dependency was needed.

| Application name | Authentic asset |
| --- | --- |
| Dashboard | `layout-dashboard.svg` |
| Cleanup | `brush-cleaning.svg` |
| Disk / drive metric | `hard-drive.svg` |
| Tools | `wrench.svg` |
| Apps | `layout-grid.svg` |
| Turbo | `zap.svg` |
| Resurrection | Original `panacea_icon.png` |
| CPU | `cpu.svg` |
| Memory | `memory-stick.svg` |
| Preview scan | `file-search.svg` |
| Restore point | `shield-plus.svg` |
| Updates | `refresh-cw.svg` |

## Capability and license checks

The project Python environment had Pillow but no CairoSVG, svglib, Qt SVG or
resvg package. The existing Codex dependency bundle contained Sharp 0.35.5 with
librsvg 2.63.2. That existing renderer was used as an offline development tool;
no package was installed and no network or SVG renderer is needed at runtime.

The vendored `assets/icons/lucide/LICENSE` is the byte-exact
[upstream license](https://github.com/lucide-icons/lucide/blob/dab294f313897bacaa968b725b3259fa37c17bd1/LICENSE):
ISC for Lucide, with the upstream MIT notice for its Feather-derived subset.
Both notices are retained in source and packaged assets. Panacea's own brand
image remains outside the Lucide license and was not modified.

`manifest.json` pins revision `dab294f313897bacaa968b725b3259fa37c17bd1`, exact
official download URLs and SHA-256 hashes. `rendered.json` records output hashes
and renderer versions. Regeneration first rejects any source hash mismatch.

## Verified

- `python -m pytest tests/test_ui_icons.py -q --basetemp build/icon-tests`:
  **76 passed**. Tests cover all icon sizes, visible transparent artwork, exact
  original chalice pixels and colors, recoloring, cache isolation, frozen asset
  resolution, source/render hashes, retained license and invalid configuration.
- `node scripts/render_icons.cjs --check` with the existing Sharp installation:
  **11 renders reproduced byte-for-byte**, including the rendered manifest.
- `python scripts/icon_contact_sheet.py`: generated
  [`v2-icons-contact.png`](v2-icons-contact.png), then visually inspected it.
  The sheet uses the same 96px source and LANCZOS downsample as CTkImage at
  20/24/30/36px, idle blue-gray and selected gold, plus 22px Dashboard actions.
- Inspection: consistent round strokes, distinct Dashboard/Apps glyphs,
  recognizable cleaning brush, hard drive, wrench and lightning, transparent
  backgrounds, no clipped artwork. The original fine-line chalice is clearest
  at 24px or above. Its source's faint edge pixels and gradients are preserved.

## Reproduction

Use Node.js with Sharp 0.35.5/librsvg 2.63.2 already available locally. Set
`NODE_PATH` to that installation's `node_modules` directory when needed.

```powershell
node scripts/render_icons.cjs
node scripts/render_icons.cjs --check
python scripts/icon_contact_sheet.py
python -m pytest tests/test_ui_icons.py -q --basetemp build/icon-tests
```

The contact sheet is an asset-rendering check, not a screenshot of the Windows
application and not evidence of effective Windows DPI settings. Full UI and
packaged EXE validation must use the application's separate GUI probes.
