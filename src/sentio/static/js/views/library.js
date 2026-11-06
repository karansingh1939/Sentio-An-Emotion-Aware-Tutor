import {
  MAX_PRACTICE_TOPICS,
  escapeHtml,
  pageLabel,
  pageRange,
  topicMemory,
} from '../core/html.js';
// Documents View Controller for Sentio (ES Module)
import { sentioAPI } from '../core/api.js';
import { toast } from '../components/ui.js';
import { store } from '../core/store.js';
import { pendingJobKey, runPracticeJob } from '../core/jobs.js';

const NEW_COURSE = '__new__';
const STATE_LABEL = {
  ready: 'Ready',
  review_due: 'Review due',
  practising: 'Practising',
  not_started: 'Not started',
  no_notes: 'Not in your notes yet',
};

// One row per topic: where it is, how it is going, and what to do next.
function topicList(topics, { showLecture = false } = {}) {
  if (!topics.length) return '<p class="muted">No topics found in these notes yet.</p>';
  return `<ul class="topic-list">${topics
    .map(
      (topic, index) => `
      <li class="topic-row" data-topic="${escapeHtml(topic.id)}">
        <div class="topic-main">
          <strong>${escapeHtml(topic.title)}</strong>
          <span class="muted">${showLecture ? escapeHtml(topic.filename) + ' · ' : ''}${escapeHtml(pageRange(topic))}${topic.answers ? ` · ${topic.recent_correct} of ${topic.recent_total} correct recently` : ''}${topicMemory(topic) ? ` · ${escapeHtml(topicMemory(topic))}` : ''}</span>
        </div>
        <span class="topic-state ${escapeHtml(topic.state)}">${STATE_LABEL[topic.state]}</span>
        <div class="topic-actions">
          <button class="workspace-action" data-topic-action="review" data-topic="${escapeHtml(topic.id)}">Review</button>
          <button class="workspace-action primary" data-topic-action="practise" data-topic="${escapeHtml(topic.id)}">Practise</button>
          ${showLecture ? '' : `<button class="link-quiet" data-topic-action="rename" data-topic="${escapeHtml(topic.id)}">Rename</button>`}
          ${showLecture || index === 0 ? '' : `<button class="link-quiet" data-topic-action="merge" data-topic="${escapeHtml(topic.id)}" title="Join this topic to the one above">Merge up</button>`}
        </div>
      </li>`,
    )
    .join('')}</ul>`;
}

function syllabusForm(courseId) {
  return `<div class="syllabus-form stack" data-course="${escapeHtml(courseId)}">
    <h4>Syllabus</h4>
    <p class="muted">Add the course syllabus to see how much of it you are ready for and which topics your notes don't cover yet.</p>
    <textarea class="input syllabus-text" rows="6" aria-label="Syllabus text" placeholder="Paste the syllabus here, one topic per line or units with topics separated by commas"></textarea>
    <label class="muted">Or choose its file (PDF, Word, PowerPoint or text): <input type="file" class="syllabus-file" accept=".pdf,.docx,.pptx,.txt" /></label>
    <button class="workspace-action primary" data-syllabus-action="save" data-course="${escapeHtml(courseId)}">Save syllabus</button>
  </div>`;
}

// The syllabus by unit: each topic's status, the lecture topic it matches, and a way to fix it.
function syllabusView(syllabus, courseId) {
  const { summary } = syllabus;
  const choices = (item) =>
    [
      `<option value="auto" ${item.link_mode === 'auto' ? 'selected' : ''}>Match automatically</option>`,
      ...syllabus.topics.map(
        (topic) =>
          `<option value="manual:${escapeHtml(topic.id)}" ${item.link_mode === 'manual' && item.linked_topic_id === topic.id ? 'selected' : ''}>${escapeHtml(topic.filename)} · ${escapeHtml(topic.title)}</option>`,
      ),
      `<option value="none" ${item.link_mode === 'none' ? 'selected' : ''}>Not in my notes</option>`,
    ].join('');
  let unit = null;
  const rows = syllabus.items
    .map((item) => {
      const heading =
        item.unit !== unit
          ? `<li class="syllabus-unit">${escapeHtml(item.unit || 'Topics')}</li>`
          : '';
      unit = item.unit;
      const matched = item.topics
        .map((topic) => `${topic.filename} · ${topic.title} (${pageRange(topic)})`)
        .join('; ');
      return `${heading}
        <li class="topic-row syllabus-item" data-item="${escapeHtml(item.id)}">
          <div class="topic-main">
            <strong>${escapeHtml(item.title)}</strong>
            <span class="muted">${matched ? escapeHtml(matched) : 'No matching lecture topic'}</span>
          </div>
          <span class="topic-state ${escapeHtml(item.status)}">${STATE_LABEL[item.status]}</span>
          <div class="topic-actions">
            ${item.topics.length ? `<button class="workspace-action primary" data-syllabus-action="practise" data-item="${escapeHtml(item.id)}" data-course="${escapeHtml(courseId)}">Practise</button>` : ''}
            <select class="input syllabus-match" data-item="${escapeHtml(item.id)}" aria-label="Lecture topic for ${escapeHtml(item.title)}">${choices(item)}</select>
          </div>
        </li>`;
    })
    .join('');
  return `<div class="syllabus stack" data-course="${escapeHtml(courseId)}">
    <div class="row-between">
      <h4>Syllabus · ${summary.percent_ready}% ready</h4>
      <div>
        <button class="link-quiet" data-syllabus-action="replace" data-course="${escapeHtml(courseId)}">Replace</button>
        <button class="link-quiet" data-syllabus-action="remove" data-course="${escapeHtml(courseId)}">Remove</button>
      </div>
    </div>
    <div class="syllabus-bar" role="img" aria-label="${summary.percent_ready}% of the syllabus ready"><span style="width:${summary.percent_ready}%"></span></div>
    <p class="muted">${summary.ready} ready · ${summary.review_due ? `${summary.review_due} due for review · ` : ''}${summary.practising} practising · ${summary.not_started} not started · ${summary.no_notes} not in your notes yet</p>
    <ul class="topic-list">${rows}</ul>
  </div>`;
}

