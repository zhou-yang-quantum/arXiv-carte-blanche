import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';

const digest = JSON.parse(readFileSync(new URL('../fixtures/2026-10-06.json', import.meta.url), 'utf8'));
const ids = digest.papers.map(paper => paper.id);
const prefix = 'daily-arxiv:bookmarks:v2:';
const entry = (id, saved = true, updatedAt = Date.now(), changeId = 'remote') => ({ id, saved, updatedAt, changeId });

// A revision-aware service shared by independent browser contexts. All Dropbox
// traffic is intercepted; these tests never sign into or modify a real account.
class DropboxMock {
  files = new Map();
  uploads = [];
  tokens = [];
  authorizations = [];
  downloads = 0;
  serial = 0;
  account = 'dbid:readerA';
  nextDownloadStatus = 0;
  conflict = null;
  invalidState = false;
  cancel = false;
  blockedDownload = null;

  put(account, records) {
    this.files.set(account, { rev: String(++this.serial), document: { version: 1, records } });
  }
  records(account = 'dbid:readerA') { return this.files.get(account)?.document.records || []; }
  saved(account = 'dbid:readerA') { return this.records(account).filter(item => item.saved).map(item => item.id).sort(); }

  async install(context) {
    await context.route('**/data/archive.json', async route => {
      const response = await route.fetch();
      const data = await response.json();
      data.days = [structuredClone(digest)];
      await route.fulfill({ response, json: data });
    });
    await context.route('**/dropbox-config.json', route => route.fulfill({ json: { app_key: 'testappkey123456' } }));
    await context.route('https://www.dropbox.com/oauth2/authorize?**', async route => {
      const params = new URL(route.request().url()).searchParams;
      this.authorizations.push(Object.fromEntries(params));
      const url = new URL(params.get('redirect_uri'));
      url.searchParams.set(this.cancel ? 'error' : 'code', this.cancel ? 'access_denied' : 'test-code');
      url.searchParams.set('state', this.invalidState ? 'incorrect-state' : params.get('state'));
      await route.fulfill({ status: 302, headers: { Location: url.href }, body: '' });
    });
    await context.route('https://api.dropboxapi.com/oauth2/token', async route => {
      this.tokens.push(Object.fromEntries(new URLSearchParams(route.request().postData())));
      await route.fulfill({ json: { access_token: 'token-' + this.account, account_id: this.account, expires_in: 14400 } });
    });
    await context.route('https://content.dropboxapi.com/2/files/**', async route => {
      const request = route.request();
      if (request.method() === 'OPTIONS') {
        await route.fulfill({ headers: { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*' } });
        return;
      }
      const account = request.headers().authorization.replace('Bearer token-', '');
      const args = JSON.parse(request.headers()['dropbox-api-arg']);
      expect(args.path).toBe('/bookmarks.json');
      const headers = { 'Access-Control-Allow-Origin': '*', 'Access-Control-Expose-Headers': 'Dropbox-API-Result, Retry-After' };
      if (request.url().endsWith('/download')) {
        this.downloads++;
        if (this.blockedDownload) await this.blockedDownload;
        if (this.nextDownloadStatus) {
          const status = this.nextDownloadStatus;
          this.nextDownloadStatus = 0;
          await route.fulfill({ status, headers: { ...headers, 'Retry-After': '60' }, json: { error_summary: 'test-error' } });
          return;
        }
        const file = this.files.get(account);
        if (!file) await route.fulfill({ status: 409, headers, json: { error_summary: 'path/not_found/...' } });
        else {
          const body = typeof file.document === 'string' ? file.document : JSON.stringify(file.document);
          await route.fulfill({ headers: { ...headers, 'Dropbox-API-Result': JSON.stringify({ rev: file.rev, size: body.length }) }, body });
        }
        return;
      }
      if (this.conflict) { this.conflict(account); this.conflict = null; }
      const file = this.files.get(account);
      const document = JSON.parse(request.postData());
      this.uploads.push({ account, args, document });
      if ((args.mode['.tag'] === 'add' && file) || (args.mode['.tag'] === 'update' && file?.rev !== args.mode.update)) {
        await route.fulfill({ status: 409, headers, json: { error_summary: 'path/conflict/file/...' } });
        return;
      }
      const rev = String(++this.serial);
      this.files.set(account, { rev, document });
      await route.fulfill({ headers, json: { rev } });
    });
  }
}

async function openSettings(page) {
  if (await page.locator('#saved-button').getAttribute('aria-pressed') !== 'true') await page.locator('#saved-button').click();
  if (!await page.locator('#sync-dialog').isVisible()) await page.getByRole('button', { name: 'Dropbox sync', exact: true }).click();
}
async function connect(page) {
  await openSettings(page);
  await page.locator('#connect-dropbox').click();
  await expect(page.locator('#save-storage-status')).toHaveText('Saved papers are synced with Dropbox.');
  await expect(page.locator('#saved-button')).toHaveAttribute('aria-pressed', 'true');
  expect(new URL(page.url()).search).toBe('');
}
async function sync(page) {
  await openSettings(page);
  await page.getByRole('button', { name: 'Sync now', exact: true }).click();
  await expect(page.locator('#sync-status')).toHaveText('Saved papers are synced with Dropbox.');
  await page.getByRole('button', { name: 'Close Dropbox sync' }).click();
}
async function toggle(page, rank) {
  if (await page.locator('#sync-dialog').isVisible()) await page.locator('#close-sync').click();
  await page.locator('#latest-button').click();
  await page.locator(`.paper-card[data-rank="${rank}"] [data-action="save"]`).click();
}

test('unconfigured sync keeps local saves and fits a narrow screen', async ({ page }) => {
  await page.route('**/dropbox-config.json', route => route.fulfill({ json: { app_key: '' } }));
  await page.setViewportSize({ width: 320, height: 700 });
  await page.goto('/');
  await toggle(page, 1);
  await openSettings(page);
  await expect(page.locator('#connect-dropbox')).toBeDisabled();
  await expect(page.locator('#sync-status')).toContainText('not available on this site yet');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  const box = await page.locator('#sync-dialog').boundingBox();
  expect(box.x).toBeGreaterThanOrEqual(0);
  expect(box.x + box.width).toBeLessThanOrEqual(320);
  await page.screenshot({ path: '.cache/dropbox-mobile.png' });
  await page.reload();
  await expect(page.locator('#saved-count')).toHaveText('1');
});

test('PKCE connects, imports legacy saves, and stores no persistent access token', async ({ page, context }) => {
  const cloud = new DropboxMock();
  await cloud.install(context);
  await page.addInitScript(id => {
    if (!localStorage.getItem('legacy-seeded')) {
      localStorage.setItem('daily-arxiv:saved:v1', JSON.stringify([id]));
      localStorage.setItem('legacy-seeded', 'true');
    }
  }, ids[0]);
  await page.goto('/');
  await expect(page.locator('#saved-count')).toHaveText('1');
  await connect(page);
  expect(cloud.saved()).toEqual([ids[0]]);
  const auth = cloud.authorizations[0], token = cloud.tokens[0];
  expect(auth.code_challenge_method).toBe('S256');
  expect(auth.token_access_type).toBe('online');
  expect(auth.scope).toBe('files.content.read files.content.write');
  expect(auth.state).toMatch(/^[\w-]{43}$/);
  expect(createHash('sha256').update(token.code_verifier).digest('base64url')).toBe(auth.code_challenge);
  expect(token).toEqual(expect.objectContaining({ grant_type: 'authorization_code', client_id: auth.client_id, redirect_uri: auth.redirect_uri }));
  expect(token).not.toHaveProperty('client_secret');
  const storage = await page.evaluate(() => ({ local: JSON.stringify(localStorage), session: JSON.stringify(sessionStorage) }));
  expect(storage.local).not.toContain('token-dbid');
  expect(storage.session).toContain('token-dbid:readerA');
  expect(storage.session).not.toContain('code_verifier');
  await page.reload();
  await expect(page.locator('#save-storage-status')).toHaveText('Saved papers are synced with Dropbox.');
  expect(cloud.authorizations).toHaveLength(1);
});

test('independent devices merge changes, retry a revision conflict, and preserve removals', async ({ browser }) => {
  const cloud = new DropboxMock();
  const a = await browser.newContext(), b = await browser.newContext();
  try {
    await cloud.install(a); await cloud.install(b);
    const first = await a.newPage(), second = await b.newPage();
    await first.goto('/'); await second.goto('/');
    await toggle(first, 1); await connect(first); await connect(second);
    await second.evaluate(() => { Object.defineProperty(navigator, 'onLine', { configurable: true, value: false }); });
    await toggle(second, 2);
    await second.evaluate(() => bookmarkSync.sync());
    await toggle(first, 1); // remove a previously synced bookmark
    await sync(first);
    await expect.poll(() => cloud.saved()).toEqual([]);
    cloud.conflict = account => cloud.put(account, [...cloud.records(account), entry(ids[2])]);
    await second.evaluate(() => { Object.defineProperty(navigator, 'onLine', { configurable: true, value: true }); window.dispatchEvent(new Event('online')); });
    await expect(second.locator('#save-storage-status')).toHaveText('Saved papers are synced with Dropbox.');
    expect(cloud.saved()).toEqual([ids[1], ids[2]].sort());
    expect(cloud.records().find(item => item.id === ids[0]).saved).toBe(false);
    expect(cloud.uploads.filter(upload => upload.args.mode['.tag'] === 'update').length).toBeGreaterThanOrEqual(3);
    for (const upload of cloud.uploads) {
      expect(upload.args.strict_conflict).toBe(true);
      expect(upload.args.autorename).toBe(false);
    }
    await sync(first);
    await expect(first.locator('#saved-count')).toHaveText('2');
    await expect(first.locator(`.paper-card[data-id="${ids[0]}"]`)).toHaveCount(0);
  } finally { await a.close(); await b.close(); }
});

test('switching Dropbox accounts isolates bookmarks and preserves disconnected edits', async ({ page, context }) => {
  const cloud = new DropboxMock();
  await cloud.install(context);
  await page.goto('/'); await toggle(page, 1); await connect(page);
  await openSettings(page); await page.getByRole('button', { name: 'Disconnect', exact: true }).click();
  await toggle(page, 2); // queued for reader A, even while disconnected
  cloud.account = 'dbid:readerB';
  cloud.put(cloud.account, [entry(ids[2])]);
  await connect(page);
  await expect(page.locator('#saved-count')).toHaveText('1');
  expect(cloud.saved('dbid:readerB')).toEqual([ids[2]]);
  expect(cloud.uploads.filter(upload => upload.account === 'dbid:readerB')).toHaveLength(0);
  await openSettings(page); await page.getByRole('button', { name: 'Disconnect', exact: true }).click();
  cloud.account = 'dbid:readerA';
  await connect(page);
  expect(cloud.saved()).toEqual([ids[0], ids[1]].sort());
  await expect(page.locator('#saved-count')).toHaveText('2');
});

for (const kind of ['state mismatch', 'cancelled']) {
  test(`OAuth ${kind} keeps local bookmarks and never exchanges a token`, async ({ page, context }) => {
    const cloud = new DropboxMock();
    cloud.invalidState = kind === 'state mismatch'; cloud.cancel = kind === 'cancelled';
    await cloud.install(context);
    await page.goto('/'); await toggle(page, 1); await openSettings(page);
    await Promise.all([page.waitForEvent('domcontentloaded'), page.locator('#connect-dropbox').click()]);
    await page.evaluate(() => bookmarkSync.ready);
    await expect(page.locator('#save-storage-status')).toHaveText('Saved papers stay in this browser.');
    await openSettings(page);
    await expect(page.locator('#sync-status')).toContainText(kind === 'cancelled' ? 'cancelled' : 'Could not verify');
    await expect(page.locator('#saved-count')).toHaveText('1');
    expect(cloud.tokens).toHaveLength(0);
    expect(cloud.uploads).toHaveLength(0);
    expect(new URL(page.url()).search).toBe('');
  });
}

test('401 expiry retains local edits for reconnect without repeating failed requests', async ({ page, context }) => {
  const cloud = new DropboxMock();
  await cloud.install(context);
  await page.goto('/'); await connect(page);
  cloud.nextDownloadStatus = 401;
  await toggle(page, 1);
  await openSettings(page);
  await expect(page.locator('#sync-status')).toContainText('connection expired');
  await expect(page.locator('#connect-dropbox')).toHaveText('Reconnect Dropbox');
  const count = cloud.downloads;
  await page.evaluate(() => window.dispatchEvent(new Event('focus')));
  expect(cloud.downloads).toBe(count);
  expect(await page.evaluate(key => sessionStorage.getItem(key), prefix + 'dropbox-session')).toBeNull();
  await connect(page);
  expect(cloud.saved()).toEqual([ids[0]]);
});

test('malformed remote file is never overwritten and local saves stay usable', async ({ page, context }) => {
  const cloud = new DropboxMock();
  cloud.files.set(cloud.account, { rev: 'bad-file', document: '{invalid json' });
  await cloud.install(context);
  await page.goto('/'); await toggle(page, 1); await openSettings(page);
  await page.locator('#connect-dropbox').click();
  await expect(page.locator('#save-storage-status')).toContainText('not valid JSON');
  await expect(page.locator('#saved-count')).toHaveText('1');
  expect(cloud.uploads).toHaveLength(0);
  cloud.put(cloud.account, [entry(ids[1])]);
  await sync(page);
  expect(cloud.saved()).toEqual([ids[0], ids[1]].sort());
});

test('rate limits delay retries while saves remain local', async ({ page, context }) => {
  const cloud = new DropboxMock();
  await cloud.install(context);
  await page.goto('/'); await connect(page);
  await page.clock.install();
  cloud.nextDownloadStatus = 429;
  await toggle(page, 1);
  await page.clock.runFor(700);
  await expect(page.locator('#save-storage-status')).toContainText('Dropbox is busy');
  const count = cloud.downloads;
  await page.evaluate(() => window.dispatchEvent(new Event('focus')));
  await page.clock.runFor(1000);
  expect(cloud.downloads).toBe(count);
  await expect(page.locator('#saved-count')).toHaveText('1');
  await page.clock.runFor(60000);
  await expect(page.locator('#save-storage-status')).toHaveText('Saved papers are synced with Dropbox.');
  expect(cloud.saved()).toEqual([ids[0]]);
});

test('disconnect during a download prevents a late response changing local bookmarks', async ({ page, context }) => {
  const cloud = new DropboxMock();
  await cloud.install(context);
  await page.goto('/'); await connect(page);
  cloud.put(cloud.account, [entry(ids[2])]);
  let release;
  cloud.blockedDownload = new Promise(resolve => { release = resolve; });
  const downloads = cloud.downloads;
  await page.evaluate(() => { bookmarkSync.sync(); });
  await expect.poll(() => cloud.downloads).toBeGreaterThan(downloads);
  await openSettings(page); await page.getByRole('button', { name: 'Disconnect', exact: true }).click();
  release();
  await expect(page.locator('#sync-status')).toContainText('disconnected');
  await page.evaluate(() => bookmarkSync.running);
  await expect(page.locator('#saved-count')).toHaveText('0');
  expect(cloud.uploads).toHaveLength(1); // only the initial empty file
});

test('same-browser tabs share local edits without needing a Dropbox connection', async ({ page, context }) => {
  const cloud = new DropboxMock();
  await cloud.install(context);
  const other = await context.newPage();
  await page.goto('/'); await other.goto('/');
  await toggle(page, 1);
  await expect(other.locator('#saved-count')).toHaveText('1');
  await expect(other.getByRole('button', { name: 'Unsave item 1', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await toggle(other, 2);
  await expect(page.locator('#saved-count')).toHaveText('2');
  await toggle(other, 1);
  await expect(page.locator('#saved-count')).toHaveText('1');
  // A stale writer must not replace a newer cache merely by writing last.
  await other.evaluate(key => localStorage.setItem(key, JSON.stringify({ version: 1, records: [] })), prefix + 'records:local');
  await expect.poll(() => page.evaluate(key => JSON.parse(localStorage.getItem(key)).records.length, prefix + 'records:local')).toBe(2);
  await page.reload();
  await expect(page.getByRole('button', { name: 'Save item 1', exact: true })).toHaveAttribute('aria-pressed', 'false');
  expect(cloud.uploads).toHaveLength(0);
});

test('time-based expiry stops sync until reconnect and retains pending edits', async ({ page, context }) => {
  const cloud = new DropboxMock();
  await cloud.install(context);
  await page.clock.install();
  await page.goto('/'); await connect(page);
  const count = cloud.downloads;
  await page.clock.runFor(14400001);
  await expect(page.locator('#save-storage-status')).toContainText('connection expired');
  await toggle(page, 2);
  await page.clock.runFor(1000);
  expect(cloud.downloads).toBe(count);
  await expect(page.locator('#saved-count')).toHaveText('1');
  await connect(page);
  expect(cloud.saved()).toEqual([ids[1]]);
});

test('unsupported remote versions and duplicate entries are left untouched', async ({ page, context }) => {
  const cloud = new DropboxMock();
  cloud.files.set(cloud.account, { rev: 'future-file', document: { version: 2, records: [] } });
  await cloud.install(context);
  await page.goto('/'); await toggle(page, 1); await openSettings(page);
  await page.locator('#connect-dropbox').click();
  await expect(page.locator('#save-storage-status')).toContainText('unsupported format');
  cloud.put(cloud.account, [entry(ids[2]), entry(ids[2])]);
  await openSettings(page); await page.locator('#sync-now').click();
  await expect(page.locator('#sync-status')).toContainText('invalid entries');
  expect(cloud.uploads).toHaveLength(0);
  await expect(page.locator('#saved-count')).toHaveText('1');
});
