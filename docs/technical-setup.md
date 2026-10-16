# Technical setup and agent reference

This documents the current local Codex → GitHub → GitHub Pages pipeline. It includes reproducible technical settings only; machine paths and schedule identifiers are represented by placeholders. Start with the [README](../README.md) for a short introduction.

## Data flow and source files

```text
GitHub Actions collector → sources/YYYY-MM-DD.json
Local Codex task or Windows watcher → tools/local_pipeline.py
  → dated source snapshot + prompts/local-research.md
  → fresh codex exec research context → validated Markdown
  → tools/publish_digest.py → incoming/YYYY-MM-DD.md on GitHub main
Push to main → GitHub Actions build → dist/ → GitHub Pages
```

| File or directory | Role |
| --- | --- |
| `local-pipeline.json` | Categories, queue start date, due time, model defaults, retry and timeout settings. |
| `prompts/local-research.md` | Actual research instructions passed to each local generation context. |
| `prompts/researcher-profile.md` | Durable interests, confirmed knowledge, and provisional publication-based context; the research prompt instructs each fresh generator to read it before screening. |
| `preferences.json` | Public selection criteria copied into the website; not loaded by the research controller. |
| `sources/` | Immutable dated announcement evidence and captured paper metadata. Legacy snapshots use v1; Atom snapshots record the version in the new announcement. |
| `incoming/` | Markdown digests parsed directly at build time. |
| `content/digests/` | Structured JSON digests, also accepted by the build. |
| `tools/import_digest.py` | Markdown parser, validation, and optional manual JSON import. |
| `tools/build.py` | Archive validation and static-site assembly. |
| `site/` | Website source. |
| `.cache/local-pipeline/` | Ignored local settings, queue state, research inputs, drafts, and logs. |

The builder requires at least one digest. If starting a fresh archive, keep an example until your first valid digest is ready. Duplicate dates with different substantive content are rejected; matching JSON can retain manually reviewed topic tags.

## Research prompt and personalization

The full, executable research prompt is [prompts/local-research.md](../prompts/local-research.md). The controller appends the exact target date, a compact catalog path, and a command to retrieve stored abstracts:

The prompt reads the durable [researcher profile](../prompts/researcher-profile.md)
before screening and the frozen [renewed October 6 digest](../prompts/examples/2026-10-06.md)
once after selection as a writing reference. The example guides explanatory depth
and structure; current dated sources supply facts. A dedicated editorial pass
checks motivation, mechanism, targeted background, and significance before output.

```sh
python tools/local_pipeline.py paper YYYY-MM-DD ID1 ID2
```

Its current editorial rules prioritize quantum field theory, non-equilibrium physics, quantum error correction, quantum simulation, quantum algorithms, and exactly solvable models. They exclude materials, quantum chemistry, bilayer graphene, TMDs, high-temperature superconductivity, most experiments, overly mathematical string theory, and overly computer-science-heavy algorithms. Change these paragraphs and the assumed background to match the intended reader, and mirror the public criteria in `preferences.json`.

The prompt also instructs each fresh generator to read [prompts/researcher-profile.md](../prompts/researcher-profile.md). Keep durable interests and knowledge calibration there; confirmed reader feedback takes precedence over publication-based inferences. Summaries begin with motivation and the existing obstacle before explaining the mechanism and results. Background fills paper-specific conceptual gaps, and **Why it matters?** assesses scientific significance, potential impact, and connections to durable interests. Save lasting reading feedback in the prompt or profile; the generator does not inherit previous conversations or refresh the profile from the web on every run.

The model screens the catalog, reads saved announcement abstracts for plausible candidates, and consults original arXiv sources as needed. It uses the frozen source version recorded in the metadata: `source_v1` for legacy snapshots or `versioned_url` for Atom snapshots. It selects ten papers by default, with a maximum of twenty, using only distinct IDs from that date's verified first-announcement batch. Historical catch-up uses the historical batch. Replacement announcements and old papers newly cross-listed on the date are excluded; a new announcement may already be v2. Explanations include summary, background/motivation, and personal relevance, with numerical ranking and no priority verdicts.

The controller requests `status` (`ready` or `insufficient`), `reason`, `markdown`, `math_pronunciations`, and `phrase_groups`. The pronunciation list provides an exact English reading for each distinct item equation; phrase groups mark source-exact terminology and optional pauses between meaningful parts. Both come from the same research run without duplicating the prose or making another model call. An insufficient selection becomes `needs-review` rather than padded content. Validation checks the date, 10–20 distinct consecutive ranks, required sections, catalog membership, exact stored titles, complete pronunciation coverage, and nonoverlapping phrase groups that preserve whole equations. These checks do not independently verify every scientific claim, the semantics of every spoken formula, or the intended modifier scope of a technical phrase.

