# Lucide subset for Panacea

Original SVG files from [Lucide](https://github.com/lucide-icons/lucide), pinned
at commit `dab294f313897bacaa968b725b3259fa37c17bd1`.

`manifest.json` records the official source URL and SHA-256 of each unmodified
upstream SVG and license. `LICENSE` is the complete upstream ISC license with
the additional MIT notice for Feather-derived icons.

`png/` contains 96×96 transparent renders. `rendered.json` records renderer
versions and hashes. Runtime uses their alpha channels with the Panacea palette.
The SVG renderer is a development tool, not a dependency of the application.

Regenerate offline with Node.js and Sharp 0.35.5 (librsvg 2.63.2):

```powershell
# If using an existing external Sharp installation, point NODE_PATH at its
# parent node_modules directory. No installation is needed in Codex's bundle.
node scripts/render_icons.cjs
node scripts/render_icons.cjs --check
```

Panacea's own `assets/panacea_icon.png` is used for Resurrection. It is not a
Lucide asset and is never replaced or recolored by this icon system.
