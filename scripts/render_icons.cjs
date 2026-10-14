/** Render the pinned local Lucide SVG subset; never fetch assets at runtime.
 * Requires Node.js + sharp 0.35.5 (development tool only).
 * Set NODE_PATH to an existing installation if sharp is not locally installed.
 *   node scripts/render_icons.cjs
 *   node scripts/render_icons.cjs --check
 * --check verifies sources and byte-for-byte output without changing files.
 */
'use strict';

const fs = require('node:fs/promises');
const path = require('node:path');
const crypto = require('node:crypto');
const sharp = require('sharp');

const root = path.resolve(__dirname, '../assets/icons/lucide');
const check = process.argv.includes('--check');
const sha256 = data => crypto.createHash('sha256').update(data).digest('hex');

async function main() {
  const manifest = JSON.parse(await fs.readFile(path.join(root, 'manifest.json'), 'utf8'));
  if (sharp.versions.sharp !== '0.35.5') {
    throw new Error(`Use sharp 0.35.5 for reproducible PNGs; found ${sharp.versions.sharp}`);
  }
  if (!check) await fs.mkdir(path.join(root, 'png'), {recursive: true});
  let count = 0;
  const outputs = {};
  for (const [relative, entry] of Object.entries(manifest.files)) {
    const source = await fs.readFile(path.join(root, relative));
    if (sha256(source) !== entry.sha256) {
      throw new Error(`Upstream source hash mismatch: ${relative}`);
    }
    if (!relative.endsWith('.svg')) continue;
    // 24px source at 4x density gives 96px antialiased masks for HiDPI CTkImage.
    // Keep source SVG bytes unchanged; currentColor defaults to black.
    const output = await sharp(source, {density: 288})
      .resize(96, 96)
      .ensureAlpha()
      .png({compressionLevel: 9, adaptiveFiltering: false, palette: false})
      .toBuffer();
    const target = relative.replace(/^svg\//, 'png/').replace(/\.svg$/, '.png');
    outputs[target] = sha256(output);
    if (check) {
      const current = await fs.readFile(path.join(root, target));
      if (!current.equals(output)) throw new Error(`PNG differs from source render: ${target}`);
    } else {
      await fs.writeFile(path.join(root, target), output);
    }
    count++;
  }
  const renderedManifest = {
    size: 96,
    sharp: sharp.versions.sharp,
    librsvg: sharp.versions.rsvg,
    files: outputs,
  };
  const renderedText = JSON.stringify(renderedManifest, null, 2) + '\n';
  const outputManifest = path.join(root, 'rendered.json');
  if (check) {
    if (await fs.readFile(outputManifest, 'utf8') !== renderedText) {
      throw new Error('Rendered asset manifest differs; regenerate and review the assets');
    }
  } else {
    await fs.writeFile(outputManifest, renderedText);
  }
  console.log(`${check ? 'Verified' : 'Rendered'} ${count} local Lucide icons at 96px.`);
}

main().catch(error => {
  console.error(error.message);
  process.exitCode = 1;
});
