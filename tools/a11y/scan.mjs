import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { createHash } from 'node:crypto';
import { readFile, realpath, stat, mkdir, writeFile, appendFile, readdir, rm } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import puppeteer from 'puppeteer-core';
import axe from 'axe-core';

const here = path.dirname(fileURLToPath(import.meta.url));
export const tags = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa', 'best-practice'];

export function fingerprint(items) {
  const entries = items.map(item => JSON.stringify([item.rule, item.target, item.failure])).sort();
  return createHash('sha256').update(JSON.stringify(entries)).digest('hex');
}

/**
 * The message used for matching. EXACT for every rule except `target-size`, whose message embeds measured pixel
 * sizes (e.g. "96.3px by 16px", "diameter of 21.2px"). Those follow the runner's fallback-font metrics and were
 * seen to change between two GitHub runs of identical code (85.9px vs 96.3px for the same link), which made the
 * gate flake. For that one rule the pixel numbers are ignored; the page, rule and element (selector) must still
 * match exactly, and so must the rest of the message, so a finding can neither appear nor disappear unnoticed.
 */
export function canonicalFailure(item) {
  return item.rule === 'target-size' ? String(item.failure).replace(/\d+(?:\.\d+)?px/g, 'Npx') : item.failure;
}

export function compare(actual, baseline) {
  const key = item => JSON.stringify([item.page, item.rule, item.target, canonicalFailure(item)]);
  const remaining = new Map();
  for (const item of baseline) remaining.set(key(item), (remaining.get(key(item)) || 0) + 1);
  const regressions = [];
  for (const item of actual) {
    const count = remaining.get(key(item)) || 0;
    if (count) remaining.set(key(item), count - 1);
    else regressions.push(item);
  }
  const stale = [...remaining].filter(([, count]) => count > 0)
    .map(([entry, count]) => { const [page, rule, target] = JSON.parse(entry); return { page, rule, target, count }; });
  return { regressions, resolved: [...remaining.values()].reduce((a, b) => a + b, 0), stale };
}

export function findings(page, violations) {
  return violations.flatMap(rule => rule.nodes.map(node => ({
    page, rule: rule.id, impact: rule.impact, target: node.target,
    failure: node.failureSummary, help: rule.helpUrl,
  })));
}

// ---------------------------------------------------------------------------------------------------------
// Sharding + baseline evaluation. These are pure functions so the gate's decisions (new page fails, stale entry
// fails, every page lands in exactly one shard) are unit-tested without a browser.
// ---------------------------------------------------------------------------------------------------------

/** Parse "2/4" -> { index: 2, total: 4 } (1-based). Empty/undefined -> null (scan everything). */
export function parseShard(value) {
  if (!value) return null;
  const match = /^(\d+)\/(\d+)$/.exec(String(value).trim());
  assert.ok(match, `A11Y_SHARD must look like "2/4", got "${value}"`);
  const index = Number(match[1]);
  const total = Number(match[2]);
  assert.ok(total >= 1 && index >= 1 && index <= total, `A11Y_SHARD out of range: ${value}`);
  return { index, total };
}

/** Deterministic shard (0-based) for a page name: stable across machines, runs and page additions. */
export function shardOf(name, total) {
  return parseInt(createHash('sha256').update(name).digest('hex').slice(0, 8), 16) % total;
}

export function inShard(name, shard) {
  return !shard || shardOf(name, shard.total) === shard.index - 1;
}

/**
 * Baseline format 2:
 *   failures: ["<exact axe failureSummary>", ...]          deduplicated message table
 *   pages:    { "<page>": { "<rule>": [ [ <target>, <failure index> ], ... ] } }   EVERY reviewed page is listed,
 *                                                                                  clean pages as {}
 */
export function expectedFindings(baseline, include = () => true) {
  return Object.entries(baseline.pages).filter(([page]) => include(page)).flatMap(([page, rules]) =>
    Object.entries(rules).flatMap(([rule, nodes]) =>
      nodes.map(([target, index]) => {
        assert.ok(index >= 0 && index < baseline.failures.length, `${page}/${rule}: bad failure index ${index}`);
        return { page, rule, target, failure: baseline.failures[index] };
      })));
}

/**
 * Decide PASS/FAIL for one run (all pages or one shard).
 *  - regressions: any finding not in the reviewed baseline. A page that is NOT in the baseline therefore fails
 *    as soon as it has ANY finding (new-page failure); a clean new page is allowed.
 *  - resolved:    baseline entries no longer observed. A fixed finding must be pruned (stale-baseline pruning).
 *  - stalePages:  pages listed in the baseline that the build no longer generates (must be pruned too).
 */
