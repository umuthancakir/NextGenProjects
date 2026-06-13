'use strict';
const express      = require('express');
const multer       = require('multer');
const path         = require('path');
const fs           = require('fs/promises');
const { v4: uuid } = require('uuid');

const config               = require('../config');
const ChunkSession         = require('../models/ChunkSession');
const File                 = require('../models/File');
const storage              = require('../storage/LocalStorage');
const { hashFile }         = require('../services/hasher');
const { processImage }     = require('../services/imageProcessor');
const { analyzeImage }     = require('../services/tagger');
const { validateFile }     = require('../middleware/validate');
const { uploadRateLimit, checkQuota } = require('../middleware/rateLimiter');
const ws                   = require('../ws');

const router = express.Router();

// multer stores chunks in memory (max 2MB per chunk)
const upload = multer({
  storage: multer.memoryStorage(),
  limits:  { fileSize: 2 * 1024 * 1024 },
});

// ── 1. Init upload session ─────────────────────────────────────────────────
router.post('/init', uploadRateLimit, async (req, res) => {
  const { fileName, totalChunks, mimeType } = req.body;

  if (!fileName || !totalChunks || !mimeType) {
    return res.status(400).json({ error: 'fileName, totalChunks and mimeType are required' });
  }
  if (!config.ALLOWED_MIME.has(mimeType)) {
    return res.status(415).json({ error: `MIME type not allowed: ${mimeType}` });
  }

  const uploadId = uuid();
  const uploader = req.headers['x-user-id'] || 'anonymous';

  await ChunkSession.create({
    uploadId,
    totalChunks: parseInt(totalChunks, 10),
    originalName: fileName,
    mimeType,
    uploader,
  });

  await fs.mkdir(path.join(config.CHUNKS_DIR, uploadId), { recursive: true });

  res.json({ uploadId, chunkSize: config.CHUNK_SIZE });
});

// ── 2. Upload individual chunk ─────────────────────────────────────────────
router.post('/chunk', upload.single('chunk'), async (req, res) => {
  const { uploadId, chunkIndex } = req.body;
  if (!uploadId || chunkIndex === undefined || !req.file) {
    return res.status(400).json({ error: 'uploadId, chunkIndex and chunk data required' });
  }

  const session = await ChunkSession.findOne({ uploadId });
  if (!session) return res.status(404).json({ error: 'Upload session not found' });

  const idx       = parseInt(chunkIndex, 10);
  const chunkFile = path.join(config.CHUNKS_DIR, uploadId, `chunk_${String(idx).padStart(6, '0')}`);
  await fs.writeFile(chunkFile, req.file.buffer);

  await ChunkSession.updateOne({ uploadId }, { $addToSet: { receivedChunks: idx } });

  const received = session.receivedChunks.length + 1; // +1 optimistically
  const percent  = Math.round((received / session.totalChunks) * 30); // 0-30% for chunk phase

  ws.notify(uploadId, {
    type:    'progress',
    stage:   'uploading',
    percent,
    message: `Received chunk ${received} of ${session.totalChunks}`,
  });

  res.json({ ok: true, received });
});

