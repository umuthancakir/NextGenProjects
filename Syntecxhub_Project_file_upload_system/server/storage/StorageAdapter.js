'use strict';

/**
 * Abstract storage interface — swap LocalStorage for an S3Adapter, MinIO, etc.
 * without touching any route or service code.
 */
class StorageAdapter {
  /** Save buffer to storage, return a logical key. */
  async put(key, buffer) { throw new Error('Not implemented'); }

  /** Return a readable stream for the given key. */
  async get(key) { throw new Error('Not implemented'); }

  /** Delete an object by key. */
  async remove(key) { throw new Error('Not implemented'); }

  /** Check whether a key exists. */
  async exists(key) { throw new Error('Not implemented'); }

  /** Move a local temp path into storage under the given key. */
  async moveFrom(localPath, key) { throw new Error('Not implemented'); }

  /** Return the absolute local path (for Sharp processing before upload). */
  localPath(key) { throw new Error('Not implemented'); }
}

module.exports = StorageAdapter;
