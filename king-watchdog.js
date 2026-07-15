/**
 * king-watchdog.js — keep all services alive (13 tenants, 25 characters, 6 lipsync skills)
 *
 * Monitors:
 *   - Docker containers (studio-assets, neo4j, auth, etc.)
 *   - king-bridge API (port 8109)
 *   - Ollama (port 11434) — model inference
 *   - Static file server (port 8888)
 *
 * Features:
 *   - Auto-restart dead services
 *   - HTTP health checks
 *   - Graceful shutdown
 *   - Structured logging to watchdog.log
 *
 * Usage:
 *   node king-watchdog.js
 */

const fs = require('fs');
const path = require('path');
const http = require('http');
const { spawn, spawnSync } = require('child_process');

const HERE = __dirname;
const LOG_FILE = path.join(HERE, 'watchdog.log');
const POLL_MS = 30000;  // 30 seconds

// ─── Logging ─────────────────────────────────────────────────────────────────
function now() {
  return new Date().toISOString().slice(0, 19) + ' UTC';
}

function log(msg) {
  const line = `[${now()}] ${msg}`;
  console.log(line);
  fs.appendFileSync(LOG_FILE, line + '\n', { encoding: 'utf-8' });
}

// ─── HTTP Health Checks ──────────────────────────────────────────────────────
function httpReady(url, timeoutMs = 4000) {
  return new Promise((resolve) => {
    const timeoutHandle = setTimeout(() => resolve(false), timeoutMs);
    http.get(url, (res) => {
      clearTimeout(timeoutHandle);
      resolve(res.statusCode === 200);
    }).on('error', () => {
      clearTimeout(timeoutHandle);
      resolve(false);
    });
  });
}

// ─── Docker Operations ────────────────────────────────────────────────────────
function dockerRunning(containerName) {
  try {
    const result = spawnSync('docker', [
      'inspect',
      '--format', '{{.State.Status}}',
      containerName
    ], { encoding: 'utf-8' });
    return result.status === 0 && result.stdout.trim() === 'running';
  } catch (e) {
    return false;
  }
}

function dockerRestart(containerName) {
  log(`RESTART docker:${containerName}`);
  try {
    spawnSync('docker', ['restart', containerName]);
  } catch (e) {
    log(`ERROR restarting ${containerName}: ${e.message}`);
  }
}

