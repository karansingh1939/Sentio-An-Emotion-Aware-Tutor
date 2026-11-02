// Slide study view: read a lecture slide by slide, ask the tutor about the current slide and,
// if the student switches the camera on, see a labelled mood guess with an occasional offer.
import { sentioAPI } from '../core/api.js';
import { store } from '../core/store.js';
import { toast } from '../components/ui.js';
import { escapeHtml } from '../core/html.js';

const ROUTE = '#/slides';
const MOOD_POLL_MS = 10000;
const NUDGE_QUIET_MS = 2 * 60 * 1000;
const BREAK_MS = 2 * 60 * 1000;
const STREAM_TIMEOUT_MS = 200000;
const EXPLAIN = 'Explain this slide.';
const EXPLAIN_SIMPLY = 'Explain this slide more simply.';
const NUDGES = {
  simpler: { text: 'Want a simpler explanation?', accept: 'Yes, explain it more simply' },
  break: { text: 'Take a short break?', accept: 'Take a 2-minute break' },
};

// A session is a slide session when it studies one lecture in slides mode.
export function slideDocumentId(session) {
  const id = session?.metadata?.document_id;
  if (session?.metadata?.mode !== 'slides') return null;
  if (typeof id !== 'string' || !id || ['none', 'all'].includes(id)) return null;
  return id.startsWith('course:') || /[\s,]/.test(id) ? null : id;
}

export function moodText(label) {
  return `Camera guess: ${label}`;
}

export function formatCountdown(seconds) {
  const left = Math.max(0, Math.ceil(seconds));
  return `${Math.floor(left / 60)}:${String(left % 60).padStart(2, '0')}`;
}

// The same offer is not repeated within two minutes of showing it.
export function nudgeAllowed(shownAt, kind, now) {
  const last = shownAt[kind];
  return last === undefined || now - last >= NUDGE_QUIET_MS;
}

// The tutor's answer as safe HTML: escaped text (through the tutor's own renderer when it is
// available) and one chip per cited slide.
export function answerHtml(data, renderMarkdown) {
  let body;
  try {
    body = renderMarkdown ? renderMarkdown(data.text) : null;
  } catch {
    body = null;
  }
  if (body == null) {
    body = String(data.text ?? '')
      .split(/\n{2,}/)
      .map((part) => `<p>${escapeHtml(part).replace(/\n/g, '<br>')}</p>`)
      .join('');
  } else {
    body = `<div class="slide-answer-text">${body}</div>`;
  }
  const label =
    data.answer_mode === 'source_excerpt'
      ? '<p class="muted">Source excerpt: relevant passages, not a generated explanation.</p>'
      : '';
  const chips = (data.source_citations || [])
    .map(
      (c) =>
        `<span class="cite-chip">${escapeHtml(c.filename)} · Slide ${escapeHtml(c.page)}</span>`,
    )
    .join('');
  return `${label}${body}${chips ? `<div class="source-row">${chips}</div>` : ''}`;
}

