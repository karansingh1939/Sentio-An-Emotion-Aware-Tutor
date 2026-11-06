import { sentioAPI } from '../core/api.js';
import { store } from '../core/store.js';
import { escapeHtml } from '../core/html.js';

// Progress: stat tiles and a sortable topic-mastery report.
// Layout follows the Reports screen in docs/design/inspiration/amplo-dashboard.md.

const percentage = (value) => Math.round(Math.max(0, Math.min(1, Number(value) || 0)) * 100);
const SORTS = [
  ['weakest', 'Weakest first'],
  ['strongest', 'Strongest first'],
  ['name', 'A–Z'],
];
const band = (mastery) => (mastery >= 0.8 ? 'green' : mastery >= 0.4 ? '' : 'amber');

export class AnalyticsView {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
    this.revision = 0;
    this.sort = 'weakest';
  }
  init() {
    store.subscribe('activeRoute', (route) => {
      if (route === '#/analytics') this.load();
      else this.revision++;
    });
    this.render({});
  }
  async load() {
    const user = store.getState('currentUser');
    if (!user) return;
    const revision = ++this.revision;
    const current = () =>
      revision === this.revision &&
      store.getState('currentUser')?.id === user.id &&
      store.getState('activeRoute') === '#/analytics';
    this.container.innerHTML = '<p role="status">Loading your progress…</p>';
    try {
      const profile = await sentioAPI.get(`/student/${encodeURIComponent(user.id)}/profile`);
      if (current()) this.render(profile);
    } catch (error) {
      if (!current()) return;
      this.container.innerHTML = `<p role="alert">${escapeHtml(error.message)}</p><button id="retry-analytics">Try again</button>`;
      this.container.querySelector('#retry-analytics').onclick = () => this.load();
    }
  }
  sorted(topics) {
    const list = [...topics];
    if (this.sort === 'name') return list.sort(([a], [b]) => a.localeCompare(b));
    if (this.sort === 'strongest') return list.sort(([, a], [, b]) => b - a);
    return list.sort(([, a], [, b]) => a - b);
  }
  render(profile) {
    this.profile = profile;
    const topics = Object.entries(profile.topic_mastery || {});
    const priorities = profile.review_priorities || [];
    const rows = this.sorted(topics)
      .map(
        ([topic, mastery]) => `<li class="report-row">
          <span class="report-name">${escapeHtml(topic.replaceAll('_', ' '))}</span>
          <div class="meter ${band(mastery)}" role="img" aria-label="${escapeHtml(topic)} mastery ${percentage(mastery)}%"><i style="width:${percentage(mastery)}%"></i></div>
          <b>${percentage(mastery)}%</b>
        </li>`,
      )
      .join('');
    this.container.innerHTML = `
      <div class="view-header"><h2>Your progress</h2><p>Use your saved practice to decide what to revisit.</p></div>
      <div class="stat-grid">
        <div class="stat"><div class="stat-label">Practice estimate${topics.length ? '' : ' (not assessed yet)'}</div><div class="stat-value">${topics.length ? `<span data-count="${percentage(profile.overall_mastery)}" data-suffix="%">${percentage(profile.overall_mastery)}%</span>` : '—'}</div></div>
        <div class="stat"><div class="stat-label">Day learning streak</div><div class="stat-value"><span data-count="${Number(profile.learning_streak) || 0}">${escapeHtml(profile.learning_streak || 0)}</span></div></div>
        <div class="stat"><div class="stat-label">Topics to review: ${escapeHtml(priorities.join(', ') || 'none due')}</div><div class="stat-value">${escapeHtml(priorities.length)}</div></div>
      </div>
      <sentio-card title="Topic mastery">
        ${
          topics.length
            ? `<div class="report-head"><p class="muted card-sub">${topics.length} topic${topics.length === 1 ? '' : 's'} · from quiz answers and card ratings</p>
                <div class="seg" role="group" aria-label="Sort topics">${SORTS.map(([value, label]) => `<button type="button" class="seg-option" data-sort="${value}" aria-pressed="${this.sort === value}">${label}</button>`).join('')}</div></div>
              <ul class="mastery-list report-list">${rows}</ul>`
            : '<p role="status">Complete a quiz or flashcard review to build your topic mastery.</p>'
        }
        <p class="muted">Estimates combine quiz answers and self-reported card ratings. They guide review; they do not prove understanding.</p>
      </sentio-card>
    `;
    this.container.querySelectorAll('[data-sort]').forEach((button) => {
      button.onclick = () => {
        this.sort = button.dataset.sort;
        this.render(this.profile);
      };
    });
  }
}
