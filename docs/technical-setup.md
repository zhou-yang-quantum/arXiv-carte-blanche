# Technical setup and agent reference

This documents the current local Codex → GitHub → GitHub Pages pipeline. It includes reproducible technical settings only; machine paths and schedule identifiers are represented by placeholders. Start with the [README](../README.md) for a short introduction.

## Data flow and source files

```text
GitHub Actions collector → sources/YYYY-MM-DD.json
Windows watcher (no model for queue checks) → tools/local_pipeline.py
  → dated source snapshot + screening, writing, and audio instructions
  → fresh codex exec research context → validated Markdown
  → tools/publish_digest.py → incoming/YYYY-MM-DD.md on GitHub main
Push to main → GitHub Actions build → dist/ → GitHub Pages
```

| File or directory | Role |
| --- | --- |
| `local-pipeline.json` | Automatic-generation enabled state, categories, queue start date, due time, model, effort, retry and timeout settings. |
| `prompts/local-research.md` | Startup screening, dated eligibility, and source-handling instructions. |
| `prompts/local-research-writing.md` | Detailed editorial requirements and final digest format, supplied at startup. |
| `prompts/local-research-audio.md` | Equation pronunciations and phrase groups, supplied at startup. |
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

The controller combines [screening and source instructions](../prompts/local-research.md),
[writing instructions](../prompts/local-research-writing.md), and
[audio instructions](../prompts/local-research-audio.md) into one startup prompt.
All three files and the JSON output schema are available from the beginning of
each fresh research session. Separate files make the requirements easier to edit;
they do not introduce separate generation stages or model sessions. The isolated
two-paper experiment found higher token usage with deferred loading, so that
option was removed; see the [token economy report](token-economy.md).
The controller appends the exact target date and commands to retrieve the paged
catalog and stored abstracts.

The prompt reads the durable [researcher profile](../prompts/researcher-profile.md)
before screening. The controller randomly extracts one item from the latest
available earlier digest into the run's `style-example.md`, reused on retries.
Sources include local Markdown/JSON archives and published cached results when
the checkout has not yet synced; unpublished drafts are excluded. A single item
from the frozen [October 6 digest](../prompts/examples/2026-10-06.md) is a bootstrap
fallback for later dates. With no earlier example, the prompt's format stands alone.
After selecting and carefully studying the current papers, the model reads only
the extracted item for presentation guidance. It must derive selection, technical
details, background, and significance independently from the current sources.
A dedicated editorial pass checks motivation, mechanism, targeted background,
and significance before output. The example's subject or length is not a constraint.

```sh
python tools/local_pipeline.py catalog YYYY-MM-DD
python tools/local_pipeline.py paper YYYY-MM-DD ID1 ID2
python tools/local_pipeline.py paper YYYY-MM-DD ID1 --details
```

Each lookup returns valid JSON bounded to **8,000 UTF-8 bytes**, including its
envelope. The `papers` array contains the next records; `next_command` gives the
exact continuation, and `complete: true` marks the end of the request. Read all
catalog pages before screening, and follow every metadata continuation. Requests
accept up to 20 IDs and deduplicate repeated IDs while preserving their order.
No candidate is removed by paging or keyword filtering.

The normal research view preserves exact titles, complete authors and abstracts,
categories, and the recorded `source_v1` or `versioned_url`. Collection bookkeeping
is omitted from this view, but `--details` exposes every stored field through the
same paging. Source snapshots and publication validation remain unchanged. A single
record larger than a page is delivered as contiguous `fragment.text` pieces of
its compact JSON, with `offset`, `end`, `total_characters`, and `record_complete`.
Concatenating the pieces reconstructs the entire record; there is no abstract
shortening. Follow `next_command` and finish that record before assessing it.

The generator must run each lookup page in a separate tool call, forward stdout
without a JSON-escaped tool-result envelope, and keep both shell and enclosing
output budgets at least 10,000 tokens. Combining several individually safe outputs
can still exceed an enclosing limit; bounded CLI pages cannot enforce a caller's
tool settings. A truncation warning or missing JSON ending requires recovery of
that page alone before proceeding. Large primary-source pages should likewise be
read in focused sections. Keep candidate notes and avoid repeating metadata reads
without a concrete research or recovery need; necessary source checking and rereads
remain allowed. These are delivery controls, not limits on scientific study or prose.