export class SlidesView {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
    this.revision = 0;
    this.deck = null;
    this.index = 0;
    this.sessionId = null;
    this.savedNumber = null;
    this.lastSlide = {};
    this.saving = Promise.resolve();
    this.request = null;
    this.busy = false;
    this.cameraOn = false;
    this.cameraWatch = null;
    this.moodTimer = null;
    this.breakTimer = null;
    this.breakUntil = 0;
    this.nudgeKind = null;
    this.nudgeShownAt = {};
  }

  init() {
    store.subscribe('activeRoute', (route) => {
      if (route === ROUTE) this.load();
      else this.leave();
    });
    store.subscribe('currentUser', () => {
      this.lastSlide = {};
      if (store.getState('activeRoute') === ROUTE) this.load();
      else this.leave();
    });
    let lastSession;
    store.subscribe('activeSessionId', (id) => {
      const changed = lastSession !== undefined && id !== lastSession;
      lastSession = id;
      if (changed && store.getState('activeRoute') === ROUTE) this.load();
    });
    document.addEventListener('keydown', (event) => this.onKey(event));
  }

  // ── Loading ────────────────────────────────
  async load() {
    this.leave();
    const revision = this.revision;
    const owner = store.getState('currentUser')?.id;
    const sessionId = store.getState('activeSessionId');
    const current = () =>
      revision === this.revision &&
      store.getState('currentUser')?.id === owner &&
      store.getState('activeSessionId') === sessionId &&
      store.getState('activeRoute') === ROUTE;
    if (!owner || !sessionId) return this.renderNoSession();
    this.container.innerHTML =
      '<div id="slides-view" class="slides-view"><p role="status">Loading slides…</p></div>';
    try {
      let session = store.getState('activeSession');
      if (!session?.metadata) {
        session = await sentioAPI.get(`/sessions/${encodeURIComponent(sessionId)}`);
        if (!current()) return;
        if (session.status && session.status !== 'active') return this.renderNoSession();
      }
      const documentId = slideDocumentId(session);
      if (!documentId) return this.renderNoSession();
      const deck = await sentioAPI.get(`/documents/${encodeURIComponent(documentId)}/slides`);
      if (!current()) return;
      if (!Array.isArray(deck?.slides)) throw new Error('The slides could not be read.');
      this.sessionId = sessionId;
      this.deck = deck;
      const wanted = this.lastSlide[sessionId] ?? session.metadata.slide;
      const found = deck.slides.findIndex((slide) => slide.number === wanted);
      this.index = Math.max(0, found);
      this.savedNumber = found >= 0 ? wanted : null;
      this.render();
    } catch (error) {
      if (!current()) return;
      this.container.innerHTML = `<div id="slides-view" class="slides-view"><p role="alert">${escapeHtml(error.message)}</p><button type="button" class="workspace-action" id="retry-slides">Try again</button></div>`;
      const retry = this.container.querySelector('#retry-slides');
      if (retry) retry.onclick = () => this.load();
    }
  }

  // Stop everything this view started: requests, polling, countdown and the camera.
  leave() {
    this.revision++;
    this.abortAnswer();
    this.stopMoodPolling();
    clearInterval(this.cameraWatch);
    this.cameraWatch = null;
    clearInterval(this.breakTimer);
    this.breakTimer = null;
    this.breakUntil = 0;
    this.nudgeKind = null;
    // Only stop a camera this view was showing; other pages manage their own.
    if (this.deck || this.cameraOn) window.stopWebcam?.();
    this.cameraOn = false;
    this.deck = null;
    this.sessionId = null;
  }

  renderNoSession() {
    this.container.innerHTML = `
      <div id="slides-view" class="slides-view">
        <div class="view-header"><h2 class="page-title">Study slides</h2></div>
        <div class="notice" role="status">
          <p>Open your Library and choose Study slides next to a lecture to start.</p>
          <p><a class="workspace-action primary" href="#/documents">Go to Library</a></p>
        </div>
      </div>`;
  }

  // ── Rendering ──────────────────────────────
  slide() {
    return this.deck?.slides?.[this.index] || null;
  }

  render() {
    const slides = this.deck?.slides || [];
    if (!slides.length) {
      this.container.innerHTML = `
        <div id="slides-view" class="slides-view">
          <div class="view-header"><h2 class="page-title">Study slides</h2><p class="muted">${escapeHtml(this.deck?.filename || '')}</p></div>
          <div class="notice" role="status">
            <p>No slides with text were found in this lecture.</p>
            <p><a class="workspace-action primary" href="#/documents">Go to Library</a></p>
          </div>
        </div>`;
      return;
    }
    const slide = this.slide() || slides[0];
    this.container.innerHTML = `
      <div id="slides-view" class="slides-view">
        <div class="view-header">
          <h2 class="page-title">Study slides</h2>
          <p class="muted">${escapeHtml(this.deck.filename)}</p>
        </div>
        <div class="slides-layout">
          <nav class="slide-list" aria-label="Slides">
            <ol>
              ${slides
                .map(
                  (item, i) =>
                    `<li><button type="button" class="slide-item${i === this.index ? ' current' : ''}" data-index="${i}" ${i === this.index ? 'aria-current="true"' : ''}><span class="slide-item-number">${escapeHtml(item.number)}</span><span class="slide-item-title">${escapeHtml(item.title || `Slide ${item.number}`)}</span></button></li>`,
                )
                .join('')}
            </ol>
          </nav>
          <section class="slide-main" aria-label="Current slide">
            <article class="slide-card">
              <p class="muted" id="slide-position">${escapeHtml(this.positionText())}</p>
              <h3 id="slide-title">${escapeHtml(slide.title)}</h3>
              <div id="slide-text" class="slide-text">${escapeHtml(slide.text)}</div>
            </article>
            <div class="btn-row slide-controls">
              <button type="button" class="workspace-action" id="slide-prev">Previous</button>
              <button type="button" class="workspace-action" id="slide-next">Next</button>
              <button type="button" class="workspace-action primary" id="slide-explain">Explain this slide</button>
              <button type="button" class="workspace-action emotion-only" id="slide-camera-toggle" aria-pressed="false">Turn on camera</button>
            </div>
            <div class="slide-mood-row emotion-only">
              <span class="badge" id="slide-mood" title="A guess from your camera. It can be wrong." hidden></span>
            </div>
            <div class="notice slide-nudge" id="slide-nudge" role="status" hidden>
              <span id="slide-nudge-text"></span>
              <span id="slide-countdown" aria-hidden="true"></span>
              <button type="button" class="workspace-action primary" id="slide-nudge-accept"></button>
              <button type="button" class="workspace-action" id="slide-nudge-dismiss">Not now</button>
            </div>
            <form class="slide-ask" id="slide-ask-form">
              <label for="slide-question">Ask about this slide</label>
              <div class="btn-row">
                <input type="text" class="input slide-question" id="slide-question" maxlength="1000" autocomplete="off" placeholder="For example: why does this matter?" />
                <button type="submit" class="workspace-action" id="slide-ask">Ask</button>
              </div>
            </form>
            <div id="slide-answer" class="slide-answer" aria-live="polite"></div>
          </section>
        </div>
      </div>`;
    this.bindEvents();
    this.updateNav();
  }

  positionText() {
    return `Slide ${this.index + 1} of ${this.deck?.slides?.length || 0}`;
  }

  // Updates the parts that change with the slide, so the question and answer stay in place.
  showSlide() {
    const slide = this.slide();
    if (!slide) return;
    const title = this.container.querySelector('#slide-title');
    if (title) title.textContent = slide.title ?? '';
    const text = this.container.querySelector('#slide-text');
    if (text) text.textContent = slide.text ?? '';
    const position = this.container.querySelector('#slide-position');
    if (position) position.textContent = this.positionText();
    this.container.querySelectorAll('.slide-item').forEach((item) => {
      const here = Number(item.dataset.index) === this.index;
      item.classList.toggle('current', here);
      if (here) {
        item.setAttribute('aria-current', 'true');
        item.scrollIntoView?.({ block: 'nearest' });
      } else item.removeAttribute('aria-current');
    });
    this.updateNav();
  }

  updateNav() {
    const prev = this.container.querySelector('#slide-prev');
    const next = this.container.querySelector('#slide-next');
    if (prev) prev.disabled = this.index <= 0;
    if (next) next.disabled = this.index >= (this.deck?.slides?.length || 0) - 1;
  }

  setAnswer(html) {
    const answer = this.container.querySelector('#slide-answer');
    if (answer) answer.innerHTML = html;
  }

  setBusy(busy) {
    this.busy = busy;
    ['#slide-explain', '#slide-ask', '#slide-question', '#slide-nudge-accept'].forEach(
      (selector) => {
        const element = this.container.querySelector(selector);
        if (element) element.disabled = busy;
      },
    );
    this.container.querySelector('#slide-answer')?.setAttribute('aria-busy', String(busy));
  }

  // ── Events ─────────────────────────────────
  bindEvents() {
    const $ = (selector) => this.container.querySelector(selector);
    $('#slide-prev').onclick = () => this.go(this.index - 1);
    $('#slide-next').onclick = () => this.go(this.index + 1);
    this.container.querySelectorAll('.slide-item').forEach((item) => {
      item.onclick = () => this.go(Number(item.dataset.index));
    });
    $('#slide-explain').onclick = () => this.ask(EXPLAIN);
    $('#slide-ask-form').onsubmit = (event) => {
      event.preventDefault();
      const input = $('#slide-question');
      const question = input.value.trim();
      if (!question) return input.focus();
      input.value = '';
      this.ask(question, input);
    };
    $('#slide-camera-toggle').onclick = () => this.toggleCamera();
    $('#slide-nudge-accept').onclick = () => this.acceptNudge();
    $('#slide-nudge-dismiss').onclick = () => this.dismissNudge();
    this.cameraWatch = setInterval(() => this.syncCamera(), 1000);
  }

  onKey(event) {
    if (store.getState('activeRoute') !== ROUTE || !this.deck) return;
    if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
    if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
    const target = event.target;
    if (target?.closest?.('input, textarea, select, [contenteditable="true"], sentio-modal'))
      return;
    event.preventDefault();
    this.go(this.index + (event.key === 'ArrowRight' ? 1 : -1));
  }

  // ── Moving between slides ──────────────────
  go(index) {
    const slides = this.deck?.slides || [];
    if (index < 0 || index >= slides.length || index === this.index) return;
    this.abortAnswer();
    this.setAnswer('');
    this.index = index;
    this.showSlide();
    this.saveSlide(slides[index].number).catch((error) =>
      toast('Could not remember your place: ' + error.message, true),
    );
  }

  // Saves run one after another so the server ends on the slide the student is on.
  saveSlide(number) {
    const sessionId = this.sessionId;
    const run = async () => {
      await sentioAPI.request(`/sessions/${encodeURIComponent(sessionId)}/slide`, {
        method: 'PUT',
        body: JSON.stringify({ number }),
      });
      if (sessionId === this.sessionId) {
        this.savedNumber = number;
        this.lastSlide[sessionId] = number;
      }
    };
    const saved = this.saving.then(run, run);
    this.saving = saved.catch(() => {});
    return saved;
  }

  // ── Asking the tutor ───────────────────────
  abortAnswer() {
    const request = this.request;
    this.request = null;
    if (!request) return;
    request.controller.abort();
    if (request.sent && !request.complete)
      window.cancelTutorRequest?.(request.sessionId, request.requestId);
    this.setBusy(false);
  }

  async ask(message, input = null) {
    const slide = this.slide();
    if (this.busy || !slide || !this.sessionId) return;
    const sessionId = this.sessionId;
    const revision = this.revision;
    const requestId =
      globalThis.crypto?.randomUUID?.() || `${Date.now()}_${Math.random().toString(36).slice(2)}`;
    const request = {
      controller: new AbortController(),
      sessionId,
      requestId,
      complete: false,
      sent: false,
    };
    const stale = () => this.request !== request || revision !== this.revision;
    this.request = request;
    this.setBusy(true);
    this.setAnswer('<p class="muted" id="slide-status">Getting the slide ready…</p>');
    const timer = setTimeout(() => request.controller.abort(), STREAM_TIMEOUT_MS);
    let text = '';
    let data = null;
    try {
      // The tutor explains the slide the server has saved, so save before asking.
      if (message === EXPLAIN || this.savedNumber !== slide.number) {
        await this.saveSlide(slide.number);
        if (stale()) return;
      }
      if (typeof window.readTutorEvents !== 'function')
        throw new Error('The tutor is not ready yet. Reload the page and try again.');
      request.sent = true;
      const response = await sentioAPI.post(
        `/sessions/${encodeURIComponent(sessionId)}/chat/stream`,
        { message, request_id: requestId },
        { signal: request.controller.signal, stream: true, timeout: STREAM_TIMEOUT_MS },
      );
      await window.readTutorEvents(response, (kind, value) => {
        if (stale()) return;
        if (kind === 'status' && !text) {
          const status = this.container.querySelector('#slide-status');
          if (status) status.textContent = String(value.stage ?? '');
        } else if (kind === 'delta') {
          text += value.text ?? '';
          this.setAnswer('<div class="slide-draft"></div>');
          const draft = this.container.querySelector('.slide-draft');
          if (draft) draft.textContent = text;
        } else if (kind === 'complete') {
          data = value;
        } else if (kind === 'cancelled' || kind === 'error') {
          throw new Error(value.detail || 'The tutor could not answer.');
        }
      });
      if (stale()) return;
      if (!data) throw new Error('The connection ended before the answer was saved. Try again.');
      request.complete = true;
      if (!data.text) {
        this.setAnswer('');
        toast('The tutor did not answer. Try again.', true);
      } else {
        this.setAnswer(
          answerHtml(
            data,
            typeof window.renderMarkdown === 'function' ? window.renderMarkdown : null,
          ),
        );
      }
    } catch (error) {
      if (stale()) return;
      if (input && !input.value) input.value = message;
      this.setAnswer(
        text
          ? '<p class="muted">The answer stopped early. Ask again to get the full answer.</p>'
          : '',
      );
      toast(
        error.name === 'AbortError' ? 'The answer took too long. Try again.' : error.message,
        true,
      );
    } finally {
      clearTimeout(timer);
      if (request.sent && !request.complete && this.request === request) {
        window.cancelTutorRequest?.(sessionId, requestId);
      }
      if (this.request === request) {
        this.request = null;
        this.setBusy(false);
      }
    }
  }

  // ── Camera and mood ────────────────────────
  toggleCamera() {
    if (window.camStream) {
      window.disableCamera?.();
    } else if (typeof window.toggleWebcamDirect === 'function') {
      window.toggleWebcamDirect();
    } else {
      toast('The camera is not available right now.', true);
    }
    this.syncCamera();
  }

  // The camera code reports no events, so the view checks whether its stream is running.
  syncCamera() {
    const on = Boolean(window.camStream);
    if (on === this.cameraOn) return;
    this.cameraOn = on;
    const button = this.container.querySelector('#slide-camera-toggle');
    if (button) {
      button.textContent = on ? 'Turn off camera' : 'Turn on camera';
      button.setAttribute('aria-pressed', String(on));
    }
    if (on) this.startMoodPolling();
    else {
      this.stopMoodPolling();
      this.hideMood();
      if (!this.breakUntil) this.hideNudge();
    }
  }

  startMoodPolling() {
    this.stopMoodPolling();
    this.pollMood();
    this.moodTimer = setInterval(() => this.pollMood(), MOOD_POLL_MS);
  }

  stopMoodPolling() {
    clearInterval(this.moodTimer);
    this.moodTimer = null;
  }

  async pollMood() {
    const revision = this.revision;
    const sessionId = this.sessionId;
    if (!sessionId) return;
    try {
      const mood = await sentioAPI.get(`/sessions/${encodeURIComponent(sessionId)}/mood`);
      if (revision !== this.revision || !this.cameraOn) return;
      this.applyMood(mood);
    } catch {
      if (revision === this.revision) this.hideMood();
    }
  }

  applyMood(mood) {
    const label = typeof mood?.label === 'string' ? mood.label.trim() : '';
    const chip = this.container.querySelector('#slide-mood');
    if (chip) {
      chip.textContent = label ? moodText(label) : '';
      chip.hidden = !label;
    }
    if (mood?.nudge === 'simpler' || mood?.nudge === 'break') this.offerNudge(mood.nudge);
    else if (!this.breakUntil) this.hideNudge();
  }

  hideMood() {
    const chip = this.container.querySelector('#slide-mood');
    if (chip) {
      chip.hidden = true;
      chip.textContent = '';
    }
  }

  offerNudge(kind) {
    if (this.breakUntil || this.nudgeKind === kind) return;
    const now = Date.now();
    if (!nudgeAllowed(this.nudgeShownAt, kind, now)) {
      this.hideNudge();
      return;
    }
    this.nudgeShownAt[kind] = now;
    this.nudgeKind = kind;
    this.showNudge(NUDGES[kind].text, NUDGES[kind].accept);
  }

  showNudge(text, acceptLabel) {
    const nudge = this.container.querySelector('#slide-nudge');
    if (!nudge) return;
    nudge.querySelector('#slide-nudge-text').textContent = text;
    nudge.querySelector('#slide-countdown').textContent = '';
    const accept = nudge.querySelector('#slide-nudge-accept');
    accept.textContent = acceptLabel || '';
    accept.hidden = !acceptLabel;
    accept.disabled = this.busy;
    nudge.querySelector('#slide-nudge-dismiss').textContent = acceptLabel ? 'Not now' : 'End break';
    nudge.hidden = false;
  }

  hideNudge() {
    this.nudgeKind = null;
    const nudge = this.container.querySelector('#slide-nudge');
    if (nudge) nudge.hidden = true;
  }

  acceptNudge() {
    const kind = this.nudgeKind;
    if (kind === 'simpler') {
      this.hideNudge();
      this.ask(EXPLAIN_SIMPLY);
    } else if (kind === 'break') {
      this.startBreak();
    }
  }

  dismissNudge() {
    if (this.breakUntil) this.endBreak();
    else this.hideNudge();
  }

  startBreak() {
    this.nudgeKind = null;
    this.breakUntil = Date.now() + BREAK_MS;
    this.showNudge('Short break. Rest your eyes and come back when the timer ends.', '');
    this.tickBreak();
    clearInterval(this.breakTimer);
    this.breakTimer = setInterval(() => this.tickBreak(), 1000);
  }

  tickBreak() {
    const left = (this.breakUntil - Date.now()) / 1000;
    if (left <= 0) return this.endBreak();
    const countdown = this.container.querySelector('#slide-countdown');
    if (countdown) countdown.textContent = formatCountdown(left);
  }

  endBreak() {
    clearInterval(this.breakTimer);
    this.breakTimer = null;
    this.breakUntil = 0;
    this.hideNudge();
  }
}
