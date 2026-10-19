# Prompts

[local-research.md](local-research.md) defines screening and source-handling rules;
writing and audio instructions live in separate files. Edit the corresponding
file for future digests. All three instruction files are supplied together at
startup. They are separate files for maintenance, with no deferred loading.

| Instructions | Where they live | How they are used |
| --- | --- | --- |
| Screening and source study | [local-research.md](local-research.md) | Defines selection, dated eligibility, complete paged metadata reads, and careful primary-source study. |
| Explanations, editorial review, and digest format | [local-research-writing.md](local-research-writing.md) | Preserves the full summary/background/significance guidance and final Markdown structure. Supplied at startup. |
| Equation pronunciation and terminology groups | [local-research-audio.md](local-research-audio.md) | Adds audio annotations without rewriting or shortening the digest. Supplied at startup. |
| Durable interests and assumed knowledge | [researcher-profile.md](researcher-profile.md) | The research prompt explicitly tells each fresh generator to read this file before screening. Update it when broad interests or knowledge change; daily updates are unnecessary. |
| Writing style and format | `.cache/local-pipeline/runs/YYYY-MM-DD/style-example.md` | The controller randomly selects one item from the latest available earlier digest and saves it for that run, including retries. The generator reads only this item after studying the current papers. It guides presentation; selection and scientific content must come from the current batch and its primary sources. The frozen [October 6 digest](examples/2026-10-06.md) is a bootstrap source only when earlier published digests are unavailable; only one item is extracted. |
| Run date, paged catalog/metadata commands, and JSON output contract | [tools/local_pipeline.py](../tools/local_pipeline.py) | The controller supplies these at runtime. Lookup pages are capped at 8,000 UTF-8 bytes with explicit continuations. Full abstracts and source-version links are preserved; `paper --details` exposes collection evidence separately. Read each page in a separate tool call and finish continuations before assessing papers. |
| Automatic generation | Windows startup watcher and [local-pipeline.json](../local-pipeline.json) | Windows checks the queue without a model and starts Codex only for due digests. The local configuration controls the clock, model, effort, and enabled state; see the [technical guide](../docs/technical-setup.md#local-installation-and-schedule). |

The controller checks that all three instruction files exist before starting
generation. The JSON output schema is also present from startup. A two-paper
experiment found no savings from deferred instruction loading, so that option
was removed; see the [token economy report](../docs/token-economy.md).

The speech engine reads text prepared by [tools/speech_text.py](../tools/speech_text.py)
from the digest and its pronunciation list. It does not run a separate LLM prompt.
Future readings use compact QEC parameters, explicit “sub” before subscripts,
subscript-before-dagger operator names, context-appropriate simple letter names,
and optional `[p]` pauses and `(word group)` timing controls inside math readings.
The same run also marks source-exact `phrase_groups` for multiword terminology,
shared modifiers, and multi-name terms, using the paper's meaning to place pauses.
See [audio/README.md](../audio/README.md) for the audio pipeline.

The generator uses a fresh research context with the dated catalog and saved
metadata. It does not inherit an earlier ChatGPT conversation. The website's
`preferences.json` describes the selection criteria but is not read by the
generator.

Refine explanation preferences in conversation, then save durable changes in the
prompt or profile so future runs receive them. The profile separates confirmed
knowledge from provisional publication-based context. A monthly review is optional;
the generator does not update the profile or consult Scholar on every run.

The unused conversational and cloud prompt files have been removed. Their earlier
versions remain in Git history. Current setup, scheduling, and recovery instructions
are consolidated in the [technical guide](../docs/technical-setup.md).
