import { MAX_PRACTICE_TOPICS, escapeHtml, pageRange, topicMemory } from '../core/html.js';
import { store } from '../core/store.js';
import { sentioAPI } from '../core/api.js';

// Today: an overview of real progress, what is due, goals and the daily plan.
// Layout reference: docs/design/mockups/today-dark.png. Every figure comes from the API.

const percent = (value) => Math.round(Math.max(0, Math.min(1, Number(value) || 0)) * 100);
const DAY = 86400;
const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`;

function greeting() {
  const hour = new Date().getHours();
  return hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening';
}

function nextGoal(goals) {
  const now = Date.now() / 1000;
  return (goals || [])
    .filter((goal) => goal.target_date && goal.target_date > now)
    .sort((a, b) => a.target_date - b.target_date)[0];
}

// One line of what matters today, built only from real counts.
function statusLine(due, notes, goals) {
  const parts = [
    due
      ? `<span><i class="live-dot"></i>${plural(due, 'topic')} due for review</span>`
      : '<span>Nothing due for review</span>',
  ];
  if (notes !== undefined) parts.push(`<span>${plural(notes, 'lecture')} ready</span>`);
  const next = nextGoal(goals);
  if (next) {
    const days = Math.ceil((next.target_date - Date.now() / 1000) / DAY);
    parts.push(`<span>Next goal in ${plural(days, 'day')}</span>`);
  }
  return parts.join('');
}

const ACTION_LABELS = {
  review_flashcards: 'Review flashcards',
  take_quiz: 'Practise this topic',
  start_tutoring: 'Learn with your tutor',
  review_prerequisites: 'Review the foundations',
  increase_challenge: 'Try a harder question',
};
const DESTINATIONS = { review_flashcards: '#/flashcards', take_quiz: '#/quizzes' };

// Big figure, three sub-figures, the next step, and a ring of topics by strength.
function progressCard(profile, topics, recommendations, noteCount) {
  if (profile === null) return '<p class="muted">Progress is currently unavailable.</p>';
  const buckets = [
    ['Strong', 'var(--green)', topics.filter(([, m]) => m >= 0.8).length],
    ['Building', 'var(--accent)', topics.filter(([, m]) => m >= 0.4 && m < 0.8).length],
    ['Needs review', 'var(--yellow)', topics.filter(([, m]) => m < 0.4).length],
  ];
  const total = topics.length;
  const circumference = 2 * Math.PI * 50;
  let offset = 0;
  const arcs = buckets
    .filter(([, , n]) => n)
    .map(([, color, n], index) => {
      const length = (n / total) * circumference;
      const gap = n < total ? 4 : 0;
      const arc = `<circle cx="60" cy="60" r="50" fill="none" stroke="${color}" stroke-width="10" stroke-linecap="round" stroke-dasharray="${Math.max(0.1, length - gap).toFixed(1)} ${circumference.toFixed(1)}" stroke-dashoffset="${(-offset).toFixed(1)}" transform="rotate(-90 60 60)" data-draw="${index * 120}"/>`;
      offset += length;
      return arc;
    })
    .join('');
  const next = recommendations?.[0];
  const tip = next
    ? `<div class="tip"><span class="tip-icon" aria-hidden="true">→</span><div><div>Your next step</div><p class="muted">${escapeHtml(next.explanation || ACTION_LABELS[next.action] || 'Continue learning')}</p></div><a class="workspace-action primary recommended-action" href="${DESTINATIONS[next.action] || '#/tutor'}" data-topic="${escapeHtml(next.topic_id || next.topic || '')}">${escapeHtml(ACTION_LABELS[next.action] || 'Continue')}</a></div>`
    : recommendations === null
      ? '<p class="muted">Recommendations are currently unavailable.</p>'
      : '<div class="tip"><span class="tip-icon" aria-hidden="true">→</span><div><div>Your next step</div><p class="muted">Begin with a question from your notes.</p></div><a class="workspace-action primary" href="#/documents">Choose notes</a></div>';
  return `
    <div class="progress-layout">
      <div>
        <p class="muted card-sub">From your quizzes and flashcard ratings</p>
        <div class="big-figure">${
          total
            ? `<span data-count="${percent(profile.overall_mastery)}" data-suffix="%">${percent(profile.overall_mastery)}%</span> <span class="big-unit">mastery</span>`
            : '<span class="big-unit">Not assessed yet</span>'
        }</div>
        <div class="trio">
          <div><small>Study streak</small><b><span data-count="${Number(profile.learning_streak) || 0}">${escapeHtml(profile.learning_streak || 0)}</span> days</b></div>
          <div><small>Topics assessed</small><b>${total}</b></div>
          <div><small>Notes ready</small><b>${noteCount ?? '—'}</b></div>
        </div>
        ${tip}
        <p class="muted fine-print">Estimates guide review; they are not proof of understanding.</p>
      </div>
      <div class="ring-block">
        <svg class="ring" viewBox="0 0 120 120" role="img" aria-label="${plural(total, 'topic')}: ${buckets.map(([label, , n]) => `${n} ${label.toLowerCase()}`).join(', ')}">
          <circle cx="60" cy="60" r="50" fill="none" stroke="var(--press)" stroke-width="10"/>
          ${arcs}
          <circle cx="60" cy="60" r="37" fill="var(--bg3)"/>
          <text x="60" y="61" text-anchor="middle" class="ring-value">${total}</text>
          <text x="60" y="75" text-anchor="middle" class="ring-label">topic${total === 1 ? '' : 's'}</text>
        </svg>
        <ul class="legend">${buckets.map(([label, color, n]) => `<li><i style="background:${color}"></i>${label}<b>${n}</b></li>`).join('')}</ul>
      </div>
    </div>`;
}

// Sessions started per day over the chosen range, against the range before it.
function sessionsChart(sessions, days) {
  const now = Date.now() / 1000;
  const bins = (skip) => {
    const out = Array(days).fill(0);
    sessions.forEach((session) => {
      const age = Math.floor((now - session.created_at) / DAY) - skip;
      if (age >= 0 && age < days) out[days - 1 - age] += 1;
    });
    return out;
  };
  const current = bins(0);
  const before = bins(days);
  const total = current.reduce((a, b) => a + b, 0);
  const previous = before.reduce((a, b) => a + b, 0);
  const delta = previous ? Math.round(((total - previous) / previous) * 100) : null;
  const max = Math.max(2, ...current, ...before);
  const point = (value, index) =>
    `${((index / (days - 1)) * 560).toFixed(1)} ${(150 - (value / max) * 120).toFixed(1)}`;
  const line = (values) =>
    values.map((value, index) => `${index ? 'L' : 'M'}${point(value, index)}`).join(' ');
  const range = [
    [7, 'Week'],
    [30, 'Month'],
  ]
    .map(
      ([value, label]) =>
        `<button type="button" class="seg-option" data-days="${value}" aria-pressed="${value === days}">${label}</button>`,
    )
    .join('');
  return `
    <div class="chart-head">
      <p class="muted card-sub">Sessions started per day</p>
      <div class="seg chart-range" role="group" aria-label="Chart range">${range}</div>
    </div>
    <div class="chart-figure"><span class="big-figure" data-count="${total}">${total}</span>${
      delta === null
        ? ''
        : `<span class="delta ${delta >= 0 ? 'up' : 'down'}">${delta >= 0 ? '+' : ''}${delta}%</span>`
    }<span class="muted">${delta === null ? `sessions in the last ${days} days` : `vs the ${days} days before`}</span></div>
    <svg class="area-chart" viewBox="0 0 560 160" preserveAspectRatio="none" role="img" aria-label="${plural(total, 'session')} in the last ${days} days">
      <defs><linearGradient id="area-fill" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#4d80ff" stop-opacity="0.3"/><stop offset="1" stop-color="#4d80ff" stop-opacity="0"/></linearGradient></defs>
      <g class="grid-lines"><line x1="0" x2="560" y1="30" y2="30"/><line x1="0" x2="560" y1="90" y2="90"/><line x1="0" x2="560" y1="150" y2="150"/></g>
      <path d="${line(current)} L560 160 L0 160Z" fill="url(#area-fill)" class="area"/>
      ${previous ? `<path d="${line(before)}" class="line-before" fill="none"/>` : ''}
      <path d="${line(current)}" class="line-now" fill="none" vector-effect="non-scaling-stroke" data-draw="0"/>
    </svg>
    <div class="chart-legend muted"><span><i class="swatch now"></i>This period</span>${previous ? '<span><i class="swatch before"></i>The period before</span>' : ''}</div>`;
}

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

function dueTable(topics) {
  if (!topics.length)
    return '<p class="muted card-sub">Nothing is due. Topics appear here once you have probably started to forget them.</p>';
  const rows = topics
    .slice(0, MAX_PRACTICE_TOPICS)
    .map(
      (topic) => `<tr>
        <td><span class="topic-cell"><span class="tile ${tileClass(topic.filename)}" aria-hidden="true">${escapeHtml(initials(topic.filename))}</span>${escapeHtml(topic.title)}</span></td>
        <td class="muted">${escapeHtml(topic.filename)} · ${escapeHtml(pageRange(topic))}</td>
        <td><span class="topic-state review_due">${escapeHtml(topicMemory(topic) || 'Review due')}</span></td>
        <td class="row-action"><button type="button" class="workspace-action pill review-topic" data-topic="${escapeHtml(topic.id)}">Review</button></td>
      </tr>`,
    )
    .join('');
  return `
    <p class="muted card-sub">You have probably started to forget these. A short quiz keeps them fresh.</p>
    <div class="table-scroll"><table class="due-table">
      <thead><tr><th>Topic</th><th>Notes</th><th>Memory</th><th><span class="visually-hidden">Action</span></th></tr></thead>
      <tbody>${rows}</tbody>
    </table></div>
    <button id="practise-due-btn" class="workspace-action primary">Practise all due topics</button>`;
}

function goalCountdown(goals) {
  const next = nextGoal(goals);
  if (!next) return '';
  const left = Math.max(0, next.target_date - Date.now() / 1000);
  const tiles = [
    [Math.floor(left / DAY), 'Days'],
    [Math.floor((left % DAY) / 3600), 'Hrs'],
    [Math.floor((left % 3600) / 60), 'Min'],
  ];
  return `
    <div class="goal-head"><p class="muted">Next goal</p><strong>${escapeHtml(next.goal_text)}</strong></div>
    <div class="countdown">${tiles.map(([value, label]) => `<div><b>${String(value).padStart(2, '0')}</b><small>${label}</small></div>`).join('')}</div>`;
}

function dailyPlan(plan) {
  if (!plan) return '<p>Daily plan unavailable. Retry when storage is ready.</p>';
  const done = plan.tasks
    .filter((task) => task.completed_at)
    .reduce((sum, task) => sum + (Number(task.minutes) || 0), 0);
  const budget = Number(plan.budget_minutes) || 0;
  const share = budget ? Math.min(100, Math.round((done / budget) * 100)) : 0;
  return `
    <div class="plan-meter"><span class="muted">${escapeHtml(plan.budget_minutes)} minute budget. Completion is self-reported.</span><b>${done} of ${budget} min</b></div>
    <div class="meter" role="img" aria-label="${done} of ${budget} minutes done"><i style="width:${share}%"></i></div>
    <ul class="study-list plan-list">${plan.tasks.map((task) => `<li><label><input type="checkbox" class="plan-complete" data-task="${escapeHtml(task.task_id)}" ${task.completed_at ? 'checked' : ''}> ${escapeHtml(task.title)}</label><small>${escapeHtml(task.minutes)} min${task.evidence_count ? ` · ${escapeHtml(task.evidence_count)} saved practice records` : ''}</small><a class="workspace-action" href="${escapeHtml(task.destination)}">Open</a></li>`).join('')}</ul>`;
}

export class TodayView {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
    this.revision = 0;
    this.chartDays = 30;
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
      sentioAPI.get('/documents'),
      sentioAPI.get('/topics/due'),
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
      'Library',
      'Topics due',
    ];
    const failed = results.flatMap((result, index) =>
      result.status === 'rejected' ? [labels[index]] : [],
    );
    this.plan = values[4];
    this.preferences = values[5];
    this.goals = values[6]?.goals;
    this.noteCount = values[7]?.documents?.filter((item) => item.status === 'indexed').length;
    this.dueTopics = values[8]?.topics || [];
    this.data = [values[0], values[1], values[2]?.sessions, values[3], failed];
    this.render(...this.data);
  }

  // Topics from several lectures study all notes; the quiz still uses only their slides.
  async practiseDue(chosen = this.dueTopics) {
    const owner = store.getState('currentUser')?.id;
    const topics = chosen.slice(0, MAX_PRACTICE_TOPICS);
    if (!topics.length) return;
    const documents = new Set(topics.map((topic) => topic.document_id));
    const started = await window.startSession({
      difficulty: 'beginner',
      subject: 'My notes',
      topic: topics
        .map((topic) => topic.title)
        .join('; ')
        .slice(0, 150),
      documentId: documents.size === 1 ? topics[0].document_id : 'all',
      topicIds: topics.map((topic) => topic.id),
      isCurrent: () => owner === store.getState('currentUser')?.id,
    });
    if (started) window.location.hash = '#/quizzes';
  }

  render(profile, recommendations, sessions, ready, failed) {
    const activeId = store.getState('activeSessionId');
    const topics = Object.entries(profile?.topic_mastery || {});
    this.container.innerHTML = `
      <div class="today-heading view-header">
        <div>
          <h2>${greeting()}</h2>
          <p class="status-line">${statusLine(this.dueTopics.length, this.noteCount, this.goals)}</p>
        </div>
        <div class="btn-row">
          <a class="workspace-action" href="#/history">Study history</a>
          <a class="workspace-action primary" href="${activeId ? '#/tutor' : '#/documents'}">${activeId ? 'Continue studying' : this.noteCount ? 'Choose notes to study' : 'Add your first notes'}</a>
        </div>
      </div>
      ${failed.length ? `<div id="dashboard-errors" class="notice error" role="alert">${escapeHtml(failed.join(', '))} unavailable. Your saved work is unchanged. <button id="retry-dash-btn" class="workspace-action">Retry</button></div>` : ''}
      ${ready && !ready.ai.ready ? `<div class="notice" role="status"><strong>Your local tutor needs attention.</strong><br>${escapeHtml(ready.ai.action)} You can still browse notes and saved practice.</div>` : ''}
      <div class="today-grid today-top">
        <sentio-card title="Learning progress" class="progress-card">${progressCard(profile, topics, recommendations, this.noteCount)}</sentio-card>
        <sentio-card title="Study sessions" class="sessions-card">${
          sessions === undefined
            ? '<p class="muted">Study history is currently unavailable.</p>'
            : sessionsChart(sessions || [], this.chartDays)
        }</sentio-card>
      </div>
      <div class="today-grid today-mid">
        <sentio-card title="Topics due for review" class="due-card">${dueTable(this.dueTopics)}</sentio-card>
        <div class="today-side">
          <sentio-card title="Exam goals" class="goal-card">
            ${goalCountdown(this.goals)}
            ${this.goals ? `<ul class="study-list goal-list">${this.goals.map((goal) => `<li><span>${escapeHtml(goal.goal_text)}${goal.target_date ? `<br><small>Target: ${escapeHtml(new Date(goal.target_date * 1000).toLocaleDateString())}</small>` : ''}</span><button type="button" class="workspace-action goal-done" data-goal="${escapeHtml(goal.goal_id)}">Complete goal</button></li>`).join('')}</ul>` : '<p>Goals unavailable.</p>'}
            <form id="goal-form" class="inline-form"><label for="goal-text">What do you want to prepare for?</label><input id="goal-text" maxlength="500" required placeholder="Understand mechanics before my exam"><label for="goal-date">Target date (optional)</label><input id="goal-date" type="date"><button class="workspace-action" type="submit">Add goal</button></form>
          </sentio-card>
          <sentio-card title="Daily revision" class="plan-card">
            ${dailyPlan(this.plan)}
            ${this.preferences ? `<form id="budget-form" class="inline-form"><label for="daily-budget">Budget for new daily plans (minutes)</label><div class="btn-row"><input id="daily-budget" type="number" min="5" max="240" value="${escapeHtml(this.preferences.daily_minutes)}" required><button class="workspace-action" type="submit">Save budget</button></div></form>` : ''}
            <p id="plan-status" role="status" aria-live="polite"></p>
          </sentio-card>
        </div>
      </div>
      <div class="today-grid today-low">
        <section class="study-guide card" aria-labelledby="study-guide-title">
          <h3 id="study-guide-title">Your study path</h3>
          <ol><li><a href="#/documents">Add notes</a><span>Upload a PDF, Word document or text file. Wait for “Ready to study”.</span></li><li><a href="#/documents">Study a concept</a><span>Choose Study beside your notes, then ask a question. Check the cited passage.</span></li><li><a href="${activeId ? '#/quizzes' : '#/documents'}">Practice and review</a><span>After starting study, make a quiz or cards. Saved practice stays available.</span></li></ol>
        </section>
        <sentio-card title="Recent study">${
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
        }</sentio-card>
        <sentio-card title="A workspace that stays yours"><p class="muted">Your documents and learning history stay on this machine. Camera experiments are optional.</p><a class="workspace-action" href="#/settings">Preferences & privacy</a></sentio-card>
      </div>`;
    this.bind(sessions);
  }

  bind(sessions) {
    // The Review tab shows a dot while topics are due.
    document
      .querySelector('#sidebar .nav-link[href="#/quizzes"]')
      ?.classList.toggle('has-news', this.dueTopics.length > 0);
    const retry = this.container.querySelector('#retry-dash-btn');
    if (retry) retry.onclick = () => this.loadDashboardData();
    const practiseDue = this.container.querySelector('#practise-due-btn');
    if (practiseDue) practiseDue.onclick = () => this.practiseDue();
    this.container.querySelectorAll('.review-topic').forEach((button) => {
      button.onclick = () =>
        this.practiseDue(this.dueTopics.filter((topic) => topic.id === button.dataset.topic));
    });
    const chartRange = () =>
      this.container.querySelectorAll('.chart-range button').forEach((button) => {
        button.onclick = () => {
          this.chartDays = Number(button.dataset.days);
          const body = this.container.querySelector('.sessions-card .card-content');
          if (!body) return;
          body.innerHTML = sessionsChart(sessions || [], this.chartDays);
          chartRange();
          window.sentioMotion?.drawStrokes(body);
          window.sentioMotion?.countUp(body);
        };
      });
    chartRange();
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
