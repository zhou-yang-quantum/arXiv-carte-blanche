# Announcement snapshots

These immutable, dated JSON files preserve arXiv announcement batches and v1
title/author/abstract metadata. The free GitHub Actions collector records them
without model calls, allowing the local Plus-backed generator to catch up while
the computer has been off. Submission timestamps are not used to guess
announcement dates. Version 2 snapshots additionally require a dated new listing
in the paper's primary category; late cross-lists of older papers are recorded as
excluded. Replacements are absent from these new-announcement listings.

The original October 7 and October 8 version 1 snapshots retain the complete
candidate catalogs used in the first trials, including a few old cross-lists.
All papers selected in those trials were newly announced on the respective day.
Existing snapshots are never refreshed to newer paper versions.

The GitHub collector is the sole automated arXiv downloader. Local GPT runs
read saved snapshots and check GitHub again after five minutes when a batch is
not archived yet. They do not start a concurrent arXiv crawl. HTML requests
respect the [15-second crawl delay](https://arxiv.org/robots.txt); legacy API
requests respect [one request every three seconds](https://info.arxiv.org/help/api/tou.html).
Rate-limit retries honor Retry-After and do not publish incomplete batches.

The first-announcement audit removed arXiv:2610.05589 from the October 7 digest:
it was originally announced in quant-ph on October 6 before being cross-listed
into math-ph on October 7. The original candidate snapshot remains as provenance.