[The prompt map](../prompts/README.md) identifies the active research prompt, runtime instructions, and saved scheduled-task prompt. Earlier conversational and cloud prompts have been removed; Git history retains them. This guide is the current reference for setup and recovery.

Changing `categories` in `local-pipeline.json` affects collection of new snapshots. Existing snapshots are retained unchanged, so choose a new start date when beginning a different subject collection. If you need topic filters beyond the current physics labels, update both the keyword-to-tag rules in `tools/import_digest.py` (`TOPICS`) and the allowed labels in `tools/build.py` (`TOPICS`). Changing preferences alone does not change those filters or rerank old digests.

Selection counts outside 10–20 require changing `MIN_PAPERS`/`MAX_PAPERS` in the importer, the research prompt, and corresponding tests. `preferences.json` selection fields are descriptive, not enforcement settings.

## Fork-specific settings

Before using automatic publication, redirect the code to your own repository:

| Location | Required change |
| --- | --- |
| `tools/project.py` | Set `REPOSITORY` and `WEBSITE`. The publisher, source reader, audio publisher, and archive builder share these settings. `LEGACY_REPOSITORY` keeps existing recording links compatible after a rename. |
| `site/index.html` and `README.md` | Update the public repository and website links; adjust the title/branding if desired. |
| `site/audio.js` | Match the canonical and legacy audio URL prefixes to `tools/project.py`; unrelated repositories remain rejected. |
| `tests/test_audio.py` and `tests/browser/archive.spec.js` | If changing the audio destination, match the audio fixture URL prefixes to it. |

Audio is optional. For a text-only fork, remove the audio cache, dependency preparation, and generation steps from `.github/workflows/pages.yml`; leave the build and deploy steps. Start without a generated `audio/index.json`. For audio setup and licenses, see [audio/README.md](../audio/README.md), substituting your own URL in its download example.

Keep `main` as the publishing branch, or update both the workflow branch filter and the publisher's read/write branch values consistently. Choose `start_date` deliberately: it is the beginning of the missing-weekday queue, not just a label. Retained example digests count as completed dates.

## Website reading controls and saved papers

The archive sidebar groups dates under month/year headings. Readers can hide it, and a date dropdown remains available when it is hidden or on narrow screens. **Latest** returns to the newest digest; topic filters and **Saved** browse across the archive. **Compact view** collapses paper details, and each paper has its own **Show details / Hide details** button. The search field and mark-as-read controls have been removed.

Paper cards show a numerical rank beside the title, authors and arXiv ID, then **Summary**, **Background**, and **Why it matters?** sections. Redundant inline v1 source links are omitted from rendering and copied text; arXiv and PDF footer links remain. The browser tab uses the selected digest title (`arXiv-YYYY-MM-DD`) even in Saved or filtered views, with `site/quantum-chip.svg` as both the favicon and brand icon.

Bookmarks persist in browser storage and can optionally sync through each reader's own Dropbox account. The site remains static; no paid backend or model API is involved. Configure the public app key and redirect URLs using [the Dropbox setup guide](dropbox-sync.md), then connect from **Saved → Dropbox sync** on each device. An empty key leaves local saves enabled and Dropbox connection disabled.