export function evaluate({ scanned, errors = [], baseline, names, shard = null }) {
  const include = page => inShard(page, shard);
  const actual = scanned.flatMap(page => page.findings);
  const expected = expectedFindings(baseline, include);
  const { regressions, resolved, stale } = compare(actual, expected);
  const generated = new Set(names);
  const stalePages = Object.keys(baseline.pages).filter(page => include(page) && !generated.has(page)).sort();
  const newPages = names.filter(page => include(page) && !(page in baseline.pages)).sort();
  const newPagesWithFindings = [...new Set(regressions.map(item => item.page))].filter(page => newPages.includes(page));
  const failed = errors.length > 0 || regressions.length > 0 || resolved > 0 || stalePages.length > 0;
  return { regressions, resolved, stale, stalePages, newPages, newPagesWithFindings, existing: actual.length, failed };
}

/** Build a format-2 baseline proposal from observed pages (written to .work only; a human reviews and copies it). */
export function proposeBaseline(pages, names, review) {
  const table = [];
  const index = new Map();
  const out = {};
  for (const name of names) out[name] = {};
  for (const page of pages) {
    for (const item of page.findings) {
      if (!index.has(item.failure)) { index.set(item.failure, table.length); table.push(item.failure); }
      (out[page.page][item.rule] ||= []).push([item.target, index.get(item.failure)]);
    }
  }
  return { format: 2, axeVersion: axe.version, review, failures: table, pages: out };
}

export function defaultChrome() {
  if (process.env.CHROME_BIN) return process.env.CHROME_BIN;
  const candidates = process.platform === 'win32'
    ? ['C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
       'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe']
    : ['/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser'];
  return candidates.find(existsSync) || candidates[0];
}

