'use strict';
const crypto = require('crypto');
const fs     = require('fs');

/**
 * Stream a file through SHA-256 and return the hex digest.
 * Used for deduplication — identical content produces the same hash.
 */
async function hashFile(filePath) {
  return new Promise((resolve, reject) => {
    const hash   = crypto.createHash('sha256');
    const stream = fs.createReadStream(filePath);
    stream.on('error', reject);
    stream.on('data', chunk => hash.update(chunk));
    stream.on('end',  ()    => resolve(hash.digest('hex')));
  });
}

module.exports = { hashFile };
