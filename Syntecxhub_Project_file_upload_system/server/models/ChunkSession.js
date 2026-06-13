'use strict';
const { Schema, model } = require('mongoose');

const chunkSessionSchema = new Schema({
  uploadId:       { type: String, required: true, unique: true },
  totalChunks:    { type: Number, required: true },
  receivedChunks: { type: [Number], default: [] },
  originalName:   { type: String, required: true },
  mimeType:       { type: String, required: true },
  uploader:       { type: String, default: 'anonymous' },
  expiresAt:      { type: Date, default: () => new Date(Date.now() + 24 * 3600 * 1000) },
}, { timestamps: true });

chunkSessionSchema.index({ expiresAt: 1 }, { expireAfterSeconds: 0 });

module.exports = model('ChunkSession', chunkSessionSchema);
