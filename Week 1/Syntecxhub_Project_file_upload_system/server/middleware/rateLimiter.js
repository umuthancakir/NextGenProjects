'use strict';
const rateLimit = require('express-rate-limit');
const File      = require('../models/File');
const config    = require('../config');

/** Per-user upload rate limit (keyed by X-User-Id header or IP fallback). */
const uploadRateLimit = rateLimit({
  windowMs:         60 * 60 * 1000, // 1 hour
  max:              config.RATE_LIMIT,
  keyGenerator:     req => req.headers['x-user-id'] || req.ip,
  standardHeaders:  true,
  legacyHeaders:    false,
  message:          { error: `Upload rate limit exceeded. Max ${config.RATE_LIMIT} uploads per hour.` },
});

/**
 * Check whether the uploader has exceeded their total storage quota.
 * Runs as an Express middleware before /upload/complete.
 */
async function checkQuota(req, res, next) {
  const uploader = req.headers['x-user-id'] || 'anonymous';

  const result = await File.aggregate([
    { $match: { uploader, deleted: false } },
    { $group: { _id: null, total: { $sum: '$size' } } },
  ]);

  const usedBytes = result[0]?.total ?? 0;

  if (usedBytes >= config.QUOTA_BYTES) {
    const usedMB  = (usedBytes  / 1024 / 1024).toFixed(1);
    const limitMB = (config.QUOTA_BYTES / 1024 / 1024).toFixed(0);
    return res.status(413).json({
      error: `Storage quota exceeded (${usedMB} MB / ${limitMB} MB limit).`,
    });
  }

  next();
}

module.exports = { uploadRateLimit, checkQuota };
