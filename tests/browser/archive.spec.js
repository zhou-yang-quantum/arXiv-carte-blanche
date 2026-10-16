import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';

const originalDigest = JSON.parse(readFileSync(new URL('../fixtures/2026-10-06.json', import.meta.url), 'utf8'));

async function archiveFixture(route) {
  const response = await route.fetch();
  const data = await response.json();
  // Stable fixtures also survive an explicitly regenerated historical digest.
  data.days = [structuredClone(originalDigest)];
  return { response, data };
}

test.beforeEach(async ({ page }) => {
  await page.route('**/data/archive.json', async (route) => {
    const { response, data } = await archiveFixture(route);
    await route.fulfill({ response, json: data });
  });
});

test('dated digest, readable math, and complete paper sections', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'arXiv-2026-10-06', exact: true })).toBeVisible();
  await expect(page.locator('.paper-card')).toHaveCount(10);
  await expect(page.locator('.paper-background')).toHaveCount(10);
  await expect(page.locator('.paper-why')).toHaveCount(10);
  await expect(page.locator('.priority-tag')).toHaveCount(0);
  await expect(page.locator('.paper-label, .read-button')).toHaveCount(0);
  await expect(page.locator('.paper-tag')).toHaveCount(0);
  await expect(page.locator('.brand-symbol')).toHaveAttribute('src', './quantum-chip.svg');
  await expect(page.locator('.paper-summary').first()).toHaveCSS('font-size', '17.5px');
  await expect(page.locator('.katex').first()).toBeVisible();
  expect(await page.locator('.katex-error').count()).toBe(0);
  expect(await page.locator('.paper-summary').first().textContent()).not.toContain('ARXIVMATHPLACEHOLDER');
  await page.screenshot({ path: '.cache/desktop.png', fullPage: false });
  expect(errors).toEqual([]);
});

test('hiding the archive centers reading and remembers the choice across reloads', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto('/');
  const sidebar = page.getByRole('complementary', { name: 'Digest archive' });
  await expect(sidebar).toBeVisible();
  await page.getByRole('button', { name: 'Hide sidebar', exact: true }).click();
  await expect(sidebar).toBeHidden();
  await expect(page.getByRole('button', { name: 'Show sidebar', exact: true })).toHaveAttribute('aria-expanded', 'false');
  await expect(page.getByRole('combobox', { name: 'Choose a digest date' })).toBeVisible();
  const shell = await page.locator('.page-shell').boundingBox();
  expect(Math.abs(shell.x + shell.width / 2 - 720)).toBeLessThan(1);
  await page.reload();
  await expect(sidebar).toBeHidden();
  await page.getByRole('button', { name: 'Show sidebar', exact: true }).click();
  await expect(sidebar).toBeVisible();
  await expect(page.getByRole('combobox', { name: 'Choose a digest date' })).toBeHidden();
  await page.reload();
  await expect(sidebar).toBeVisible();
});

test('theme follows the device until selected, then persists across reloads', async ({ page }) => {
  await page.emulateMedia({ colorScheme: 'dark' });
  await page.goto('/');
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await expect(page.getByRole('button', { name: 'Switch to light mode' })).toHaveAttribute('aria-pressed', 'true');
  await expect(page.locator('body')).toHaveCSS('background-color', 'rgb(21, 29, 33)');
  await expect(page.locator('.prose').first()).toHaveCSS('color', 'rgb(208, 217, 217)');
  await page.emulateMedia({ colorScheme: 'light' });
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
  await page.getByRole('button', { name: 'Switch to dark mode' }).click();
  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await expect(page.locator('meta[name="theme-color"]')).toHaveAttribute('content', '#151d21');
  await page.getByRole('button', { name: 'Switch to light mode' }).click();
  await page.emulateMedia({ colorScheme: 'dark' });
  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
});

