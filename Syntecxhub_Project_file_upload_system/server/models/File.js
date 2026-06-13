'use strict';
const { Schema, model } = require('mongoose');

const variantSchema = new Schema({
  thumbnail: String,
  medium:    String,
  full:      String,
  original:  String,
}, { _id: false });

const versionSchema = new Schema({
  hash:       String,
  name:       String,
  size:       Number,
  uploadedAt: { type: Date, default: Date.now },
}, { _id: false });

const fileSchema = new Schema({
  hash:         { type: String, required: true, unique: true },
  originalName: { type: String, required: true },
  mimeType:     { type: String, required: true },
  size:         { type: Number, required: true },
  uploader:     { type: String, default: 'anonymous' },

  dimensions:   { width: Number, height: Number },
  orientation:  { type: String, enum: ['portrait', 'landscape', 'square'] },
  variants:     variantSchema,

  tags:         [String],
  colors:       { dominant: String, palette: [String] },
  exif:         Schema.Types.Mixed,

  deleted:      { type: Boolean, default: false },
  deletedAt:    Date,

  uploadCount:  { type: Number, default: 1 },
  versions:     [versionSchema],
}, { timestamps: true });

fileSchema.index({ uploader: 1, deleted: 1 });
fileSchema.index({ tags: 1 });
fileSchema.index({ 'colors.dominant': 1 });
fileSchema.index({ createdAt: -1 });

module.exports = model('File', fileSchema);
