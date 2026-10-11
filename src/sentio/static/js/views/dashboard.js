import { escapeHtml } from '../core/html.js';
import { store } from '../core/store.js';
import { sentioAPI } from '../core/api.js';

const percent = (value) => Math.round(Math.max(0, Math.min(1, Number(value) || 0)) * 100);

export class DashboardView {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
    this.revision = 0;
  }

  init() {
    store.subscribe('activeRoute', (route) => {
      if (route === '#/dashboard' && store.getState('currentUser')) this.loadDashboardData();
      else this.revision++;
    });
  }

  async loadDashboardData() {
    const user = store.getState('currentUser');
    if (!user) return;
    const revision = ++this.revision;
    this.container.innerHTML = '<p role="status">Preparing your study workspace…</p>';
    const id = encodeURIComponent(user.id);
    const results = await Promise.allSettled([
      sentioAPI.get(`/student/${id}/profile`),
      sentioAPI.get(`/student/${id}/recommendations`),
      sentioAPI.get('/sessions'),
      sentioAPI.get('/ready'),
    ]);
    if (revision !== this.revision || store.getState('currentUser')?.id !== user.id) return;
    const values = results.map((result) => (result.status === 'fulfilled' ? result.value : null));
    const labels = ['Progress', 'Recommendations', 'History', 'System status'];
    const failed = results.flatMap((result, index) =>
      result.status === 'rejected' ? [labels[index]] : [],
    );
    this.render(values[0], values[1], values[2]?.sessions, values[3], failed);
  }

  render(profile, recommendations, sessions, ready, failed) {
    const activeId = store.getState('activeSessionId');
    const topics = Object.entries(profile?.topic_mastery || {});
    const actionLabels = {
      review_flashcards: 'Review flashcards',
      take_quiz: 'Practise this topic',
      start_tutoring: 'Learn with your tutor',
      review_prerequisites: 'Review the foundations',
      increase_challenge: 'Try a harder question',
    };
    const destinations = { review_flashcards: '#/flashcards', take_quiz: '#/quizzes' };
    this.container.innerHTML = `
      <div class="today-heading view-header">
        <div><h2>Today</h2><p>A little understanding, built one session at a time.</p></div>
        <a class="workspace-action primary" href="#/tutor">${activeId ? 'Continue studying' : 'Start studying'}</a>
      </div>
      ${failed.length ? `<div id="dashboard-errors" class="notice error" role="alert">${escapeHtml(failed.join(', '))} unavailable. Your saved work is unchanged. <button id="retry-dash-btn" class="workspace-action">Retry</button></div>` : ''}
      ${ready && !ready.ai.ready ? `<div class="notice" role="status"><strong>Your local tutor needs attention.</strong><br>${escapeHtml(ready.ai.action)} You can still browse notes and saved practice.</div>` : ''}
      <div class="today-columns">
        <section>
          <sentio-card title="Your next step">
            ${
              recommendations === null
                ? '<p class="muted">Recommendations are currently unavailable.</p>'
                : recommendations?.length
                  ? `<ul class="study-list">${recommendations
                      .slice(0, 4)
                      .map(
                        (rec) =>
                          `<li><a class="recommended-action" href="${destinations[rec.action] || '#/tutor'}" data-topic="${escapeHtml(rec.topic_id || rec.topic || '')}">${escapeHtml(actionLabels[rec.action] || 'Continue learning')}</a><p class="muted">${escapeHtml(rec.explanation || '')}</p></li>`,
                      )
                      .join('')}</ul>`
                  : '<p>Begin with a question from your notes. Your review priorities will appear as you practise.</p><a class="workspace-action" href="#/documents">Choose study material</a>'
            }
          </sentio-card>
          <sentio-card title="Recent study">
            ${
              sessions === undefined
                ? '<p class="muted">Study history is currently unavailable.</p>'
                : sessions?.length
                  ? `<ul class="study-list">${sessions
                      .slice(0, 5)
                      .map(
                        (session) =>
                          `<li><a href="#/tutor" class="continue-session" data-session="${escapeHtml(session.session_id)}">${escapeHtml(session.topic || 'General study')}</a><br><small>${escapeHtml(session.subject.replaceAll('_', ' '))} · ${escapeHtml(new Date(session.created_at * 1000).toLocaleDateString())} · ${escapeHtml(session.status)}</small></li>`,
                      )
                      .join('')}</ul>`
                  : '<p class="muted">Your first session starts here. Upload some notes or ask about a concept you want to understand.</p>'
            }
          </sentio-card>
        </section>
        <section>
          <sentio-card title="Learning progress">
            ${
              profile === null
                ? '<p class="muted">Progress is currently unavailable.</p>'
                : `<div class="metric-row"><span>Study streak</span><strong>${escapeHtml(profile.learning_streak || 0)} days</strong></div><div class="metric-row"><span>Estimated mastery</span><strong>${topics.length ? percent(profile.overall_mastery) + '%' : 'Not assessed yet'}</strong></div><p class="muted">Estimates guide review; they are not proof of understanding.</p>${
                    topics.length
                      ? `<ul class="study-list">${topics
                          .slice(0, 5)
                          .map(
                            ([topic, mastery]) =>
                              `<li>${escapeHtml(topic.replaceAll('_', ' '))}<br><progress value="${percent(mastery)}" max="100" aria-label="${escapeHtml(topic)} estimated mastery"></progress> ${percent(mastery)}%</li>`,
                          )
                          .join('')}</ul>`
                      : '<p>Practise a topic to start building your progress.</p>'
                  }`
            }
          </sentio-card>
          <sentio-card title="A workspace that stays yours"><p class="muted">Your documents and learning history stay on this machine. Camera experiments are optional.</p><a class="workspace-action" href="#/settings">Preferences & privacy</a></sentio-card>
        </section>
      </div>`;
    const retry = this.container.querySelector('#retry-dash-btn');
    if (retry) retry.onclick = () => this.loadDashboardData();
    this.container.querySelectorAll('.continue-session').forEach((link) => {
      link.onclick = () => store.setState('activeSessionId', link.dataset.session);
    });
    this.container.querySelectorAll('.recommended-action').forEach((link) => {
      link.onclick = () => {
        if (link.dataset.topic && document.getElementById('f-topic')) {
          document.getElementById('f-topic').value = link.dataset.topic;
        }
      };
    });
  }
}
