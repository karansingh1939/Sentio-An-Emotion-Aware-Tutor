import { sentioAPI } from '../core/api.js';
import { store } from '../core/store.js';
import { escapeHtml } from '../core/html.js';

export class HistoryView {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
    this.revision = 0;
    this.sessions = [];
  }
  init() {
    store.subscribe('activeRoute', (route) => {
      if (route === '#/history') this.load();
      else this.revision++;
    });
    this.render([]);
  }
  async load(offset = 0) {
    const owner = store.getState('currentUser')?.id;
    const revision = ++this.revision;
    if (!offset) this.container.innerHTML = '<p role="status">Loading study history…</p>';
    const current = () =>
      revision === this.revision &&
      store.getState('currentUser')?.id === owner &&
      store.getState('activeRoute') === '#/history';
    try {
      const result = await sentioAPI.get(`/sessions?limit=20&offset=${offset}`);
      if (!current()) return;
      this.sessions = offset
        ? [...this.sessions, ...(result.sessions || [])]
        : result.sessions || [];
      this.nextOffset = result.next_offset;
      this.render(this.sessions);
    } catch (error) {
      if (!current()) return;
      this.container.innerHTML = `<p role="alert">${escapeHtml(error.message)}</p><button id="retry-history">Try again</button>`;
      this.container.querySelector('#retry-history').onclick = () => this.load();
    }
  }
  render(sessions) {
    this.container.innerHTML = `
      <div class="view-header"><h2>Study history</h2><p>Your recent learning sessions.</p></div>
      ${
        sessions.length
          ? `<div style="overflow-x:auto"><table style="width:100%;text-align:left;border-spacing:0 16px">
      <thead><tr><th scope="col">Topic</th><th scope="col">Subject</th><th scope="col">Status</th><th scope="col">Started</th><th scope="col">Messages</th></tr></thead>
      <tbody>${sessions.map((s) => `<tr><td>${escapeHtml(s.topic || 'General')}</td><td>${escapeHtml(s.subject)}</td><td>${escapeHtml(s.status)}</td><td>${escapeHtml(new Date(s.created_at * 1000).toLocaleString())}</td><td>${escapeHtml(s.total_exchanges ?? s.exchanges?.length ?? 0)}</td></tr>`).join('')}</tbody></table></div>`
          : '<p role="status">Your sessions will appear here after you start studying.</p>'
      }
      ${this.nextOffset != null ? '<button class="workspace-action" id="history-more">Load more sessions</button>' : ''}
    `;
    const more = this.container.querySelector('#history-more');
    if (more)
      more.onclick = () => {
        more.disabled = true;
        this.load(this.nextOffset);
      };
  }
}
