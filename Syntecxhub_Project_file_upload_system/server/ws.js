'use strict';
const { WebSocketServer } = require('ws');

// Map of uploadId → Set<WebSocket> for targeted progress delivery
const _clients = new Map();

function setup(httpServer) {
  const wss = new WebSocketServer({ server: httpServer, path: '/ws' });

  wss.on('connection', (ws) => {
    ws._uploadId = null;

    ws.on('message', (data) => {
      try {
        const msg = JSON.parse(data.toString());
        if (msg.type === 'subscribe' && msg.uploadId) {
          ws._uploadId = msg.uploadId;
          if (!_clients.has(msg.uploadId)) _clients.set(msg.uploadId, new Set());
          _clients.get(msg.uploadId).add(ws);
        }
      } catch { /* ignore malformed messages */ }
    });

    ws.on('close', () => {
      if (ws._uploadId && _clients.has(ws._uploadId)) {
        _clients.get(ws._uploadId).delete(ws);
        if (_clients.get(ws._uploadId).size === 0) _clients.delete(ws._uploadId);
      }
    });
  });

  console.log('[ws] WebSocket server listening on /ws');
}

/**
 * Push a progress event to all clients subscribed to an uploadId.
 * Called from route handlers during pipeline execution.
 *
 * @param {string} uploadId
 * @param {{ type: string, stage?: string, percent?: number, message?: string, [key: string]: any }} event
 */
function notify(uploadId, event) {
  const sockets = _clients.get(uploadId);
  if (!sockets || sockets.size === 0) return;

  const payload = JSON.stringify({ uploadId, ...event });
  for (const ws of sockets) {
    if (ws.readyState === 1 /* OPEN */) ws.send(payload);
  }

  if (event.type === 'complete' || event.type === 'error') {
    _clients.delete(uploadId);
  }
}

module.exports = { setup, notify };