test('theme toggle works without browser storage and fits narrow screens', async ({ page }) => {
  await page.addInitScript(() => {
    Storage.prototype.getItem = () => { throw new Error('Storage disabled'); };
    Storage.prototype.setItem = () => { throw new Error('Storage disabled'); };
  });
  await page.emulateMedia({ colorScheme: 'light' });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.setViewportSize({ width: 320, height: 700 });
  await page.goto('/');
  await expect(page.locator('.paper-card')).toHaveCount(10);
  await page.getByRole('button', { name: 'Switch to dark mode' }).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  const nav = page.locator('.header-inner nav');
  const box = await nav.boundingBox();
  expect(box.x).toBeGreaterThanOrEqual(0);
  expect(box.x + box.width).toBeLessThanOrEqual(320);
  await page.screenshot({ path: '.cache/mobile-dark.png', fullPage: false });
  expect(errors).toEqual([]);
});

test('topic filters, existing query links, empty state, and reset without a search bar', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('.paper-card')).toHaveCount(10);
  await expect(page.getByRole('searchbox')).toHaveCount(0);
  await page.goto('/#q=Krylov');
  await expect(page.locator('.paper-card')).toHaveCount(1);
  await expect(page.locator('.paper-card h3')).toContainText('Krylov');
  await page.goto('/#q=nothing-matches-this-query');
  await expect(page.getByRole('heading', { name: 'No matching papers.' })).toBeVisible();
  await page.getByRole('button', { name: 'Clear filters' }).click();
  await expect(page.locator('.paper-card')).toHaveCount(10);
  await page.getByRole('button', { name: 'Quantum error correction', exact: true }).click();
  const count = await page.locator('.paper-card').count();
  expect(count).toBeGreaterThan(0); expect(count).toBeLessThan(10);
});

test('saved papers survive a reload without read-status controls', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'Save item 1', exact: true }).click();
  await page.reload();
  await expect(page.getByRole('button', { name: 'Unsave item 1', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByRole('button', { name: 'Mark as read', exact: true })).toHaveCount(0);
  await page.getByRole('button', { name: 'Saved 1' }).click();
  await expect(page.locator('.paper-card')).toHaveCount(1);
  await page.getByRole('button', { name: 'Unsave item 1', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'No saved papers.' })).toBeVisible();
});