// ── 3. Assemble + process ─────────────────────────────────────────────────
router.post('/complete', checkQuota, async (req, res) => {
  const { uploadId } = req.body;
  if (!uploadId) return res.status(400).json({ error: 'uploadId required' });

  const session = await ChunkSession.findOne({ uploadId });
  if (!session) return res.status(404).json({ error: 'Upload session not found' });

  if (session.receivedChunks.length < session.totalChunks) {
    return res.status(409).json({
      error: `Not all chunks received: ${session.receivedChunks.length}/${session.totalChunks}`,
    });
  }

  // ── Assemble chunks ────────────────────────────────────────────────────
  ws.notify(uploadId, { type: 'progress', stage: 'assembling', percent: 35, message: 'Assembling chunks…' });

  const chunkDir  = path.join(config.CHUNKS_DIR, uploadId);
  const chunkFiles = (await fs.readdir(chunkDir)).sort();
  const tempPath   = path.join(config.TEMP_DIR, `${uploadId}_assembled`);

  const { createWriteStream } = require('fs');
  await new Promise(async (resolve, reject) => {
    const ws_ = createWriteStream(tempPath);
    ws_.on('error', reject);
    ws_.on('finish', resolve);
    for (const f of chunkFiles) {
      const data = await fs.readFile(path.join(chunkDir, f));
      ws_.write(data);
    }
    ws_.end();
  });

  // ── Validate ───────────────────────────────────────────────────────────
  ws.notify(uploadId, { type: 'progress', stage: 'validating', percent: 45, message: 'Validating file…' });

  const validation = await validateFile(tempPath, session.mimeType);
  if (!validation.ok) {
    await fs.unlink(tempPath).catch(() => {});
    ws.notify(uploadId, { type: 'error', message: validation.reason });
    return res.status(422).json({ error: validation.reason });
  }

  // ── Hash + dedup ───────────────────────────────────────────────────────
  ws.notify(uploadId, { type: 'progress', stage: 'hashing', percent: 55, message: 'Computing content hash…' });

  const hash     = await hashFile(tempPath);
  const existing = await File.findOne({ hash, deleted: false });

  if (existing) {
    await fs.unlink(tempPath).catch(() => {});
    await fs.rm(chunkDir, { recursive: true, force: true }).catch(() => {});
    await ChunkSession.deleteOne({ uploadId });

    // Track that another user uploaded the same file
    await File.updateOne({ hash }, { $inc: { uploadCount: 1 },
      $push: { versions: { hash, name: session.originalName, size: existing.size, uploadedAt: new Date() } }
    });

    ws.notify(uploadId, { type: 'complete', duplicate: true, file: existing });
    return res.json({ duplicate: true, file: existing });
  }

  // ── Store original ─────────────────────────────────────────────────────
  ws.notify(uploadId, { type: 'progress', stage: 'storing', percent: 60, message: 'Storing original…' });
  await storage.moveFrom(tempPath, `originals/${hash}`);

  // ── Image processing pipeline ──────────────────────────────────────────
  ws.notify(uploadId, { type: 'progress', stage: 'processing', percent: 70, message: 'Generating WebP variants…' });

  const origPath  = storage.localPath(`originals/${hash}`);
  const imageData = await processImage(origPath, hash);

  // ── AI tagging ─────────────────────────────────────────────────────────
  ws.notify(uploadId, { type: 'progress', stage: 'tagging', percent: 85, message: 'Analysing image content…' });

  const tagData = await analyzeImage(origPath);

  // Add orientation tag
  tagData.tags.push(imageData.orientation);
  if (imageData.width && imageData.height) {
    const mp = ((imageData.width * imageData.height) / 1e6).toFixed(1);
    tagData.tags.push(`${mp}mp`);
  }

  // ── Persist to MongoDB ─────────────────────────────────────────────────
  ws.notify(uploadId, { type: 'progress', stage: 'saving', percent: 92, message: 'Saving metadata…' });

  const stat = await fs.stat(origPath);
  const file = await File.create({
    hash,
    originalName: session.originalName,
    mimeType:     session.mimeType,
    size:         stat.size,
    uploader:     session.uploader,
    dimensions:   { width: imageData.width, height: imageData.height },
    orientation:  imageData.orientation,
    variants:     imageData.variants,
    tags:         [...new Set(tagData.tags)],
    colors:       { dominant: tagData.dominantColor, palette: tagData.palette },
    exif:         imageData.exif,
  });

  // ── Cleanup ────────────────────────────────────────────────────────────
  await fs.rm(chunkDir, { recursive: true, force: true }).catch(() => {});
  await ChunkSession.deleteOne({ uploadId });

  ws.notify(uploadId, { type: 'complete', duplicate: false, file });
  res.json({ file });
});

module.exports = router;
