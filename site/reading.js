/* Canonical text exports. Keep TeX intact and never read KaTeX's duplicate DOM. */
(function (root) {
  'use strict';
  const mathPattern = /\\\[[\s\S]*?\\\]|\\\([\s\S]*?\\\)|\$\$[\s\S]*?\$\$|(?<!\\)\$(?!\$)(?:\\.|[^$\n])+?\$/g;
  function removeSourceLinks(source) {
    return (source || '').replace(/\s*\[v1\b[^\]]*\]\(https:\/\/arxiv\.org\/(?:html|abs)\/[^)]+\)/gi, '');
  }
  function decode(value) {
    const named = { amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: ' ', ndash: '–', mdash: '—' };
    return value.replace(/&(#x[\da-f]+|#\d+|[a-z]+);/gi, (all, name) => {
      if (name[0] === '#') {
        const number = name[1].toLowerCase() === 'x' ? parseInt(name.slice(2), 16) : parseInt(name.slice(1), 10);
        return number > 0 && number <= 0x10ffff ? String.fromCodePoint(number) : all;
      }
      return named[name] ?? all;
    });
  }
  function plainText(source) {
    if (!source) return '';
    source = removeSourceLinks(source);
    const equations = [];
    let prefix = 'DIGESTMATH';
    while (source.includes(prefix)) prefix += 'X';
    const protectedSource = source.replace(mathPattern, (math) => {
      equations.push(math); return prefix + (equations.length - 1) + 'END';
    });
    const inline = (tokens) => (tokens || []).map((token) => {
      if (token.tokens) return inline(token.tokens);
      if (token.type === 'br') return '\n';
      if (token.type === 'html') return token.text.replace(/<[^>]*>/g, '');
      return token.text || '';
    }).join('');
    const blocks = (tokens) => tokens.map((token) => {
      if (token.type === 'space' || token.type === 'hr') return '';
      if (token.type === 'list') return token.items.map((item, index) =>
        (token.ordered ? ((token.start || 1) + index) + '. ' : '• ') + blocks(item.tokens)).join('\n');
      if (token.type === 'blockquote') return blocks(token.tokens);
      if (token.type === 'table') return [token.header, ...token.rows].map((row) => row.map((cell) => inline(cell.tokens)).join(' | ')).join('\n');
      if (token.tokens) return inline(token.tokens);
      if (token.type === 'html') return token.text.replace(/<(script|style)[\s\S]*?<\/\1>/gi, '').replace(/<[^>]*>/g, '');
      return token.text || '';
    }).filter(Boolean).join('\n\n');
    return decode(blocks(root.marked.lexer(protectedSource)))
      .replace(new RegExp(prefix + '(\\d+)END', 'g'), (_, index) => equations[Number(index)])
      .replace(/[ \t]+\n/g, '\n').trim();
  }
  function itemText(day, paper) {
    return ['Item ' + paper.rank + '.', plainText(paper.title),
      'Authors: ' + plainText(paper.authors || ''), 'arXiv:' + paper.id,
      'Summary', plainText(paper.summary), 'Background', plainText(paper.background),
      'Why it matters?', plainText(paper.why)].join('\n\n');
  }
  function dayText(day) {
    return [day.title, day.overview ? 'Overview\n\n' + plainText(day.overview) : '',
      ...day.papers.map((paper) => itemText(day, paper)), day.notes ? 'Notes\n\n' + plainText(day.notes) : '']
      .filter(Boolean).join('\n\n');
  }
  function voiceText(day) {
    return 'Prepare to read ' + day.title + ' (' + day.papers.length + ' items). The text below is the authoritative digest. '
      + 'Confirm its date and item count, then wait for me to say "start". '
      + 'Start with Item 1. Introduce each item with only "Item N", pause, then read its title. Do not repeat the digest date before each item. '
      + 'Read each requested item completely and verbatim: title, authors, arXiv ID, summary, background, and why it matters. '
      + 'Pronounce the mathematics faithfully. Stop after each item and wait for my questions or the next reading command. '
      + 'Keep answers to questions separate from the reading. Before "read item N", locate that exact dated item again. '
      + 'Do not summarize, add information, silently correct equations, or reconstruct missing text. If the exact source is unavailable, stop and say so.\n\n'
      + 'BEGIN DIGEST: ' + day.title + '\n\n' + dayText(day) + '\n\nEND DIGEST: ' + day.title;
  }
  root.DigestReading = Object.freeze({ plainText, itemText, dayText, voiceText, mathPattern, removeSourceLinks });
})(globalThis);