test('mobile reading, deep links, preferences, and no horizontal overflow', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/#date=2026-10-06&paper=4');
  const card = page.locator('#paper-2026-10-06-4');
  await expect(card).toBeInViewport();
  await expect(page.getByRole('combobox', { name: 'Choose a digest date' })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.getByRole('button', { name: 'View selection preferences' }).click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await expect(page.getByRole('dialog')).toContainText('Bilayer graphene');
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).not.toBeVisible();
  await page.getByRole('button', { name: 'Latest', exact: true }).click();
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(0);
  await page.screenshot({ path: '.cache/mobile.png', fullPage: false });
  await page.getByRole('button', { name: 'Compact view' }).click();
  expect(await page.locator('.paper-detail[open]').count()).toBe(0);
  await page.getByRole('button', { name: 'Reading view' }).click();
  await expect(page.locator('.paper-detail[open]')).toHaveCount(10);
  await page.setViewportSize({ width: 320, height: 700 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  const actions = page.locator('.paper-actions').first();
  const buttons = actions.locator('button, a');
  const layout = await buttons.evaluateAll(elements => elements.map(element => ({
    y: element.getBoundingClientRect().y, font: getComputedStyle(element).fontSize,
  })));
  expect(layout).toHaveLength(3);
  expect(new Set(layout.map(button => button.y)).size).toBe(1);
  expect(new Set(layout.map(button => button.font)).size).toBe(1);
  await actions.getByRole('button', { name: 'Hide details', exact: true }).click();
  await expect(actions.getByRole('button', { name: 'Show details', exact: true })).toHaveAttribute('aria-expanded', 'false');
  await expect(page.locator('.paper-detail').first()).not.toHaveAttribute('open');
  await actions.getByRole('button', { name: 'Show details', exact: true }).click();
  await expect(page.locator('.paper-detail').first()).toHaveAttribute('open', '');
});

test('additional dates navigate and search across the entire archive', async ({ page }) => {
  await page.route('**/data/archive.json', async (route) => {
    const { response, data } = await archiveFixture(route);
    const older = structuredClone(data.days[0]);
    older.date = '2026-10-02'; older.title = 'arXiv-2026-10-02';
    older.papers[0].title = 'An older unique research idea';
    data.days.push(older);
    await route.fulfill({ response, json: data });
  });
  await page.goto('/');
  await expect(page.locator('.paper-card')).toHaveCount(10);
  await page.getByRole('button', { name: 'Earlier selection' }).click();
  await expect(page.getByRole('heading', { name: 'arXiv-2026-10-02', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Later selection' }).click();
  await page.goto('/#q=older%20unique');
  await expect(page.locator('.paper-card')).toHaveCount(1);
  await expect(page.locator('.paper-card')).toHaveAttribute('data-date', '2026-10-02');
  await expect(page.locator('.paper-label')).toHaveCount(0);
  const prompt = new URL(await page.getByRole('link', { name: 'Ask GPT about item 1', exact: true }).getAttribute('href')).searchParams.get('prompt');
  expect(prompt).toContain('BEGIN DIGEST ITEM: arXiv-2026-10-02');
  expect(prompt).toContain('An older unique research idea');
});

test('imported Markdown cannot run HTML or javascript links', async ({ page }) => {
  await page.route('**/data/archive.json', async (route) => {
    const { response, data } = await archiveFixture(route);
    data.days[0].papers[0].summary = '<img src=x onerror="window.badImport=true"><script>window.badImport=true</script>\n\n[Unsafe](javascript:alert(1))\n\nA safe summary.';
    await route.fulfill({ response, json: data });
  });
  await page.goto('/');
  await expect(page.locator('.paper-card')).toHaveCount(10);
  expect(await page.evaluate(() => Boolean(window.badImport))).toBe(false);
  await expect(page.locator('.paper-summary a').first()).not.toHaveAttribute('href', /javascript:/);
});

test('twenty-paper days support mobile direct links without a reading-order bar or verdicts', async ({ page }) => {
  await page.route('**/data/archive.json', async (route) => {
    const { response, data } = await archiveFixture(route);
    const day = data.days[0];
    const additional = structuredClone(day.papers).map((paper, index) => {
      paper.rank = index + 11;
      paper.id = `2610.${String(paper.rank).padStart(5, '0')}`;
      paper.title = `Additional paper ${paper.rank}`;
      paper.url = `https://arxiv.org/abs/${paper.id}`;
      delete paper.priority;
      return paper;
    });
    day.papers.push(...additional);
    day.reading_order = day.papers.map((paper) => paper.rank);
    await route.fulfill({ response, json: data });
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/#date=2026-10-06&paper=20');
  const card = page.locator('#paper-2026-10-06-20');
  await expect(card).toBeInViewport();
  await expect(page.locator('.paper-card')).toHaveCount(20);
  await expect(page.locator('.paper-detail[open]')).toHaveCount(20);
  await expect(page.locator('.priority-tag')).toHaveCount(0);
  await expect(page.locator('#paper-total')).toHaveCount(0);
  await expect(page.locator('#reading-plan, #reading-order')).toHaveCount(0);
  await page.getByRole('button', { name: 'Save item 20', exact: true }).click();
  await page.reload();
  await expect(page.getByRole('button', { name: 'Unsave item 20', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await page.getByRole('button', { name: 'Latest', exact: true }).click();
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(0);
  await page.screenshot({ path: '.cache/mobile-20.png', fullPage: false });
  await page.setViewportSize({ width: 320, height: 700 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test('Ask GPT context preserves TeX and omits redundant source links', async ({ page }) => {
  await page.route('**/data/archive.json', async (route) => {
    const { response, data } = await archiveFixture(route);
    data.days[0].papers[0].summary = 'Exact **claim**, with \\(x^2+1\\), $z=3/2$, and [a source](https://arxiv.org/abs/2610.03864). [v1 paper](https://arxiv.org/html/2610.03864v1)';
    await route.fulfill({ response, json: data });
  });
  await page.goto('/');
  const full = new URL(await page.getByRole('link', { name: 'Ask GPT about item 1', exact: true }).getAttribute('href')).searchParams.get('prompt');
  expect(full).toContain('BEGIN DIGEST ITEM: arXiv-2026-10-06');
  expect(full).toContain('Item 1.\n\n');
  expect(full).not.toContain('arXiv-2026-10-06 — Item');
  expect(full).toContain('Exact claim, with \\(x^2+1\\), $z=3/2$, and a source.');
  expect(full).not.toContain('v1 paper');
  await expect(page.getByRole('link', { name: 'v1 paper', exact: true })).toHaveCount(0);
  expect(full).not.toContain('**');
  expect(full).not.toContain('DIGESTMATH');
  await expect(page.locator('.katex-error')).toHaveCount(0);
});

test('Ask GPT opens ChatGPT with the complete selected item, TeX and original paper links', async ({ page, context }) => {
  const summary = 'Exact claim: \\(x^2+1\\), $z=3/2$, α + β & 50% #1? Café.';
  await page.route('**/data/archive.json', async (route) => {
    const { response, data } = await archiveFixture(route);
    data.days[0].papers[0].summary = summary;
    await route.fulfill({ response, json: data });
  });
  // Intercept the external destination so tests never send a prompt to ChatGPT.
  await context.route('https://chatgpt.com/**', route => route.fulfill({ contentType: 'text/html', body: '<p>ChatGPT handoff</p>' }));
  await page.goto('/');
  await page.getByRole('button', { name: 'Compact view', exact: true }).click();
  const ask = page.getByRole('link', { name: 'Ask GPT about item 1', exact: true });
  await expect(ask).toBeVisible();
  await expect(page.getByRole('button', { name: 'Copy item 1', exact: true })).toHaveCount(0);
  await expect(ask).toHaveAttribute('target', '_blank');
  await expect(ask).toHaveAttribute('rel', 'noopener noreferrer');
  const opened = page.waitForEvent('popup');
  await ask.focus();
  await page.keyboard.press('Enter');
  const chat = await opened;
  await chat.waitForURL('https://chatgpt.com/**');
  const url = new URL(chat.url());
  expect(url.origin).toBe('https://chatgpt.com');
  const prompt = url.searchParams.get('prompt');
  expect(prompt).toContain('physics and maths questions');
  expect(prompt).toContain('Refer to the original arXiv paper');
  expect(prompt).toContain('If you cannot access the paper, say so');
  expect(prompt).toContain('wait for my questions');
  expect(prompt).toContain('Original paper: https://arxiv.org/abs/2610.03864');
  expect(prompt).toContain('PDF: https://arxiv.org/pdf/2610.03864');
  expect(prompt).toContain('BEGIN DIGEST ITEM: arXiv-2026-10-06\n\nItem 1.\n\n');
  expect(prompt).toContain(originalDigest.papers[0].title);
  expect(prompt).toContain('Authors: ' + originalDigest.papers[0].authors);
  expect(prompt).toContain('Summary\n\n' + summary);
  expect(prompt).toContain('Background\n\nOrdinary \\(0\\)-form symmetry');
  expect(prompt).toContain('Why it matters?\n\nvery high.');
  expect(prompt).toContain('END DIGEST ITEM: arXiv-2026-10-06');
  expect(prompt).not.toContain(originalDigest.papers[1].title);
  expect((prompt.match(/x\^2\+1/g) || []).length).toBe(1);
  expect(prompt).not.toContain('DIGESTMATH');
  expect(await chat.evaluate(() => window.opener)).toBeNull();
});

test('a delayed audio index does not block reading or Ask GPT', async ({ page }) => {
  let pending;
  await page.route('**/data/audio/index.json', (route) => { pending = route; });
  await page.goto('/');
  await expect(page.locator('.paper-card')).toHaveCount(10);
  await expect(page.getByRole('link', { name: 'Ask GPT about item 1', exact: true })).toBeVisible();
  await pending.fulfill({ json: { days: {} } });
});

async function audioFixture(page) {
  await page.addInitScript(() => {
    window.mediaActions = {};
    Object.defineProperty(navigator, 'mediaSession', { configurable: true, value: {
      setActionHandler: (name, fn) => { window.mediaActions[name] = fn; },
      setPositionState: (state) => { window.mediaPosition = state; }, playbackState: 'none', metadata: null,
    } });
  });
  const base = 'https://github.com/zhou-yang-quantum/daily-arXiv/releases/download/audio-fixture/';
  await page.route('**/data/audio/index.json', (route) => route.fulfill({ json: { days: { '2026-10-06': {
    day: { url: base + 'day.mp3', duration: 360 },
    items: Array.from({ length: 12 }, (_, index) => ({ rank: index + 1, id: '2610.' + String(index + 1).padStart(5, '0'),
      title: 'Paper ' + (index + 1), url: base + 'item-' + String(index + 1).padStart(2, '0') + '.mp3', start: index * 30, duration: 30 })),
    playlist_url: base + 'arxiv-2026-10-06-playlist.zip',
  } } } }));
  // Actual decodable PCM exercises HTMLMediaElement, not a mocked play method.
  const frames = 360 * 8000;
  const wav = Buffer.alloc(44 + frames * 2);
  wav.write('RIFF', 0); wav.writeUInt32LE(wav.length - 8, 4); wav.write('WAVEfmt ', 8);
  wav.writeUInt32LE(16, 16); wav.writeUInt16LE(1, 20); wav.writeUInt16LE(1, 22);
  wav.writeUInt32LE(8000, 24); wav.writeUInt32LE(16000, 28); wav.writeUInt16LE(2, 32); wav.writeUInt16LE(16, 34);
  wav.write('data', 36); wav.writeUInt32LE(frames * 2, 40);
  await page.route(base + '*.mp3*', (route) => {
    const range = route.request().headers().range?.match(/bytes=(\d+)-(\d*)/);
    const start = range ? Number(range[1]) : 0;
    const end = range?.[2] ? Math.min(Number(range[2]), wav.length - 1) : wav.length - 1;
    return route.fulfill({ body: wav.subarray(start, end + 1), contentType: 'audio/wav', status: range ? 206 : 200,
      headers: { 'accept-ranges': 'bytes', ...(range ? { 'content-range': `bytes ${start}-${end}/${wav.length}` } : {}) } });
  });
  await page.route(base + '*.zip', (route) => route.fulfill({ body: Buffer.from('PK\x05\x06' + '\0'.repeat(18)),
    contentType: 'application/zip', headers: { 'content-disposition': 'attachment; filename="arxiv-2026-10-06-playlist.zip"' } }));
}

test('a twelve-track playlist supports item jumps, previous/next, speed and lock-screen controls', async ({ page }) => {
  await audioFixture(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  await page.getByRole('button', { name: 'Play day', exact: true }).click();
  await expect.poll(() => page.locator('audio').evaluate((a) => a.paused)).toBe(false);
  await expect.poll(() => page.locator('audio').evaluate((a) => a.readyState >= 2 && Number.isFinite(a.duration))).toBe(true);
  await expect(page.locator('#audio-title')).toHaveText('arXiv-2026-10-06 — Item 1 of 12');
  await expect(page.locator('#audio-track option')).toHaveCount(12);
  await expect(page.getByRole('button', { name: 'Previous track', exact: true })).toBeDisabled();
  await expect(page.getByRole('button', { name: 'Reconnect audio', exact: true })).toHaveCount(0);
  expect(await page.evaluate(() => window.mediaActions.seekbackward)).toBeNull();
  expect(await page.evaluate(() => window.mediaActions.seekforward)).toBeNull();
  await page.evaluate(() => { document.querySelector('audio').currentTime = 15; window.mediaActions.pause(); });
  await expect.poll(() => page.locator('audio').evaluate((a) => a.paused)).toBe(true);
  await expect.poll(() => page.locator('audio').evaluate((a) => a.seeking)).toBe(false);
  await expect.poll(() => page.locator('audio').evaluate((a) => a.currentTime)).toBe(15);
  await page.evaluate(() => window.mediaActions.nexttrack());
  expect(await page.locator('audio').evaluate((a) => a.currentTime)).toBeCloseTo(30, 0);
  await expect(page.locator('#audio-track')).toHaveValue('1');
  await page.evaluate(() => window.mediaActions.seekto({ seekTime: 5 }));
  expect(await page.locator('audio').evaluate((a) => a.currentTime)).toBeCloseTo(35, 0);
  expect(await page.evaluate(() => window.mediaPosition.duration)).toBe(30);
  expect(await page.evaluate(() => window.mediaPosition.position)).toBeCloseTo(5, 0);
  await page.evaluate(() => window.mediaActions.previoustrack());
  expect(await page.locator('audio').evaluate((a) => a.currentTime)).toBeCloseTo(0, 0);
  await page.getByRole('combobox', { name: 'Playback speed' }).selectOption('1.5');
  expect(await page.locator('audio').evaluate((a) => a.playbackRate)).toBe(1.5);
  await page.evaluate(() => window.mediaActions.play());
  await expect.poll(() => page.locator('audio').evaluate((a) => a.paused)).toBe(false);
  await page.getByRole('button', { name: 'Play item 4', exact: true }).click();
  await expect(page.locator('#audio-title')).toHaveText('arXiv-2026-10-06 — Item 4 of 12');
  expect(await page.locator('audio').evaluate((a) => a.currentTime)).toBeGreaterThanOrEqual(90);
  await page.getByRole('combobox', { name: 'Choose a playlist track' }).selectOption('11');
  await expect(page.getByRole('button', { name: 'Next track', exact: true })).toBeDisabled();
  await page.getByRole('button', { name: 'Previous track', exact: true }).click();
  await expect(page.locator('#audio-track')).toHaveValue('10');
  await page.getByRole('button', { name: 'Next track', exact: true }).click();
  await expect(page.locator('#audio-track')).toHaveValue('11');
  // Every item jump uses the same native stream; no between-item network load.
  await expect(page.locator('audio')).toHaveAttribute('src', /\/day.mp3$/);
  await expect.poll(() => page.locator('audio').evaluate((a) => a.paused)).toBe(false);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.setViewportSize({ width: 320, height: 700 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: '.cache/mobile-audio.png', fullPage: false });
  await page.getByRole('button', { name: 'Close audio player', exact: true }).click();
  await expect(page.locator('#audio-player')).toBeHidden();
  expect(await page.evaluate(() => navigator.mediaSession.playbackState)).toBe('none');
});

test('playing an item first opens the complete playlist at that item and advances without reloading', async ({ page }) => {
  await audioFixture(page);
  let loads = 0;
  page.on('request', (request) => { if (request.url().includes('/day.mp3')) loads++; });
  await page.goto('/');
  await page.getByRole('button', { name: 'Play item 3', exact: true }).click();
  await expect(page.locator('#audio-title')).toHaveText('arXiv-2026-10-06 — Item 3 of 12');
  await expect(page.locator('#audio-status')).toHaveText('Playing');
  expect(await page.locator('audio').evaluate((audio) => audio.currentTime)).toBeGreaterThanOrEqual(60);
  const requests = loads;
  await page.locator('audio').evaluate((audio) => { audio.currentTime = 89.9; });
  await expect(page.locator('#audio-title')).toHaveText('arXiv-2026-10-06 — Item 4 of 12');
  expect(loads).toBe(requests);
  await page.getByRole('button', { name: 'Play day', exact: true }).click();
  await expect(page.locator('#audio-track')).toHaveValue('0');
  expect(await page.locator('audio').evaluate((audio) => audio.currentTime)).toBeLessThan(3);
  await page.locator('audio').evaluate((audio) => { audio.currentTime = 359.8; });
  await expect(page.locator('#audio-status')).toHaveText('Finished');
  expect(await page.locator('audio').evaluate((audio) => audio.paused)).toBe(true);
});

test('download saves the published dated playlist ZIP and leaves playback running', async ({ page }) => {
  await startAudio(page);
  const downloaded = page.waitForEvent('download');
  await page.getByRole('link', { name: 'Download playlist (ZIP)', exact: true }).click();
  const file = await downloaded;
  expect(file.suggestedFilename()).toBe('arxiv-2026-10-06-playlist.zip');
  expect(file.url()).toContain('/arxiv-2026-10-06-playlist.zip');
  expect(await page.locator('audio').evaluate((audio) => audio.paused)).toBe(false);
});

async function startAudio(page) {
  await audioFixture(page);
  await page.goto('/');
  await page.getByRole('button', { name: 'Play day', exact: true }).click();
  await expect(page.locator('#audio-status')).toHaveText('Playing');
}

// Keep the real media element/decoder, but simulate Chrome's frozen timeline
// and insufficient-buffer signals. Desktop emulation cannot lock an Android phone.
async function stallAudio(page) {
  await page.locator('audio').evaluate((audio) => {
    const currentTime = Object.getOwnPropertyDescriptor(HTMLMediaElement.prototype, 'currentTime');
    const time = audio.currentTime;
    Object.defineProperty(audio, 'currentTime', { configurable: true, get: () => time,
      set: (value) => currentTime.set.call(audio, value) });
    Object.defineProperty(audio, 'readyState', { configurable: true, get: () => 2 });
    audio.dispatchEvent(new Event('timeupdate'));
    audio.dispatchEvent(new Event('waiting'));
  });
}

test('buffering survives time updates and reconnect preserves position and speed', async ({ page }) => {
  await page.clock.install();
  await startAudio(page);
  await page.getByRole('combobox', { name: 'Playback speed' }).selectOption('1.5');
  await page.locator('audio').evaluate((audio) => { audio.currentTime = 45; });
  await expect.poll(() => page.locator('audio').evaluate((audio) => audio.seeking)).toBe(false);
  await stallAudio(page);
  await page.locator('audio').evaluate((audio) => {
    audio.dispatchEvent(new Event('durationchange'));
    audio.dispatchEvent(new Event('timeupdate'));
  });
  await expect(page.locator('#audio-status')).toHaveText('Buffering audio…');
  expect(await page.evaluate(() => navigator.mediaSession.playbackState)).toBe('paused');
  const original = await page.locator('audio').getAttribute('src');
  await page.clock.fastForward(16000);
  await expect(page.locator('audio')).toHaveAttribute('src', /[?]reconnect=/);
  expect(await page.locator('audio').getAttribute('src')).toContain(original);
  await page.locator('audio').evaluate((audio) => { delete audio.currentTime; delete audio.readyState; });
  await expect(page.locator('#audio-status')).toHaveText('Playing');
  await expect.poll(() => page.locator('audio').evaluate((audio) => audio.currentTime)).toBeGreaterThanOrEqual(45);
  expect(await page.locator('audio').evaluate((audio) => audio.currentTime)).toBeLessThan(48);
  expect(await page.locator('audio').evaluate((audio) => audio.playbackRate)).toBe(1.5);
});

test('paused and closed audio stays stopped after stall, network and foreground events', async ({ page }) => {
  await page.clock.install();
  await startAudio(page);
  await stallAudio(page);
  await page.evaluate(() => window.mediaActions.pause());
  await expect(page.locator('#audio-status')).toHaveText('Paused');
  const src = await page.locator('audio').getAttribute('src');
  await page.clock.fastForward(60000);
  await page.evaluate(() => {
    window.dispatchEvent(new Event('online'));
    window.dispatchEvent(new Event('pageshow'));
    document.dispatchEvent(new Event('visibilitychange'));
  });
  await expect(page.locator('audio')).toHaveAttribute('src', src);
  expect(await page.locator('audio').evaluate((audio) => audio.paused)).toBe(true);
  await page.getByRole('button', { name: 'Close audio player', exact: true }).click();
  await page.clock.fastForward(60000);
  await expect(page.locator('audio')).not.toHaveAttribute('src');
  expect(await page.evaluate(() => navigator.mediaSession.playbackState)).toBe('none');
});

test('consecutive stalls stop retrying and play can resume without a reconnect button', async ({ page }) => {
  await page.clock.install();
  await startAudio(page);
  await stallAudio(page);
  for (let retry = 0; retry < 3; retry++) {
    const oldSource = await page.locator('audio').getAttribute('src');
    await page.clock.fastForward(16000);
    await expect(page.locator('audio')).not.toHaveAttribute('src', oldSource);
    await expect.poll(() => page.locator('audio').evaluate((audio) => Boolean(audio.duration))).toBe(true);
    // A new playing event without timeline progress must not reset the limit.
    await page.locator('audio').evaluate((audio) => audio.dispatchEvent(new Event('playing')));
  }
  await page.clock.fastForward(16000);
  await expect(page.locator('#audio-status')).toHaveText('Audio interrupted. Tap play to resume here.');
  const source = await page.locator('audio').getAttribute('src');
  await page.clock.fastForward(60000);
  await expect(page.locator('audio')).toHaveAttribute('src', source);
  await page.locator('audio').evaluate((audio) => { delete audio.currentTime; delete audio.readyState; });
  await page.getByRole('button', { name: 'Play audio', exact: true }).click();
  await expect(page.locator('#audio-status')).toHaveText('Playing');
});

test('lock-screen play refreshes the connection when the media still reports playing', async ({ page }) => {
  await startAudio(page);
  await page.locator('audio').evaluate((audio) => { audio.currentTime = 30; });
  await expect.poll(() => page.locator('audio').evaluate((audio) => audio.seeking)).toBe(false);
  await page.evaluate(() => window.mediaActions.play());
  await expect(page.locator('audio')).toHaveAttribute('src', /[?]reconnect=/);
  await expect(page.locator('#audio-status')).toHaveText('Playing');
  expect(await page.locator('audio').evaluate((audio) => audio.currentTime)).toBeGreaterThanOrEqual(30);
  expect(await page.locator('audio').evaluate((audio) => audio.currentTime)).toBeLessThan(33);
});

test('a reconnect waiting for metadata respects pause and cannot restore into another track', async ({ page }) => {
  await startAudio(page);
  await page.locator('audio').evaluate((audio) => { audio.currentTime = 40; });
  await expect.poll(() => page.locator('audio').evaluate((audio) => audio.seeking)).toBe(false);
  let pending;
  await page.route('**/day.mp3?reconnect=*', (route) => { pending = route; });
  await page.evaluate(() => window.mediaActions.play());
  await expect.poll(() => Boolean(pending)).toBe(true);
  await page.evaluate(() => window.mediaActions.pause());
  await expect(page.locator('#audio-status')).toHaveText('Paused');
  // Fall through to the real decodable WAV fixture once the connection returns.
  await pending.fallback();
  await expect.poll(() => page.locator('audio').evaluate((audio) => audio.currentTime)).toBeGreaterThanOrEqual(40);
  expect(await page.locator('audio').evaluate((audio) => audio.paused)).toBe(true);
  pending = null;
  await page.evaluate(() => window.mediaActions.play());
  await expect.poll(() => Boolean(pending)).toBe(true);
  await page.getByRole('button', { name: 'Play item 1', exact: true }).click();
  await pending.fallback();
  await expect(page.locator('#audio-title')).toHaveText('arXiv-2026-10-06 — Item 1 of 12');
  await expect(page.locator('#audio-status')).toHaveText('Playing');
  expect(await page.locator('audio').evaluate((audio) => audio.currentTime)).toBeLessThan(3);
});

test('offline stalls wait for the network and reconnect when it returns', async ({ page }) => {
  await page.clock.install();
  await startAudio(page);
  await stallAudio(page);
  await page.evaluate(() => Object.defineProperty(navigator, 'onLine', { configurable: true, get: () => false }));
  const src = await page.locator('audio').getAttribute('src');
  await page.clock.fastForward(30000);
  await expect(page.locator('#audio-status')).toHaveText('Waiting for connection…');
  await expect(page.locator('audio')).toHaveAttribute('src', src);
  await page.evaluate(() => {
    delete navigator.onLine;
    window.dispatchEvent(new Event('online'));
  });
  await expect(page.locator('audio')).toHaveAttribute('src', /[?]reconnect=/);
  await page.locator('audio').evaluate((audio) => { delete audio.currentTime; delete audio.readyState; });
  await expect(page.locator('#audio-status')).toHaveText('Playing');
});
