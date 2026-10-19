# Token economy and instruction-loading experiment

## Production changes — October 19, 2026

The Windows watcher checks the due-date queue using ordinary code. A completed
queue check does not start a model and consumes no model tokens. The redundant
model-backed app schedule was paused on the installed machine. New installations
need only the Windows watcher. Automatic generation is controlled by `enabled`
in `local-pipeline.json`, with `pause` and `resume` commands. Completed dates are
not regenerated, concurrent runs are locked out, and saved results are reused
when publication needs retrying. See the [technical guide](technical-setup.md).

Each research run now receives one randomly selected item from the latest
available earlier digest as a style reference. Previously it loaded the complete
37,151-character October 6 example. The item is saved for retries and guides
presentation only. Selection, technical explanations, background, and significance
must come from careful study of the current papers. The character reduction is
real; a fixed daily token saving cannot be inferred from it because repeated
context, caching, and research paths vary.

Catalog and metadata lookups use pages bounded to 8,000 UTF-8 bytes, including the
JSON envelope. Compact records retain complete titles, authors, abstracts,
categories, IDs, and the recorded source-version link. Collection evidence remains
available through `paper --details`. Explicit continuation commands preserve all
records; an unusually large record is delivered as lossless fragments instead of
silently truncating its abstract. The prompt requires separate page reads,
completion checks, and source notes before assessment. Necessary scientific
rereads remain allowed. These bounds protect the metadata tools; they cannot
guarantee that arbitrary external web or shell output will never be truncated.

The replay check covered 1,884 saved records across ten dates without content
loss; the largest emitted page was 7,998 bytes. Regression tests cover UTF-8 size
limits, continuation behavior, oversized records, and exact reconstruction.

## Two-paper instruction-loading experiment

The October 19 saved snapshot contained seven papers listing `hep-lat`. Two
independent research sessions each produced a two-paper test digest using the
same profile, snapshot, fixed earlier style item, and instruction content.
Both selected arXiv:2610.23675 and arXiv:2610.23681. The configured model was
GPT-6.1 Sol with High reasoning and Standard service, using ChatGPT authentication.
The test did not publish, synthesize speech, or update the production queue.

The first session received screening, writing, and audio instructions together
at startup. The second read writing instructions after source study and audio
instructions after prose drafting, within one continuous session. The output
schema was present initially in both. No tool-output truncation warning occurred
in either session.

| Metric | All instructions at startup | Instructions loaded later | Change |
| --- | ---: | ---: | ---: |
| Initial prompt characters | 18,579 | 7,145 | −61.5% |
| Uncached input tokens | 80,858 | 94,680 | +17.1% |
| Cached input tokens | 444,416 | 570,624 | +28.4% |
| Output tokens, including reasoning | 7,794 | 9,018 | +15.7% |
| Total reported tokens | 533,068 | 674,322 | **+26.5%** |
| Summary/background/significance words | 999 | 934 | −6.5% |
| Automated validation | Pass | Fail | Audio phrase annotation |

Input tokens are context the model processes, including instructions, earlier
messages, and tool results. Cached input is the portion reused through prompt
caching; uncached input is the remainder. Output tokens cover generated text and
reported reasoning tokens. Cached tokens are already included in total input,
and reasoning is already included in output: neither should be added twice.
Totals accumulate across the session's model calls, so they can exceed its maximum
context size. These raw counts do not directly measure ChatGPT subscription
allowance or a dollar bill; API billing also depends on model-specific rates.

Both prose samples explained motivation, mechanisms, paper-specific background,
and significance with appropriate limitations. The pressure summaries distinguished
the new hard-scale calculation from existing nonperturbative magnetic input and
qualified the role of resummation. The lattice truncation summaries explained the
projector construction and qualified the finite-coupling, small-volume evidence.
This small review found comparable scientific treatment, not proof of equivalent
quality across future digests.

The later-loading result failed the existing audio validator: its phrase group
`non-Abelian field theory` occurred only in the daily overview, outside narrated
paper fields. Both results passed equation-coverage checks. No validator or result
was changed to conceal the failure. Audio instructions were subsequently clarified
to exclude overview-only annotations; that clarification was not retested with
another model run.

## Decision and limitations

Deferred instruction loading did not save tokens in this pair. It is excluded
from production, including the configuration option and temporary benchmark
runner. The three Markdown files remain separate for maintenance and are always
loaded together at startup. Full editorial requirements, primary-source study,
the output schema, and the production 10–20-paper validation remain in place.

One pair cannot isolate the instruction-loading effect statistically. The first
session ran before the second; cache warmth, research paths, and model variability
can affect usage. The measured 26.5% increase must not be extrapolated to a full
daily digest. Raw prompts, events, outputs, and the machine-readable report remain
in the ignored local experiment cache for review.
