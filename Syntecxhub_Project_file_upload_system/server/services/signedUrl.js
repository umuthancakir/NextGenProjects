'use strict';
const crypto              = require('crypto');
const { SIGNING_SECRET, SIGNED_URL_TTL, BASE_URL } = require('../config');

function _sign(fileId, size, expires) {
  return crypto
    .createHmac('sha256', SIGNING_SECRET)
    .update(`${fileId}:${size}:${expires}`)
    .digest('hex');
}

/**
 * Generate a time-limited signed URL for a file variant.
 * Works like AWS S3 presigned URLs — expiry is embedded in the URL,
 * and HMAC prevents forgery.
 */
function generate(fileId, size = 'medium', ttlSeconds = SIGNED_URL_TTL) {
  const expires = Date.now() + ttlSeconds * 1000;
  const sig     = _sign(fileId, size, expires);
  return `${BASE_URL}/api/files/serve/${fileId}?size=${size}&expires=${expires}&sig=${sig}`;
}

/**
 * Validate a signed URL's signature and expiry.
 * Uses timing-safe comparison to prevent timing attacks.
 */
function validate(fileId, size, expires, sig) {
  if (!expires || !sig) return false;
  if (Date.now() > parseInt(expires, 10)) return false;

  const expected = _sign(fileId, size, parseInt(expires, 10));
  try {
    return crypto.timingSafeEqual(Buffer.from(sig, 'hex'), Buffer.from(expected, 'hex'));
  } catch {
    return false;
  }
}

module.exports = { generate, validate };
