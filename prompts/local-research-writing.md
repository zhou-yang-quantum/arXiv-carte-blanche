# Writing instructions

After selecting and studying the current papers, read the controller-provided
style reference once, if available. It contains one randomly selected item from
an earlier digest. Use it only as guidance for format, connected explanatory
prose, motivation-first openings, targeted Background, and measured significance
assessments. Do not load a whole previous digest or other examples.
The example must not influence paper selection or supply technical details,
definitions, mechanisms, results, equations, or significance claims. Study each
selected paper's own primary source carefully enough to support its summary,
Background, and Why it matters? independently. Use the current target date and
reader profile; do not copy the example's paper choices, claims, dates, or stock
phrases. Its topic, length, and level of technicality are not a template for other
papers. Let each paper's needs determine its explanation and length.

Keep a clean numerical ranking and a concise daily overview, without priority
labels such as "must read", "high", or "very high". Give each item a coherent,
slightly discursive explanation for a fellow theoretical physicist. Preserve
technical substance while making the reasoning easy to follow; do not compress
the entry into an abstract-like list of named techniques and results. Let the
complexity of the paper determine the length rather than imposing a word quota.
Use your space to connect motivation, mechanism, and consequences. Avoid a
compressed abstract style, unexplained strings of technical labels, generic
topic matching, and boilerplate caveats. Let the explanation develop naturally
in paragraphs. A concise daily overview does not require compressed paper entries.

Summary: begin with the physical question, motivation, and existing obstacle so
the reader understands the big picture before the technical result. Then explain
the authors' central idea, what they actually calculate or construct, the main
result, and the scope of the evidence. Connect these steps in paragraphs. Give a
short intuitive gloss when a specialized term first becomes necessary; reserve
the fuller explanation for Background. Introduce symbols and explain what an
equation tells us. Distinguish established results from the authors' claims and
from your assessment. Include limitations where they qualify a result, without
letting a list of caveats displace its explanation.

Background: explain the paper-specific concepts and jargon that are necessary
to understand the mechanism and are not established knowledge in the reader
profile. Prioritize these conceptual gaps over textbook definitions the reader
already knows. Explain what each concept is, how it works at an intuitive level,
and why the paper needs it; use a small example when helpful. Expanding an acronym
or replacing jargon with more jargon is not an explanation. Do not repeat the
summary's motivation or supply a generic introduction to the whole field.
A definition alone is often insufficient: explain the paper-specific conceptual
bridge, how an unfamiliar construction operates, and why it enables the result.
For a paper using code automorphisms and fold-transversal gates, for example,
explain those constructions and their role in logical operations rather than
spending Background on qLDPC or the Clifford/non-Clifford distinction. This is a
calibration example, not a requirement to discuss these terms in other papers.
Verify specialized definitions from the source when needed. Do not omit essential
concepts just to keep Background short, or invent a definition from a term's name.

Why it matters?: give a high-level, reasoned verdict on the scientific significance
and potential impact of the work, then explain a substantive connection to the
reader's durable interests or a worthwhile broader direction. Identify what it
changes relative to previous understanding or capability, and what would be
needed for a proposed impact to follow. Distinguish conceptual advances, useful
methods, and incremental results when the evidence supports that assessment.
Avoid hype, priority badges, generic topic matching, and speculative claims about
the reader's immediate projects. This section should assess the contribution
rather than repeat the results.

Before returning the digest, check each item: does the opening explain why the
problem is worth solving before presenting results? Can the reader understand
the central mechanism without unexplained specialist terminology? Does Background
address the likely gaps in the profile rather than rehearse known basics? Does
Why it matters? give an evidence-based assessment rather than just name interests?
Do a dedicated editorial pass after selection and source verification. Repair
missing steps between the physical question, construction or calculation, result,
and significance. Revise weak sections before returning the JSON. Use the single
style reference, when available, to check presentation and continuity; derive
the scientific content and assessment from each current paper's own sources.

Use the arXiv link at the bottom of each item, without redundant inline links
labeled "v1 paper", "v1 abstract", or similar. Verify claims from the recorded source version.

Return only the final JSON object matching the supplied schema. If at least ten
appropriate papers cannot be supported, set status to "insufficient", explain
briefly in reason, and leave markdown empty. Otherwise set status to "ready",
reason to a brief explanation of the selection size, and markdown to a complete
UTF-8 digest with this structure for every item:

# arXiv-YYYY-MM-DD

Brief overview of the batch and selection.

## arXiv-YYYY-MM-DD — Item 1

### Exact title from the stored announcement metadata
**Authors — arXiv:YYMM.NNNNN**

Motivation-first, source-grounded summary paragraphs, with Markdown and LaTeX as helpful.

**Background.** Paper-specific concepts and unfamiliar jargon needed to understand the mechanism.

**Why it matters?** Scientific significance, potential impact, and connection to durable interests.

[arXiv YYMM.NNNNN](https://arxiv.org/abs/YYMM.NNNNN)

Repeat consecutive ranks through the actual paper count. Optionally finish with
`My reading order would be **1 → 2 → ... → N**.` using every rank exactly once,
followed by a brief synthesis. Use the provided date everywhere. Use no HTML,
internal ChatGPT citation markers, code fence around the digest, or conversational
offers. The final JSON is saved directly by the controller; do not duplicate it in
a file-writing tool or another response.
