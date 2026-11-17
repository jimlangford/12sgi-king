import assert from 'node:assert/strict';
import { after, before, test } from 'node:test';
import { mkdir, writeFile, rm } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { audit, compare, evaluate, expectedFindings, fingerprint, inShard, launch, parseShard,
  proposeBaseline, serve, shardOf } from './scan.mjs';

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
  await writeFile(path.join(root, 'broken-css.html'), `<!doctype html><html lang="en"><head>
    <meta charset="utf-8"><title>Broken stylesheet fixture</title>
    <link rel="stylesheet" href="nope.css"></head><body>
    <main><h1>Page with a missing stylesheet</h1></main></body></html>`);
  // Colour depends on the hour: pale (fails contrast) before noon Honolulu, dark from noon. A frozen noon clock
  // must therefore always render the dark, passing variant no matter when the test runs.
  await writeFile(path.join(root, 'clock.html'), `<!doctype html><html lang="en"><head>
    <meta charset="utf-8"><title>Clock fixture</title></head><body><main><h1>Clock</h1>
    <p id="t" style="background:#fff">Time dependent text.</p></main>
    <script>document.getElementById('t').style.color = new Date().getHours() < 12 ? '#eeeeee' : '#000000';</script>
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

test('a missing stylesheet is an error unless it is a documented known defect, and a fixed defect must be pruned', async () => {
  await assert.rejects(audit(browser, origin, 'broken-css.html'), /missing local stylesheet/);
  const tolerated = await audit(browser, origin, 'broken-css.html', ['nope.css']);
  assert.equal(tolerated.knownDefects.length, 1, 'the page is still scanned and the defect is reported');
  await assert.rejects(audit(browser, origin, 'broken-css.html', ['something-else.css']), /missing local stylesheet/);
  await assert.rejects(audit(browser, origin, 'good.html', ['nope.css']), /no longer occurs/);
});

test('the page clock is frozen so time-dependent pages give the same findings at any time of day', async () => {
  const first = await audit(browser, origin, 'clock.html');
  const second = await audit(browser, origin, 'clock.html');
  assert.deepEqual(first.findings, [], 'noon-Honolulu variant has readable text; an unfrozen morning clock would fail it');
  assert.equal(fingerprint(first.findings), fingerprint(second.findings));
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

// ----- full-site gate decisions (pure functions, no browser) -----------------------------------------------

const MSG = 'Fix any of the following:\n  Document does not have a main landmark';
const finding = (page, rule = 'landmark-one-main', target = ['html']) => ({ page, rule, target, failure: MSG });
const baselineFor = pages => ({ format: 2, failures: [MSG], pages });
const scanned = (page, ...items) => ({ page, findings: items });

test('every page lands in exactly one shard, deterministically and roughly evenly', () => {
  const names = Array.from({ length: 500 }, (_, i) => `section-${i % 37}/page-${i}.html`);
  for (const total of [1, 2, 4, 7]) {
    const counts = new Array(total).fill(0);
    for (const name of names) {
      const owners = Array.from({ length: total }, (_, i) => inShard(name, { index: i + 1, total })).filter(Boolean);
      assert.equal(owners.length, 1, `${name} must belong to exactly one of ${total} shards`);
      assert.equal(shardOf(name, total), shardOf(name, total));
      counts[shardOf(name, total)]++;
    }
    assert.equal(counts.reduce((a, b) => a + b, 0), names.length);
    if (total > 1) for (const n of counts) assert.ok(n > names.length / total * 0.6 && n < names.length / total * 1.4, `uneven shard ${counts}`);
  }
  assert.equal(inShard('anything.html', null), true, 'no shard means scan everything');
});

test('A11Y_SHARD values are validated, never silently ignored', () => {
  assert.deepEqual(parseShard('2/4'), { index: 2, total: 4 });
  assert.equal(parseShard(''), null);
  for (const bad of ['0/4', '5/4', '2', 'a/b', '2/0', '1/4/9']) assert.throws(() => parseShard(bad), /A11Y_SHARD/, bad);
});

test('gate passes only when observed findings exactly equal the reviewed baseline', () => {
  const baseline = baselineFor({ 'a.html': { 'landmark-one-main': [[['html'], 0]] }, 'b.html': {} });
  const ok = evaluate({ scanned: [scanned('a.html', finding('a.html')), scanned('b.html')], baseline, names: ['a.html', 'b.html'] });
  assert.equal(ok.failed, false);
  assert.equal(ok.existing, 1);
});

test('a NEW page with any finding fails; a clean new page is allowed but reported', () => {
  const baseline = baselineFor({ 'a.html': {} });
  const bad = evaluate({ scanned: [scanned('a.html'), scanned('new.html', finding('new.html'))], baseline, names: ['a.html', 'new.html'] });
  assert.equal(bad.failed, true);
  assert.deepEqual(bad.newPagesWithFindings, ['new.html']);
  const clean = evaluate({ scanned: [scanned('a.html'), scanned('new.html')], baseline, names: ['a.html', 'new.html'] });
  assert.equal(clean.failed, false);
  assert.deepEqual(clean.newPages, ['new.html']);
});

test('a fixed finding must be pruned: stale baseline entries fail', () => {
  const baseline = baselineFor({ 'a.html': { 'landmark-one-main': [[['html'], 0]] } });
  const stale = evaluate({ scanned: [scanned('a.html')], baseline, names: ['a.html'] });
  assert.equal(stale.failed, true);
  assert.equal(stale.resolved, 1);
});

test('a page removed from the build must be pruned from the baseline', () => {
  const baseline = baselineFor({ 'a.html': {}, 'gone.html': {} });
  const verdict = evaluate({ scanned: [scanned('a.html')], baseline, names: ['a.html'] });
  assert.equal(verdict.failed, true);
  assert.deepEqual(verdict.stalePages, ['gone.html']);
});

test('a changed failure message on an existing node is a regression, not a pass', () => {
  const baseline = baselineFor({ 'a.html': { 'landmark-one-main': [[['html'], 0]] } });
  const changed = { ...finding('a.html'), failure: 'Fix any of the following:\n  contrast ratio is now 1.01' };
  const verdict = evaluate({ scanned: [scanned('a.html', changed)], baseline, names: ['a.html'] });
  assert.equal(verdict.failed, true);
  assert.equal(verdict.regressions.length, 1);
  assert.equal(verdict.resolved, 1);
});

test('scan errors always fail the gate, even when every finding matches', () => {
  const baseline = baselineFor({ 'a.html': {} });
  const verdict = evaluate({ scanned: [scanned('a.html')], errors: ['b.html: timeout'], baseline, names: ['a.html'] });
  assert.equal(verdict.failed, true);
});

test('each shard judges only its own pages and cannot see or hide another shard\'s entries', () => {
  const names = Array.from({ length: 40 }, (_, i) => `p${i}.html`);
  const pages = Object.fromEntries(names.map(n => [n, { 'landmark-one-main': [[['html'], 0]] }]));
  const baseline = baselineFor(pages);
  for (let index = 1; index <= 4; index++) {
    const shard = { index, total: 4 };
    const mine = names.filter(n => inShard(n, shard));
    const ok = evaluate({ scanned: mine.map(n => scanned(n, finding(n))), baseline, names, shard });
    assert.equal(ok.failed, false, `shard ${index} should pass when its own pages match`);
    const regress = evaluate({ scanned: mine.map(n => scanned(n, finding(n), finding(n, 'region', ['p']))), baseline, names, shard });
    assert.equal(regress.failed, true, `shard ${index} must catch a new finding on its own pages`);
  }
});

test('proposed baselines round-trip exactly and list clean pages', () => {
  const found = [scanned('a.html', finding('a.html'), finding('a.html', 'region', ['p'])), scanned('b.html')];
  const proposal = proposeBaseline(found, ['a.html', 'b.html'], { date: 'x' });
  assert.deepEqual(proposal.pages['b.html'], {});
  const again = compare(found.flatMap(p => p.findings), expectedFindings(proposal));
  assert.deepEqual([again.regressions.length, again.resolved], [0, 0]);
  assert.throws(() => expectedFindings({ failures: [], pages: { 'a.html': { r: [[['x'], 3]] } } }), /bad failure index/);
});
