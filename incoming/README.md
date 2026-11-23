# Daily digest delivery

Create one UTF-8 Markdown file here for each daily selection:

`incoming/YYYY-MM-DD.md`

Start with `# arXiv-YYYY-MM-DD` and a brief daily overview, followed by 1–15 consecutively ranked item headings:
`## arXiv-YYYY-MM-DD — Item N`.

Each item must include a `###` paper title, authors and `arXiv:YYMM.NNNNN`,
summary paragraphs, `**Background.**`, and
`**Why it matters?**`. The older `**Why it matters for you:**` heading remains accepted for existing digests.

From November 20, 2026 onward, rank the complete batch and keep at most fifteen
qualifying papers. Include fewer when fewer qualify; do not pad the list.
Earlier archived dates retain their original limit of twenty. Do not include priority verdicts such as “must read” or
“high.” Legacy digests containing priority lines remain supported.

The existing GitHub Pages workflow automatically parses, validates, and publishes
these files. No model API calls or generated-JSON commits are needed. A malformed
entry fails the build and leaves the previous successful website in place.

Do not overwrite earlier dates. If the same date also exists in `content/digests/`,
the substantive content must agree; the reviewed JSON's topic tags take precedence.

The active research prompt is [prompts/local-research.md](../prompts/local-research.md).
The local controller validates and publishes its output; see the
[technical guide](../docs/technical-setup.md) for the current pipeline.
