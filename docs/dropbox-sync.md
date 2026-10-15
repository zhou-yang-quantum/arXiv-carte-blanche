# Dropbox bookmark sync

The static website supports optional Dropbox sync without a separate server. Each reader authorizes their own Dropbox account. Visitors who do not connect keep using browser saves; they never write to the site owner's Dropbox.

## One-time setup for the site owner

1. Open the [Dropbox app console](https://www.dropbox.com/developers/apps/create), signed into your Dropbox account. Create an app with **Scoped access**, **App folder** access, and a unique name, such as `daily-arXiv-saves-yourname`. Do not choose Full Dropbox. Dropbox limits App folder access to the app's dedicated folder ([permissions guide](https://docs.dropboxapi.com/dropbox-api/docs/developer-resources/developer-guide)).
2. In the app's **Permissions** tab, enable `files.content.read` and `files.content.write`, then **Submit**. The website explicitly requests only these two scopes.
3. Under **Settings → OAuth 2 → Redirect URIs**, add each address you will use, exactly, including the trailing slash:

   ```text
   https://zhou-yang-quantum.github.io/daily-arXiv/
   http://localhost:8080/
   http://127.0.0.1:8080/
   http://127.0.0.1:4173/
   ```

   The first address is production. The others are optional local previews/tests. For a fork, substitute its own Pages URL. The app uses authorization-code flow with PKCE, so leave implicit grant disabled. No generated access token, app secret, or refresh token is needed ([Dropbox OAuth guide](https://docs.dropboxapi.com/dropbox-api/docs/oauth)).
4. Copy **App key** from Settings into `site/dropbox-config.json`:

   ```json
   { "app_key": "YOUR_PUBLIC_APP_KEY" }
   ```

   This key is public and safe to include in site source. **Do not paste the App secret or an access token.** An empty key leaves Dropbox connection disabled while browser saves work normally. You can send the public App key to the coding assistant to finish this setting.
5. Build with `npm run build`. For Docker preview, use `docker compose up --build -d --wait`. Publish the source changes through your normal GitHub Pages workflow when ready; changing your local preview does not update the live site.
6. Open **Saved → Dropbox sync → Connect Dropbox**. Approve access. Repeat on your other device with the same Dropbox account. The app creates `bookmarks.json` in `Apps/<your-app-folder-name>/`; do not create or share the file manually.

For personal use, the app can remain in development mode: connecting your own account on multiple devices does not require production approval. To let other readers connect their own accounts, choose **Enable additional users** in the Dropbox app console. Dropbox's current rules allow up to 500 development users, but reaching 50 linked users starts a two-week deadline to obtain production approval before new connections are frozen. Reviews normally begin at 50 linked users, with exceptions for justified early review. Consult the [production approval instructions](https://docs.dropboxapi.com/dropbox-api/docs/developer-resources/developer-guide#production-approval) before a wider launch. Set the app's privacy-policy URL to `https://zhou-yang-quantum.github.io/daily-arXiv/privacy.html` after that page is published (substitute your site URL for a fork).

## Everyday behavior

- On first connection, the browser's existing local saves merge with the account's Dropbox file. Each device needs its own connection. Subsequent account switches use separate cached lists and do not upload the previous account's bookmarks into the new one.
- Saving and removing papers works immediately in the browser, then syncs after a short delay. Returning to the page or choosing **Sync now** pulls changes from other devices. There is no continuous background polling.
- Offline changes remain in browser storage and retry when the page is online. Keep the tab open or reopen the website for syncing; there is no server-side background job.
- If two devices edit simultaneously, conditional revision writes retry and merge changes per paper. Removed entries are retained as tombstones to stop stale devices restoring them. The latest timestamp wins for the same paper, with a stable tie-breaker. Keep device clocks reasonably accurate.
- Tokens are short lived and stored only in tab session storage. Reconnect after expiry or in a new tab/session. This browser-only implementation intentionally does not keep a long-lived refresh token. Bookmarks persist in Dropbox independently of the connection.
- Disconnect stops this tab's sync and removes its token, while preserving local and Dropbox bookmark copies. For deletion and revocation steps, see the website's `privacy.html` page.
- Invalid or unsupported Dropbox files are left untouched, and errors leave the browser's saves available. Rate limits and temporary failures receive delayed retries.

No model API is involved. Dropbox does not charge for its API access; normal account storage and API limits apply ([Dropbox developer support](https://www.dropbox.com/developers/support)). No paid backend is required.

## Verification

`tests/browser/dropbox.spec.js` uses a mocked Dropbox service to check PKCE, local migration, independent devices, removals, conflict retries, account separation, expired sessions, offline recovery, and invalid files. It never uses real credentials. A real end-to-end connection still needs your app key, registered redirect URI, and interactive Dropbox approval.