The theme follows the operating system until the reader chooses light or dark; that choice and the archive-sidebar preference persist in browser storage. The calendar picker and paginated **All** view remain future work, tracked in the [README to-do list](../README.md#to-do-future-implementations).

**Play day** and **Play item** open the same continuous day recording, using item boundaries as chapters. The player offers track selection, previous/next, seeking within the current item, speed controls, Media Session controls, and automatic recovery after stalled playback. **Download playlist (ZIP)** appears when the published audio index includes the archive of dated individual MP3s. New narration uses version 6: item number, a pause, then the title without repeating the digest date, plus optional short pauses and slightly faster groups within equations, and normal-speed grouping for multiword technical terms. See [audio/README.md](../audio/README.md) for generation, recovery limits, and the remaining physical-device lock-screen check.

## Local installation and schedule

The automatic controller and watcher currently require **Windows**, including the running-app detection. A different operating system needs adaptations to that check and the watcher; the static site and manual imports work independently.

Prerequisites: Python 3.11+, Node.js 22+, Git, Codex CLI and desktop app, and GitHub CLI (`gh`). Set up your own ChatGPT and GitHub authentication interactively. For Codex authentication options, see the [official OpenAI documentation](https://learn.chatgpt.com/docs/auth).

```sh
npm ci
python -m pip install tzdata
codex login
gh auth login
python tools/local_pipeline.py plan
```

`tzdata` supplies IANA timezone data on Windows. Confirm the Codex login uses ChatGPT and the GitHub account has write access to your fork. The controller enforces ChatGPT authentication, removes model API keys and GitHub tokens from the model subprocess environment, and has no automatic paid-API or model fallback. It obtains the GitHub credential through `gh` only in the Python publishing process.

Create a **local** task in Codex's Scheduled view, with this repository as its working directory. The current setup uses **10:00 Monday–Friday, America/Chicago**, **`gpt-6.1-sol`**, and **High** reasoning effort. Select a model available to your account if reproducing the setup. Match the task clock to `timezone`, `hour`, and `minute` in `local-pipeline.json`; changing the app's clock alone does not change when the controller considers a date due.

Save the checkout as a local project in the app and attach the task to that project. A projectless task starts from the home folder; putting an absolute checkout path in its prompt does not grant write access to the project's cache and can cause a `run.lock` permission error.

The saved task's prompt, with only its absolute checkout path replaced by `<REPO_ROOT>`, is:

> Run the local daily-arXiv controller from `<REPO_ROOT>` with the command `python tools/local_pipeline.py run`. This project uses local ChatGPT subscription authentication and the existing GitHub CLI login; no paid model API or purchased credits are authorized. The controller finds every missing due weekday from October 7, 2026 onward, reads saved arXiv announcement snapshots, runs fresh subscribed GPT research for each day, validates the dated digest, and publishes through Python. Its runtime model and reasoning effort should match this schedule's saved model and effort. Do not research or write a second digest yourself, expose credentials, alter website code, overwrite published days, create another schedule, or use a cloud environment. If the controller reports already-running, waiting-for-app, up-to-date, retry, or needs-review, report that status accurately. Report new published dates, paper counts, and website links briefly; do not repeat the complete digests. Startup catch-up is handled by the installed Windows watcher using the same controller and lock.

For your copy, replace `<REPO_ROOT>` with your local checkout and the start date with your configured `start_date`.

Install the watcher from the checkout:

```powershell
powershell.exe -NoProfile -File tools/install-local-watcher.ps1 -StartNow
```

This records the local Python/Codex executable paths in ignored `.cache/local-pipeline/runtime.json` and registers a current-user login task. Add your saved Codex task's directory identifier as `automation_id` in that JSON, preserving the installer-generated fields. The controller reads the task from `<CODEX_HOME>/automations/<automation_id>/automation.toml` (default Codex home: `~/.codex`). This lets the task's saved model, reasoning effort, and pause status control automatic catch-up too. Without that link, the controller uses `local-pipeline.json` defaults and cannot observe an app-task pause. These saved-task fields are an implementation dependency; check `load_config()` if the app's storage format changes.

The watcher checks once per minute while the Codex app is running and calls `run --automatic` when work is due. A five-minute Windows trigger restarts an interrupted watcher, while `IgnoreNew` leaves a running instance alone. It does not start the app or wake the computer. A process lock prevents concurrent triggers from generating the same day. Opening the app after an absence processes missing weekdays oldest first, including gaps before newer entries. Before the due time, only older missing days are eligible. An empty queue makes no research-model call.

Pausing the linked saved task also pauses automatic startup catch-up. An already-running controller and its research process must be stopped separately. Manual `run` commands can still generate and publish while the schedule is paused, so use them only for an explicitly requested test or recovery.

Each research run launches a fresh `codex exec` context with live search, the configured model/effort, automatic approval review, an output schema, and a saved final JSON result. See `generation_command()` in `tools/local_pipeline.py` for the exact flags and the [official non-interactive Codex documentation](https://learn.chatgpt.com/docs/non-interactive-mode) for the CLI interface.

## Source capture and website publication

[`.github/workflows/collect-arxiv.yml`](../.github/workflows/collect-arxiv.yml) runs the source collector at **02:17, 04:17, 06:17, 08:17, and 10:17 on weekdays in America/New_York**, or manually. It reads categories from `local-pipeline.json`, captures the official Atom feeds, and commits complete dated snapshots to `sources/`. Once the day's snapshot exists, later scheduled capture windows skip downloading. It uses no AI model and continues independently of the local machine and its paused or active research task.

Feed entries labeled `new` establish first-announcement eligibility. Cross-lists are checked against their original subject feeds; replacements and older cross-lists are excluded. Captured metadata includes the exact feed version without per-paper API lookups. Completed downloads are cached for recovery after a later failure, and existing snapshots remain unchanged. See [sources/README.md](../sources/README.md) for the snapshot formats and collector behavior.

The local controller reads those snapshots instead of crawling arXiv. Missing evidence leaves a day queued for another GitHub check in five minutes, without a research-model call. Historical inputs can be recovered from saved feed downloads; an uncached old batch needs explicit historical recovery with `python tools/collect_arxiv.py --historical`. A missing or stale feed is not evidence of an empty day. A verified closed empty batch can be recorded as `no-batch`.

After research, the local controller validates the result and calls the Python publisher. The automatic path creates `incoming/YYYY-MM-DD.md` and `audio/scripts/YYYY-MM-DD.json` together in one Git commit, updating `main` without force. If the branch moves, it rebuilds against the new parent and checks the dated entry again. An identical existing digest is treated as already delivered; a different one is protected from overwrite. The manual publisher still accepts a Markdown-only delivery. This remote commit does not update your local Git checkout, so pull remote changes before your next local commit. Audio preparation and licenses are documented in [audio/README.md](../audio/README.md).

[`.github/workflows/pages.yml`](../.github/workflows/pages.yml) runs on pushes to `main` or manual dispatch. It installs Node/Python dependencies, runs Python tests, attempts offline audio generation/reuse, validates the archive, uploads `dist/`, and deploys that artifact to Pages. Markdown is parsed during the build; generated digest JSON need not be committed. Only `dist/` is deployed. Marked, KaTeX, fonts, and their licenses are bundled in the site. Audio uses offline speech synthesis and GitHub Release assets; audio-generation failures are allowed without blocking text publication.

Manual dispatch accepts optional `audio_dates`, a comma-separated list without spaces (for example, `2026-10-14,2026-10-15`), to generate or reuse only those dates' recordings. Leave it blank to process all dates. Other still-current recordings are retained from the published index. New and reused releases receive a playlist ZIP without requiring speech to be regenerated; see the [audio publication notes](../audio/README.md).

In your fork, enable Actions and select **Settings → Pages → Build and deployment → Source → GitHub Actions**, using the existing workflow. See [GitHub's publishing-source documentation](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site). The collector needs `contents: write`; the Pages build also needs it for audio releases, and the deploy job needs `pages: write` and `id-token: write`. The workflow declares these permissions and uses the built-in GitHub token; local publication uses your separate `gh` login.

## Digest format

Save UTF-8 Markdown at `incoming/YYYY-MM-DD.md`:

```markdown
# arXiv-YYYY-MM-DD

Brief overview identifying the announcement batch.

## arXiv-YYYY-MM-DD — Item 1

### Exact paper title
**Authors — arXiv:YYMM.NNNNN**

Source-grounded summary.

**Background.** Paper-specific concepts and unfamiliar jargon.

**Why it matters?** Scientific significance, potential impact, and connection to durable interests.

[arXiv YYMM.NNNNN](https://arxiv.org/abs/YYMM.NNNNN)
```

Repeat items 1–N with 10–20 unique IDs and consecutive ranks. Use the same real date in the filename, title, and every item heading. An optional reading-order note can follow the final item. For manual additions, build locally, commit the Markdown, and push. The optional `python tools/import_digest.py FILE.md` command writes structured JSON instead; importing is unnecessary for files already in `incoming/`.

## Inspection, recovery, and verification

```sh
python tools/local_pipeline.py plan
python tools/local_pipeline.py status
python tools/local_pipeline.py run --limit 1
python tools/local_pipeline.py retry YYYY-MM-DD
```

`plan` and `status` inspect the queue without calling a model. `run` generates and publishes due dates and requires the app to be running; `--limit 1` bounds a trial to one date. `retry` reopens an unsuccessful date after you address its cause, preserves the previous result, and refuses completed dates. Network or generation failures receive a cooldown (default 60 minutes); insufficient or invalid output needs review. Drafts, JSON results, and logs are in `.cache/local-pipeline/runs/`; queue state is in `.cache/local-pipeline/state.json`. Deleting that cache loses local review/retry history.

For build or pipeline changes:

```sh
python -m unittest discover -s tests
npm run build
```

For website interaction changes, additionally run:

```sh
npx playwright install chromium
npx playwright test
```

Keep credentials, auth files, absolute machine paths, local schedule IDs, and runtime logs out of committed documentation and digests. `.cache/` and `.env*` are ignored. The published site includes digest text and `preferences.json`, so use only information you intend readers to see.
