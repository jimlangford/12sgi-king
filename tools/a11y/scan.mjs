import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { createHash } from 'node:crypto';
import { readFile, realpath, stat, mkdir, writeFile, appendFile, readdir } from 'node:fs/promises';
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

export function compare(actual, baseline) {
  const key = item => JSON.stringify([item.page, item.rule, item.target, item.failure]);
  const remaining = new Map();
  for (const item of baseline) remaining.set(key(item), (remaining.get(key(item)) || 0) + 1);
  const regressions = [];
  for (const item of actual) {
    const count = remaining.get(key(item)) || 0;
    if (count) remaining.set(key(item), count - 1);
    else regressions.push(item);
  }
  return { regressions, resolved: [...remaining.values()].reduce((a, b) => a + b, 0) };
}

export function findings(page, violations) {
  return violations.flatMap(rule => rule.nodes.map(node => ({
    page, rule: rule.id, impact: rule.impact, target: node.target,
    failure: node.failureSummary, help: rule.helpUrl,
  })));
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

export async function audit(browser, origin, name) {
  const page = await browser.newPage();
  const blocked = new Set();
  const missingStyles = new Set();
  try {
    await page.setViewport({ width: 1280, height: 900, deviceScaleFactor: 1 });
    await page.emulateTimezone('Pacific/Honolulu');
    await page.emulateMediaFeatures([{ name: 'prefers-reduced-motion', value: 'reduce' }]);
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
    const result = await page.evaluate(async runTags => {
      await document.fonts.ready;
      return axe.run(document, { runOnly: { type: 'tag', values: runTags } });
    }, tags);
    assert.equal(missingStyles.size, 0, `${name}: missing local stylesheet`);
    assert.ok(result.passes.length > 0, `${name}: axe did not run`);
    return { page: name, findings: findings(name, result.violations),
      incomplete: result.incomplete.map(rule => ({ rule: rule.id, nodes: rule.nodes.length })),
      passedRules: result.passes.length, blocked: [...blocked].sort() };
  } finally {
    await page.close();
  }
}

export async function launch() {
  return puppeteer.launch({
    executablePath: process.env.CHROME_BIN || '/usr/bin/google-chrome',
    headless: true,
    args: ['--no-sandbox', '--disable-dev-shm-usage', '--disable-background-networking'],
    userDataDir: path.join(here, '.work', 'chrome-profile'),
    // Keep Chromium scratch files inside this task's workspace.
    env: { ...process.env, TMPDIR: path.join(here, '.work') },
  });
}

async function main() {
  const output = path.join(here, '.work');
  await mkdir(output, { recursive: true });
  const scope = JSON.parse(await readFile(path.join(here, 'scope.json'), 'utf8'));
  const baseline = JSON.parse(await readFile(path.join(here, 'baseline.json'), 'utf8'));
  assert.equal(baseline.axeVersion, axe.version, 'Baseline engine version must be reviewed');
  const names = (await readdir(path.join(output, 'site'), { recursive: true }))
    .filter(name => name.endsWith('.html')).sort();
  assert.ok(names.length, 'Generated public HTML is missing');
  assert.deepEqual(scope.pages, baseline.pages, 'Scope changes require explicit baseline review');
  const selected = scope.pages;
  const { server, origin } = await serve(path.join(output, 'site'));
  let browser;
  const report = { engine: axe.version, tags, scope: scope.description, pages: [], errors: [] };
  // This hard deadline also covers a stuck browser evaluation, not only navigation.
  const deadline = setTimeout(() => {
    console.error('Accessibility scan exceeded 150 seconds');
    process.exit(1);
  }, 150000);
  try {
    browser = await launch();
    let next = 0;
    await Promise.all(Array.from({ length: 1 }, async () => {
      while (next < selected.length) {
        const name = selected[next++];
        try { report.pages.push(await audit(browser, origin, name)); }
        catch (error) { report.errors.push(`${name}: ${error.message}`); }
      }
    }));
    report.pages.sort((a, b) => a.page.localeCompare(b.page));
    const actual = report.pages.flatMap(page => page.findings);
    const expected = Object.entries(baseline.targets).flatMap(([page, rules]) =>
      Object.entries(rules).flatMap(([rule, targets]) =>
        targets.map(target => ({ page, rule, target, failure: baseline.failures[rule] }))));
    Object.assign(report, compare(actual, expected));
    report.existing = actual.length;
    report.status = report.errors.length || report.regressions.length || report.resolved
      ? 'FAIL' : 'PASS (regression gate only)';
    const incomplete = report.pages.reduce((sum, page) =>
      sum + page.incomplete.reduce((n, rule) => n + rule.nodes, 0), 0);
    const summary = [
      '## PUBLIC static accessibility — ' + report.status, '',
      scope.description, '',
      `Baseline backlog: ${baseline.review.backlog}`, '',
      `axe-core ${axe.version}; WCAG 2 A/AA, 2.1 A/AA, 2.2 AA and semantic best practices; contrast enabled.`,
      `Scanned ${report.pages.length}/${selected.length} pilot pages of ${names.length} generated pages at /site/ (1280×900, Chromium).`,
      `COVERAGE GAP: ${names.length - selected.length} generated HTML files, including changes/new pages outside this pilot, are not gated.`,
      `Observed node findings: ${report.existing}; new/changed findings: ${report.regressions.length}; resolved baseline entries: ${report.resolved}.`,
      `Scan errors: ${report.errors.length}; incomplete node checks needing human review: ${incomplete}.`, '',
      `Stale baseline entries requiring pruning: ${report.resolved}. Fixed findings cannot retain an allowance.`, '',
      '| Page | Existing + new findings | Incomplete rules |',
      '| --- | ---: | ---: |',
      ...report.pages.map(page => `| ${page.page} | ${page.findings.length} | ${page.incomplete.length} |`),
      '', 'External requests and backend fetch/XHR are blocked. Only generated static output is served.',
      'Pilot baseline covers exact page/rule/selector/failure multisets. Changed failures require review; resolved entries must be pruned.',
      'This does not cover responsive states, authenticated interaction, or manual WCAG requirements.',
      'JSON contains exact rule/selector/failure details and blocked origins. No HTML or owner material is uploaded.',
      ...report.errors.map(error => `\nERROR: ${error}`), '',
    ].join('\n');
    await writeFile(path.join(output, 'report.json'), JSON.stringify(report, null, 2) + '\n');
    await writeFile(path.join(output, 'summary.md'), summary);
    if (process.env.GITHUB_STEP_SUMMARY) await appendFile(process.env.GITHUB_STEP_SUMMARY, summary);
    console.log(summary);
    if (report.errors.length || report.regressions.length || report.resolved) process.exitCode = 1;
  } finally {
    clearTimeout(deadline);
    if (browser) await browser.close();
    await new Promise(resolve => server.close(resolve));
  }
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch(error => { console.error(error); process.exitCode = 1; });
}