// ─── Service Definitions ─────────────────────────────────────────────────────
const DOCKER_SERVICES = [\n  { name: 'studio-assets-studio-assets-1', health: 'http://localhost:8108/api/v2/ready' },\n  { name: 'studio-assets-studio-neo4j-1',  health: null },\n  { name: '12sgi-king-auth-1',             health: 'http://localhost:8101/api/v2/ready' },\n];\n\nconst PROCESS_SERVICES = [\n  {\n    id: 'king-bridge',\n    cmd: 'python',\n    args: [\n      '-m', 'uvicorn',\n      'services.king_bridge.app.main:app',\n      '--host', '127.0.0.1',\n      '--port', '8109',\n    ],\n    cwd: HERE,\n    healthUrl: 'http://localhost:8109/api/v2/ready',\n  },\n  {\n    id: 'static-server',\n    cmd: 'python',\n    args: [\n      '-m', 'http.server',\n      '8888',\n      '--directory', HERE,\n    ],\n    cwd: HERE,\n    healthUrl: 'http://localhost:8888/',\n  },\n];\n\n// ─── Process Management ──────────────────────────────────────────────────────\nconst procMap = new Map();\n\nfunction ensureProcess(svc) {\n  let proc = procMap.get(svc.id);\n  const alive = proc && !proc.killed;\n\n  if (alive && svc.healthUrl) {\n    return httpReady(svc.healthUrl).then((ready) => {\n      if (!ready) {\n        log(`UNRESPONSIVE ${svc.id} — killing and restarting`);\n        proc.kill();\n        procMap.delete(svc.id);\n        return startProcess(svc);\n      }\n    });\n  }\n\n  if (!alive) {\n    return startProcess(svc);\n  }\n}\n\nfunction startProcess(svc) {\n  return new Promise((resolve) => {\n    log(`START ${svc.id}: ${svc.cmd} ${svc.args.join(' ')}`);\n    const proc = spawn(svc.cmd, svc.args, {\n      cwd: svc.cwd,\n      stdio: ['ignore', 'ignore', 'ignore'],\n    });\n    procMap.set(svc.id, proc);\n    proc.on('error', (err) => {\n      log(`ERROR starting ${svc.id}: ${err.message}`);\n    });\n    // Wait 3s for startup\n    setTimeout(resolve, 3000);\n  });\n}\n\n// ─── Service Checks ──────────────────────────────────────────────────────────\nasync function checkDocker() {\n  for (const svc of DOCKER_SERVICES) {\n    if (!dockerRunning(svc.name)) {\n      log(`DOWN docker:${svc.name}`);\n      dockerRestart(svc.name);\n      await new Promise((r) => setTimeout(r, 5000));\n    } else if (svc.health && !(await httpReady(svc.health))) {\n      log(`UNHEALTHY docker:${svc.name} — restarting`);\n      dockerRestart(svc.name);\n      await new Promise((r) => setTimeout(r, 5000));\n    }\n  }\n}\n\nasync function checkProcesses() {\n  for (const svc of PROCESS_SERVICES) {\n    await ensureProcess(svc);\n  }\n}\n\nasync function checkOllama() {\n  const ready = await httpReady('http://localhost:11434/api/tags', 3000);\n  if (!ready) {\n    log('WARNING: Ollama not responding on :11434 — degraded inference mode');\n  }\n}\n\nfunction tailscaleServeHint() {\n  try {\n    const result = spawnSync('tailscale', ['serve', 'status'], {\n      encoding: 'utf-8',\n      stdio: ['ignore', 'pipe', 'ignore'],\n    });\n    if (result.status === 0) {\n      if (!result.stdout.includes('8109')) {\n        log('HINT: run `tailscale serve --bg http://8109` to expose king-bridge');\n      }\n      if (!result.stdout.includes('8888')) {\n        log('HINT: run `tailscale serve --bg http://8888` to expose static pages');\n      }\n    }\n  } catch (e) {\n    // tailscale not installed\n  }\n}\n\n// ─── Main Loop ───────────────────────────────────────────────────────────────\nasync function main() {\n  log('=== king-watchdog started ===');\n  log(`Monitoring: ${DOCKER_SERVICES.length} Docker + ${PROCESS_SERVICES.length} processes`);\n  log('Tenants: 13 (9 films, 1 game, 2 music videos, 1 civic studio)');\n  log('Characters: 25 • Lipsync skills: 6 • Render styles: 5 • Civic divisions: 12');\n  tailscaleServeHint();\n\n  // Initial startup\n  await checkDocker();\n  await checkProcesses();\n  await checkOllama();\n\n  let loopCount = 0;\n  while (true) {\n    try {\n      await checkDocker();\n      await checkProcesses();\n      // Every 5 minutes also check Ollama\n      if (loopCount % 10 === 0) {\n        await checkOllama();\n      }\n      loopCount++;\n      await new Promise((r) => setTimeout(r, POLL_MS));\n    } catch (err) {\n      log(`ERROR in watchdog loop: ${err.message}`);\n      await new Promise((r) => setTimeout(r, POLL_MS));\n    }\n  }\n}\n\n// ─── Graceful Shutdown ───────────────────────────────────────────────────────\nprocess.on('SIGINT', () => {\n  log('watchdog shutting down...');\n  for (const proc of procMap.values()) {\n    try {\n      proc.kill();\n    } catch (e) {}\n  }\n  process.exit(0);\n});\n\nif (require.main === module) {\n  main().catch((err) => {\n    log(`FATAL: ${err.message}`);\n    process.exit(1);\n  });\n}\n\nmodule.exports = { httpReady, dockerRunning, dockerRestart };\n