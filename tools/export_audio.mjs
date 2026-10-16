// Build a spoken version by replacing verified math, without rewriting prose.
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { marked } from 'marked';
globalThis.marked = marked;
await import('../site/reading.js');
const reading = globalThis.DigestReading;
const [input, output, scriptFolder = fileURLToPath(new URL('../audio/scripts/', import.meta.url))] = process.argv.slice(2);
const days = JSON.parse(await fs.readFile(input, 'utf8'));
await fs.mkdir(output, { recursive: true });
function normalizeSpeech(text) {
  return text.replace(/\b(?:QEC|QFT|QLDPC|LDPC|CNOT|CCZ|QCD|SPT|SYK|RG|YM|OTOC)\b/g, word => [...word].join(' '))
    .replace(/\[\[/g, '[ [').replace(/\]\]/g, '] ]');
}
function pronounce(text, substitutions, robustLetters = false, flattenRhythm = false) {
  return normalizeSpeech(reading.plainText(text).replace(reading.mathPattern, expression => {
    if (!substitutions.has(expression)) throw new Error('Missing English pronunciation: ' + expression);
    let spoken = substitutions.get(expression);
    if (flattenRhythm) spoken = spoken.replace(/\[p\]/g, ' ').replace(/[()]/g, '').replace(/[ \t]+/g, ' ').trim();
    // In the pinned US phonemizer, ordinary capital A can become an article.
    // Apply the tested /eɪ/ spelling only to letter A inside math substitutions.
    return robustLetters && /(?<![A-Za-z])A(?![a-z])/.test(expression) ? spoken.replace(/\bA\b/g, 'eh') : spoken;
  }));
}
function prepareSection(name, source, substitutions, robustLetters, rhythmic, phraseGroups = []) {
  if (!rhythmic) return { name, text: pronounce(source, substitutions, robustLetters) };
  let prefix = 'DIGESTPHRASE';
  while (source.includes(prefix)) prefix += 'X';
  const phrases = new Map();
  let protectedSource = source;
  for (const parts of phraseGroups) {
    const phrase = parts.join(' ');
    if (!source.includes(phrase)) continue;
    const token = prefix + phrases.size + 'END';
    protectedSource = protectedSource.split(phrase).join(token);
    phrases.set(token, parts);
  }
  const plain = reading.plainText(protectedSource);
  const segments = [];
  function addText(text, speed = 1.0) {
    if (!text) return;
    const previous = segments.at(-1);
    // Keep a following sentence mark attached to its phrase, not a TTS call by itself.
    if (previous?.keep_together) {
      const punctuation = text.match(/^[.,;:!?…'"’”)\]]+/)?.[0] ?? '';
      previous.text += punctuation;
      text = text.slice(punctuation.length);
      if (!text) return;
    }
    if (previous?.speed === speed && !previous.keep_together) previous.text += text;
    else segments.push({ text, speed });
  }
  let offset = 0;
  const pattern = new RegExp(reading.mathPattern.source + (phrases.size ? '|' + prefix + '\\d+END' : ''), 'g');
  for (const match of plain.matchAll(pattern)) {
    addText(normalizeSpeech(plain.slice(offset, match.index)));
    if (phrases.has(match[0])) {
      phrases.get(match[0]).forEach((part, index) => {
        if (index) segments.push({ pause_seconds: 0.18 });
        // Treat name separators and compound-word hyphens as word joins, not asides.
        const spoken = pronounce(part, substitutions, robustLetters, true).replace(/(\p{L})[–—-](?=\p{L})/gu, '$1 ').replace(/[ \t]+/g, ' ');
        if (!spoken.trim() || spoken.length > 650) throw new Error('Audio phrase is empty or too long');
        segments.push({ text: spoken, speed: 1.0, keep_together: true });
      });
    } else {
      // Only parse equation rhythm controls inside a verified math substitution.
      const spoken = pronounce(match[0], substitutions, robustLetters);
      for (const part of spoken.split(/(\[p\]|\([^()]+\))/g)) {
        if (part === '[p]') segments.push({ pause_seconds: 0.18 });
        else if (part.startsWith('(') && part.endsWith(')')) addText(part.slice(1, -1), 1.1);
        else addText(part);
      }
    }
    offset = match.index + match[0].length;
  }
  addText(normalizeSpeech(plain.slice(offset)));
  // Keep speech.txt readable: timing controls are metadata, never spoken words.
  const text = segments.map(segment => segment.text ?? ' ').join('').replace(/[ \t]+/g, ' ').trim();
  if (!phrases.size) return { name, text, segments };
  const runs = [];
  for (const segment of segments) {
    if ('pause_seconds' in segment) { runs.push(segment); continue; }
    const previous = runs.at(-1);
    const run = previous?.speed === segment.speed ? previous : { text: '', speed: segment.speed };
    if (run !== previous) runs.push(run);
    // The renderer indexes Python strings by Unicode code points, not UTF-16 units.
    const start = [...run.text].length;
    run.text += segment.text;
    if (segment.keep_together) {
      (run.protected_spans ??= []).push([start, [...run.text].length]);
    }
  }
  return { name, text, segments: runs };
}
for (const day of days) {
  let script;
  try { script = JSON.parse(await fs.readFile(path.join(scriptFolder, day.date + '.json'), 'utf8')); }
  catch (error) { if (error.code === 'ENOENT') continue; throw error; }
  if (![2, 3, 4, 5, 6].includes(script.version) || script.date !== day.date) throw new Error('Invalid dated speech script');
  const modern = script.version >= 3;
  const simpleHeading = script.version >= 4;
  const rhythmic = script.version >= 5;
  const phraseGroups = script.version >= 6 ? script.phrase_groups : [];
  if (!Array.isArray(phraseGroups)) throw new Error('Missing audio phrase groups');
  const substitutions = new Map(script.pronunciations.map(entry => [entry.latex, entry.spoken]));
  const spokenDate = new Intl.DateTimeFormat('en-US', { timeZone: 'UTC', month: 'long', day: 'numeric', year: 'numeric' }).format(new Date(day.date + 'T12:00:00Z'));
  const items = day.papers.map(paper => {
    const heading = prepareSection('heading', (simpleHeading ? '' : 'arXiv, ' + spokenDate + '. Item ' + paper.rank + '.\n\n') + paper.title, substitutions, modern, rhythmic, phraseGroups);
    const authors = 'Authors: ' + reading.plainText(paper.authors) + '.\n\narXiv number ' + paper.id.split('.').map(part => [...part].join(' ')).join(', point, ');
    const sections = [
      ...(simpleHeading ? [{ name: 'item', text: 'Item ' + paper.rank + '.' }] : []),
      ...(modern ? [heading, { name: 'authors', text: authors }] : [{ name: 'heading', text: heading.text + '\n\n' + authors }]),
      ...[['summary', 'Summary.\n\n' + paper.summary], ['background', 'Background.\n\n' + paper.background],
        ['why', 'Why it matters?\n\n' + paper.why]].map(([name, source]) => prepareSection(name, source, substitutions, modern, rhythmic, phraseGroups)),
    ];
    return { rank: paper.rank, id: paper.id, title: reading.plainText(paper.title), sections,
      text: sections.map(section => section.text).join('\n\n') };
  });
  const prepared = { version: script.version, date: day.date, title: day.title, source_hash: script.source_hash,
    section_pause_seconds: 1.5, heading_pause_seconds: 0.5, item_pause_seconds: 1.5,
    items, text: items.map(item => item.text).join('\n\n') };
  if (modern) prepared.title_author_pause_seconds = 0.75;
  if (simpleHeading) prepared.item_title_pause_seconds = 0.6;
  await fs.writeFile(path.join(output, day.date + '.json'), JSON.stringify(prepared, null, 2) + '\n');
  await fs.writeFile(path.join(output, day.date + '.txt'), prepared.text + '\n');
}
console.log('Prepared English speech scripts; day audio contains items only.');
