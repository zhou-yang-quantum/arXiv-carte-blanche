# Prompts

[local-research.md](local-research.md) is the research prompt used by the current
pipeline. Edit this file to change paper selection, explanations, or equation
readings for future digests.

| Instructions | Where they live | How they are used |
| --- | --- | --- |
| Research and audio pronunciation | [local-research.md](local-research.md) | The controller reads this file for each new research run. The same run selects papers, writes the digest, and supplies equation-to-English pronunciations. |
| Durable interests and assumed knowledge | [researcher-profile.md](researcher-profile.md) | The research prompt explicitly tells each fresh generator to read this file before screening. Update it when broad interests or knowledge change; daily updates are unnecessary. |
| Writing style and explanatory depth | [examples/2026-10-06.md](examples/2026-10-06.md) | A frozen copy of the renewed October 6 digest. The generator reads it once after selection as a writing reference, using current sources and the current reader profile for each new digest. |
| Run date, catalog, metadata command, and JSON output contract | [tools/local_pipeline.py](../tools/local_pipeline.py) | The controller supplies these at runtime, together with the research prompt. |
| Scheduled task | Saved in the local Codex app | Starts the controller. A sanitized copy is in the [technical guide](../docs/technical-setup.md#local-installation-and-schedule). |

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