Its current editorial rules prioritize quantum field theory, non-equilibrium physics, quantum error correction, quantum simulation, quantum algorithms, and exactly solvable models. They exclude materials, quantum chemistry, bilayer graphene, TMDs, high-temperature superconductivity, most experiments, overly mathematical string theory, and overly computer-science-heavy algorithms. Change these paragraphs and the assumed background to match the intended reader, and mirror the public criteria in `preferences.json`.

The prompt also instructs each fresh generator to read [prompts/researcher-profile.md](../prompts/researcher-profile.md). Keep durable interests and knowledge calibration there; confirmed reader feedback takes precedence over publication-based inferences. Summaries begin with motivation and the existing obstacle before explaining the mechanism and results. Background fills paper-specific conceptual gaps, and **Why it matters?** assesses scientific significance, potential impact, and connections to durable interests. Save lasting reading feedback in the prompt or profile; the generator does not inherit previous conversations or refresh the profile from the web on every run.

The model screens the catalog, reads saved announcement abstracts for plausible candidates, and consults original arXiv sources as needed. It uses the frozen source version recorded in the metadata: `source_v1` for legacy snapshots or `versioned_url` for Atom snapshots. The generator assesses the complete batch, ranks all qualifying papers, and includes all when twenty or fewer qualify; otherwise it selects the top twenty. There is no minimum quota or preferred count, and fewer than ten is acceptable. It must not stop screening when ten or twenty candidates have been found or pad the selection with weak or redundant contributions. The generator's saved `reason` explains its selection size. Only distinct IDs from that date's verified first-announcement batch are eligible. Historical catch-up uses the historical batch. Replacement announcements and old papers newly cross-listed on the date are excluded; a new announcement may already be v2. Explanations include summary, background/motivation, and personal relevance, with numerical ranking and no priority verdicts.

The controller requests `status` (`ready` or `insufficient`), `reason`, `markdown`, `math_pronunciations`, and `phrase_groups`. The pronunciation list provides an exact English reading for each distinct item equation; phrase groups mark source-exact terminology and optional pauses between meaningful parts. Both come from the same research run without duplicating the prose or making another model call. An insufficient selection becomes `needs-review` rather than padded content. Validation checks the date, 1–20 distinct consecutive ranks, required sections, catalog membership, exact stored titles, complete pronunciation coverage, and nonoverlapping phrase groups that preserve whole equations. These checks do not independently verify every scientific claim, the semantics of every spoken formula, or the intended modifier scope of a technical phrase.

Before strict validation, the controller copies unambiguous capitalization from the final text into generated phrase groups. A prose-only delivery hint that no longer occurs in that text is skipped with an `audio-annotation-skipped` event on standard output in the controller log. Invalid optional groups (such as overlaps, duplicates, or unsafe boundaries) cause an `audio-grouping-fallback` event and ordinary narration without grouping hints. Neither fallback adds, removes, or rewrites narrated prose. Equation keys may copy an unambiguous exact source spelling differing only in surrounding whitespace or a terminal unescaped sentence period/comma inside identical math delimiters, with an `audio-equation-key-aligned` event. Mathematical tokens and the spoken reading are preserved; missing or changed formulas and ambiguous matches still fail strict validation. Saved research results use the same preparation step, so these annotation repairs do not require another research call.

[The prompt map](../prompts/README.md) identifies the active research prompt, runtime instructions, and local scheduling controls. Earlier conversational and cloud prompts have been removed; Git history retains them. This guide is the current reference for setup and recovery.

Changing `categories` in `local-pipeline.json` affects collection of new snapshots. Existing snapshots are retained unchanged, so choose a new start date when beginning a different subject collection. If you need topic filters beyond the current physics labels, update both the keyword-to-tag rules in `tools/import_digest.py` (`TOPICS`) and the allowed labels in `tools/build.py` (`TOPICS`). Changing preferences alone does not change those filters or rerank old digests.

