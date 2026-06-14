'use strict';
const sharp   = require('sharp');
const path    = require('path');
const fs      = require('fs/promises');
const storage = require('../storage/LocalStorage');

const VARIANTS = [
  { name: 'thumbnail', width: 200, height: 200, fit: 'cover',   quality: 80 },
  { name: 'medium',    width: 800, height: null, fit: 'inside',  quality: 85 },
  { name: 'full',      width: null, height: null, fit: 'inside', quality: 90 },
];

/**
 * Run the full Sharp pipeline on an uploaded image:
 *   1. Read metadata (dimensions, format)
 *   2. Generate thumbnail (200×200 cover crop)
 *   3. Generate medium  (800px wide, preserve ratio)
 *   4. Generate full    (original dimensions, WebP re-encode)
 *   5. Strip EXIF for privacy (Sharp does this by default on conversion)
 *
 * All outputs are stored under processed/{hash}/ as WebP files.
 * Returns { width, height, format, variants, exif }
 */
async function processImage(originalPath, hash) {
  const img      = sharp(originalPath);
  const meta     = await img.metadata();
  const variants = {};

  const processedBase = `processed/${hash}`;

  for (const v of VARIANTS) {
    let pipeline = sharp(originalPath); // fresh clone per variant

    if (v.width || v.height) {
      pipeline = pipeline.resize(v.width, v.height, {
        fit: v.fit,
        withoutEnlargement: true,
      });
    }

    pipeline = pipeline.webp({ quality: v.quality });

    const key    = `${processedBase}/${v.name}.webp`;
    const buffer = await pipeline.toBuffer();
    await storage.put(key, buffer);

    // Expose as a server path (will be wrapped in a signed URL by the route)
    variants[v.name] = `processed/${hash}/${v.name}.webp`;
  }

  // Also track the original
  variants.original = `originals/${hash}`;

  // Extract safe EXIF fields (Sharp strips full EXIF during WebP conversion)
  const exif = {};
  if (meta.exif) {
    // We deliberately do NOT forward raw EXIF — privacy by design.
    // Only keep non-identifying technical fields.
    exif.colorSpace   = meta.space;
    exif.hasProfile   = !!meta.icc;
    exif.hasAlpha     = !!meta.hasAlpha;
    exif.density      = meta.density;
  }

  const orientation =
    meta.width === meta.height ? 'square'
    : meta.width > meta.height ? 'landscape'
    : 'portrait';

  return {
    width:  meta.width,
    height: meta.height,
    format: meta.format,
    orientation,
    variants,
    exif,
  };
}

module.exports = { processImage };