// Board columns, in learning order. Topics not in the notes stay in the syllabus view.
const BOARD_COLUMNS = [
  ['not_started', 'Not started'],
  ['practising', 'Practising'],
  ['review_due', 'Review due'],
  ['ready', 'Ready'],
];
const BOARD_LIMIT = 60; // lectures fetched for the board at most

const tileClass = (text) =>
  `t${[...(text || '')].reduce((sum, ch) => sum + ch.charCodeAt(0), 0) % 4}`;
const initials = (filename) =>
  (filename || '?')
    .replace(/\.[a-z0-9]+$/i, '')
    .split(/[^\p{L}\p{N}]+/u)
    .filter(Boolean)
    .slice(0, 2)
    .map((word) => [...word][0])
    .join('')
    .toUpperCase() || '?';

// How far along a topic is, as a 0–100 bar, from the evidence the server keeps.
function topicShare(topic) {
  if (typeof topic.recall === 'number') return Math.round(topic.recall * 100);
  if (topic.recent_total) return Math.round((topic.recent_correct / topic.recent_total) * 100);
  return topic.state === 'ready' ? 100 : 0;
}

function boardCard(topic) {
  const memory = topicMemory(topic);
  const evidence = topic.recent_total
    ? `${topic.recent_correct} of ${topic.recent_total} correct`
    : 'Not practised yet';
  return `<article class="board-card ${escapeHtml(topic.state)}">
    <div class="board-card-file"><span class="tile ${tileClass(topic.filename)}" aria-hidden="true">${escapeHtml(initials(topic.filename))}</span><span>${escapeHtml(topic.filename)}</span></div>
    <h4>${escapeHtml(topic.title)}</h4>
    ${topic.state === 'not_started' ? '' : `<div class="meter ${topic.state === 'ready' ? 'green' : topic.state === 'review_due' ? 'amber' : ''}"><i style="width:${topicShare(topic)}%"></i></div>`}
    <div class="board-card-meta"><span>${escapeHtml(pageRange(topic))} · ${escapeHtml(memory || evidence)}</span></div>
    <div class="board-card-actions">
      <button type="button" class="workspace-action pill" data-topic-action="review" data-topic="${escapeHtml(topic.id)}">Review</button>
      <button type="button" class="workspace-action" data-topic-action="practise" data-topic="${escapeHtml(topic.id)}">Practise</button>
    </div>
  </article>`;
}

function boardView(topics) {
  if (!topics.length)
    return '<p class="muted">No topics yet. Topics appear once your notes are ready to study.</p>';
  return BOARD_COLUMNS.map(([state, label]) => {
    const cards = topics.filter((topic) => topic.state === state);
    return `<section class="board-column" aria-label="${label}">
      <div class="board-column-head"><span class="topic-state ${state}">${label}</span><span class="board-count">${cards.length.toLocaleString()}</span></div>
      ${cards.length ? cards.map(boardCard).join('') : '<p class="muted board-empty">Nothing here yet.</p>'}
    </section>`;
  }).join('');
}

function progressLine(summary) {
  if (!summary.total) return 'No topics yet';
  const due = summary.review_due ? `${summary.review_due} due for review · ` : '';
  return `${summary.ready} of ${summary.total} topic${summary.total === 1 ? '' : 's'} ready · ${due}${summary.practising} practising · ${summary.not_started} not started`;
}

// A title that wraps onto a second line ("Microprocessor &" / "Computer Architecture")
// continues while a line ends mid-phrase; the title stops at the first sentence mark.
const CONTINUES = /(?:[&,+/–-]|\b(?:and|or|of|the|to|for|in|on|with|a|an))$/i;
export function openingTitle(text) {
  const lines = String(text || '')
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean);
  let title = lines.shift() || '';
  while (CONTINUES.test(title) && lines.length) title = `${title} ${lines.shift()}`;
  return title
    .split(/[.:!?]/)[0]
    .trim()
    .slice(0, 80);
}

