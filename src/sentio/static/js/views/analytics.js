import { sentioAPI } from '../core/api.js';
import { store } from '../core/store.js';
import { escapeHtml } from '../core/html.js';

const percentage = (value) => Math.round(Math.max(0, Math.min(1, Number(value) || 0)) * 100);
export class AnalyticsView {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
  }
  init() {
    store.subscribe('activeRoute', (route) => {
      if (route === '#/analytics') this.load();
    });
    this.render({});
  }
  async load() {
    const user = store.getState('currentUser');
    if (!user) return;
    this.container.innerHTML = '<p role="status">Loading learning analytics?</p>';
    try {
      this.render(await sentioAPI.get(`/student/${encodeURIComponent(user.id)}/profile`));
    } catch (error) {
      this.container.innerHTML = `<p role="alert">${escapeHtml(error.message)}</p><button id="retry-analytics">Try again</button>`;
      this.container.querySelector('#retry-analytics').onclick = () => this.load();
    }
  }
  render(profile) {
    const topics = Object.entries(profile.topic_mastery || {});
    this.container.innerHTML = `
      <div class="view-header"><h2>Learning Analytics</h2><p>Progress from your quizzes, reviews, and tutoring sessions.</p></div>
      <p>Overall mastery: <strong>${percentage(profile.overall_mastery)}%</strong></p>
      <p>Learning streak: ${escapeHtml(profile.learning_streak || 0)} days</p>
      ${topics.length ? `<ul style="padding:0;list-style:none">${topics.map(([topic, mastery]) => `<li style="margin:20px 0"><label>${escapeHtml(topic.replaceAll('_', ' '))}: ${percentage(mastery)}%<br><progress style="width:100%" max="100" value="${percentage(mastery)}" aria-label="${escapeHtml(topic)} mastery"></progress></label></li>`).join('')}</ul>` : '<p role="status">Complete a quiz or flashcard review to build your topic mastery.</p>'}
      <p>Review priorities: ${escapeHtml((profile.review_priorities || []).join(', ') || 'No reviews due')}</p>
    `;
  }
}
