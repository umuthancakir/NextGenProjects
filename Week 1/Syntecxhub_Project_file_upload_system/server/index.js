'use strict';
require('dotenv').config();
const http    = require('http');
const path    = require('path');
const express = require('express');
const cors    = require('cors');

const config        = require('./config');
const { connect }   = require('./db');
const ws            = require('./ws');
const uploadRoutes  = require('./routes/upload');
const fileRoutes    = require('./routes/files');

const app    = express();
const server = http.createServer(app);

// ── Middleware ─────────────────────────────────────────────────────────────
app.use(cors());
app.use(express.json());
app.use(express.static(config.PUBLIC_DIR));

// ── Routes ─────────────────────────────────────────────────────────────────
app.use('/api/upload', uploadRoutes);
app.use('/api/files',  fileRoutes);

// Health check
app.get('/api/health', (_, res) => res.json({ ok: true, ts: new Date() }));

// SPA fallback
app.get('*', (_, res) =>
  res.sendFile(path.join(config.PUBLIC_DIR, 'index.html'))
);

// ── Boot ───────────────────────────────────────────────────────────────────
(async () => {
  await connect();
  ws.setup(server);

  server.listen(config.PORT, () => {
    console.log(`[server] http://localhost:${config.PORT}`);
    console.log(`[server] WebSocket  ws://localhost:${config.PORT}/ws`);
  });
})();