export class LibraryView {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
    this.documents = [];
    this.courses = [];
    this.uploadCourse = '';
    this.batchStatus = '';
    this.batchItems = [];
    this.failedFiles = [];
    this.filterQuery = '';
    this.libraryView =
      globalThis.localStorage?.getItem('sentio_library_view') === 'board' ? 'board' : 'list';
    this.ocrReady = false;
    this.revision = 0;
    this.uploadInProgress = false;
    this.justUploadedId = null;
    this.topics = new Map();
    this.syllabi = new Map();
    this.container.addEventListener('click', (event) => this.onTopicAction(event));
    this.container.addEventListener('click', (event) => this.onSyllabusAction(event));
    this.container.addEventListener('change', (event) => this.onSyllabusMatch(event));
  }

  async init() {
    store.subscribe('currentUser', () => {
      this.justUploadedId = null;
      this.documents = [];
      this.courses = [];
      this.uploadCourse = '';
      this.revision++;
    });
    // Listen to route changes to load documents when opened
    store.subscribe('activeRoute', (route) => {
      if (route === '#/documents') {
        this.loadDocuments();
      } else {
        this.revision++;
      }
    });
  }

  async loadDocuments() {
    const revision = ++this.revision;
    const owner = store.getState('currentUser')?.id;
    const current = () =>
      this.revision === revision &&
      store.getState('currentUser')?.id === owner &&
      store.getState('activeRoute') === '#/documents';
    this.container.innerHTML = `
      <div class="center-state">
        <sentio-loader size="32px"></sentio-loader>
      </div>
    `;

    try {
      const [res, capabilities, courses] = await Promise.all([
        sentioAPI.get('/documents'),
        sentioAPI.get('/documents/capabilities'),
        sentioAPI.get('/courses'),
      ]);
      if (!current()) return;
      this.current = current;
      this.ocrReady = capabilities.ocr_available;
      this.documents = res.documents || [];
      this.courses = courses.courses || [];
      if (!this.courses.some((course) => course.id === this.uploadCourse)) this.uploadCourse = '';
      this.render();
      this.bindEvents();
      this.loadCourseProgress(current);
      if (this.libraryView === 'board') this.loadBoard(current);
      if (localStorage.getItem(pendingJobKey('/documents/jobs', false))) this.uploadFile(null);
    } catch (e) {
      if (!current()) return;
      this.container.innerHTML = `
        <div style="padding:40px;text-align:center;">
          <div style="margin-bottom:12px;color:var(--red);">${window.sentioIcon('alert', 28)}</div>
          <div style="color:var(--red);font-weight:bold;">Couldn’t load your library</div>
          <div style="color:var(--text-dim);font-size:14px;margin-top:8px;">${escapeHtml(e.message)}</div>
          <button id="retry-docs-btn" class="workspace-action primary" style="margin-top:16px;">Try again</button>
        </div>
      `;
      const btn = this.container.querySelector('#retry-docs-btn');
      if (btn) btn.onclick = () => this.loadDocuments();
    }
  }

  courseName(courseId) {
    return this.courses.find((course) => course.id === courseId)?.name || '';
  }

  courseOptions(selected, { none, create }) {
    return [
      `<option value="">${escapeHtml(none)}</option>`,
      ...this.courses.map(
        (course) =>
          `<option value="${escapeHtml(course.id)}" ${course.id === selected ? 'selected' : ''}>${escapeHtml(course.name)}</option>`,
      ),
      create ? `<option value="${NEW_COURSE}">+ New course…</option>` : '',
    ].join('');
  }

  renderRows(docs) {
    return docs
      .map((d) => {
        const state =
          d.status === 'indexed' ? 'ready' : d.status === 'failed' ? 'failed' : 'working';
        return `
        <tr class="document-row" data-search="${escapeHtml((d.filename + ' ' + this.courseName(d.course_id)).toLowerCase())}" style="border-bottom:1px solid var(--border);color:var(--text);">
          <td style="padding:10px;width:100%;max-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${escapeHtml(d.filename)}">
            ${escapeHtml(d.filename)}
          </td>
          <td style="padding:10px;">
            <span class="doc-state ${state}">${escapeHtml(state === 'ready' ? 'Ready to study' : state === 'failed' ? 'Needs retry' : 'Processing')}</span>
          </td>
          <td style="padding:10px;">
            <select class="input move-course" data-id="${escapeHtml(d.id)}" aria-label="Course for ${escapeHtml(d.filename)}">
              ${this.courseOptions(d.course_id, { none: 'Not in a course', create: false })}
            </select>
          </td>
          <td style="padding:10px;text-align:right;">
            <button class="workspace-action primary study-doc-btn" data-id="${escapeHtml(d.id)}" ${d.status === 'indexed' ? '' : 'disabled'}>Study</button>
            <details class="row-menu">
              <summary class="workspace-action" aria-label="More actions for ${escapeHtml(d.filename)}">More</summary>
              <div class="row-menu-list">
                ${d.status === 'indexed' ? `<button class="row-menu-item" data-action="study-slides" data-id="${escapeHtml(d.id)}">Study slides</button>` : ''}
                <button class="row-menu-item preview-doc-btn" data-id="${escapeHtml(d.id)}">Preview</button>
                <button class="row-menu-item topics-doc-btn" data-id="${escapeHtml(d.id)}" ${d.status === 'indexed' ? '' : 'disabled'}>Topics</button>
                <button class="row-menu-item danger delete-doc-btn" data-id="${escapeHtml(d.id)}">Delete</button>
              </div>
            </details>
          </td>
        </tr>
      `;
      })
      .join('');
  }

  renderGroup(title, docs, course) {
    const ready = docs.some((d) => d.status === 'indexed');
    return `
      <section class="course-group stack" ${course ? `data-course="${escapeHtml(course.id)}"` : ''}>
        <div class="row-between course-header">
          <h3 class="course-title">${escapeHtml(title)} <span class="badge">${docs.length.toLocaleString()} lecture${docs.length === 1 ? '' : 's'}</span></h3>
          ${
            course
              ? `<div>
                  <button class="workspace-action primary study-course-btn" data-id="${escapeHtml(course.id)}" ${ready ? '' : 'disabled'}>Study course</button>
                  <button class="workspace-action rename-course-btn" data-id="${escapeHtml(course.id)}">Rename</button>
                  <button class="link-danger delete-course-btn" data-id="${escapeHtml(course.id)}">Delete course</button>
                </div>`
              : ''
          }
        </div>
        ${
          course
            ? `<p class="muted course-progress" data-course="${escapeHtml(course.id)}">Loading progress…</p>
              <details class="course-progress-panel" data-course="${escapeHtml(course.id)}">
                <summary>Progress by topic</summary>
                <div class="course-progress-body"></div>
              </details>`
            : ''
        }
        ${
          docs.length
            ? `<div class="library-table-wrap">
                <table class="library-table" style="width:100%;border-collapse:collapse;font-size:14px;text-align:left;">
                  <thead>
                    <tr style="border-bottom:1px solid var(--border);color:var(--text-dim);">
                      <th style="padding:10px;">Filename</th>
                      <th style="padding:10px;">Status</th>
                      <th style="padding:10px;">Course</th>
                      <th style="padding:10px;text-align:right;">Actions</th>
                    </tr>
                  </thead>
                  <tbody>${this.renderRows(docs)}</tbody>
                </table>
              </div>`
            : '<p class="muted">No lectures yet. Choose this course when you upload.</p>'
        }
      </section>
    `;
  }

  render() {
    const loose = this.documents.filter((d) => !this.courseName(d.course_id));
    const groups = [
      ...this.courses.map((course) =>
        this.renderGroup(
          course.name,
          this.documents.filter((d) => d.course_id === course.id),
          course,
        ),
      ),
      loose.length || !this.courses.length
        ? this.renderGroup(this.courses.length ? 'Not in a course' : 'All notes', loose, null)
        : '',
    ].join('');
    const accept = this.ocrReady
      ? '.pdf,.docx,.pptx,.txt,.png,.jpg,.jpeg'
      : '.pdf,.docx,.pptx,.txt';

    this.container.innerHTML = `
      <div class="view-header view-header row-between">
        <div>
          <h2 class="page-title">Library</h2>
          <p class="muted">Upload your lecture notes and slides, group them into courses, then choose Study to ask questions about them.</p>
        </div>
        <button ${store.getState('currentUser')?.role === 'admin' ? '' : 'hidden'} id="sync-library-btn" class="workspace-action">
          ${window.sentioIcon('refresh', 16)} Sync disk folder
        </button>
      </div>

      ${this.justUploadedId ? `<div class="notice library-ready" role="status">Your notes are ready. <button class="workspace-action primary study-doc-btn" data-id="${escapeHtml(this.justUploadedId)}">Study these notes</button></div>` : ''}
      <div class="library-layout ${this.libraryView === 'board' ? 'is-board' : ''}" style="display:grid;gap:20px;width:100%;">
        <!-- Left: Search and List -->
        <div class="stack stack-lg">
          <sentio-card title="Your notes">
            <div style="display:flex;gap:10px;margin-bottom:16px;">
              <input type="text" id="doc-search-input" value="${escapeHtml(this.filterQuery)}" placeholder="Search files or courses..." style="flex:1;min-width:0;background:var(--bg3);border:1px solid var(--border);border-radius:var(--radius);padding:8px 12px;color:var(--text);font-family:var(--mono);font-size:14px;outline:none;" />
              <button class="workspace-action" id="new-course-btn">New course</button>
            </div>

            ${
              this.documents.length === 0 && this.courses.length === 0
                ? `
              <div class="library-empty">
                <p class="library-empty-title">Add your first lecture</p>
                <p class="muted">Drop slides, a PDF, a Word document or a text file on the right. Each one shows up here, ready to study.</p>
                <ul class="ghost-rows" aria-hidden="true">
                  <li><span class="ghost-name">Lecture 1 · Introduction.pptx</span><span class="doc-state ready">Ready to study</span></li>
                  <li><span class="ghost-name">Week 2 notes.pdf</span><span class="doc-state ready">Ready to study</span></li>
                </ul>
              </div>
            `
                : `<div class="library-view-bar"><div class="seg" role="group" aria-label="Library view">${[
                    ['list', 'List'],
                    ['board', 'Board'],
                  ]
                    .map(
                      ([value, label]) =>
                        `<button type="button" class="seg-option" data-library-view="${value}" aria-pressed="${this.libraryView === value}">${label}</button>`,
                    )
                    .join('')}</div><p id="doc-search-status" role="status"></p></div>
                  <div class="stack stack-lg" ${this.libraryView === 'board' ? 'hidden' : ''}>${groups}</div>
                  ${this.libraryView === 'board' ? '<div id="topic-board" class="topic-board"><p role="status">Loading topics…</p></div>' : ''}`
            }
          </sentio-card>
        </div>

        <!-- Right: Upload Panel -->
        <div style="display:flex;flex-direction:column;gap:20px;">
          <sentio-card title="Add your notes">
            <div style="margin-bottom:16px;">
              <label class="form-label" for="upload-course">Course</label>
              <select class="input" id="upload-course">
                ${this.courseOptions(this.uploadCourse, { none: 'Not in a course', create: true })}
              </select>
            </div>
            <div id="drop-zone" class="drop-zone" role="button" tabindex="0" aria-label="Choose study material files">
              <span class="drop-zone-icon">${window.sentioIcon('upload', 24)}</span>
              <span class="drop-zone-title">Drop files anywhere on this page</span>
              <span class="muted">or choose files. Several at once is fine.</span>
              <input type="file" id="file-uploader" multiple style="display:none;" accept="${accept}" />
            </div>

            <p class="muted">PowerPoint, PDF, Word or text. 20 MiB per file. ${this.ocrReady ? 'English OCR enabled; up to 20 scanned pages.' : 'Scans and images require the optional OCR tools.'}</p>
            <p id="upload-batch" role="status" class="muted">${escapeHtml(this.batchStatus)}</p>
            <div id="upload-list">${this.renderUploadList()}</div>
            <div id="library-job" role="region" aria-label="Upload progress"></div>

          </sentio-card>
        </div>
      </div>
    `;
  }

  // Ask for a course name; returns the created course, or null if cancelled or failed.
  async createCourse() {
    const name = (window.prompt('Course name, for example "Operating Systems"') || '').trim();
    if (!name) return null;
    try {
      const course = await sentioAPI.post('/courses', { name });
      this.courses = [...this.courses, course].sort((a, b) => a.name.localeCompare(b.name));
      toast(`Course "${course.name}" created.`);
      return course;
    } catch (error) {
      toast('Course not created: ' + error.message, true);
      return null;
    }
  }

  bindEvents() {
    this.container.querySelectorAll('[data-library-view]').forEach((button) => {
      button.onclick = () => {
        if (this.libraryView === button.dataset.libraryView) return;
        this.libraryView = button.dataset.libraryView;
        globalThis.localStorage?.setItem('sentio_library_view', this.libraryView);
        this.render();
        this.bindEvents();
        const current = this.current || (() => true);
        this.loadCourseProgress(current);
        if (this.libraryView === 'board') this.loadBoard(current);
      };
    });
    this.container.querySelectorAll('.study-doc-btn').forEach((button) => {
      button.onclick = () =>
        this.studyDocument(this.documents.find((item) => item.id === button.dataset.id));
    });
    this.container.querySelectorAll('[data-action="study-slides"]').forEach((button) => {
      button.onclick = () =>
        this.studySlides(this.documents.find((item) => item.id === button.dataset.id));
    });
    this.container.querySelectorAll('.study-course-btn').forEach((button) => {
      button.onclick = () =>
        this.studyCourse(this.courses.find((course) => course.id === button.dataset.id));
    });
    // 1. Search filter binding
    const search = this.container.querySelector('#doc-search-input');
    if (search) {
      search.oninput = (e) => {
        this.filterQuery = e.target.value;
        this.applyFilter();
      };
    }

    this.applyFilter();
    this.container.querySelectorAll('.preview-doc-btn').forEach((button) => {
      button.onclick = () => this.previewDocument(button.dataset.id);
    });
    this.container.querySelectorAll('.topics-doc-btn').forEach((button) => {
      button.onclick = () => this.showDocumentTopics(button.dataset.id);
    });

    // 2. Courses: create, rename, delete, move lectures
    const newCourse = this.container.querySelector('#new-course-btn');
    if (newCourse)
      newCourse.onclick = async () => {
        if (await this.createCourse()) this.loadDocuments();
      };
    this.container.querySelectorAll('.rename-course-btn').forEach((button) => {
      button.onclick = async () => {
        const course = this.courses.find((item) => item.id === button.dataset.id);
        const name = (window.prompt('Rename course', course?.name || '') || '').trim();
        if (!course || !name || name === course.name) return;
        try {
          await sentioAPI.request(`/courses/${encodeURIComponent(course.id)}`, {
            method: 'PATCH',
            body: JSON.stringify({ name }),
          });
          this.loadDocuments();
        } catch (error) {
          toast('Rename failed: ' + error.message, true);
        }
      };
    });
    this.container.querySelectorAll('.delete-course-btn').forEach((button) => {
      button.onclick = async () => {
        const course = this.courses.find((item) => item.id === button.dataset.id);
        if (
          !course ||
          !confirm(`Delete the course "${course.name}"? Its lectures stay in your library.`)
        )
          return;
        try {
          await sentioAPI.delete(`/courses/${encodeURIComponent(course.id)}`);
          toast('Course deleted. Its lectures are now outside any course.');
          this.loadDocuments();
        } catch (error) {
          toast('Delete failed: ' + error.message, true);
        }
      };
    });
    this.container.querySelectorAll('.move-course').forEach((select) => {
      select.onchange = async () => {
        try {
          await sentioAPI.request(`/documents/${encodeURIComponent(select.dataset.id)}/course`, {
            method: 'PATCH',
            body: JSON.stringify({ course_id: select.value || null }),
          });
          this.loadDocuments();
        } catch (error) {
          toast('Move failed: ' + error.message, true);
          this.loadDocuments();
        }
      };
    });

    // 3. Sync Library Button binding
    const syncBtn = this.container.querySelector('#sync-library-btn');
    if (syncBtn) {
      syncBtn.onclick = async () => {
        store.setState('loading', true);
        try {
          const res = await sentioAPI.post('/documents/sync');
          toast(`Library scan finished! Synced: ${res.report?.indexed_count || 0} files.`);
          this.loadDocuments();
        } catch (e) {
          toast('Sync failed: ' + e.message, true);
        } finally {
          store.setState('loading', false);
        }
      };
    }

    // 4. Delete Document buttons binding
    this.container.querySelectorAll('.delete-doc-btn').forEach((btn) => {
      btn.onclick = async (e) => {
        const docId = e.target.dataset.id;
        if (
          !confirm(
            'Are you sure you want to delete this document? This will remove all Qdrant vector chunks and delete the raw file from disk.',
          )
        ) {
          return;
        }

        store.setState('loading', true);
        try {
          await sentioAPI.delete(`/documents/${docId}`);
          toast('Document deleted successfully.');
          this.loadDocuments();
        } catch (err) {
          toast('Delete failed: ' + err.message, true);
        } finally {
          store.setState('loading', false);
        }
      };
    });

    // 5. Course for uploads, drag and drop + file picker
    const courseSelect = this.container.querySelector('#upload-course');
    if (courseSelect)
      courseSelect.onchange = async () => {
        if (courseSelect.value !== NEW_COURSE) {
          this.uploadCourse = courseSelect.value;
          return;
        }
        const course = await this.createCourse();
        this.uploadCourse = course ? course.id : this.uploadCourse;
        courseSelect.innerHTML = this.courseOptions(this.uploadCourse, {
          none: 'Not in a course',
          create: true,
        });
      };
    const dropZone = this.container.querySelector('#drop-zone');
    const uploader = this.container.querySelector('#file-uploader');
    if (uploader) uploader.disabled = this.uploadInProgress;

    if (dropZone && uploader) {
      dropZone.onclick = () => {
        if (!this.uploadInProgress) uploader.click();
      };
      dropZone.onkeydown = (event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          dropZone.click();
        }
      };

      // Files can be dropped anywhere on the Library page.
      const carriesFiles = (e) => [...(e.dataTransfer?.types || [])].includes('Files');
      this.container.ondragover = (e) => {
        if (!carriesFiles(e)) return;
        e.preventDefault();
        this.container.classList.add('is-dropping');
      };
      this.container.ondragleave = (e) => {
        if (!this.container.contains(e.relatedTarget))
          this.container.classList.remove('is-dropping');
      };
      this.container.ondrop = (e) => {
        if (!carriesFiles(e)) return;
        e.preventDefault();
        this.container.classList.remove('is-dropping');
        this.uploadFiles([...e.dataTransfer.files]);
      };

      uploader.onchange = (e) => {
        this.uploadFiles([...e.target.files]);
      };
    }
    this.bindUploadList();
  }

  applyFilter() {
    let shown = 0;
    this.container.querySelectorAll('.document-row').forEach((row) => {
      row.hidden = !row.dataset.search.includes(this.filterQuery.toLowerCase());
      if (!row.hidden) shown++;
    });
    const status = this.container.querySelector('#doc-search-status');
    if (status)
      status.textContent = `${shown.toLocaleString()} matching material${shown === 1 ? '' : 's'}`;
  }

  // The board shows every topic from ready lectures, grouped by learning state.
  async loadBoard(current) {
    const lectures = this.documents.filter((d) => d.status === 'indexed').slice(0, BOARD_LIMIT);
    const results = await Promise.allSettled(
      lectures.map((d) => sentioAPI.get(`/documents/${encodeURIComponent(d.id)}/topics`)),
    );
    if (!current()) return;
    const board = this.container.querySelector('#topic-board');
    if (!board) return;
    const topics = results.flatMap((result) =>
      result.status === 'fulfilled' ? result.value.topics || [] : [],
    );
    this.remember(topics);
    const failed = results.filter((result) => result.status === 'rejected').length;
    board.innerHTML =
      boardView(topics) +
      (failed
        ? `<p class="muted" role="status">${failed} lecture${failed === 1 ? '' : 's'} could not load.</p>`
        : '') +
      (this.documents.filter((d) => d.status === 'indexed').length > BOARD_LIMIT
        ? `<p class="muted">Showing topics from the first ${BOARD_LIMIT} lectures.</p>`
        : '');
    board.querySelectorAll('.board-column').forEach((column, index) => {
      column.style.animationDelay = `${index * 50}ms`;
      column.classList.add('enter-rise');
    });
  }

  remember(topics) {
    for (const topic of topics) this.topics.set(topic.id, topic);
  }

  // Each course shows how many topics are ready, a per-topic panel and its weak topics.
  async loadCourseProgress(current) {
    await Promise.all(
      this.courses.map(async (course) => {
        let progress, syllabus;
        try {
          [progress, syllabus] = await Promise.all([
            sentioAPI.get(`/courses/${encodeURIComponent(course.id)}/progress`),
            sentioAPI.get(`/courses/${encodeURIComponent(course.id)}/syllabus`),
          ]);
        } catch {
          return;
        }
        if (!current()) return;
        const line = this.container.querySelector(`.course-progress[data-course="${course.id}"]`);
        const body = this.container.querySelector(
          `.course-progress-panel[data-course="${course.id}"] .course-progress-body`,
        );
        if (!line || !body) return;
        const topics = progress.lectures.flatMap((lecture) => lecture.topics);
        this.remember(topics);
        this.syllabi.set(course.id, syllabus);
        line.textContent = syllabus.items.length
          ? `${syllabus.summary.percent_ready}% of the syllabus ready · ${progressLine(progress.summary)}. Practice estimate from your quizzes and flashcards.`
          : `${progressLine(progress.summary)}. Practice estimate from your quizzes and flashcards.`;
        body.innerHTML = `
          ${syllabus.items.length ? syllabusView(syllabus, course.id) : syllabusForm(course.id)}
          ${
            progress.due.length
              ? `<div class="due-topics stack">
                  <div class="row-between"><h4>Due for review</h4>
                    <button class="workspace-action primary practise-due-btn" data-course="${escapeHtml(course.id)}">Practise due topics</button>
                  </div>
                  ${topicList(progress.due, { showLecture: true })}
                </div>`
              : ''
          }
          ${
            progress.weak.length
              ? `<div class="weak-topics stack">
                  <div class="row-between"><h4>Weak topics</h4>
                    <button class="workspace-action primary practise-weak-btn" data-course="${escapeHtml(course.id)}">Practise weak topics</button>
                  </div>
                  ${topicList(progress.weak, { showLecture: true })}
                </div>`
              : ''
          }
          ${progress.lectures
            .map(
              (lecture) =>
                `<div class="stack"><h4>${escapeHtml(lecture.filename)}</h4>${topicList(lecture.topics)}</div>`,
            )
            .join('')}`;
        const practise = (button, chosen) => {
          if (!button) return;
          button.onclick = () => {
            const topics = chosen.slice(0, MAX_PRACTICE_TOPICS);
            this.startStudy(
              {
                subject: course.name,
                topic: topics
                  .map((topic) => topic.title)
                  .join('; ')
                  .slice(0, 150),
                documentId: `course:${course.id}`,
                topicIds: topics.map((topic) => topic.id),
              },
              '#/quizzes',
            );
          };
        };
        practise(body.querySelector('.practise-weak-btn'), progress.weak);
        practise(body.querySelector('.practise-due-btn'), progress.due);
      }),
    );
  }

  async onSyllabusAction(event) {
    const button = event.target.closest('[data-syllabus-action]');
    if (!button) return;
    const courseId = button.dataset.course;
    const course = this.courses.find((item) => item.id === courseId);
    const path = `/courses/${encodeURIComponent(courseId)}/syllabus`;
    const action = button.dataset.syllabusAction;
    if (action === 'practise') {
      const item = this.syllabi.get(courseId)?.items.find((i) => i.id === button.dataset.item);
      if (!item) return;
      const documents = [...new Set(item.topics.map((topic) => topic.document_id))];
      await this.startStudy(
        {
          subject: course?.name || 'My notes',
          topic: item.title,
          documentId: documents.length === 1 ? documents[0] : `course:${courseId}`,
          topicIds: item.topics.map((topic) => topic.id),
        },
        '#/quizzes',
      );
      return;
    }
    if (action === 'replace') {
      button.closest('.syllabus').outerHTML = syllabusForm(courseId);
      return;
    }
    try {
      if (action === 'remove') {
        if (!confirm('Remove this syllabus? Your notes and practice stay.')) return;
        await sentioAPI.delete(path);
      } else if (action === 'save') {
        const form = button.closest('.syllabus-form');
        const body = new FormData();
        const file = form.querySelector('.syllabus-file').files[0];
        if (file) body.append('file', file);
        else body.append('text', form.querySelector('.syllabus-text').value);
        button.disabled = true;
        await sentioAPI.request(path, { method: 'PUT', body });
        toast('Syllabus saved and matched to your lectures.');
      }
    } catch (error) {
      toast('Syllabus not saved: ' + error.message, true);
      button.disabled = false;
      return;
    }
    this.loadDocuments();
  }

  async onSyllabusMatch(event) {
    const select = event.target.closest('.syllabus-match');
    if (!select) return;
    const [mode, topicId] = select.value.split(':');
    try {
      await sentioAPI.request(`/syllabus/${encodeURIComponent(select.dataset.item)}`, {
        method: 'PATCH',
        body: JSON.stringify({ mode, topic_id: topicId || null }),
      });
    } catch (error) {
      toast('Match not changed: ' + error.message, true);
    }
    this.loadDocuments();
  }

  async showDocumentTopics(documentId) {
    const owner = store.getState('currentUser')?.id;
    try {
      const lecture = await sentioAPI.get(`/documents/${encodeURIComponent(documentId)}/topics`);
      if (owner !== store.getState('currentUser')?.id) return;
      this.remember(lecture.topics);
      const modal = document.createElement('sentio-modal');
      modal.setAttribute('title', `Topics in ${lecture.filename}`);
      modal.innerHTML = `<p class="muted">Practice estimate from your quizzes and flashcards: Ready means your last 3 answers on the topic were all correct and you probably still remember it. Review due means it is time to check again.</p>${topicList(lecture.topics)}`;
      modal.addEventListener('click', (event) => this.onTopicAction(event, modal));
      document.body.appendChild(modal);
    } catch (error) {
      toast('Topics unavailable: ' + error.message, true);
    }
  }

  async onTopicAction(event, modal = null) {
    const button = event.target.closest('[data-topic-action]');
    if (!button) return;
    const topic = this.topics.get(button.dataset.topic);
    if (!topic) return;
    const action = button.dataset.topicAction;
    const lecture = this.documents.find((d) => d.id === topic.document_id);
    const study = {
      subject: this.courseName(lecture?.course_id) || 'My notes',
      topic: topic.title,
      documentId: topic.document_id,
    };
    if (action === 'review') {
      modal?.close();
      await this.startStudy(study, '#/tutor');
      return;
    }
    if (action === 'practise') {
      modal?.close();
      await this.startStudy({ ...study, topicIds: [topic.id] }, '#/quizzes');
      return;
    }
    try {
      if (action === 'rename') {
        const title = (window.prompt('Rename topic', topic.title) || '').trim();
        if (!title || title === topic.title) return;
        await sentioAPI.request(`/topics/${encodeURIComponent(topic.id)}`, {
          method: 'PATCH',
          body: JSON.stringify({ name: title }),
        });
      } else if (action === 'merge') {
        if (!confirm(`Join "${topic.title}" to the topic above it?`)) return;
        await sentioAPI.post(`/topics/${encodeURIComponent(topic.id)}/merge`, {});
      }
    } catch (error) {
      toast('Topic not updated: ' + error.message, true);
      return;
    }
    if (modal) {
      modal.close();
      this.showDocumentTopics(topic.document_id);
    }
    this.loadDocuments();
  }

  async previewDocument(documentId) {
    const owner = store.getState('currentUser')?.id;
    const revision = this.revision;
    try {
      const result = await sentioAPI.get(`/documents/${documentId}/preview`);
      if (owner !== store.getState('currentUser')?.id || revision !== this.revision) return;
      const modal = document.createElement('sentio-modal');
      modal.setAttribute('title', result.document.filename);
      modal.innerHTML =
        '<p>Extracted source text. Check scans for recognition errors.</p><div class="document-preview"></div><button class="preview-more" type="button">Show more</button>';
      document.body.appendChild(modal);
      const append = (data) => {
        for (const chunk of data.chunks) {
          const section = document.createElement('section');
          section.innerHTML = `<h3>${escapeHtml(pageLabel(result.document.filename, chunk.page_number || 1))}</h3><p style="white-space:pre-wrap">${escapeHtml(chunk.text_content)}</p>`;
          modal.querySelector('.document-preview').appendChild(section);
        }
        const more = modal.querySelector('.preview-more');
        more.hidden = data.next_offset === null;
        more.onclick = async () => {
          more.disabled = true;
          try {
            append(
              await sentioAPI.get(`/documents/${documentId}/preview?offset=${data.next_offset}`),
            );
          } catch (error) {
            toast(error.message, true);
          } finally {
            more.disabled = false;
          }
        };
      };
      append(result);
    } catch (error) {
      toast('Preview unavailable: ' + error.message, true);
    }
  }

  // One row per file in the current batch, with its own state.
  renderUploadList() {
    if (!this.batchItems.length) return '';
    const label = {
      waiting: 'Waiting',
      working: 'Processing',
      done: 'Ready to study',
      failed: 'Not added',
    };
    const pill = { waiting: '', working: 'working', done: 'ready', failed: 'failed' };
    const rows = this.batchItems
      .map(
        (item) => `<li class="upload-item">
          <span class="upload-name">${window.sentioIcon('file', 16)}<span>${escapeHtml(item.name)}</span></span>
          <span class="doc-state ${pill[item.state]}">${label[item.state]}</span>
        </li>`,
      )
      .join('');
    const retry =
      this.failedFiles.length && !this.uploadInProgress
        ? `<button type="button" class="workspace-action" id="retry-failed-btn">${window.sentioIcon('refresh', 16)} Try ${this.failedFiles.length === 1 ? 'it' : 'them'} again</button>`
        : '';
    return `<ul class="upload-list">${rows}</ul>${retry}`;
  }

  updateUploadList() {
    const list = this.container.querySelector('#upload-list');
    if (!list) return;
    list.innerHTML = this.renderUploadList();
    this.bindUploadList();
  }

  bindUploadList() {
    this.container.querySelector('#retry-failed-btn')?.addEventListener('click', () => {
      const files = this.failedFiles;
      this.failedFiles = [];
      this.uploadFiles(files);
    });
  }

  // Several files upload one after another; a failure is reported and the rest continue.
  async uploadFiles(files) {
    if (!files.length) return;
    if (this.uploadInProgress) {
      toast('Wait for the current upload to finish, then add these files.');
      return;
    }
    const owner = store.getState('currentUser')?.id;
    const courseId = this.uploadCourse;
    const failed = [];
    this.failedFiles = [];
    this.batchItems = files.map((file) => ({ name: file.name, state: 'waiting' }));
    this.updateUploadList();
    for (const [index, file] of files.entries()) {
      if (owner !== store.getState('currentUser')?.id) return;
      this.batchStatus =
        files.length > 1 ? `Uploading ${index + 1} of ${files.length}: ${file.name}` : '';
      const status = this.container.querySelector('#upload-batch');
      if (status) status.textContent = this.batchStatus;
      this.batchItems[index].state = 'working';
      this.updateUploadList();
      const ok = await this.uploadFile(file, courseId);
      this.batchItems[index].state = ok ? 'done' : 'failed';
      if (!ok) {
        failed.push(file.name);
        this.failedFiles.push(file);
      }
      this.updateUploadList();
    }
    this.batchStatus =
      files.length > 1
        ? `${files.length - failed.length} of ${files.length} files added.` +
          (failed.length ? ` Not added: ${failed.join(', ')}.` : '')
        : '';
    const status = this.container.querySelector('#upload-batch');
    if (status) status.textContent = this.batchStatus;
    if (failed.length && files.length > 1)
      toast(`${failed.length} file${failed.length === 1 ? '' : 's'} could not be added.`, true);
  }

  // Returns true when the file was indexed.
  async uploadFile(file, courseId = '') {
    if (this.uploadInProgress) return false;
    this.uploadInProgress = true;
    const owner = store.getState('currentUser')?.id;
    const revision = this.revision;
    const uploader = this.container.querySelector('#file-uploader');
    let refreshed = false;
    let added = false;
    if (uploader) uploader.disabled = true;
    try {
      // A newly chosen file is a new intent. Finish reconnecting the previous
      // receipt before sending it, rather than consuming this file as a retry.
      const pendingKey = pendingJobKey('/documents/jobs', false);
      if (file && localStorage.getItem(pendingKey)) {
        try {
          await runPracticeJob(
            '/documents/jobs',
            null,
            this.container.querySelector('#library-job'),
            { sessionScoped: false },
          );
        } catch (error) {
          if (localStorage.getItem(pendingKey)) throw error;
        }
        if (owner !== store.getState('currentUser')?.id || localStorage.getItem(pendingKey))
          return false;
      }
      // Navigation can replace the progress panel while the prior receipt is read.
      if (!this.container.querySelector('#library-job')) await this.loadDocuments();
      if (
        owner !== store.getState('currentUser')?.id ||
        !this.container.querySelector('#library-job')
      )
        return false;
      const form = new FormData();
      if (file) {
        form.append('file', file);
        form.append('category', 'notes');
        if (courseId) form.append('course_id', courseId);
      }
      const result = await runPracticeJob(
        '/documents/jobs',
        null,
        this.container.querySelector('#library-job'),
        {
          sessionScoped: false,
          submit: (requestId) => {
            if (!file) throw new Error('Choose the file again to retry this upload.');
            return sentioAPI.request('/documents/jobs', {
              method: 'POST',
              body: form,
              headers: { 'Idempotency-Key': requestId },
            });
          },
        },
      );
      added = Boolean(result);
      if (
        result &&
        owner === store.getState('currentUser')?.id &&
        store.getState('activeRoute') === '#/documents'
      ) {
        toast(
          `${file ? file.name + ' saved. ' : 'Study material saved. '}` +
            (result.indexing_mode === 'keyword'
              ? 'Keyword search is available; semantic indexing was unavailable.'
              : 'Ready for study.'),
        );
        this.justUploadedId = result.document_id;
        await this.loadDocuments();
        refreshed = true;
      }
    } catch (error) {
      if (owner === store.getState('currentUser')?.id && revision === this.revision) {
        this.container.querySelector('#library-job').textContent =
          `${file ? file.name + ': ' : ''}${error.message}` +
          (file ? ' Use Try again below.' : ' Choose the file again to retry.');
        toast('Upload did not finish: ' + error.message, true);
      }
    } finally {
      this.uploadInProgress = false;
      if (uploader) uploader.disabled = false;
      const currentUploader = this.container.querySelector('#file-uploader');
      if (currentUploader && owner === store.getState('currentUser')?.id)
        currentUploader.disabled = false;
      if (
        !refreshed &&
        revision !== this.revision &&
        store.getState('activeRoute') === '#/documents' &&
        owner === store.getState('currentUser')?.id
      )
        await this.loadDocuments();
    }
    return added;
  }

  async startStudy(options, route = '#/tutor') {
    const owner = store.getState('currentUser')?.id;
    store.setState('loading', true);
    try {
      const started = await window.startSession({
        difficulty: 'beginner',
        isCurrent: () => owner === store.getState('currentUser')?.id,
        ...options,
      });
      if (started) window.location.hash = route;
    } finally {
      store.setState('loading', false);
    }
  }

  // One click: the topic comes from the document, so no setup dialog is needed.
  // The opening line (usually a title) matches the notes better than the filename.
  async studyDocument(doc) {
    if (!doc) return;
    let topic = doc.filename.replace(/\.[^.]+$/, '').replace(/[_-]+/g, ' ');
    try {
      const preview = await sentioAPI.get(
        `/documents/${encodeURIComponent(doc.id)}/preview?limit=1`,
      );
      const opening = openingTitle(preview.chunks[0]?.text_content);
      if (opening) topic = opening;
    } catch {
      // The filename remains a usable topic.
    }
    await this.startStudy({
      subject: this.courseName(doc.course_id) || 'My notes',
      topic,
      documentId: doc.id,
    });
  }

  // Read one lecture slide by slide with the tutor beside it.
  async studySlides(doc) {
    if (!doc) return;
    await this.startStudy(
      {
        subject: this.courseName(doc.course_id) || 'My notes',
        topic: doc.filename.replace(/\.[^.]+$/, '').replace(/[_-]+/g, ' '),
        documentId: doc.id,
        mode: 'slides',
      },
      '#/slides',
    );
  }

  // Study every lecture in a course, including lectures added later.
  async studyCourse(course) {
    if (!course) return;
    await this.startStudy({
      subject: course.name,
      topic: course.name,
      documentId: `course:${course.id}`,
    });
  }
}
