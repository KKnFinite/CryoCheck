const fs = require("node:fs/promises");
const path = require("node:path");
const sharp = require("sharp");

const repositoryRoot = path.resolve(__dirname, "..");
const imageDirectory = path.join(repositoryRoot, "app", "static", "img");
const approvedMasterPath = path.join(imageDirectory, "logo_blue.png");
const transparentIcons = [
  ["favicon-16x16.png", 16],
  ["favicon-32x32.png", 32],
  ["icon-180.png", 180],
  ["icon-192.png", 192],
  ["icon-512.png", 512],
  ["mstile-150x150.png", 150],
];

function createIco(images) {
  const headerSize = 6;
  const directoryEntrySize = 16;
  const directorySize = directoryEntrySize * images.length;
  const header = Buffer.alloc(headerSize + directorySize);
  header.writeUInt16LE(0, 0);
  header.writeUInt16LE(1, 2);
  header.writeUInt16LE(images.length, 4);

  let imageOffset = headerSize + directorySize;
  images.forEach(({ size, payload }, index) => {
    const entryOffset = headerSize + (index * directoryEntrySize);
    header.writeUInt8(size === 256 ? 0 : size, entryOffset);
    header.writeUInt8(size === 256 ? 0 : size, entryOffset + 1);
    header.writeUInt8(0, entryOffset + 2);
    header.writeUInt8(0, entryOffset + 3);
    header.writeUInt16LE(1, entryOffset + 4);
    header.writeUInt16LE(32, entryOffset + 6);
    header.writeUInt32LE(payload.length, entryOffset + 8);
    header.writeUInt32LE(imageOffset, entryOffset + 12);
    imageOffset += payload.length;
  });

  return Buffer.concat([header, ...images.map(({ payload }) => payload)]);
}

async function renderTransparentIcon(size) {
  return sharp(approvedMasterPath)
    .resize(size, size, {
      fit: "contain",
      position: "centre",
      withoutEnlargement: true,
    })
    .png({ compressionLevel: 9, adaptiveFiltering: true })
    .toBuffer();
}

async function generateIcons() {
  const generated = new Map();
  await Promise.all(
    transparentIcons.map(async ([filename, size]) => {
      const payload = await renderTransparentIcon(size);
      generated.set(size, payload);
      await fs.writeFile(path.join(imageDirectory, filename), payload);
    }),
  );

  const maskableArtwork = await sharp(approvedMasterPath)
    .resize(384, 384, {
      fit: "contain",
      position: "centre",
      withoutEnlargement: true,
    })
    .png({ compressionLevel: 9, adaptiveFiltering: true })
    .toBuffer();
  await sharp({
    create: {
      width: 512,
      height: 512,
      channels: 4,
      background: "#071b33",
    },
  })
    .composite([{ input: maskableArtwork, gravity: "centre" }])
    .png({ compressionLevel: 9, adaptiveFiltering: true })
    .toFile(path.join(imageDirectory, "icon-maskable-512.png"));

  const favicon = createIco(
    [16, 32].map((size) => ({ size, payload: generated.get(size) })),
  );
  await fs.writeFile(path.join(imageDirectory, "favicon.ico"), favicon);
}

generateIcons().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
