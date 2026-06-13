'use strict';
require('dotenv').config();
const path = require('path');

const ROOT = path.join(__dirname, '..');

module.exports = {
  PORT:              parseInt(process.env.PORT || '4000', 10),
  MONGO_URI:         process.env.MONGO_URI || 'mongodb://localhost:27017/fileupload',
  SIGNING_SECRET:    process.env.SIGNING_SECRET || 'dev-secret-change-in-production',
  SIGNED_URL_TTL:    parseInt(process.env.SIGNED_URL_TTL_SECONDS || '3600', 10),
  BASE_URL:          process.env.BASE_URL || 'http://localhost:4000',

  MAX_FILE_SIZE:     parseInt(process.env.MAX_FILE_SIZE_MB || '50', 10) * 1024 * 1024,
  QUOTA_BYTES:       parseInt(process.env.STORAGE_QUOTA_MB || '500', 10) * 1024 * 1024,
  RATE_LIMIT:        parseInt(process.env.UPLOAD_RATE_LIMIT_PER_HOUR || '60', 10),

  CHUNK_SIZE:        1 * 1024 * 1024, // 1 MB hint for frontend

  ORIGINALS_DIR:     path.join(ROOT, 'uploads', 'originals'),
  PROCESSED_DIR:     path.join(ROOT, 'uploads', 'processed'),
  CHUNKS_DIR:        path.join(ROOT, 'uploads', 'chunks'),
  TEMP_DIR:          path.join(ROOT, 'uploads', 'temp'),
  PUBLIC_DIR:        path.join(ROOT, 'public'),

  ALLOWED_MIME: new Set([
    'image/jpeg', 'image/png', 'image/gif',
    'image/webp', 'image/bmp', 'image/tiff',
  ]),

  MAGIC_SIGNATURES: {
    'image/jpeg': [[0xFF, 0xD8, 0xFF]],
    'image/png':  [[0x89, 0x50, 0x4E, 0x47]],
    'image/gif':  [[0x47, 0x49, 0x46, 0x38]],
    'image/webp': [[0x52, 0x49, 0x46, 0x46]], // RIFF....WEBP, checked separately
    'image/bmp':  [[0x42, 0x4D]],
    'image/tiff': [[0x49, 0x49, 0x2A, 0x00], [0x4D, 0x4D, 0x00, 0x2A]],
  },
};
