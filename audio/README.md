# Digest recordings

`index.json` is generated locally or by GitHub Actions and is not committed.
Recordings are immutable GitHub Release assets, keeping the repository and Pages
deployment small. Each date has one continuous MP3 and a separate MP3 per paper.
The release identity includes the source text, speech preparation, and voice.
Unchanged recordings are reused; corrected digests cannot use old recordings.

New recordings use free CPU synthesis with [Kokoro ONNX](https://github.com/thewh1teagle/kokoro-onnx),
the `af_heart` American-English voice, and checksum-pinned model/voice assets.
The runtime is MIT and the [model is Apache-2.0](https://huggingface.co/hexgrad/Kokoro-82M);
the model card records training-data credits. Voice attribution is retained in
each release. The roughly 354 MB of model assets stay in an ignored local cache
or GitHub Actions cache, not in Git history or the published website.

The same subscribed Codex research run returns a compact equation-to-English
pronunciation list and source-exact terminology groups. They add some output
tokens but no second model call or paid speech API. The controller publishes the digest and
`audio/scripts/YYYY-MM-DD.json` together in one protected Git commit. Validation
requires every distinct item equation exactly once. Code creates the spoken
version from the original title, authors, ID, summary, background, and relevance.
Only math notation, acronym pronunciation, and annotated phrase delivery change.
Redundant inline v1 source
links are omitted from rendering and speech; the footer arXiv link remains.
`speech.txt` in each new release contains the actual English narration.

The generator checks the source and pronunciation hashes. A changed equation
reading cannot silently use an old recording. Missing or stale pronunciation
metadata stops new audio rather than falling back to symbol-by-symbol reading.
Existing pronunciation companions use narration version 4. New daily deliveries
use version 6, which adds terminology grouping to version 5's math rhythm while
retaining “Item 1”, a 0.6-second pause,
then the title, without a repeated digest date. The title-to-authors pause and
tested letter-A pronunciation inside equations are retained. Updating a companion
invalidates its previous recording; the publication workflow generates a new
immutable release on its next run.

Future math readings follow the preferences in `prompts/local-research.md`:
`[[4,2,2]]` is “four two two” in a QEC context, and creation operators use the
subscript before “dagger”: `c_j` is “C sub J”, and `c_{j+1}` is
“C sub (J plus one)”. Single-letter symbols such as `N` and `\mathcal{N}`
are simply “N” when context is clear, as in “large N” or “N equals four super
Yang Mills”; use “capital N” when clarification is needed. Versions 5 and later
accept `[p]` in a math pronunciation for 0.18
seconds of actual silence, and `(words)` for a compact group spoken at 1.1 times
the normal speed. For example:
`F sub J [p] equals [p] C sub J dagger [p] plus [p] C sub (J plus one) dagger`.
Groups cannot nest or contain pauses. These controls apply only inside the
equation's `spoken` field; prose parentheses keep their ordinary meaning. The
exporter converts the controls into timing segments and removes them from
`speech.txt`. Versions 2–4 retain their original rendering behavior.

Version 6 also accepts `phrase_groups`: a list of lists of exact source parts.
For example, `["Large $N$ Vector and SYK-like Models"]` keeps the whole term
together; `["Large $N$", "Vector and SYK-like Models"]` inserts a 0.18-second
pause after the shared modifier. The research run chooses grouping from the
paper's meaning. `["Sachdev–Ye–Kitaev"]` treats the names as one continuous
unit, with dash separators converted to spaces for synthesis. Groups can span
inline math and ordinary words. They retain normal speed, override internal
math rhythm, and stay in a single synthesis request without ordinary chunking.
The written title and prose are preserved. Validation requires source-exact,
nonoverlapping groups and rejects boundaries that split a math expression.
Updating grouping changes the audio identity; versions 2–5 keep their previous
behavior. Kokoro still determines pitch and word-level prosody inside a group;
a single synthesis request cannot guarantee a completely flat contour or zero
model-generated silence.

**Play day** opens the day's complete playlist at Item 1. **Play item** opens the
same playlist at that item. The track picker and previous/next buttons jump between
items; the progress bar seeks within the current item. Speed, play/pause, position,
item titles, and previous/next actions are also registered with Media Session for
lock-screen and headphone controls. There are no 30-second skip buttons.

The player requests automatic preloading and distinguishes buffering from actual
playback. While playback is requested, a 15-second lack of progress triggers a
fresh connection at the current position and selected speed, with at most three
consecutive attempts. Recovery also checks when the page returns or the network
reconnects. Pausing or closing cancels recovery. Recovery runs automatically;
there is no reconnect control. A real Pixel lock-screen check is still needed:
a website cannot detect every Android audio-output interruption or run recovery
while Chrome suspends its JavaScript.

The whole-day recording is the item PCM recordings concatenated in rank order,
starting with Item 1 and without a daily overview or closing notes. The playlist
uses this continuous native stream with the manifest's item boundaries as chapters.
A sleeping page does not have to load another file or run JavaScript between
papers. Changing tracks seeks within that stream, while the player and lock-screen
timeline show the position within the selected item. There are 1.5 seconds of real
silence between summary, background, and relevance, a 0.6-second pause between
the item number and title, a 0.75-second pause between
title and authors, a 0.5-second pause before summary, and an item-end pause.
**Download playlist (ZIP)** saves all the individual item MP3s in rank order,
named `arxiv-YYYY-MM-DD-item-01.mp3`, `arxiv-YYYY-MM-DD-item-02.mp3`, and so on.
The release publisher builds the ZIP for both new and reused recordings without
regenerating speech. The link appears only after the archive is published and
listed in the audio index. Extract the ZIP to play the files in an Android audio
player offline.
Kokoro is a speech model, not a physics solver: correctness comes from the
checked English script, and unusual names can still need pronunciation corrections.
Audio failures leave reading/copy available and do not block text publication.

For a local refresh of an already published audio index:

```powershell
python -c "import urllib.request; urllib.request.urlretrieve('https://zhou-yang-quantum.github.io/arXiv-carte-blanche/data/audio/index.json', 'audio/index.json')"
docker compose up --build -d --wait
```

For offline rendering, install Node build dependencies, Python speech dependencies,
FFmpeg and eSpeak NG, then run `python tools/generate_audio.py --local-only --date YYYY-MM-DD`.
Alternatively, build `docker build -f audio/Dockerfile -t daily-arxiv-speech .` and
mount the repository at `/app` when running the image with `--local-only --date YYYY-MM-DD`.
Publishing uses the existing GitHub CLI login or the workflow's scoped token.

The **Publish arXiv carte blanche** workflow also accepts an optional `audio_dates` input:
comma-separated dates without spaces, such as `2026-10-14,2026-10-15`. A manual
run processes only those recordings and then publishes the site. Leave it blank
to process all dates. To publish text promptly, first select dates whose recordings
are already available, then queue the new dates in a second run. Each run retains
the other still-current recordings from the published audio index.

For a fast website publication that reuses available recordings, select **reuse_audio_only** in the manual workflow, or run `python tools/generate_audio.py --reuse-only`. Missing recordings are skipped without starting synthesis. Existing pre-rename manifest links are normalized to the current repository without regenerating their MP3 files.
