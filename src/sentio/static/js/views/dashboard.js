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
      sentioAPI.get(
        `/study/daily-plan?day=${new Date().getFullYear()}-${String(new Date().getMonth() + 1).padStart(2, '0')}-${String(new Date().getDate()).padStart(2, '0')}`,
      ),
      sentioAPI.get('/study/preferences'),
      sentioAPI.get(`/students/${id}/goals`),
    ]);
    if (revision !== this.revision || store.getState('currentUser')?.id !== user.id) return;
    const values = results.map((result) => (result.status === 'fulfilled' ? result.value : null));
    const labels = [
      'Progress',
      'Recommendations',
      'History',
      'System status',
      'Daily plan',
      'Preferences',
      'Goals',
    ];
    const failed = results.flatMap((result, index) =>
      result.status === 'rejected' ? [labels[index]] : [],
    );
    this.plan = values[4];
    this.preferences = values[5];
    this.goals = values[6]?.goals;
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
          <sentio-card title="Daily revision">
            ${this.plan ? `<p>${escapeHtml(this.plan.budget_minutes)} minute budget. Completion is self-reported.</p><ul class="study-list">${this.plan.tasks.map((task) => `<li><label><input type="checkbox" class="plan-complete" data-task="${escapeHtml(task.task_id)}" ${task.completed_at ? 'checked' : ''}> ${escapeHtml(task.title)}</label><br><small>${escapeHtml(task.minutes)} min${task.evidence_count ? ` · ${escapeHtml(task.evidence_count)} saved practice records` : ''}</small> <a class="workspace-action" href="${escapeHtml(task.destination)}">Open</a></li>`).join('')}</ul>` : '<p>Daily plan unavailable. Retry when storage is ready.</p>'}
            ${this.preferences ? `<form id="budget-form"><label for="daily-budget">Budget for new daily plans (minutes)</label><input id="daily-budget" type="number" min="5" max="240" value="${escapeHtml(this.preferences.daily_minutes)}" required><button class="workspace-action" type="submit">Save budget</button></form>` : ''}
            <p id="plan-status" role="status" aria-live="polite"></p>
          </sentio-card>
          <sentio-card title="Exam goals">
            ${this.goals ? `<ul class="study-list">${this.goals.map((goal) => `<li>${escapeHtml(goal.goal_text)}${goal.target_date ? `<br><small>Target: ${escapeHtml(new Date(goal.target_date * 1000).toLocaleDateString())}</small>` : ''}<button type="button" class="workspace-action goal-done" data-goal="${escapeHtml(goal.goal_id)}">Complete goal</button></li>`).join('')}</ul>` : '<p>Goals unavailable.</p>'}
            <form id="goal-form"><label for="goal-text">What do you want to prepare for?</label><input id="goal-text" maxlength="500" required placeholder="Understand mechanics before my exam"><label for="goal-date">Target date (optional)</label><input id="goal-date" type="date"><button class="workspace-action" type="submit">Add goal</button></form>
          </sentio-card>
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
    const owner = store.getState('currentUser')?.id;
    const showStatus = (message) => {
      if (
        store.getState('currentUser')?.id === owner &&
        store.getState('activeRoute') === '#/dashboard'
      )
        this.container.querySelector('#plan-status').textContent = message;
    };
    this.container.querySelectorAll('.plan-complete').forEach((input) => {
      input.onchange = async () => {
        input.disabled = true;
        try {
          await sentioAPI.request(
            `/study/daily-plan/${this.plan.day}/tasks/${input.dataset.task}`,
            { method: 'PATCH', body: JSON.stringify({ completed: input.checked }) },
          );
          showStatus('Task completion saved.');
        } catch (error) {
          input.checked = !input.checked;
          showStatus(error.message);
        } finally {
          input.disabled = false;
        }
      };
    });
    const budget = this.container.querySelector('#budget-form');
    if (budget)
      budget.onsubmit = async (event) => {
        event.preventDefault();
        try {
          await sentioAPI.request('/study/preferences', {
            method: 'PUT',
            body: JSON.stringify({
              daily_minutes: Number(this.container.querySelector('#daily-budget').value),
            }),
          });
          showStatus(
            'Budget saved. Existing daily tasks stay available; new plans use this budget.',
          );
        } catch (error) {
          showStatus(error.message);
        }
      };
    this.container.querySelector('#goal-form').onsubmit = async (event) => {
      event.preventDefault();
      const goalText = this.container.querySelector('#goal-text').value.trim();
      const dateValue = this.container.querySelector('#goal-date').value;
      if (!goalText) return;
      try {
        await sentioAPI.post(`/students/${encodeURIComponent(owner)}/goals`, {
          goal_text: goalText,
          topic_id: store.getState('activeSession')?.topic || null,
          target_date: dateValue ? new Date(dateValue + 'T00:00:00').getTime() / 1000 : null,
        });
        if (
          store.getState('currentUser')?.id === owner &&
          store.getState('activeRoute') === '#/dashboard'
        )
          this.loadDashboardData();
      } catch (error) {
        showStatus(error.message);
      }
    };
    this.container.querySelectorAll('.goal-done').forEach((button) => {
      button.onclick = async () => {
        button.disabled = true;
        try {
          await sentioAPI.request(
            `/students/${encodeURIComponent(owner)}/goals/${button.dataset.goal}`,
            { method: 'PATCH', body: JSON.stringify({ status: 'completed' }) },
          );
          if (
            store.getState('currentUser')?.id === owner &&
            store.getState('activeRoute') === '#/dashboard'
          )
            this.loadDashboardData();
        } catch (error) {
          showStatus(error.message);
          button.disabled = false;
        }
      };
    });
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
