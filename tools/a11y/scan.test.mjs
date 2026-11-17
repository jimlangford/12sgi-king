import assert from 'node:assert/strict';
import { after, before, test } from 'node:test';
import { mkdir, writeFile, rm } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { audit, compare, fingerprint, launch, serve } from './scan.mjs';

const root = path.join(path.dirname(fileURLToPath(import.meta.url)), '.work', 'fixtures');
let browser, server, origin;

before(async () => {
  await mkdir(root, { recursive: true });
  await writeFile(path.join(root, 'good.html'), `<!doctype html><html lang="en"><head>
    <meta charset="utf-8"><title>Good fixture</title></head><body>
    <main><h1>Accessible fixture</h1><p style="color:#000;background:#fff">Readable text.</p>
    <img alt="A decorative test marker" src="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg'/%3E">
    </main></body></html>`);
  await writeFile(path.join(root, 'bad.html'), `<!doctype html><html lang="en"><head>
    <meta charset="utf-8"><title>Bad fixture</title></head><body>
    <h1>Broken fixture</h1><p style="color:#eee;background:#fff">This contrast must fail.</p>
    <img src="missing.png"><button aria-label="Broken" aria-not-real="true">Action</button>
    <script>fetch('http://127.0.0.1:9/api');fetch('https://example.invalid/blocked');</script>
    </body></html>`);
  ({ server, origin } = await serve(root));
  browser = await launch();
});

after(async () => {
  if (browser) await browser.close();
  if (server) await new Promise(resolve => server.close(resolve));
  await rm(root, { recursive: true, force: true });
});

test('real browser accepts accessible fixture and detects contrast, alt, semantics and ARIA failures', async () => {
  const good = await audit(browser, origin, 'good.html');
  assert.deepEqual(good.findings, []);
  const bad = await audit(browser, origin, 'bad.html');
  const rules = new Set(bad.findings.map(item => item.rule));
  for (const rule of ['color-contrast', 'image-alt', 'landmark-one-main', 'aria-valid-attr']) {
    assert.ok(rules.has(rule), `Real axe browser scan must detect ${rule}`);
  }
  const csp = (await fetch(origin + '/site/bad.html')).headers.get('content-security-policy');
  assert.ok(csp.includes("connect-src 'none'"));
  assert.ok(csp.includes("worker-src 'none'"));
  assert.notEqual(fingerprint(bad.findings), fingerprint([]));
});

test('missing generated page is an error, never a successful empty scan', async () => {
  await assert.rejects(audit(browser, origin, 'absent.html'), /missing generated page/);
});

test('static server does not expose repository, backend routes or traversal', async () => {
  for (const route of ['/api/health', '/CANON.md', '/site/%2e%2e%2fpackage.json']) {
    assert.equal((await fetch(origin + route)).status, 404);
  }
});

test('baseline fingerprints are order-independent and exact, including contrast and duplicate counts', () => {
  const item = { page: 'x.html', rule: 'color-contrast', target: ['p'], failure: 'ratio 1.12' };
  const second = { ...item, target: ['h1'] };
  assert.equal(fingerprint([item, second]), fingerprint([second, item]));
  assert.notEqual(fingerprint([{ ...item, failure: 'ratio 1.01' }]), fingerprint([item]));
  assert.notEqual(fingerprint([second]), fingerprint([item]));
  assert.notEqual(fingerprint([item, item]), fingerprint([item]));
  assert.notEqual(fingerprint([]), fingerprint([item]));
  assert.equal(compare([], [item]).resolved, 1);
  assert.equal(compare([item, item], [item]).regressions.length, 1);
});
