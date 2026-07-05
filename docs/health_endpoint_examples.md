# Health endpoint examples

This document provides two minimal examples for a /health endpoint that returns JSON suitable for basic monitoring.

Python / Flask example

app.py:

from flask import Flask, jsonify
import requests
import os
from datetime import datetime

app = Flask(__name__)

SURFACES = {
    'surfaceA': os.environ.get('SURFACE_A_HOST', 'TS_IP_OR_HOSTNAME_A:8782'),
    'surfaceB': os.environ.get('SURFACE_B_HOST', 'TS_IP_OR_HOSTNAME_B:8782'),
}

@app.route('/health')
def health():
    status = {'homepage':'ok', 'tailscale':'unknown', 'timestamp': datetime.utcnow().isoformat() + 'Z'}
    # Check surfaces
    for name, hostport in SURFACES.items():
        try:
            r = requests.get(f'http://{hostport}/', timeout=3)
            status[name] = 'ok' if r.status_code == 200 else f'error:{r.status_code}'
        except Exception as e:
            status[name] = f'error:{str(e)}'
    # Optionally check tailscale if available
    try:
        import subprocess
        out = subprocess.check_output(['tailscale', 'status'], stderr=subprocess.DEVNULL)
        status['tailscale'] = 'connected'
    except Exception:
        status['tailscale'] = 'not-available'
    return jsonify(status)


Node / Express example

// server.js
const express = require('express');
const fetch = require('node-fetch');
const app = express();
const port = process.env.PORT || 3000;

const SURFACES = {
  surfaceA: process.env.SURFACE_A_HOST || 'TS_IP_OR_HOSTNAME_A:8782',
  surfaceB: process.env.SURFACE_B_HOST || 'TS_IP_OR_HOSTNAME_B:8782'
};

app.get('/health', async (req, res) => {
  const result = { homepage: 'ok', timestamp: new Date().toISOString(), tailscale: 'unknown' };
  for (const [name, hostport] of Object.entries(SURFACES)) {
    try {
      const r = await fetch(`http://${hostport}/`, { timeout: 3000 });
      result[name] = r.ok ? 'ok' : `error:${r.status}`;
    } catch (e) {
      result[name] = `error:${e.message}`;
    }
  }
  res.json(result);
});

app.listen(port, () => console.log(`Health server listening on ${port}`));
