'use strict';
const fs            = require('fs/promises');
const fsSync        = require('fs');
const path          = require('path');
const StorageAdapter = require('./StorageAdapter');
const { ORIGINALS_DIR, PROCESSED_DIR } = require('../config');

class LocalStorage extends StorageAdapter {
  /** key format: "originals/{hash}" or "processed/{hash}/{variant}.webp" */
  _resolve(key) {
    if (key.startsWith('originals/'))  return path.join(ORIGINALS_DIR, key.slice(10));
    if (key.startsWith('processed/'))  return path.join(PROCESSED_DIR, key.slice(10));
    throw new Error(`Unknown storage prefix in key: ${key}`);
  }

  async put(key, buffer) {
    const p = this._resolve(key);
    await fs.mkdir(path.dirname(p), { recursive: true });
    await fs.writeFile(p, buffer);
  }

  async get(key) {
    return fsSync.createReadStream(this._resolve(key));
  }

  async remove(key) {
    await fs.unlink(this._resolve(key)).catch(() => {});
  }

  async exists(key) {
    return fs.access(this._resolve(key)).then(() => true).catch(() => false);
  }

  async moveFrom(localPath, key) {
    const dest = this._resolve(key);
    await fs.mkdir(path.dirname(dest), { recursive: true });
    await fs.rename(localPath, dest).catch(async () => {
      // cross-device: copy then unlink
      await fs.copyFile(localPath, dest);
      await fs.unlink(localPath);
    });
  }

  localPath(key) {
    return this._resolve(key);
  }
}

module.exports = new LocalStorage();
