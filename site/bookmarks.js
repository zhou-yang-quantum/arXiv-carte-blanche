/* Optional Dropbox sync. Only short-lived, per-user tokens enter session storage. */
(function (root) {
  'use strict';
  const PREFIX = 'daily-arxiv:bookmarks:v2:';
  const PROFILE = PREFIX + 'profile';
  const SESSION = PREFIX + 'dropbox-session';
  const PENDING = PREFIX + 'dropbox-pkce';
  const FILE = '/bookmarks.json';
  const SCOPES = 'files.content.read files.content.write';
  const MAX_BYTES = 2 * 1024 * 1024;
  const validId = id => typeof id === 'string' && /^(?:[a-z-]+\/\d{7}|\d{4}\.\d{4,5})$/.test(id);
  const validAccount = id => typeof id === 'string' && /^dbid:[A-Za-z0-9_-]{3,200}$/.test(id);
  const recordKey = profile => PREFIX + 'records:' + profile;
  const read = (storage, key) => { try { return JSON.parse(storage.getItem(key)); } catch { return null; } };
  const write = (storage, key, value) => { try { storage.setItem(key, JSON.stringify(value)); return true; } catch { return false; } };
  const remove = (storage, key) => { try { storage.removeItem(key); } catch {} };
  const base64url = bytes => btoa(String.fromCharCode(...bytes)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  const random = () => base64url(crypto.getRandomValues(new Uint8Array(32)));
  const compare = (a, b) => a.updatedAt - b.updatedAt || (a.changeId > b.changeId ? 1 : a.changeId < b.changeId ? -1 : Number(b.saved) - Number(a.saved));

  function parseDocument(document) {
    if (!document || document.version !== 1 || !Array.isArray(document.records) || document.records.length > 20000) {
      throw new Error('The Dropbox bookmark file has an unsupported format. It has not been overwritten.');
    }
    const result = new Map();
    for (const entry of document.records) {
      if (!entry || !validId(entry.id) || typeof entry.saved !== 'boolean'
          || !Number.isSafeInteger(entry.updatedAt) || entry.updatedAt < 0
          || typeof entry.changeId !== 'string' || !/^[A-Za-z0-9_-]{1,100}$/.test(entry.changeId)
          || result.has(entry.id)) {
        throw new Error('The Dropbox bookmark file contains invalid entries. It has not been overwritten.');
      }
      result.set(entry.id, { id: entry.id, saved: entry.saved, updatedAt: entry.updatedAt, changeId: entry.changeId });
    }
    return result;
  }
  function serialize(records) {
    return JSON.stringify({ version: 1, records: [...records.values()].sort((a, b) => a.id < b.id ? -1 : a.id > b.id ? 1 : 0) });
  }
  function merge(a, b) {
    const result = new Map(a);
    for (const [id, entry] of b) if (!result.has(id) || compare(entry, result.get(id)) > 0) result.set(id, entry);
    return result;
  }

  class DropboxBookmarks extends EventTarget {
    constructor() {
      super();
      // Accessing the storage getter itself can throw in privacy-restricted browsers.
      try { this.local = localStorage; } catch { this.local = null; }
      try { this.sessionStorage = sessionStorage; } catch { this.sessionStorage = null; }
      const session = read(this.sessionStorage, SESSION);
      this.session = session && validAccount(session.accountId) && typeof session.accessToken === 'string'
        && Number.isFinite(session.expiresAt) && typeof session.appKey === 'string' ? session : null;
      const previousProfile = read(this.local, PROFILE);
      this.profile = this.session?.accountId || (validAccount(previousProfile) ? previousProfile : 'local');
      this.records = this.loadRecords(this.profile);
      this.saved = new Set([...this.records.values()].filter(entry => entry.saved).map(entry => entry.id));
      this.generation = 0;
      this.controllers = new Set();
      this.ui = { state: 'loading', message: 'Checking Dropbox availability…' };
      this.appKey = '';
      this.callback = this.consumeCallback();
      this.ready = this.initialize();
      window.addEventListener('online', () => this.sync());
      window.addEventListener('focus', () => { if (document.visibilityState === 'visible') this.sync(); });
      document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') this.sync(); });
      window.addEventListener('storage', event => {
        if (event.key !== recordKey(this.profile) || !event.newValue) return;
        try {
          const incoming = parseDocument(JSON.parse(event.newValue));
          const combined = merge(this.records, incoming);
          if (serialize(combined) !== serialize(this.records)) { this.apply(combined, 'storage'); this.schedule(); }
          // A stale tab may write last and close before processing our newer
          // storage event. Restore the merged cache even if this tab is current.
          else if (serialize(combined) !== serialize(incoming)) write(this.local, recordKey(this.profile), JSON.parse(serialize(combined)));
        } catch {}
      });
    }
    loadRecords(profile) {
      const stored = read(this.local, recordKey(profile));
      if (stored) { try { return parseDocument(stored); } catch { return new Map(); } }
      const result = new Map();
      if (profile === 'local') {
        const legacy = read(this.local, 'daily-arxiv:saved:v1');
        for (const id of Array.isArray(legacy) ? legacy : []) if (validId(id)) {
          result.set(id, { id, saved: true, updatedAt: 0, changeId: 'legacy' });
        }
      }
      write(this.local, recordKey(profile), JSON.parse(serialize(result)));
      return result;
    }
    apply(records, origin) {
      const previous = [...this.saved].sort().join('|');
      this.records = records;
      this.saved.clear();
      for (const entry of records.values()) if (entry.saved) this.saved.add(entry.id);
      const stored = write(this.local, recordKey(this.profile), JSON.parse(serialize(records)));
      if ([...this.saved].sort().join('|') !== previous) this.dispatchEvent(new CustomEvent('change', { detail: { origin } }));
      return stored;
    }
    setStatus(state, message) {
      this.ui = { state, message };
      this.dispatchEvent(new Event('status'));
    }
    get connected() { return Boolean(this.session && this.session.expiresAt > Date.now()); }
    toggle(id) {
      if (!validId(id)) return false;
      let updatedAt = Date.now();
      for (const entry of this.records.values()) updatedAt = Math.max(updatedAt, entry.updatedAt + 1);
      const records = new Map(this.records);
      const changeId = root.crypto?.randomUUID?.() || Date.now().toString(36) + '-' + Math.random().toString(36).slice(2);
      records.set(id, { id, saved: !this.saved.has(id), updatedAt, changeId });
      const stored = this.apply(records, 'local');
      if (this.session) this.schedule();
      return stored;
    }
    consumeCallback() {
      const url = new URL(location.href);
      if (!url.searchParams.has('code') && !url.searchParams.has('error')) return null;
      const pending = read(this.sessionStorage, PENDING);
      const callback = { code: url.searchParams.get('code'), error: url.searchParams.get('error'), state: url.searchParams.get('state'), pending };
      for (const key of ['code', 'state', 'error', 'error_description']) url.searchParams.delete(key);
      if (pending && callback.state === pending.state && typeof pending.returnHash === 'string' && pending.returnHash.startsWith('#')) url.hash = pending.returnHash;
      history.replaceState(null, '', url.pathname + url.search + url.hash);
      return callback;
    }
    async initialize() {
      try {
        const response = await this.fetch('./dropbox-config.json');
        const config = response.ok ? await response.json() : null;
        if (typeof config?.app_key === 'string' && /^[A-Za-z0-9]{5,100}$/.test(config.app_key)) this.appKey = config.app_key;
      } catch {}
      if (!this.appKey) {
        this.session = null;
        remove(this.sessionStorage, SESSION);
        this.setStatus('unconfigured', 'Dropbox sync is not available on this site yet. Saved papers stay in this browser.');
        return;
      }
      if (this.session?.appKey !== this.appKey && this.session) this.disconnect();
      if (this.callback) {
        try { await this.finishAuthorization(this.callback); }
        catch (error) { this.setStatus('error', error.message); }
        this.callback = null;
      } else if (this.session && !this.connected) this.expire();
      else this.setStatus('local', 'Saved papers are stored in this browser. Connect Dropbox to sync across devices.');
      if (this.connected) { this.armExpiry(); this.sync(); }
    }
    async connect() {
      await this.ready;
      if (!this.appKey) return;
      try {
        if (!root.crypto?.subtle) throw new Error('Dropbox needs a secure connection. Open the HTTPS website or a localhost preview.');
        const verifier = random();
        const state = random();
        const redirectUri = new URL('./', location.href).href;
        const challenge = base64url(new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier))));
        if (!write(this.sessionStorage, PENDING, { verifier, state, appKey: this.appKey, redirectUri, returnHash: location.hash, createdAt: Date.now() })) {
          throw new Error('This browser cannot keep the Dropbox connection request. Allow session storage, or continue using local saves.');
        }
        const url = new URL('https://www.dropbox.com/oauth2/authorize');
        url.search = new URLSearchParams({ client_id: this.appKey, response_type: 'code', redirect_uri: redirectUri,
          code_challenge_method: 'S256', code_challenge: challenge, state, token_access_type: 'online', scope: SCOPES }).toString();
        location.assign(url.href);
      } catch (error) { this.setStatus('error', error.message); }
    }
    async finishAuthorization(callback) {
      const pending = callback.pending;
      if (!pending || !callback.state || callback.state !== pending.state || pending.appKey !== this.appKey
          || typeof pending.verifier !== 'string' || Date.now() - pending.createdAt > 15 * 60000
          || !Number.isFinite(pending.createdAt) || pending.createdAt > Date.now() + 60000
          || pending.redirectUri !== new URL('./', location.href).href) {
        throw new Error('Could not verify the Dropbox connection. Please connect again.');
      }
      remove(this.sessionStorage, PENDING);
      if (callback.error || !callback.code) throw new Error('Dropbox connection was cancelled. Your saved papers are still here.');
      const response = await this.fetch('https://api.dropboxapi.com/oauth2/token', {
        method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({ grant_type: 'authorization_code', code: callback.code, client_id: this.appKey,
          code_verifier: pending.verifier, redirect_uri: pending.redirectUri }),
      });
      if (!response.ok) throw new Error('Dropbox could not complete the connection. Please connect again.');
      const token = await response.json();
      if (typeof token.access_token !== 'string' || !token.access_token || !validAccount(token.account_id)
          || !Number.isFinite(token.expires_in) || token.expires_in <= 0) throw new Error('Dropbox returned an incomplete connection. Please connect again.');
      this.generation++;
      const accountRecords = this.loadRecords(token.account_id);
      // Only unbound browser saves are imported. Switching accounts never uploads
      // the previous account's bookmarks into the new account.
      const records = this.profile === 'local' ? merge(accountRecords, this.records) : accountRecords;
      this.profile = token.account_id;
      write(this.local, PROFILE, this.profile);
      this.apply(records, 'profile');
      this.session = { accountId: token.account_id, accessToken: token.access_token,
        expiresAt: Date.now() + Math.min(token.expires_in, 86400) * 1000, appKey: this.appKey };
      write(this.sessionStorage, SESSION, this.session);
      this.setStatus('pending', 'Connected to Dropbox. Syncing saved papers…');
    }
    armExpiry() {
      clearTimeout(this.expiryTimer);
      if (this.session) this.expiryTimer = setTimeout(() => this.expire(), Math.max(0, this.session.expiresAt - Date.now()));
    }
    clearConnection() {
      this.generation++;
      this.session = null;
      this.again = false;
      this.retryAt = 0;
      for (const controller of this.controllers) controller.abort();
      clearTimeout(this.timer);
      clearTimeout(this.expiryTimer);
      remove(this.sessionStorage, SESSION);
      remove(this.sessionStorage, PENDING);
    }
    disconnect() {
      this.clearConnection();
      this.setStatus('local', 'Dropbox is disconnected. This account’s saved papers remain on this device.');
    }
    expire() {
      this.clearConnection();
      this.setStatus('expired', 'Your Dropbox connection expired. Reconnect to sync; your changes are saved in this browser.');
    }
    schedule(delay = 650) {
      if (!this.session) return;
      this.again = true;
      clearTimeout(this.timer);
      if (!this.running) this.setStatus('pending', 'Saved in this browser. Dropbox sync is pending.');
      this.timer = setTimeout(() => this.sync(), Math.max(delay, (this.retryAt || 0) - Date.now()));
    }
    sync() {
      if (!this.appKey || !this.session) return Promise.resolve(false);
      if (!this.connected) { this.expire(); return Promise.resolve(false); }
      if (this.running) { this.again = true; return this.running; }
      if (!navigator.onLine) { this.setStatus('offline', 'You are offline. Changes are saved here and will sync when the connection returns.'); return Promise.resolve(false); }
      if (this.retryAt > Date.now()) return Promise.resolve(false);
      clearTimeout(this.timer);
      const context = { generation: this.generation, profile: this.profile, token: this.session.accessToken };
      this.running = this.syncLoop(context).finally(() => { this.running = null; if (this.again && this.current(context)) this.schedule(); });
      return this.running;
    }
    current(context) { return context.generation === this.generation && context.profile === this.profile && this.session?.accessToken === context.token; }
    async fetch(url, options = {}) {
      const controller = new AbortController();
      this.controllers.add(controller);
      const timeout = setTimeout(() => controller.abort(), 20000);
      try { return await fetch(url, { credentials: 'omit', cache: 'no-store', referrerPolicy: 'no-referrer', ...options, signal: controller.signal }); }
      finally { clearTimeout(timeout); this.controllers.delete(controller); }
    }
    async apiError(response) {
      if (response.status === 401) { this.expire(); throw new Error('Your Dropbox connection expired. Reconnect to sync your changes.'); }
      if (response.status === 429) {
        const retry = response.headers.get('Retry-After');
        const seconds = Number(retry);
        const delay = retry && Number.isFinite(seconds) ? seconds * 1000 : retry && Number.isFinite(Date.parse(retry)) ? Date.parse(retry) - Date.now() : 60000;
        this.retryAt = Date.now() + Math.max(1000, Math.min(delay, 3600000));
        throw new Error('Dropbox is busy. Your changes are saved here; sync will retry shortly.');
      }
      if (response.status === 403) throw new Error('Dropbox denied file access. Check the app permissions and reconnect. Your saves remain here.');
      if (response.status >= 500) {
        this.retryAt = Date.now() + 30000;
        throw new Error('Dropbox is temporarily unavailable. Your changes are saved here; sync will retry.');
      }
      throw new Error('Dropbox could not sync this file. Your changes are saved here. Try syncing again.');
    }
    async syncLoop(context) {
      this.setStatus('syncing', 'Syncing saved papers with Dropbox…');
      try {
        do {
          this.again = false;
          let complete = false;
          for (let attempt = 0; attempt < 4; attempt++) {
            if (!this.current(context)) return false;
            const headers = { Authorization: 'Bearer ' + context.token, 'Dropbox-API-Arg': JSON.stringify({ path: FILE }) };
            const download = await this.fetch('https://content.dropboxapi.com/2/files/download', { method: 'POST', headers });
            if (!this.current(context)) return false;
            let remote = new Map(), revision = null;
            if (download.ok) {
              const metadata = JSON.parse(download.headers.get('Dropbox-API-Result') || '{}');
              if (typeof metadata.rev !== 'string' || !metadata.rev || metadata.size > MAX_BYTES) throw new Error('The Dropbox bookmark file could not be verified. It has not been overwritten.');
              const text = await download.text();
              if (text.length > MAX_BYTES) throw new Error('The Dropbox bookmark file is too large to sync. It has not been overwritten.');
              let parsed;
              try { parsed = JSON.parse(text); }
              catch { throw new Error('The Dropbox bookmark file is not valid JSON. It has not been overwritten.'); }
              remote = parseDocument(parsed);
              revision = metadata.rev;
            } else if (download.status === 409) {
              const error = await download.json();
              if (!this.current(context)) return false;
              if (!String(error.error_summary).startsWith('path/not_found/')) await this.apiError(download);
            } else await this.apiError(download);
            if (!this.current(context)) return false;
            // Re-read in-memory records after every await so edits made during a
            // download or a conflict retry are never replaced by an older snapshot.
            this.apply(merge(this.records, remote), 'sync');
            const body = serialize(this.records);
            if (revision && body === serialize(remote)) { complete = true; break; }
            const upload = await this.fetch('https://content.dropboxapi.com/2/files/upload', {
              method: 'POST', headers: { Authorization: 'Bearer ' + context.token, 'Content-Type': 'application/octet-stream',
                'Dropbox-API-Arg': JSON.stringify({ path: FILE, mode: revision ? { '.tag': 'update', update: revision } : { '.tag': 'add' },
                  autorename: false, strict_conflict: true, mute: true }) }, body,
            });
            if (!this.current(context)) return false;
            if (upload.status === 409) {
              const error = await upload.json();
              if (!this.current(context)) return false;
              if (String(error.error_summary).includes('conflict')) continue;
            }
            if (!upload.ok) await this.apiError(upload);
            const metadata = await upload.json();
            if (!metadata.rev) throw new Error('Dropbox did not confirm the saved file. Please sync again.');
            complete = true;
            break;
          }
          if (!complete) { this.retryAt = Date.now() + 30000; throw new Error('Another device is updating your bookmarks. Changes are saved here; sync will retry.'); }
        } while (this.again && this.current(context));
        if (this.current(context)) this.setStatus('synced', 'Saved papers are synced with Dropbox.');
        return true;
      } catch (error) {
        if (this.current(context)) {
          this.again = false;
          const network = error instanceof TypeError || error.name === 'AbortError';
          if (network) this.retryAt = Date.now() + 30000;
          this.setStatus(navigator.onLine ? 'error' : 'offline', network ? 'Dropbox could not be reached. Changes are saved here and will retry.' : error.message);
          if (this.retryAt > Date.now()) this.timer = setTimeout(() => this.sync(), this.retryAt - Date.now() + 10);
        }
        return false;
      }
    }
  }
  root.DropboxBookmarks = DropboxBookmarks;
})(globalThis);
