const fs = require("node:fs/promises");
const path = require("node:path");
const sharp = require("sharp");

const repositoryRoot = path.resolve(__dirname, "..");
const imageDirectory = path.join(repositoryRoot, "app", "static", "img");
const faviconPath = path.join(imageDirectory, "favicon.svg");
const sizes = [180, 192, 512];

async function generateIcons() {
  const favicon = await fs.readFile(faviconPath);
  await Promise.all(
    sizes.map((size) => (
      sharp(favicon)
        .resize(size, size)
        .png({ compressionLevel: 9 })
        .toFile(path.join(imageDirectory, `icon-${size}.png`))
    )),
  );

  const maskableSvg = Buffer.from(`
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
      <defs>
        <linearGradient id="ice" x1="4" y1="0" x2="60" y2="64"
          gradientUnits="userSpaceOnUse">
          <stop offset="0" stop-color="#2b91c2"/>
          <stop offset="1" stop-color="#071b33"/>
        </linearGradient>
      </defs>
      <rect width="64" height="64" fill="url(#ice)"/>
      <g transform="translate(8 8) scale(.75)" fill="none" stroke="#ffffff"
        stroke-width="4" stroke-linecap="round" stroke-linejoin="round">
        <path d="M32 12v40M14.7 22l34.6 20M14.7 42l34.6-20"/>
        <path d="m25 17 7 6 7-6M25 47l7-6 7 6"/>
        <path d="m18.6 29.5 9.1-1.6-3.1-8.7
          M45.4 44.8l-9.1-1.6 3.1-8.7"/>
        <path d="m18.6 34.5 9.1 1.6-3.1 8.7
          M45.4 19.2l-9.1 1.6 3.1-8.7"/>
      </g>
    </svg>
  `);
  await sharp(maskableSvg)
    .resize(512, 512)
    .png({ compressionLevel: 9 })
    .toFile(path.join(imageDirectory, "icon-maskable-512.png"));
}

generateIcons().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
