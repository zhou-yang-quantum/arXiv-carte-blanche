# Repository rename

The project repository is **zhou-yang-quantum/arXiv-carte-blanche**. The local
checkout folder can keep its old name so existing Codex project permissions,
scheduled tasks, watcher paths, and cached speech files continue to work.

## Canonical addresses

- [Repository](https://github.com/zhou-yang-quantum/arXiv-carte-blanche)
- [Website](https://zhou-yang-quantum.github.io/arXiv-carte-blanche/)
- [Bookmark privacy](https://zhou-yang-quantum.github.io/arXiv-carte-blanche/privacy.html)

`tools/project.py` defines the repository and website used by the publisher,
source reader, audio generator, and archive builder. The browser's audio player
accepts the current repository and the exact previous repository, normalizing
old manifest links to the new address. Existing release tags, source hashes,
speech hashes, MP3 files, and playlist files do not need to change. Unrelated
repositories and lookalike names remain blocked.

GitHub redirects the old repository address and Git operations after a rename.
Do not recreate a repository with the old name: that would remove GitHub's
repository redirects. GitHub does not automatically redirect the old Pages
address. The owner chose not to preserve old website bookmarks, so the old
Pages address is retired; update website bookmarks to the new address. No
additional redirect site is created.

## Dropbox action for the owner

In the existing Dropbox app console, open **Settings → OAuth 2 → Redirect URIs**
and add this exact URI, including the trailing slash:

```text
https://zhou-yang-quantum.github.io/arXiv-carte-blanche/
```

Keep the existing public App key, permissions, app folder, and bookmark file.
The local-preview redirect URIs can stay. If configured, update the app's
privacy-policy URL to the new privacy page too. Reconnect from the new website
after updating the allowed URI.

Browser bookmarks, theme, and sidebar preferences retain their existing storage
keys. Since the site stays on the same HTTPS origin and only its path changes,
those saved settings remain available at the new address.

## Publishing and local clones

Use **Settings → Pages → GitHub Actions** as before. The deployment workflow can
be dispatched with `reuse_audio_only=true` to publish promptly without starting
new speech synthesis. Normal pushes retain the existing automatic audio behavior.

For another existing clone, update its remote:

```sh
git remote set-url origin git@github.com:zhou-yang-quantum/arXiv-carte-blanche.git
```
