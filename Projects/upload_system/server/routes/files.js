'use strict';
const express   = require('express');
const path      = require('path');
const fs        = require('fs/promises');
const fsSync    = require('fs');
const File      = require('../models/File');
const storage   = require('../storage/LocalStorage');
const signedUrl = require('../services/signedUrl');
const config    = require('../config');

const router = express.Router();

// ── List / search files ────────────────────────────────────────────────────
router.get('/', async (req, res) => {
  const {
    uploader, tag, color, orientation,
    before, after,
    sort = 'newest', page = '1', limit = '24',
    q,
  } = req.query;

  const filter = { deleted: false };

  if (uploader)    filter.uploader    = uploader;
  if (tag)         filter.tags        = tag;
  if (color)       filter['colors.dominant'] = { $regex: color, $options: 'i' };
  if (orientation) filter.orientation = orientation;
  if (before || after) {
    filter.createdAt = {};
    if (after)  filter.createdAt.$gte = new Date(after);
    if (before) filter.createdAt.$lte = new Date(before);
  }
  if (q) {
    filter.$or = [
      { originalName: { $regex: q, $options: 'i' } },
      { tags: { $regex: q, $options: 'i' } },
    ];
  }

  const sortMap = { newest: { createdAt: -1 }, oldest: { createdAt: 1 }, largest: { size: -1 }, smallest: { size: 1 } };
  const skip    = (parseInt(page, 10) - 1) * parseInt(limit, 10);

  const [files, total] = await Promise.all([
    File.find(filter).sort(sortMap[sort] || { createdAt: -1 }).skip(skip).limit(parseInt(limit, 10)).lean(),
    File.countDocuments(filter),
  ]);

  // Attach signed thumbnail URLs
  const enriched = files.map(f => ({
    ...f,
    thumbnailUrl: f.variants?.thumbnail ? signedUrl.generate(f.hash, 'thumbnail') : null,
    mediumUrl:    f.variants?.medium    ? signedUrl.generate(f.hash, 'medium')    : null,
  }));

  res.json({ files: enriched, total, page: parseInt(page, 10), pages: Math.ceil(total / parseInt(limit, 10)) });
});

// ── Get single file metadata ────────────────────────────────────────────────
router.get('/:id', async (req, res) => {
  const file = await File.findOne({ hash: req.params.id, deleted: false }).lean();
  if (!file) return res.status(404).json({ error: 'File not found' });

  res.json({
    ...file,
    signedUrls: {
      thumbnail: signedUrl.generate(file.hash, 'thumbnail'),
      medium:    signedUrl.generate(file.hash, 'medium'),
      full:      signedUrl.generate(file.hash, 'full'),
      original:  signedUrl.generate(file.hash, 'original'),
    },
  });
});

// ── Generate / refresh signed URL ──────────────────────────────────────────
router.get('/:id/signed-url', async (req, res) => {
  const { size = 'medium', ttl } = req.query;
  const file = await File.findOne({ hash: req.params.id, deleted: false });
  if (!file) return res.status(404).json({ error: 'File not found' });

  const url = signedUrl.generate(file.hash, size, ttl ? parseInt(ttl, 10) : undefined);
  res.json({ url, expiresIn: config.SIGNED_URL_TTL });
});

// ── Serve file (validates signed URL) ──────────────────────────────────────
router.get('/serve/:id', async (req, res) => {
  const { size = 'medium', expires, sig } = req.query;
  const fileId = req.params.id;

  if (!signedUrl.validate(fileId, size, expires, sig)) {
    return res.status(403).json({ error: 'Invalid or expired URL' });
  }

  const file = await File.findOne({ hash: fileId });
  if (!file) return res.status(404).json({ error: 'File not found' });

  let storageKey;
  if (size === 'original') {
    storageKey = `originals/${fileId}`;
  } else {
    storageKey = `processed/${fileId}/${size}.webp`;
  }

  const exists = await storage.exists(storageKey);
  if (!exists) return res.status(404).json({ error: 'Variant not found' });

  const mimeType = size === 'original' ? file.mimeType : 'image/webp';
  res.setHeader('Content-Type', mimeType);
  res.setHeader('Cache-Control', 'private, max-age=3600');

  const stream = await storage.get(storageKey);
  stream.pipe(res);
});

// ── Storage stats for a user ───────────────────────────────────────────────
router.get('/stats/quota', async (req, res) => {
  const uploader = req.query.uploader || req.headers['x-user-id'] || 'anonymous';

  const result = await File.aggregate([
    { $match: { uploader, deleted: false } },
    { $group: { _id: null, totalBytes: { $sum: '$size' }, count: { $sum: 1 } } },
  ]);

  const used  = result[0]?.totalBytes ?? 0;
  const count = result[0]?.count      ?? 0;
  res.json({
    usedBytes:   used,
    usedMB:      +(used / 1024 / 1024).toFixed(2),
    quotaBytes:  config.QUOTA_BYTES,
    quotaMB:     +(config.QUOTA_BYTES / 1024 / 1024).toFixed(0),
    fileCount:   count,
    percentUsed: +((used / config.QUOTA_BYTES) * 100).toFixed(1),
  });
});

// ── Soft delete ────────────────────────────────────────────────────────────
router.delete('/:id', async (req, res) => {
  const file = await File.findOne({ hash: req.params.id, deleted: false });
  if (!file) return res.status(404).json({ error: 'File not found' });

  await File.updateOne({ hash: req.params.id }, { deleted: true, deletedAt: new Date() });
  res.json({ ok: true, message: 'File moved to trash. Permanent deletion in 30 days.' });
});

// ── Restore from trash ─────────────────────────────────────────────────────
router.post('/:id/restore', async (req, res) => {
  const file = await File.findOne({ hash: req.params.id, deleted: true });
  if (!file) return res.status(404).json({ error: 'File not in trash' });

  await File.updateOne({ hash: req.params.id }, { deleted: false, $unset: { deletedAt: 1 } });
  res.json({ ok: true });
});

// ── List trash ─────────────────────────────────────────────────────────────
router.get('/trash/list', async (req, res) => {
  const uploader = req.headers['x-user-id'] || 'anonymous';
  const files    = await File.find({ deleted: true, uploader }).lean();
  res.json({ files });
});

module.exports = router;
