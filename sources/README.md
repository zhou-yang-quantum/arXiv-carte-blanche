# Announcement snapshots

These immutable, dated JSON files preserve arXiv announcement batches and frozen
title/author/abstract metadata. Legacy snapshots use v1; feed snapshots record
the actual version supplied with the new announcement. The free collector records them
without model calls, allowing the local Plus-backed generator to catch up while
the computer has been off. Submission timestamps are not used to guess
announcement dates. Version 2 snapshots additionally require a dated new listing
in the paper's primary category; late cross-lists of older papers are recorded as
excluded. Replacements are absent from these new-announcement listings.

The original October 7 and October 8 version 1 snapshots retain the complete
candidate catalogs used in the first trials, including a few old cross-lists.
All papers selected in those trials were newly announced on the respective day.
Existing snapshots are never refreshed to newer paper versions.

Daily capture uses official arXiv Atom feeds, combining the configured categories
into a request and splitting feeds that reach their documented 2000-entry limit.
Version 3 snapshots use each entry's announcement date and explicit `new` label
to verify first announcements. Cross-lists are checked against their original
subject feeds; replacements and older cross-lists are excluded. Titles, authors
and abstracts come directly from the feed. A new announcement may already be v2;
that version is recorded explicitly rather than being mislabeled as v1. No
per-paper metadata API requests are needed for daily collection.

Feed inputs are cached immediately and preserved by
GitHub Actions even when a later request fails. Completed snapshots remain
immutable. HTML-based historical recovery remains available explicitly with
`python tools/collect_arxiv.py --historical`; daily capture does not crawl HTML.

The GitHub collector is the sole automated arXiv downloader. Local GPT runs
read saved snapshots and check GitHub again after five minutes when a batch is
not archived yet. They do not start a concurrent arXiv crawl. HTML requests
respect the [15-second crawl delay](https://arxiv.org/robots.txt); legacy API
requests respect [one request every three seconds](https://info.arxiv.org/help/api/tou.html).
Rate-limit retries honor Retry-After and do not publish incomplete batches.
Morning collection retries have five scheduled windows; later windows skip
the crawl after that date is archived. A failed older recovery cannot erase a
complete newer snapshot. These changes require no model calls or paid API.

The first-announcement audit removed arXiv:2610.05589 from the October 7 digest:
it was originally announced in quant-ph on October 6 before being cross-listed
into math-ph on October 7. The original candidate snapshot remains as provenance.