Selection counts outside 1–20 require changing `MIN_PAPERS`/`MAX_PAPERS` in the importer, the research prompt, and corresponding tests. `preferences.json` selection fields are descriptive, not enforcement settings.

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

The Windows watcher is the sole automatic entry point. Do not create a model-backed Codex scheduled task just to run the controller: that starts a model turn even when the queue is empty. The earlier Codex schedule has been retired (paused); its model and pause settings no longer control this pipeline.

Configure `local-pipeline.json`: `enabled` controls automatic generation, `timezone`/`hour`/`minute` define when weekdays become due, and `model`/`reasoning_effort` control each fresh research run. The current clock and research settings remain **10:00 Monday–Friday, America/Chicago**, **`gpt-6.1-sol`**, **High** effort. Choose a model available to your account when reproducing the setup.

Install the watcher from the checkout:

```powershell
powershell.exe -NoProfile -File tools/install-local-watcher.ps1 -StartNow
```

This records Python/Codex executable paths in ignored `.cache/local-pipeline/runtime.json` and registers a current-user Windows login task. No Codex automation ID is needed; legacy `automation_id` fields are ignored and removed when reinstalling the watcher. If migrating an existing setup, pause its redundant Codex scheduled task after installing/verifying the watcher.

The watcher checks once per minute while the Codex app is running and calls `run --automatic` only when work is due and enabled. A five-minute Windows trigger restarts an interrupted watcher, while `IgnoreNew` leaves a running instance alone. It does not start the app or wake the computer. A process lock prevents concurrent workers from generating the same day. Opening the app after an absence processes missing weekdays oldest first, including gaps before newer entries. Before the due time, only older missing days are eligible. Queue checks and completed-date skips run ordinary code and consume no model tokens. Archive-wait retries check GitHub without a model; generation retries can consume tokens until a result succeeds.

Pause or resume automatic generation without a model:

```sh
python tools/local_pipeline.py pause
python tools/local_pipeline.py resume
```

These atomically update `enabled` in `local-pipeline.json`, preserving the other settings. They affect subsequent automatic runs; they do not terminate an already-running research process. Manual `run` commands can still generate and publish while paused, so use them only for an explicitly requested test or recovery. Inspect the queue with `plan` or `status`; daily results no longer create redundant Codex scheduled-chat reports. Publication state and run logs remain available locally.

Each research run launches a fresh `codex exec` context with live search, the configured model/effort, automatic approval review, an output schema, and a saved final JSON result. See `generation_command()` in `tools/local_pipeline.py` for the exact flags and the [official non-interactive Codex documentation](https://learn.chatgpt.com/docs/non-interactive-mode) for the CLI interface.

The watcher uses `controller-process.ps1` to capture stdout and stderr independently and checks the process exit code. A harmless native warning cannot terminate a successful process through PowerShell's error handling; actual nonzero exits remain failures and both streams are logged. Restart the idle Windows watcher after changing watcher or bridge code so the running instance loads the changes.

New research writes `result.pending.json` and promotes it to the reusable `result.json` only after a successful process exit and JSON parsing. Interrupted or incomplete outputs are retained as `result.incomplete-*.json` on the next attempt and are never treated as completed research. GitHub login failures before research receive the configured retry cooldown as well. Publication retries reuse completed research and protect existing remote dates.

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

Repeat items 1–N with 1–20 unique IDs and consecutive ranks. Use the same real date in the filename, title, and every item heading. An optional reading-order note can follow the final item. For manual additions, build locally, commit the Markdown, and push. The optional `python tools/import_digest.py FILE.md` command writes structured JSON instead; importing is unnecessary for files already in `incoming/`.

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

The completed instruction-loading experiment and its quality checks are recorded
in the [token economy report](token-economy.md). Deferred loading and its temporary
benchmark runner are excluded from the production implementation. The production
parser still requires 1–20 papers. Raw experiment artifacts remain in the ignored
local cache; they are not published with the website.

Keep credentials, auth files, absolute machine paths, local schedule IDs, and runtime logs out of committed documentation and digests. `.cache/` and `.env*` are ignored. The published site includes digest text and `preferences.json`, so use only information you intend readers to see.