export async function serve(root) {
  const base = await realpath(root);
  const server = createServer(async (req, res) => {
    try {
      const url = new URL(req.url, 'http://localhost');
      if (req.method !== 'GET' || !url.pathname.startsWith('/site/')) throw Error('Not static');
      const name = decodeURIComponent(url.pathname.slice(6));
      const filename = await realpath(path.join(base, name));
      if (!filename.startsWith(base + path.sep) || !(await stat(filename)).isFile()) throw Error('Not a file');
      const types = { '.html': 'text/html', '.css': 'text/css', '.js': 'text/javascript',
        '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png',
        '.woff2': 'font/woff2', '.jpg': 'image/jpeg', '.ico': 'image/x-icon' };
      res.writeHead(200, {
        'Content-Type': types[path.extname(filename)] || 'application/octet-stream',
        'Content-Security-Policy': "connect-src 'none'; worker-src 'none'; frame-src 'self'; form-action 'none'",
      });
      res.end(await readFile(filename));
    } catch {
      res.writeHead(404);
      res.end('Not found');
    }
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  return { server, origin: `http://127.0.0.1:${server.address().port}` };
}

/**
 * `known` = substrings of stylesheet URLs that are a DOCUMENTED, reviewed defect for this page (scope.json
 * knownDefects). The page is still scanned. Any OTHER missing stylesheet is an error, and a known defect that no
 * longer occurs is also an error ("fixed - prune the entry"), so an allowance can never outlive its defect.
 */
export async function audit(browser, origin, name, known = []) {
  const page = await browser.newPage();
  const blocked = new Set();
  const missingStyles = new Set();
  try {
    await page.setViewport({ width: 1280, height: 900, deviceScaleFactor: 1 });
    await page.emulateTimezone('Pacific/Honolulu');
    await page.emulateMediaFeatures([{ name: 'prefers-reduced-motion', value: 'reduce' }]);
    // Freeze the page clock to ONE fixed instant before any page script runs. Pages such as king/aupuni.html
    // paint live time-zone clocks whose colours (and therefore axe contrast results) depend on the wall-clock
    // time; without this the gate gave different findings at different times of day (observed 2026-11-17).
    await page.evaluateOnNewDocument(() => {
      const fixed = Date.UTC(2026, 0, 15, 22, 0, 0);   // 2026-01-15 12:00 Honolulu
      const RealDate = Date;
      class FrozenDate extends RealDate {
        constructor(...args) { if (args.length === 0) super(fixed); else super(...args); }
        static now() { return fixed; }
      }
      globalThis.Date = FrozenDate;
    });
    await page.setRequestInterception(true);
    page.on('request', request => {
      const url = new URL(request.url());
      if (url.origin === origin && url.pathname.startsWith('/site/') &&
          !['fetch', 'xhr', 'websocket', 'eventsource'].includes(request.resourceType())) {
        request.continue();
      } else {
        blocked.add(url.origin === origin ? url.pathname : url.origin);
        request.abort();
      }
    });
    page.on('response', response => {
      if (response.request().resourceType() === 'stylesheet' && !response.ok()) missingStyles.add(response.url());
    });
    const url = `${origin}/site/${name.split('/').map(encodeURIComponent).join('/')}`;
    const response = await page.goto(url, { waitUntil: 'load', timeout: 15000 });
    assert.equal(response.status(), 200, `${name}: missing generated page`);
    assert.equal(decodeURI(page.url()), decodeURI(url), `${name}: unexpected redirect`);
    await page.addScriptTag({ content: axe.source });
    const runAxe = () => page.evaluate(async runTags => {
      await document.fonts.ready;
      return axe.run(document, { runOnly: { type: 'tag', values: runTags } });
    }, tags);
    // DETERMINISM: let the page get past its first 1-second timer tick, then require two CONSECUTIVE identical
    // axe results. Live-clock pages (king/aupuni.html) otherwise gave different contrast findings depending on
    // whether a tick had fired yet, so 4 of 6 shard runs failed under load (observed 2026-11-17). A page that
    // never stabilizes is reported as an error by name; it is never a random pass or fail.
    const settleMs = Number(process.env.A11Y_SETTLE_MS ?? 1500);
    await new Promise(resolve => setTimeout(resolve, settleMs));
    let result = await runAxe();
    let stable = false;
    for (let attempt = 0; attempt < 4 && !stable; attempt++) {
      const again = await runAxe();
      stable = fingerprint(findings(name, again.violations)) === fingerprint(findings(name, result.violations));
      result = again;
      if (!stable) await new Promise(resolve => setTimeout(resolve, 600));
    }
    assert.ok(stable, `${name}: accessibility results kept changing while scanning (unstable page)`);
    const missing = [...missingStyles].sort();
    const unexpected = missing.filter(url => !known.some(part => url.includes(part)));
    assert.equal(unexpected.length, 0, `${name}: missing local stylesheet ${unexpected.join(', ')}`);
    const fixed = known.filter(part => !missing.some(url => url.includes(part)));
    assert.equal(fixed.length, 0, `${name}: known stylesheet defect no longer occurs (${fixed.join(', ')}); prune it from scope.json knownDefects and re-propose the baseline`);
    assert.ok(result.passes.length > 0, `${name}: axe did not run`);
    return { page: name, findings: findings(name, result.violations),
      incomplete: result.incomplete.map(rule => ({ rule: rule.id, nodes: rule.nodes.length })),
      passedRules: result.passes.length, blocked: [...blocked].sort(), knownDefects: missing };
  } finally {
    await page.close();
  }
}

export async function launch() {
  // A UNIQUE profile per launch. A shared profile made every later run fail with "The browser is already
  // running for ...chrome-profile" whenever an earlier run left a Chrome behind (seen on Windows: all 16 tests
  // failed, including the pure unit tests that never open a page). Old profiles are swept best-effort.
  const work = path.join(here, '.work');
  await mkdir(work, { recursive: true });
  try {
    for (const name of await readdir(work)) {
      if (name.startsWith('chrome-profile-')) {
        const full = path.join(work, name);
        const info = await stat(full);
        if (Date.now() - info.mtimeMs > 3600_000) await rm(full, { recursive: true, force: true });
      }
    }
  } catch { /* sweeping is optional */ }
  return puppeteer.launch({
    executablePath: defaultChrome(),
    headless: true,
    args: ['--no-sandbox', '--disable-dev-shm-usage', '--disable-background-networking'],
    userDataDir: path.join(work, `chrome-profile-${process.pid}-${Date.now()}`),
    // Keep Chromium scratch files inside this task's workspace.
    env: { ...process.env, TMPDIR: path.join(here, '.work') },
  });
}

async function main() {
  const output = path.join(here, '.work');
  await mkdir(output, { recursive: true });
  const scope = JSON.parse(await readFile(path.join(here, 'scope.json'), 'utf8'));
  const baseline = JSON.parse(await readFile(path.join(here, 'baseline.json'), 'utf8'));
  const shard = parseShard(process.env.A11Y_SHARD);
  const propose = process.env.A11Y_PROPOSE === '1' || process.argv.includes('--propose');
  if (!propose) {   // proposing a NEW baseline must work while the old one is still in place
    assert.equal(baseline.format, 2, 'Baseline format 2 required');
    assert.equal(baseline.axeVersion, axe.version, 'Baseline engine version must be reviewed');
  }
  assert.ok(!(propose && shard), 'A11Y_PROPOSE scans every page; do not combine it with A11Y_SHARD');
  // Every generated HTML file is in scope. Documented exclusions are explicit, reasoned, and reported.
  const excluded = new Map((scope.exclude || []).map(item => [item.page, item.reason]));
  for (const [page, reason] of excluded) assert.ok(reason && reason.length > 20, `Exclusion for ${page} needs a real reason`);
  // Known, reviewed page defects (still scanned; see audit()). Every entry needs a page, a URL fragment and a real reason.
  const knownDefects = new Map();
  for (const item of scope.knownDefects || []) {
    assert.ok(item.page && Array.isArray(item.missingStylesheetContains) && item.missingStylesheetContains.length,
      'knownDefects entries need page + missingStylesheetContains');
    assert.ok(item.reason && item.reason.length > 20, `knownDefect for ${item.page} needs a real reason`);
    knownDefects.set(item.page, item.missingStylesheetContains);
  }
  const all = (await readdir(path.join(output, 'site'), { recursive: true }))
    .map(name => name.split(path.sep).join('/')).filter(name => name.endsWith('.html')).sort();
  assert.ok(all.length, 'Generated public HTML is missing');
  const names = all.filter(name => !excluded.has(name));
  for (const page of knownDefects.keys()) {
    assert.ok(all.includes(page), `knownDefects lists ${page}, which the build no longer generates; prune scope.json`);
  }
  // Diagnostic filter: A11Y_PAGES="a.html,b/c.html" scans only those pages (used with --propose to re-scan one page).
  const only = process.env.A11Y_PAGES ? new Set(process.env.A11Y_PAGES.split(',').map(s => s.trim())) : null;
  if (only) for (const page of only) assert.ok(names.includes(page), `A11Y_PAGES lists unknown page ${page}`);
  const selected = names.filter(name => inShard(name, shard) && (!only || only.has(name)));
  const concurrency = Math.max(1, Number(process.env.A11Y_CONCURRENCY || 4));
  // A settled, double-checked shard takes ~200-250s on a slow machine; keep this just under the workflow's 420s
  // `timeout` so a healthy scan is never killed by its own watchdog but a hung one still is.
  const limitMs = Number(process.env.A11Y_DEADLINE_MS || (shard ? 400000 : 1800000));
  const { server, origin } = await serve(path.join(output, 'site'));
  let browser;
  const report = { engine: axe.version, tags, scope: scope.description, shard: shard ? `${shard.index}/${shard.total}` : 'all',
    pages: [], errors: [] };
  // This hard deadline also covers a stuck browser evaluation, not only navigation.
  const deadline = setTimeout(() => {
    console.error(`Accessibility scan exceeded ${limitMs / 1000} seconds`);
    process.exit(1);
  }, limitMs);
  try {
    browser = await launch();
    // Chrome occasionally dies partway through ~500 pages ("Connection closed", observed on Windows 2026-11-17:
    // one run lost every page after the 181st). Detect that, relaunch (shared across workers), and retry the
    // page. A page that still fails stays a NAMED error; a dead browser can never turn into a silent pass.
    // Timeouts are retried too: one page timed out at 30s right after a browser crash (agendas_london.html). A page
    // that times out on all three attempts is still a named error.
    const dead = /Connection closed|Target closed|Session closed|Protocol error|browser has disconnected|Timed out|timeout/i;
    let relaunching = null;
    let relaunches = 0;
    const ensureBrowser = async failed => {
      if (browser !== failed) return;                       // another worker already replaced it
      if (!relaunching) {
        relaunching = (async () => {
          relaunches++;
          assert.ok(relaunches <= 5, 'Chrome kept dying; refusing to keep relaunching');
          try { await failed.close(); } catch { /* already dead */ }
          browser = await launch();
        })().finally(() => { relaunching = null; });
      }
      await relaunching;
    };
    let next = 0;
    await Promise.all(Array.from({ length: concurrency }, async () => {
      while (next < selected.length) {
        const name = selected[next++];
        for (let attempt = 1; attempt <= 3; attempt++) {
          const used = browser;
          try { report.pages.push(await audit(used, origin, name, knownDefects.get(name) || [])); break; }
          catch (error) {
            if (dead.test(error.message) && attempt < 3) { await ensureBrowser(used); continue; }
            report.errors.push(`${name}: ${error.message}`); break;
          }
        }
      }
    }));
    report.browserRelaunches = relaunches;
    report.pages.sort((a, b) => a.page.localeCompare(b.page));
    const incomplete = report.pages.reduce((sum, page) =>
      sum + page.incomplete.reduce((n, rule) => n + rule.nodes, 0), 0);

    if (propose) {
      const review = { date: new Date().toISOString().slice(0, 10),
        scope: 'PROPOSED full-site PUBLIC static baseline. A human must inspect this before it replaces baseline.json.',
        backlog: 'PENDING REVIEW', matching: baseline.review?.matching, limitations: baseline.review?.limitations };
      const proposal = proposeBaseline(report.pages, names, review);
      await writeFile(path.join(output, 'proposed-baseline.json'), JSON.stringify(proposal) + '\n');
      await writeFile(path.join(output, 'report.json'), JSON.stringify(report, null, 2) + '\n');
      console.log(`PROPOSED baseline written to .work/proposed-baseline.json: ${report.pages.length}/${names.length} pages, ` +
        `${report.pages.reduce((n, p) => n + p.findings.length, 0)} node findings, ${report.errors.length} scan errors.`);
      for (const error of report.errors) console.log(`ERROR: ${error}`);
      if (report.errors.length) process.exitCode = 1;
      return;
    }

    const verdict = evaluate({ scanned: report.pages, errors: report.errors, baseline, names, shard });
    Object.assign(report, { regressions: verdict.regressions, resolved: verdict.resolved,
      stalePages: verdict.stalePages, newPages: verdict.newPages, existing: verdict.existing });
    report.status = verdict.failed ? 'FAIL' : 'PASS (regression gate only)';
    const summary = [
      `## PUBLIC static accessibility — ${report.status} (shard ${report.shard})`, '',
      scope.description, '',
      `Baseline backlog: ${baseline.review.backlog}`, '',
      `axe-core ${axe.version}; WCAG 2 A/AA, 2.1 A/AA, 2.2 AA and semantic best practices; contrast enabled.`,
      `Scanned ${report.pages.length}/${selected.length} pages in this shard of ${names.length} generated pages at /site/ (1280×900, Chromium).` +
        (excluded.size ? ` Documented exclusions: ${excluded.size}.` : ''),
      `Observed node findings: ${verdict.existing}; new/changed findings: ${verdict.regressions.length}; resolved baseline entries: ${verdict.resolved}.`,
      ...(report.pages.some(p => p.knownDefects.length) ? [`KNOWN PAGE DEFECTS (reviewed, still scanned): ` +
        report.pages.filter(p => p.knownDefects.length).map(p => `${p.page} -> ${p.knownDefects.join(', ')}`).join('; '), ''] : []),
      `New pages not yet in the baseline: ${verdict.newPages.length} (${verdict.newPagesWithFindings.length} with findings = FAIL).`,
      `Baseline pages no longer generated: ${verdict.stalePages.length}. Scan errors: ${report.errors.length}; incomplete node checks needing human review: ${incomplete}.`, '',
      `Stale baseline entries requiring pruning: ${verdict.resolved}. Fixed findings cannot retain an allowance.`, '',
      ...(verdict.regressions.length ? ['### New or changed findings (first 40)',
        ...verdict.regressions.slice(0, 40).map(item => `- ${item.page} — ${item.rule} — ${JSON.stringify(item.target)}`), ''] : []),
      ...(verdict.stale.length ? ['### Baseline entries no longer observed (first 40; fixed, or a flaky page)',
        ...verdict.stale.slice(0, 40).map(item => `- ${item.page} — ${item.rule} — ${JSON.stringify(item.target)} x${item.count}`), ''] : []),
      ...(verdict.stalePages.length ? ['### Pages to prune from the baseline', ...verdict.stalePages.map(p => `- ${p}`), ''] : []),
      'External requests and backend fetch/XHR are blocked. Only generated static output is served.',
      'Baseline covers exact page/rule/selector/failure multisets. Changed failures require review; resolved entries must be pruned.',
      'This does not cover responsive states, authenticated interaction, or manual WCAG requirements.',
      'JSON contains exact rule/selector/failure details and blocked origins. No HTML or owner material is uploaded.',
      ...report.errors.map(error => `\nERROR: ${error}`), '',
    ].join('\n');
    await writeFile(path.join(output, 'report.json'), JSON.stringify(report, null, 2) + '\n');
    await writeFile(path.join(output, 'summary.md'), summary);
    if (process.env.GITHUB_STEP_SUMMARY) await appendFile(process.env.GITHUB_STEP_SUMMARY, summary);
    console.log(summary);
    if (verdict.failed) process.exitCode = 1;
  } finally {
    clearTimeout(deadline);
    if (browser) await browser.close();
    await new Promise(resolve => server.close(resolve));
  }
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch(error => { console.error(error); process.exitCode = 1; });
}
