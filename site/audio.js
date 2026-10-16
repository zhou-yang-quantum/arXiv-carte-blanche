/* Playlist chapters share one native stream, so locked-screen transitions need no JavaScript. */
(function (root) {
  'use strict';
  const audioBase = 'https://github.com/zhou-yang-quantum/arXiv-carte-blanche/releases/download/';
  const legacyAudioBase = 'https://github.com/zhou-yang-quantum/daily-arXiv/releases/download/';
  function canonicalAudioURL(url) {
    if (typeof url !== 'string') return null;
    if (url.startsWith(legacyAudioBase + 'audio-')) return audioBase + url.slice(legacyAudioBase.length);
    return url.startsWith(audioBase + 'audio-') ? url : null;
  }
  class DigestAudio {
    constructor(panel) {
      this.panel = panel;
      this.audio = panel.querySelector('audio');
      this.title = panel.querySelector('#audio-title');
      this.status = panel.querySelector('#audio-status');
      this.download = panel.querySelector('#audio-download');
      this.picker = panel.querySelector('#audio-track');
      this.toggle = panel.querySelector('#audio-toggle');
      this.timeline = panel.querySelector('#audio-progress');
      this.time = panel.querySelector('#audio-time');
      this.previous = panel.querySelector('#audio-previous');
      this.next = panel.querySelector('#audio-next');
      this.index = { days: {} };
      this.track = null;
      this.items = [];
      this.trackIndex = -1;
      this.request = 0;
      this.wantsPlayback = false;
      this.buffering = false;
      this.failure = '';
      this.pendingSeek = null;
      this.retries = 0;
      this.monitor = null;
      this.previous.addEventListener('click', () => this.skip(-1));
      this.next.addEventListener('click', () => this.skip(1));
      this.toggle.addEventListener('click', () => this.togglePlayback());
      this.picker.addEventListener('change', () => this.selectTrack(Number(this.picker.value)));
      this.timeline.addEventListener('input', () => this.seekTo(Number(this.timeline.value)));
      panel.querySelector('#audio-close').addEventListener('click', () => this.close());
      panel.querySelector('#audio-rate').addEventListener('change', (event) => {
        this.audio.playbackRate = Number(event.target.value); this.position();
      });
      this.audio.addEventListener('play', () => {
        if (!this.track) return;
        this.wantsPlayback = true;
        this.failure = '';
        this.lastProgress = performance.now();
        this.startMonitor();
        this.update();
      });
      this.audio.addEventListener('playing', () => { this.buffering = false; this.update(); });
      this.audio.addEventListener('pause', () => {
        // load() queues a pause event when reconnecting. A subsequent play()
        // has already cleared paused; only an actual pause cancels recovery.
        if (this.audio.paused) { this.wantsPlayback = false; this.stopMonitor(); }
        this.update();
      });
      this.audio.addEventListener('ended', () => {
        this.wantsPlayback = false;
        this.stopMonitor();
        this.update();
      });
      this.audio.addEventListener('loadedmetadata', () => {
        if (this.pendingSeek && Number.isFinite(this.audio.duration)) {
          this.audio.currentTime = Math.min(this.pendingSeek.time, this.audio.duration);
          this.lastPosition = this.audio.currentTime;
          this.pendingSeek = null;
        }
        this.audio.playbackRate = Number(this.panel.querySelector('#audio-rate').value);
        this.update();
      });
      this.audio.addEventListener('timeupdate', () => { this.progress(); this.update(); });
      for (const name of ['durationchange', 'ratechange', 'seeking', 'seeked', 'canplay']) {
        this.audio.addEventListener(name, () => this.update());
      }
      for (const name of ['waiting', 'stalled']) {
        this.audio.addEventListener(name, () => {
          // A stalled download is harmless while enough buffered audio remains.
          if (this.wantsPlayback && this.audio.readyState < 3) this.buffering = true;
          this.update();
        });
      }
      this.audio.addEventListener('error', () => {
        if (!this.track) return;
        if (this.wantsPlayback && this.audio.error?.code === 2) {
          this.buffering = true;
          this.update(); // The monitor retries network failures with a delay.
        } else {
          this.fail('Audio could not be loaded. Tap play to retry.');
        }
      });
      document.addEventListener('visibilitychange', () => {
        if (!document.hidden) this.checkPlayback();
      });
      root.addEventListener('pageshow', () => this.checkPlayback());
      root.addEventListener('online', () => this.checkPlayback());
      this.mediaHandlers();
    }
    entry(day, rank) {
      const data = this.index.days?.[day.date];
      if (!data?.items?.length) return null;
      const source = rank == null ? data.day : data.items.find((item) => item.rank === rank);
      const url = canonicalAudioURL(source?.url);
      if (!url) return null;
      return { ...source, url, label: day.title, date: day.date };
    }
    async play(day, rank) {
      const track = this.entry(day);
      if (!track || !this.entry(day, rank)) return;
      const data = this.index.days[day.date];
      let elapsed = 0;
      const items = data.items.map((item) => {
        const start = Number.isFinite(item.start) ? item.start : elapsed;
        elapsed = start + item.duration;
        return { ...item, start, title: item.title || day.papers.find((paper) => paper.rank === item.rank)?.title || 'Item ' + item.rank };
      });
      const selected = rank == null ? 0 : items.findIndex((item) => item.rank === rank);
      if (selected < 0) return;
      if (this.track?.url === track.url) { this.selectTrack(selected); return; }
      const request = ++this.request;
      this.stopMonitor();
      this.wantsPlayback = false;
      this.audio.pause();
      this.track = track;
      this.items = items;
      this.trackIndex = -1;
      this.pendingSeek = { time: items[selected].start };
      this.retries = 0;
      this.recoveryPosition = 0;
      this.lastPosition = 0;
      this.failure = '';
      this.buffering = true;
      this.panel.hidden = false;
      document.body.classList.add('has-audio-player');
      this.status.textContent = 'Loading audio…';
      this.picker.replaceChildren(...items.map((item, index) => {
        const option = document.createElement('option');
        option.value = index;
        option.textContent = 'Item ' + item.rank + ' — ' + item.title;
        return option;
      }));
      const playlistURL = new URL('arxiv-' + day.date + '-playlist.zip', track.url).href;
      this.download.hidden = canonicalAudioURL(data.playlist_url) !== playlistURL;
      this.download.removeAttribute('href');
      if (!this.download.hidden) this.download.href = playlistURL;
      this.download.download = 'arxiv-' + day.date + '-playlist.zip';
      this.syncTrack();
      this.audio.src = track.url;
      this.audio.playbackRate = Number(this.panel.querySelector('#audio-rate').value);
      if ('audioSession' in navigator) {
        try { navigator.audioSession.type = 'playback'; } catch { /* Optional platform API. */ }
      }
      await this.startPlayback(request);
    }
    togglePlayback() {
      if (!this.track) return;
      if (this.wantsPlayback && !this.audio.paused) this.pause();
      else if (this.failure || this.audio.error) this.reconnect(true);
      else { this.retries = 0; this.startPlayback(); }
    }
    pause() {
      this.wantsPlayback = false;
      this.stopMonitor();
      this.audio.pause();
      this.update();
    }
    selectTrack(index, play = true) {
      if (!Number.isInteger(index) || index < 0 || index >= this.items.length) return;
      const time = this.items[index].start;
      if (this.pendingSeek || this.audio.readyState < 1) this.pendingSeek = { time };
      else this.audio.currentTime = time;
      this.lastPosition = time;
      this.lastProgress = performance.now();
      this.recoveryPosition = time;
      this.retries = 0;
      this.syncTrack();
      if (play) {
        if (this.failure || this.audio.error) this.reconnect(true);
        else this.startPlayback();
      }
      this.update();
    }
    skip(offset) {
      this.syncTrack();
      this.selectTrack(this.trackIndex + offset, this.wantsPlayback);
    }
    syncTrack() {
      if (!this.track) return;
      const time = this.pendingSeek?.time ?? this.audio.currentTime;
      let index = 0;
      while (index + 1 < this.items.length && time >= this.items[index + 1].start) index++;
      if (index === this.trackIndex) return;
      this.trackIndex = index;
      const item = this.items[index];
      this.title.textContent = this.track.label + ' — Item ' + item.rank + ' of ' + this.items.length;
      this.picker.value = index;
      this.previous.disabled = index === 0;
      this.next.disabled = index === this.items.length - 1;
      if ('mediaSession' in navigator && 'MediaMetadata' in root) {
        navigator.mediaSession.metadata = new MediaMetadata({ title: 'Item ' + item.rank + ' — ' + item.title,
          artist: 'arXiv carte blanche', album: this.track.label });
      }
      this.mediaHandlers();
    }
    async startPlayback(request = this.request) {
      this.wantsPlayback = true;
      this.lastProgress = performance.now();
      this.startMonitor();
      try { await this.audio.play(); }
      catch {
        if (request === this.request && this.wantsPlayback) {
          if (this.audio.error?.code === 2) {
            this.buffering = true;
            this.update();
          } else {
            this.fail('Tap play to resume audio.');
          }
        }
      }
    }
    startMonitor() {
      if (this.monitor == null) this.monitor = root.setInterval(() => this.checkPlayback(), 3000);
    }
    stopMonitor() {
      root.clearInterval(this.monitor);
      this.monitor = null;
    }
    progress() {
      if (!this.track || this.pendingSeek || this.audio.readyState < 2) return;
      const time = this.audio.currentTime;
      if (Math.abs(time - this.lastPosition) > 0.01) {
        this.lastPosition = time;
        this.lastProgress = performance.now();
        if (this.audio.readyState >= 3) this.buffering = false;
        // Metadata/playing events alone don't prove a retry actually worked.
        if (time - this.recoveryPosition >= 10) this.retries = 0;
      }
    }
    checkPlayback() {
      if (!this.track || !this.wantsPlayback || this.audio.ended) return;
      this.progress();
      if (performance.now() - this.lastProgress < 15000) return;
      this.buffering = true;
      if (navigator.onLine === false) { this.update(); return; }
      this.reconnect();
    }
    reconnect(manual = false) {
      if (!this.track || (!manual && !this.wantsPlayback)) return;
      if (manual) this.retries = 0;
      if (this.retries >= 3) {
        this.fail('Audio interrupted. Tap play to resume here.');
        return;
      }
      const time = this.pendingSeek?.time ?? this.audio.currentTime;
      const request = ++this.request;
      this.pendingSeek = { time: Number.isFinite(time) ? time : this.lastPosition };
      this.recoveryPosition = this.pendingSeek.time;
      this.retries++;
      this.failure = '';
      this.buffering = true;
      this.status.textContent = 'Buffering audio…';
      // Re-request the stable release URL to refresh its redirect and decoder.
      // A timestamp avoids reusing a cached, expired signed download redirect.
      const url = new URL(this.track.url);
      url.searchParams.set('reconnect', Date.now() + '-' + request);
      this.audio.src = url.href;
      this.audio.load();
      this.audio.playbackRate = Number(this.panel.querySelector('#audio-rate').value);
      this.startPlayback(request);
      this.update();
    }
    fail(message) {
      this.wantsPlayback = false;
      this.failure = message;
      this.stopMonitor();
      this.audio.pause();
      this.update();
    }
    seekTo(value) {
      if (!this.track || !Number.isFinite(this.audio.duration) || this.audio.duration <= 0 || !Number.isFinite(value)) return;
      this.syncTrack();
      const item = this.items[this.trackIndex];
      this.audio.currentTime = Math.min(item.start + Math.max(0, Math.min(value, item.duration)), this.audio.duration);
      this.lastPosition = this.audio.currentTime;
      this.lastProgress = performance.now();
      this.recoveryPosition = this.audio.currentTime;
      this.retries = 0;
      this.position();
    }
    mediaState(state) {
      if ('mediaSession' in navigator) navigator.mediaSession.playbackState = state;
    }
    position() {
      const item = this.items[this.trackIndex];
      if (!item) return;
      const position = Math.max(0, Math.min((this.pendingSeek?.time ?? this.audio.currentTime) - item.start, item.duration));
      this.timeline.max = item.duration;
      this.timeline.value = position;
      const clock = (seconds) => Math.floor(seconds / 60) + ':' + String(Math.floor(seconds % 60)).padStart(2, '0');
      this.time.textContent = clock(position) + ' / ' + clock(item.duration);
      this.timeline.setAttribute('aria-valuetext', clock(position) + ' of ' + clock(item.duration));
      if (!navigator.mediaSession?.setPositionState) return;
      try { navigator.mediaSession.setPositionState({ duration: item.duration, playbackRate: this.audio.playbackRate,
        position }); } catch { /* Older browser. */ }
    }
    update() {
      if (!this.track) return;
      this.syncTrack();
      const waiting = this.buffering || this.audio.readyState < 3 || this.audio.seeking;
      const status = this.failure || (this.audio.ended ? 'Finished' : this.audio.paused ? 'Paused' :
        waiting ? (navigator.onLine === false ? 'Waiting for connection…' : 'Buffering audio…') : 'Playing');
      if (this.status.textContent !== status) this.status.textContent = status;
      const playing = this.wantsPlayback && !this.audio.paused;
      this.toggle.textContent = playing ? 'Pause' : 'Play';
      this.toggle.setAttribute('aria-label', playing ? 'Pause audio' : 'Play audio');
      this.mediaState(this.audio.paused || waiting || this.failure ? 'paused' : 'playing');
      this.position();
    }
    mediaHandlers() {
      if (!navigator.mediaSession?.setActionHandler) return;
      const actions = {
        play: () => {
          if (!this.track) return;
          if (this.failure || this.buffering || !this.audio.paused) this.reconnect(true);
          else { this.retries = 0; this.startPlayback(); }
        },
        pause: () => this.pause(), stop: () => this.close(),
        seekbackward: null, seekforward: null,
        previoustrack: this.trackIndex > 0 ? () => this.skip(-1) : null,
        nexttrack: this.trackIndex >= 0 && this.trackIndex < this.items.length - 1 ? () => this.skip(1) : null,
        seekto: (details) => this.seekTo(details.seekTime),
      };
      for (const [action, handler] of Object.entries(actions)) {
        try { navigator.mediaSession.setActionHandler(action, handler); } catch { /* Unsupported action. */ }
      }
    }
    close() {
      ++this.request;
      this.wantsPlayback = false;
      this.stopMonitor();
      this.pendingSeek = null;
      this.track = null;
      this.items = [];
      this.trackIndex = -1;
      this.audio.pause();
      this.audio.removeAttribute('src');
      this.audio.load();
      this.panel.hidden = true;
      document.body.classList.remove('has-audio-player');
      this.mediaState('none');
      if ('mediaSession' in navigator) {
        navigator.mediaSession.metadata = null;
        try { navigator.mediaSession.setPositionState?.(); } catch { /* Optional API. */ }
      }
    }
  }
  root.DigestAudio = DigestAudio;
})(globalThis);
