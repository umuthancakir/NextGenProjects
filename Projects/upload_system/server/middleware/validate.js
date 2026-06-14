'use strict';
const fs     = require('fs/promises');
const sharp  = require('sharp');
const config = require('../config');

/**
 * Check the first N bytes of a file against known magic byte signatures.
 * File extensions can be spoofed; the file header cannot.
 */
async function checkMagicBytes(filePath, claimedMime) {
  const fd     = await fs.open(filePath, 'r');
  const header = Buffer.alloc(12);
  await fd.read(header, 0, 12, 0);
  await fd.close();

  const signatures = config.MAGIC_SIGNATURES[claimedMime];
  if (!signatures) return false;

  const match = signatures.some(sig =>
    sig.every((byte, i) => header[i] === byte)
  );

  // Extra WEBP check: bytes 8-11 must be "WEBP"
  if (claimedMime === 'image/webp' && match) {
    return header.slice(8, 12).toString('ascii') === 'WEBP';
  }

  return match;
}

/**
 * Validate image dimensions using Sharp metadata.
 * Rejects images that are too small to be useful or absurdly large.
 */
async function checkDimensions(filePath) {
  const meta = await sharp(filePath).metadata();
  const { width = 0, height = 0 } = meta;

  if (width < 10 || height < 10) {
    return { ok: false, reason: `Image too small: ${width}×${height}` };
  }
  if (width > 20000 || height > 20000) {
    return { ok: false, reason: `Image dimensions exceed limit: ${width}×${height}` };
  }
  return { ok: true };
}

/**
 * Express middleware to validate an assembled file before processing.
 * Attaches `req.fileValidation = { ok, reason }`.
 */
async function validateFile(filePath, mimeType) {
  if (!config.ALLOWED_MIME.has(mimeType)) {
    return { ok: false, reason: `MIME type not allowed: ${mimeType}` };
  }

  const magicOk = await checkMagicBytes(filePath, mimeType);
  if (!magicOk) {
    return { ok: false, reason: 'File content does not match claimed type (magic byte mismatch)' };
  }

  const dimCheck = await checkDimensions(filePath);
  if (!dimCheck.ok) return dimCheck;

  return { ok: true };
}

module.exports = { validateFile };
