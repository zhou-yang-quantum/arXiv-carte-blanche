/* A static archive with optional, per-reader Dropbox bookmark sync. */
'use strict';
const $ = (selector) => document.querySelector(selector);
const icons = {
  play: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m8 4 12 8-12 8z"/></svg>',
  bot: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="5" y="7" width="14" height="13" rx="3"/><path d="M12 3v4M3 11v5m18-5v5M9 16h6"/><circle cx="9" cy="12" r=".8"/><circle cx="15" cy="12" r=".8"/></svg>',
  plus: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14M12 5v14"/></svg>',
  minus: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14"/></svg>',
  bookmark: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 3h12v18l-6-4-6 4z"/></svg>',
  arrow: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 19 19 5M5 5h14v14"/></svg>',
};
const state = { archive: null, date: '', query: '', topic: '', savedOnly: false, compact: false };
const calendarToday = new Date();
let calendarMonth = new Date(calendarToday.getFullYear(), calendarToday.getMonth(), 1);
const escapeHTML = (value) => String(value).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const bookmarkSync = new DropboxBookmarks();
const saved = bookmarkSync.saved;
const player = new DigestAudio($('#audio-player'), { isSaved: id => saved.has(id), toggleSaved });
function setSidebarHidden(hidden, savePreference = false) {
  $('#calendar-popover').hidePopover();
  $('.page-shell').classList.toggle('sidebar-hidden', hidden);
  const button = $('#sidebar-button');
  button.setAttribute('aria-expanded', String(!hidden));
  button.querySelector('span').textContent = hidden ? 'Show sidebar' : 'Hide sidebar';
  button.title = hidden ? 'Show archive sidebar' : 'Hide archive sidebar';
  if (savePreference) {
    try { localStorage.setItem('daily-arxiv:sidebar:v1', hidden ? 'hidden' : 'visible'); } catch {}
  }
}
let sidebarHidden = false;
try { sidebarHidden = localStorage.getItem('daily-arxiv:sidebar:v1') === 'hidden'; } catch {}
setSidebarHidden(sidebarHidden);
$('#sidebar-button').addEventListener('click', () => setSidebarHidden(!$('.page-shell').classList.contains('sidebar-hidden'), true));
function refreshAudioButtons() {
  if (!state.archive) return;
  const day = currentDay();
  $('#play-day').disabled = !player.entry(day);
  $('#play-day').title = player.entry(day) ? 'Play day' : 'Audio is not available yet';
  for (const card of document.querySelectorAll('.paper-card')) {
    const source = state.archive.days.find((entry) => entry.date === card.dataset.date);
    const button = card.querySelector('[data-action="play"]');
    button.disabled = !source || !player.entry(source, Number(card.dataset.rank));
    button.title = button.disabled ? 'Audio is not available yet' : 'Play item ' + card.dataset.rank;
  }
}
function refreshSyncStatus() {
  const { state: status, message } = bookmarkSync.ui;
  $('#sync-status').textContent = message;
  $('#connect-dropbox').hidden = bookmarkSync.connected;
  $('#connect-dropbox').disabled = !bookmarkSync.appKey || status === 'loading';
  $('#connect-dropbox').textContent = status === 'expired' ? 'Reconnect Dropbox' : 'Connect Dropbox';
  $('#sync-now').hidden = !bookmarkSync.connected;
  $('#sync-now').disabled = status === 'syncing';
  $('#disconnect-dropbox').hidden = !bookmarkSync.connected;
  $('#save-storage-status').textContent = bookmarkSync.connected || status === 'expired' ? message : 'Saved papers stay in this browser.';
}
bookmarkSync.addEventListener('status', refreshSyncStatus);
bookmarkSync.addEventListener('change', () => {
  $('#saved-count').textContent = String(saved.size);
  player.refreshSave();
  if (!state.archive) return;
  if (state.savedOnly) render();
  else for (const card of document.querySelectorAll('.paper-card')) {
    const button = card.querySelector('[data-action="save"]');
    const isSaved = saved.has(card.dataset.id);
    button.setAttribute('aria-pressed', String(isSaved));
    button.setAttribute('aria-label', (isSaved ? 'Unsave' : 'Save') + ' item ' + card.dataset.rank);
    button.title = button.getAttribute('aria-label');
  }
});
$('#sync-settings').addEventListener('click', () => { refreshSyncStatus(); $('#sync-dialog').showModal(); });
$('#close-sync').addEventListener('click', () => $('#sync-dialog').close());
$('#connect-dropbox').addEventListener('click', () => bookmarkSync.connect());
$('#sync-now').addEventListener('click', () => bookmarkSync.sync());
$('#disconnect-dropbox').addEventListener('click', () => bookmarkSync.disconnect());
refreshSyncStatus();
function toast(message) {
  $('#toast').textContent = message;
  $('#toast').hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => { $('#toast').hidden = true; }, 2800);
}
function toggleSaved(id) {
  const stored = bookmarkSync.toggle(id);
  if (stored) toast(saved.has(id) ? 'Paper saved' : 'Removed from saved papers');
  else toast('Your browser could not save this change. It will last for this visit.');
}
function formatDate(date, options = { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' }) {
  return new Intl.DateTimeFormat('en-US', { ...options, timeZone: 'UTC' }).format(new Date(date + 'T12:00:00Z'));
}
function math(element) {
  if (!window.renderMathInElement) return;
  renderMathInElement(element, {
    delimiters: [{ left: '\\[', right: '\\]', display: true }, { left: '$$', right: '$$', display: true }, { left: '\\(', right: '\\)', display: false }, { left: '$', right: '$', display: false }],
    throwOnError: false, trust: false, strict: 'ignore', maxExpand: 1000,
  });
}
function markdown(element, text) {
  text = DigestReading.removeSourceLinks(text);
  // Keep TeX delimiters intact through Markdown's backslash processing.
  const equations = [];
  const protectedText = text.replace(DigestReading.mathPattern, (equation) => {
    equations.push(equation); return 'ARXIVMATHPLACEHOLDER' + (equations.length - 1) + 'END';
  });
  const parsed = marked.parse(protectedText, { breaks: false, gfm: true });
  const template = document.createElement('template');
  template.innerHTML = parsed;
  // Imported notes are content, not executable HTML. Restrict markup and links.
  const allowed = new Set(['P', 'STRONG', 'EM', 'A', 'UL', 'OL', 'LI', 'BLOCKQUOTE', 'CODE', 'PRE', 'BR', 'HR', 'H4', 'H5', 'H6', 'DEL', 'TABLE', 'THEAD', 'TBODY', 'TR', 'TH', 'TD']);
  for (const node of [...template.content.querySelectorAll('*')]) {
    if (!allowed.has(node.tagName)) {
      if (['SCRIPT', 'STYLE', 'IFRAME', 'OBJECT', 'SVG', 'MATH'].includes(node.tagName)) node.remove();
      else node.replaceWith(...node.childNodes);
      continue;
    }
    const href = node.tagName === 'A' ? node.getAttribute('href') : null;
    for (const attribute of [...node.attributes]) node.removeAttribute(attribute.name);
    if (href && /^https:\/\//i.test(href)) {
      node.setAttribute('href', href); node.setAttribute('target', '_blank'); node.setAttribute('rel', 'noopener noreferrer');
    }
  }
  element.replaceChildren(template.content);
  const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  for (const node of nodes) node.textContent = node.textContent.replace(/ARXIVMATHPLACEHOLDER(\d+)END/g, (_, index) => equations[Number(index)] || '');
  math(element);
}
function currentDay() { return state.archive.days.find((day) => day.date === state.date) || state.archive.days[0]; }
function isArchiveSearch() { return Boolean(state.query || state.topic || state.savedOnly); }
function syncHash(paperRank) {
  const params = new URLSearchParams();
  params.set('date', state.date);
  if (state.query) params.set('q', state.query);
  if (state.topic) params.set('topic', state.topic);
  if (state.savedOnly) params.set('saved', '1');
  if (paperRank) params.set('paper', paperRank);
  history.replaceState(null, '', '#' + params.toString());
}
function applyHash() {
  if (!state.archive) return;
  const params = new URLSearchParams(location.hash.slice(1));
  state.date = state.archive.days.some((d) => d.date === params.get('date')) ? params.get('date') : state.archive.days[0].date;
  state.query = params.get('q') || '';
  state.topic = state.archive.topics.includes(params.get('topic')) ? params.get('topic') : '';
  state.savedOnly = params.get('saved') === '1';
  if (params.get('date') === state.date) calendarMonth = new Date(state.date.slice(0, 7) + '-01T12:00:00');
  render();
  const rank = Number(params.get('paper'));
  if (currentDay().papers.some((paper) => paper.rank === rank)) openPaper(state.date, rank);
}
function selectDate(date) {
  state.date = date; state.query = ''; state.topic = ''; state.savedOnly = false;
  calendarMonth = new Date(date.slice(0, 7) + '-01T12:00:00');
  $('#calendar-popover').hidePopover();
  syncHash(); render();
  window.scrollTo({ top: 0, behavior: 'instant' });
}
function renderArchive() {
  const days = state.archive.days;
  $('#archive-count').textContent = days.length + (days.length === 1 ? ' day' : ' days');
  $('#calendar-button').disabled = false;
  renderCalendars();
}
const monthNames = Array.from({ length: 12 }, (_, month) => new Intl.DateTimeFormat('en-US', { month: 'long' }).format(new Date(2000, month, 1)));
function availableCalendarMonths() {
  return [...new Set(state.archive.days.map(day => day.date.slice(0, 7)))].sort();
}
function calendarMonthKey(date = calendarMonth) {
  return date.getFullYear() + '-' + String(date.getMonth() + 1).padStart(2, '0');
}
function calendarDateKey(date = new Date()) {
  return calendarMonthKey(date) + '-' + String(date.getDate()).padStart(2, '0');
}
function todayMenu() {
  const today = calendarDateKey();
  return state.archive.days.filter(day => day.date <= today).sort((a, b) => b.date.localeCompare(a.date))[0];
}
function renderCalendars() {
  if (!state.archive) return;
  const months = availableCalendarMonths();
  const requested = calendarMonthKey();
  const selectedMonth = months.includes(requested) ? requested : months.filter(month => month < requested).at(-1) || months[0];
  calendarMonth = new Date(selectedMonth + '-01T12:00:00');
  const monthIndex = months.indexOf(selectedMonth);
  const year = calendarMonth.getFullYear();
  const month = calendarMonth.getMonth();
  const firstWeekday = calendarMonth.getDay();
  const dayCount = new Date(year, month + 1, 0).getDate();
  const available = new Map(state.archive.days.map(day => [day.date, day]));
  const today = calendarDateKey();
  const currentMenu = todayMenu();
  for (const calendar of document.querySelectorAll('.digest-calendar')) {
    if (!calendar.children.length) {
      calendar.innerHTML = '<div class="calendar-heading"><button class="calendar-arrow" data-month-step="-1" aria-label="Previous month"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m14 6-6 6 6 6"/></svg></button><div class="calendar-selectors"><select class="calendar-month" aria-label="Month"></select><select class="calendar-year" aria-label="Year"></select></div><button class="calendar-arrow" data-month-step="1" aria-label="Next month"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m10 6 6 6-6 6"/></svg></button></div><table class="calendar-table"><thead><tr>' + ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'].map(name => '<th scope="col"><abbr title="' + name + '">' + name.slice(0, 2) + '</abbr></th>').join('') + '</tr></thead><tbody></tbody></table><p class="sr-only calendar-announcement" aria-live="polite"></p><div class="calendar-footer"><span class="calendar-key">Digest available</span><button class="text-button" data-calendar-today>Today</button></div>';
    }
    const yearSelect = calendar.querySelector('.calendar-year');
    yearSelect.innerHTML = [...new Set(months.map(month => month.slice(0, 4)))].map(year => '<option>' + year + '</option>').join('');
    calendar.querySelector('.calendar-month').innerHTML = months.filter(month => month.startsWith(year + '-')).map(month => {
      const index = Number(month.slice(5)) - 1;
      return '<option value="' + index + '">' + monthNames[index] + '</option>';
    }).join('');
    calendar.querySelector('.calendar-month').value = month;
    calendar.querySelector('[data-month-step="-1"]').disabled = monthIndex === 0;
    calendar.querySelector('[data-month-step="1"]').disabled = monthIndex === months.length - 1;
    const todayButton = calendar.querySelector('[data-calendar-today]');
    todayButton.disabled = !currentMenu;
    todayButton.title = currentMenu?.date === today ? "Open today's menu" : currentMenu ? 'No menu for today; open the latest available (' + currentMenu.date.replaceAll('-', '/') + ')' : 'No menu is available for today yet';
    yearSelect.value = year;
    const label = monthNames[month] + ' ' + year;
    calendar.querySelector('table').setAttribute('aria-label', label);
    calendar.querySelector('.calendar-announcement').textContent = label;
    let cells = '';
    const cellCount = Math.ceil((firstWeekday + dayCount) / 7) * 7;
    for (let cell = 0; cell < cellCount; cell++) {
      if (cell % 7 === 0) cells += '<tr>';
      const number = cell - firstWeekday + 1;
      if (number < 1 || number > dayCount) cells += '<td></td>';
      else {
        const date = year + '-' + String(month + 1).padStart(2, '0') + '-' + String(number).padStart(2, '0');
        const day = available.get(date);
        const selected = state.date === date && !isArchiveSearch();
        cells += '<td><button class="calendar-day' + (selected ? ' selected' : '') + (date === today ? ' today' : '') + '" data-date="' + date + '" aria-label="' + formatDate(date) + (day ? ' · ' + day.papers.length + ' papers' : ' · No digest') + '"' + (day ? '' : ' disabled') + (selected ? ' aria-pressed="true"' : day ? ' aria-pressed="false"' : '') + (date === today ? ' aria-current="date"' : '') + '>' + number + '</button></td>';
      }
      if (cell % 7 === 6) cells += '</tr>';
    }
    calendar.querySelector('tbody').innerHTML = cells;
  }
}
for (const calendar of document.querySelectorAll('.digest-calendar')) {
  calendar.addEventListener('click', event => {
    const day = event.target.closest('[data-date]');
    if (day && !day.disabled) { selectDate(day.dataset.date); return; }
    const step = event.target.closest('[data-month-step]');
    if (step) {
      const months = availableCalendarMonths();
      const next = months[months.indexOf(calendarMonthKey()) + Number(step.dataset.monthStep)];
      if (!next) return;
      calendarMonth = new Date(next + '-01T12:00:00');
    }
    else if (event.target.closest('[data-calendar-today]')) {
      const day = todayMenu();
      if (!day) return;
      selectDate(day.date);
      if (day.date !== calendarDateKey()) toast('No menu for today yet. Showing the latest available menu.');
      return;
    }
    else return;
    renderCalendars();
  });
  calendar.addEventListener('change', event => {
    if (!event.target.matches('.calendar-month, .calendar-year')) return;
    const year = calendar.querySelector('.calendar-year').value;
    const requested = year + '-' + String(Number(calendar.querySelector('.calendar-month').value) + 1).padStart(2, '0');
    const months = availableCalendarMonths().filter(month => month.startsWith(year + '-'));
    calendarMonth = new Date((months.includes(requested) ? requested : months[0]) + '-01T12:00:00');
    renderCalendars();
  });
}
function positionCalendarPopover() {
  const popover = $('#calendar-popover');
  if (!popover.matches(':popover-open')) return;
  const button = $('#calendar-button').getBoundingClientRect();
  const width = popover.offsetWidth;
  popover.style.left = Math.max(8, Math.min(button.left, innerWidth - width - 8)) + 'px';
  popover.style.top = Math.max(8, Math.min(button.bottom + 8, innerHeight - popover.offsetHeight - 8)) + 'px';
}
$('#calendar-popover').addEventListener('toggle', event => {
  if (event.newState !== 'open') return;
  positionCalendarPopover();
  const calendar = $('#popup-calendar');
  (calendar.querySelector('.selected') || calendar.querySelector('.calendar-month')).focus({ preventScroll: true });
});
window.addEventListener('resize', () => { $('#calendar-popover').hidePopover(); });
window.addEventListener('scroll', positionCalendarPopover, { passive: true });
function renderTopics() {
  const topics = ['', ...state.archive.topics];
  $('#topic-filters').innerHTML = topics.map((topic) => '<button class="topic-chip" data-topic="' + escapeHTML(topic) + '" aria-pressed="' + (state.topic === topic) + '">' + escapeHTML(topic || 'All topics') + '</button>').join('');
}
function matches(paper) {
  if (state.savedOnly && !saved.has(paper.id)) return false;
  if (state.topic && !paper.topics.includes(state.topic)) return false;
  if (state.query) {
    const haystack = [paper.id, paper.title, paper.authors, paper.summary, paper.background, paper.why, ...paper.topics].join(' ').toLowerCase();
    if (!state.query.toLowerCase().split(/\s+/).filter(Boolean).every((word) => haystack.includes(word))) return false;
  }
  return true;
}
function renderPaper(day, paper) {
  const card = document.createElement('article');
  card.className = 'paper-card';
  card.id = 'paper-' + day.date + '-' + paper.rank;
  card.dataset.date = day.date; card.dataset.rank = paper.rank; card.dataset.id = paper.id;
  card.innerHTML = '<div class="paper-header"><div class="paper-content"><div class="paper-title-row"><span class="paper-rank">' + String(paper.rank).padStart(2, '0') + '</span><h3></h3></div><p class="authors"></p></div></div><details class="paper-detail"' + (!state.compact ? ' open' : '') + '><summary hidden>Paper details</summary><h4 class="section-label">SUMMARY</h4><div class="prose paper-summary"></div><section class="background-note"><h4 class="section-label">BACKGROUND</h4><div class="prose paper-background"></div></section><section class="why-note"><h4 class="section-label">WHY IT MATTERS?</h4><div class="prose paper-why"></div></section><div class="paper-footer"><div class="paper-links"><a href="' + paper.url + '" target="_blank" rel="noopener noreferrer">arXiv ' + icons.arrow + '</a><a class="secondary" href="https://arxiv.org/pdf/' + paper.id + '" target="_blank" rel="noopener noreferrer">PDF ' + icons.arrow + '</a></div></div></details>';
  card.querySelector('h3').textContent = paper.title; math(card.querySelector('h3'));
  card.querySelector('.authors').textContent = (paper.authors ? paper.authors + '  ·  ' : '') + 'arXiv:' + paper.id;
  const actions = document.createElement('div');
  actions.className = 'reading-actions paper-actions';
  actions.innerHTML = '<button class="text-button paper-action" data-action="play" aria-label="Play item ' + paper.rank + '" title="Play item ' + paper.rank + '">' + icons.play + '</button><button class="text-button bookmark-button paper-action" data-action="save" aria-label="' + (saved.has(paper.id) ? 'Unsave' : 'Save') + ' item ' + paper.rank + '" title="' + (saved.has(paper.id) ? 'Unsave' : 'Save') + ' item ' + paper.rank + '" aria-pressed="' + saved.has(paper.id) + '">' + icons.bookmark + '</button><a class="text-button paper-action" data-action="ask" target="_blank" rel="noopener noreferrer" aria-label="Ask GPT about item ' + paper.rank + '" title="Ask GPT about this paper">' + icons.bot + '</a><button class="text-button paper-action" data-action="details"></button>';
  actions.querySelector('[data-action="ask"]').href = 'https://chatgpt.com/?prompt=' + encodeURIComponent(DigestReading.questionPrompt(day, paper));
  const play = actions.querySelector('[data-action="play"]');
  play.disabled = !player.entry(day, paper.rank);
  if (play.disabled) play.title = 'Audio is not available yet';
  card.querySelector('.paper-content').append(actions);
  const details = card.querySelector('details');
  details.id = card.id + '-details';
  actions.querySelector('[data-action="details"]').setAttribute('aria-controls', details.id);
  details.addEventListener('toggle', () => syncDetails(card));
  syncDetails(card);
  markdown(card.querySelector('.paper-summary'), paper.summary);
  markdown(card.querySelector('.paper-background'), paper.background);
  markdown(card.querySelector('.paper-why'), paper.why);
  return card;
}
function syncDetails(card) {
  const open = card.querySelector('details').open;
  const button = card.querySelector('[data-action="details"]');
  button.innerHTML = open ? icons.minus : icons.plus;
  button.setAttribute('aria-label', open ? 'Hide details' : 'Show details');
  button.title = open ? 'Hide details' : 'Show details';
  button.setAttribute('aria-expanded', String(open));
}
function render() {
  const day = currentDay();
  const filtering = isArchiveSearch();
  const results = (filtering ? state.archive.days : [day]).flatMap((d) => d.papers.filter(matches).map((paper) => ({ day: d, paper })));
  document.title = day.title;
  $('#page-title').textContent = state.savedOnly ? 'Saved papers' : filtering ? 'Search results' : 'Le menu · ' + day.date.replaceAll('-', '/');
  $('#date-subtitle').hidden = !filtering;
  $('#date-subtitle').textContent = filtering ? state.archive.days.length + ' archived day' + (state.archive.days.length === 1 ? '' : 's') : '';
  $('#day-actions').hidden = filtering;
  $('#play-day').disabled = !player.entry(day);
  $('#play-day').title = player.entry(day) ? 'Play day' : 'Audio is not available yet';
  $('#latest-button').classList.toggle('active', !state.savedOnly);
  $('#latest-button').setAttribute('aria-pressed', !state.savedOnly);
  $('#saved-button').classList.toggle('active', state.savedOnly);
  $('#saved-button').setAttribute('aria-pressed', state.savedOnly);
  $('#saved-count').textContent = String(saved.size);
  $('#clear-filters').hidden = !filtering;
  $('#sync-settings').hidden = !state.savedOnly;
  $('#papers').replaceChildren(...results.map(({ day: d, paper }) => renderPaper(d, paper)));
  if (!results.length) {
    $('#papers').innerHTML = '<div class="empty-state"><h3>' + (state.savedOnly && !state.query && !state.topic ? 'No saved papers.' : 'No matching papers.') + '</h3><p>' + (state.savedOnly ? 'Use the bookmark button to save a paper.' : 'Try a different search or topic.') + '</p><button class="text-button" data-action="reset">Latest papers →</button></div>';
  }
  $('#day-notes').hidden = filtering || !day.notes;
  if (!filtering && day.notes) markdown($('#day-notes-content'), day.notes);
  const index = state.archive.days.indexOf(day);
  $('#day-navigation').hidden = filtering || state.archive.days.length < 2;
  $('#previous-day').disabled = index === state.archive.days.length - 1;
  $('#next-day').disabled = index === 0;
  $('#archive-status').textContent = 'Latest digest: ' + state.archive.days[0].date;
  renderArchive(); renderTopics();
}
function openPaper(date, rank) {
  const element = document.getElementById('paper-' + date + '-' + rank);
  if (!element) return;
  element.querySelector('details').open = true;
  element.scrollIntoView({ block: 'start', behavior: 'instant' });
}
function reset() { selectDate(state.archive.days[0].date); }
$('#latest-button').addEventListener('click', () => { if (state.archive) reset(); });
$('#saved-button').addEventListener('click', () => { if (!state.archive) return; state.savedOnly = !state.savedOnly; state.query = ''; state.topic = ''; syncHash(); render(); });
$('#topic-filters').addEventListener('click', (event) => { const button = event.target.closest('[data-topic]'); if (button) { state.topic = button.dataset.topic; syncHash(); render(); } });
$('#clear-filters').addEventListener('click', reset);
$('#play-day').addEventListener('click', () => { if (state.archive) player.play(currentDay()); });
$('#view-button').addEventListener('click', () => {
  state.compact = !state.compact;
  $('#view-button').setAttribute('aria-pressed', state.compact);
  $('#view-button span').textContent = state.compact ? 'Reading view' : 'Compact view';
  $('#view-button').title = state.compact ? 'Reading view' : 'Compact view';
  for (const details of document.querySelectorAll('.paper-detail')) details.open = !state.compact;
});
$('#papers').addEventListener('click', (event) => {
  if (event.target.closest('[data-action="reset"]')) { reset(); return; }
  const card = event.target.closest('.paper-card');
  if (!card) return;
  const button = event.target.closest('[data-action]');
  if (button?.dataset.action === 'details') {
    const details = card.querySelector('details');
    details.open = !details.open;
    syncDetails(card);
  } else if (button?.dataset.action === 'play') {
    const day = state.archive.days.find((entry) => entry.date === card.dataset.date);
    const paper = day?.papers.find((entry) => entry.rank === Number(card.dataset.rank));
    if (!paper) return;
    player.play(day, paper.rank);
  } else if (button?.dataset.action === 'save') {
    toggleSaved(card.dataset.id);
  }
});
$('#previous-day').addEventListener('click', () => { const i = state.archive.days.indexOf(currentDay()); if (state.archive.days[i + 1]) selectDate(state.archive.days[i + 1].date); });
$('#next-day').addEventListener('click', () => { const i = state.archive.days.indexOf(currentDay()); if (state.archive.days[i - 1]) selectDate(state.archive.days[i - 1].date); });
$('#preferences-button').addEventListener('click', () => $('#preferences-dialog').showModal());
$('#close-preferences').addEventListener('click', () => $('#preferences-dialog').close());
$('#preferences-dialog').addEventListener('click', (event) => { if (event.target === event.currentTarget) { const rect = event.currentTarget.getBoundingClientRect(); if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) event.currentTarget.close(); } });
window.addEventListener('hashchange', applyHash);
window.addEventListener('beforeprint', () => { document.querySelectorAll('.paper-detail').forEach((details) => { details.dataset.printWasOpen = details.open; details.open = true; }); });
window.addEventListener('afterprint', () => { document.querySelectorAll('.paper-detail').forEach((details) => { details.open = details.dataset.printWasOpen === 'true'; }); });
async function load() {
  // Audio availability must never delay loading the written digest.
  fetch('./data/audio/index.json').then(async (response) => {
    if (response.ok) { player.index = await response.json(); refreshAudioButtons(); }
  }).catch(() => {});
  try {
    const response = await fetch('./data/archive.json');
    if (!response.ok) throw new Error('Archive response ' + response.status);
    state.archive = await response.json();
    if (!state.archive.days?.length) throw new Error('Archive is empty');
    applyHash();
  } catch (error) {
    console.error(error);
    $('#date-subtitle').hidden = false;
    $('#date-subtitle').textContent = 'The archive could not be loaded.';
    $('#papers').innerHTML = '<div class="empty-state"><h3>Unable to load papers.</h3><p>Check your connection and reload.</p><button class="text-button" id="retry-button">Try again →</button></div>';
    $('#retry-button').addEventListener('click', load);
  }
  try {
    const response = await fetch('./data/preferences.json');
    if (!response.ok) throw new Error('Preferences unavailable');
    const preferences = await response.json();
    $('#preferences-content').innerHTML = '<h3>Prioritize</h3><div class="preference-tags">' + preferences.prioritize.map((topic) => '<span>' + escapeHTML(topic) + '</span>').join('') + '</div><h3>Exclude</h3><ul>' + preferences.exclude.map((topic) => '<li>' + escapeHTML(topic) + '</li>').join('') + '</ul><h3>Selection criteria</h3><ul>' + preferences.principles.map((principle) => '<li>' + escapeHTML(principle) + '</li>').join('') + '</ul>';
  } catch { $('#preferences-content').textContent = 'Selection preferences could not be loaded. Please reload to try again.'; }
}
load();
