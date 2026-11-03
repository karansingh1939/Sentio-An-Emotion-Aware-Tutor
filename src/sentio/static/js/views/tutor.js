import { escapeHtml } from '../core/html.js';
// Tutor View Controller for Sentio (ES Module)
import { sentioAPI } from '../core/api.js';
import { store } from '../core/store.js';
import { toast } from '../components/ui.js';
import { runPracticeJob } from '../core/jobs.js';

// Options for "study from": all notes, each course (with lectures added later) and each lecture.
// An old session saved without notes keeps a disabled entry so its state is visible.
function sourceOptions(docs, courses, selected) {
  const option = (value, label) =>
    `<option value="${escapeHtml(value)}" ${value === selected ? 'selected' : ''}>${escapeHtml(label)}</option>`;
  return [
    selected === 'none'
      ? '<option value="none" disabled selected>Not linked to notes</option>'
      : '',
    option('all', 'Search all my notes'),
    ...courses.map((course) => option(`course:${course.id}`, `Course: ${course.name}`)),
    ...docs.map((doc) => option(doc.id, doc.filename)),
  ].join('');
}

export class TutorView {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
    this.sessionsList = [];
    this.resumeRevision = 0;
    this.overviewRevision = 0;
    this.sessionListRevision = 0;
    this.documentListRevision = 0;
    this.goalListRevision = 0;
  }

  init() {
    // Listen to route changes
    store.subscribe('activeRoute', (route) => {
      if (route === '#/tutor') {
        this.setupLayout();
        this.loadSessions();
        this.interceptLegacy();

        const activeSid = store.getState('activeSessionId');
        if (activeSid && window.sessionId !== activeSid) {
          this.resumeSession(activeSid);
        }
      } else {
        this.resumeRevision++;
        this.sessionListRevision++;
        this.documentListRevision++;
        window.stopGeneration?.();
      }
    });
    store.subscribe('currentUser', () => {
      this.sessionListRevision++;
      this.documentListRevision++;
      this.sessionsList = [];
      this.renderSessionsList();
    });
    store.subscribe('activeSession', (session) => this.renderOverview(session));
  }

  // Studying one document shows its overview, or offers to write one.
  async renderOverview(session) {
    const panel = document.getElementById('notes-overview');
    if (!panel) return;
    const revision = ++this.overviewRevision;
    const documentId = session?.metadata?.document_id;
    if (
      typeof documentId !== 'string' ||
      ['none', 'all'].includes(documentId) ||
      documentId.startsWith('course:')
    ) {
      panel.hidden = true;
      panel.innerHTML = '';
      return;
    }
    const path = `/documents/${encodeURIComponent(documentId)}/overview`;
    try {
      const { overview } = await sentioAPI.get(path);
      if (revision !== this.overviewRevision) return;
      panel.hidden = false;
      if (overview) return this.showOverview(panel, overview);
      panel.innerHTML = `<div class="btn-row"><button type="button" class="workspace-action" id="make-overview-btn">Summarize these notes</button><span class="muted">A short summary, key concepts and questions to ask.</span></div>`;
      panel.querySelector('#make-overview-btn').onclick = async () => {
        const result = await runPracticeJob(`${path}/jobs`, {}, panel, { sessionScoped: false });
        if (revision === this.overviewRevision && result) this.showOverview(panel, result);
      };
    } catch {
      if (revision === this.overviewRevision) panel.hidden = true;
    }
  }

  showOverview(panel, overview) {
    panel.innerHTML = `<details open>
      <summary><strong>Overview of these notes</strong></summary>
      <p>${escapeHtml(overview.summary)}</p>
      <div class="source-row">${overview.key_concepts.map((concept) => `<span class="badge">${escapeHtml(concept)}</span>`).join('')}</div>
      <p class="muted">Ask about:</p>
      <div class="btn-row">${overview.suggested_questions.map((question) => `<button type="button" class="workspace-action suggested-question">${escapeHtml(question)}</button>`).join('')}</div>
      </details>`;
    panel.querySelectorAll('.suggested-question').forEach((button) => {
      button.onclick = () => {
        const input = document.getElementById('msg-input');
        if (!input || input.disabled) return;
        input.value = button.textContent;
        panel.querySelector('details').open = false;
        window.sendMessage();
      };
    });
  }

  // Restructure the workspace to bind HUD controls and populate dynamic lists
  setupLayout() {
    this.container.style.display = 'flex';
    this.container.style.flexDirection = 'row';
    this.container.style.height = '100%';
    this.container.style.width = '100%';
    this.container.style.padding = '0';
    this.container.style.overflow = 'hidden';

    // Global toggle for HUD drawer
    window.toggleHudDrawer = () => {
      const drawer = document.getElementById('tutor-hud-drawer');
      const btn = document.getElementById('hud-toggle-btn');
      if (drawer) {
        drawer.classList.toggle('open');
        if (btn) {
          if (drawer.classList.contains('open')) btn.classList.add('active');
          else btn.classList.remove('active');
        }
      }
    };

    // Global tab switcher for HUD drawer
    window.switchDrawerTab = (tabId) => {
      document.querySelectorAll('.drawer-tab').forEach((t) => {
        if (t.dataset.tab === tabId) t.classList.add('active');
        else t.classList.remove('active');
      });
      document.querySelectorAll('.drawer-tab-content').forEach((c) => {
        if (c.id === tabId) c.classList.add('active');
        else c.classList.remove('active');
      });
    };

    // Bind new session click in drawer
    const newBtn = this.container.querySelector('#tutor-new-session-btn');
    if (newBtn) {
      newBtn.onclick = () => this.createNewSessionDialog();
    }

    if (typeof window.initBars === 'function') {
      window.initBars();
    }

    const currentUser = store.getState('currentUser');
    if (currentUser && document.getElementById('f-student')) {
      document.getElementById('f-student').value = currentUser.id;
    }

    this.loadGroundingDocuments();
    this.loadSessionGoals();
  }

  async loadSessions() {
    const revision = ++this.sessionListRevision;
    const owner = store.getState('currentUser')?.id;
    const current = () =>
      revision === this.sessionListRevision &&
      owner === store.getState('currentUser')?.id &&
      store.getState('activeRoute') === '#/tutor';
    if (!owner) return;
    try {
      const studentId = owner;
      const res = await sentioAPI.get(`/sessions?student_id=${studentId}`);
      if (!current()) return;
      this.sessionsList = res.sessions || [];
      this.renderSessionsList();
    } catch (e) {
      if (!current()) return;
      const target = this.container.querySelector('#tutor-sessions-container');
      if (target) {
        target.innerHTML =
          '<p role="alert">Sessions could not load.</p><button id="retry-sessions">Retry</button>';
        target.querySelector('#retry-sessions').onclick = () => this.loadSessions();
      }
    }
  }

  renderSessionsList() {
    const listContainer = this.container.querySelector('#tutor-sessions-container');
    if (!listContainer) return;

    if (this.sessionsList.length === 0) {
      listContainer.innerHTML = `<span style="font-size:14px;color:var(--text-dim);text-align:center;padding:12px 0;">No sessions</span>`;
      return;
    }

    const currentSessionId = store.getState('activeSessionId');

    listContainer.innerHTML = this.sessionsList
      .map((s) => {
        const activeClass = s.session_id === currentSessionId ? 'active' : '';
        const topicName = s.topic ? s.topic.replace(/_/g, ' ') : 'General';
        const difficulty = s.difficulty || 'intermediate';

        return `
        <div class="session-item-row ${activeClass}" data-id="${escapeHtml(s.session_id)}" style="display:flex;justify-content:space-between;align-items:center;padding:8px 10px;border-radius:var(--radius);border:1px solid ${s.session_id === currentSessionId ? 'var(--border-glow)' : 'transparent'};background:${s.session_id === currentSessionId ? 'var(--bg3)' : 'transparent'};cursor:pointer;transition:background 0.2s;">
          <div class="select-session-btn" data-id="${escapeHtml(s.session_id)}" style="display:flex;flex-direction:column;gap:2px;flex:1;">
            <div style="font-weight:bold;font-size:14px;color:${s.session_id === currentSessionId ? 'var(--accent)' : 'var(--text)'};">${escapeHtml(topicName)}</div>
            <div style="font-size:14px;color:var(--text-dim);">${escapeHtml(s.subject)} · ${escapeHtml(difficulty.charAt(0).toUpperCase() + difficulty.slice(1))}</div>
          </div>
          ${s.status === 'active' ? `<button class="delete-session-btn" data-id="${escapeHtml(s.session_id)}" title="End session" aria-label="End session" style="background:none;border:none;color:var(--red);cursor:pointer;font-size:14px;padding:4px;">&times;</button>` : ''}
        </div>
      `;
      })
      .join('');

    // Bind selection
    listContainer.querySelectorAll('.select-session-btn').forEach((btn) => {
      btn.onclick = (e) => {
        const id = e.currentTarget.dataset.id;
        this.resumeSession(id);
      };
    });

    // Bind end (DELETE closes the session; it stays in the list and can be resumed)
    listContainer.querySelectorAll('.delete-session-btn').forEach((btn) => {
      btn.onclick = async (e) => {
        e.stopPropagation();
        const id = e.currentTarget.dataset.id;
        if (confirm('End this session? You can resume it later from this list.')) {
          try {
            await sentioAPI.delete(`/sessions/${id}`);
            toast('Session ended.');
            if (store.getState('activeSessionId') === id) {
              // Stop active tracking if the current session ended
              if (typeof window.endSession === 'function') window.endSession();
            }
            this.loadSessions();
          } catch (err) {
            toast('Could not end the session: ' + err.message, true);
          }
        }
      };
    });
  }

  async resumeSession(sessionId) {
    const revision = ++this.resumeRevision;
    const owner = store.getState('currentUser')?.id;
    const current = () =>
      revision === this.resumeRevision &&
      store.getState('currentUser')?.id === owner &&
      store.getState('activeRoute') === '#/tutor';
    await window.stopGeneration?.();
    try {
      toast('Resuming tutoring session...');

      // Update global states inside legacy context
      // Load session details to verify status
      let res = await sentioAPI.get(`/sessions/${sessionId}`);
      if (!current()) return;
      if (res.status !== 'active') {
        await sentioAPI.post(`/sessions/${sessionId}/resume`, {});
        if (!current()) return;
        res = await sentioAPI.get(`/sessions/${sessionId}`);
        if (!current()) return;
      }
      store.setState('activeSession', res);
      window.setLegacySessionId(sessionId);

      // Load/refresh grounding options
      const docs = await this.loadGroundingDocuments();
      if (!current()) return;
      const groundingSelect = document.getElementById('f-grounding');
      if (groundingSelect) {
        const docId = res.metadata?.document_id || 'none';
        groundingSelect.value = docId;

        // Also attach grounding change listener in resume session
        groundingSelect.onchange = (event) => window.updateGrounding(event.target.value);
      }
      await this.loadSessionGoals();
      if (!current()) return;
      const goalSelect = document.getElementById('f-goal');
      if (goalSelect) {
        goalSelect.value = res.metadata?.goal_id || '';
        goalSelect.onchange = (event) => window.updateSessionGoal(event.target.value);
      }

      // Update UI elements for active session
      const setupCard = document.getElementById('session-setup-card');
      if (setupCard) setupCard.style.display = 'none';
      const activeBar = document.getElementById('session-active-bar');
      if (activeBar) activeBar.style.display = 'flex';
      const barTopic = document.getElementById('active-bar-topic');
      if (barTopic)
        barTopic.textContent = `${res.subject || 'Tutoring'} · ${res.topic || 'Session'}`;
      const barMeta = document.getElementById('active-bar-meta');
      if (barMeta) {
        const isGrounded = res.metadata?.document_id && res.metadata.document_id !== 'none';
        barMeta.textContent = `${res.difficulty || 'intermediate'} · ${isGrounded ? 'From your notes' : 'Not linked to notes'}`;
      }

      const welcome = document.getElementById('welcome');
      if (welcome) welcome.style.display = 'none';
      const startBtn = document.getElementById('start-btn');
      if (startBtn) startBtn.style.display = 'none';
      const endBtn = document.getElementById('end-btn');
      if (endBtn) endBtn.style.display = 'inline-flex';
      const msgInput = document.getElementById('msg-input');
      if (msgInput) {
        msgInput.disabled = false;
        msgInput.placeholder =
          'Ask your tutor anything... (Enter to send, Shift+Enter for newline)';
        msgInput.focus();
      }
      const sendBtn = document.getElementById('send-btn');
      if (sendBtn) sendBtn.disabled = false;
      const camQuick = document.getElementById('cam-quick-toggle-btn');
      if (camQuick) camQuick.disabled = false;
      const micBtn = document.getElementById('mic-btn');
      if (micBtn) micBtn.disabled = false;
      const connDot = document.getElementById('conn-dot');
      if (connDot) connDot.className = 'dot live';
      const connLabel = document.getElementById('conn-label');
      if (connLabel) connLabel.textContent = 'Session active';
      const sessionLabel = document.getElementById('session-label');
      if (sessionLabel) sessionLabel.textContent = 'ID: ' + sessionId.slice(0, 8) + '…';
      const camNoSession = document.getElementById('cam-no-session');
      if (camNoSession) camNoSession.style.display = 'none';

      // Clear legacy message lists
      const chatMessages = document.getElementById('chat-messages');
      if (chatMessages) {
        chatMessages.querySelectorAll('.msg').forEach((m) => m.remove());
        const saved = await sentioAPI.get(`/sessions/${sessionId}/turns`);
        if (!current() || store.getState('activeSessionId') !== sessionId) return;
        for (const turn of saved.turns) {
          window.appendMessage?.('student', turn.message);
          window.appendTutorMessage?.(turn.response);
        }
      }

      // Synchronize live Learning State panel, duration timer, and exchange counter
      if (typeof window.updateStatePanel === 'function') {
        const resumeData = {
          learning_state: res.learning_state || 'neutral',
          detected_emotion: res.dominant_state || 'neutral',
          strategy: res.strategy || 'standard',
          difficulty: res.difficulty || 'beginner',
          engagement_score: typeof res.engagement_score === 'number' ? res.engagement_score : 0.5,
          emotion_confidence: null,
          emotion_scores: {},
          total_exchanges: typeof res.total_exchanges === 'number' ? res.total_exchanges : 0,
          duration_minutes: res.duration_minutes || 0,
          topics_covered: res.topics_covered || [],
        };
        if (typeof window.setExchangeCount === 'function') {
          window.setExchangeCount(resumeData.total_exchanges);
        }
        window.updateStatePanel(resumeData);
      }

      if (typeof window.startDurationTimer === 'function') {
        window.startDurationTimer(res.duration_minutes || 0);
      }

      this.loadSessions();
      toast('Session loaded');
    } catch (e) {
      toast('Failed to resume session: ' + e.message, true);
    }
  }

  async loadGroundingDocuments() {
    const revision = ++this.documentListRevision;
    const owner = store.getState('currentUser')?.id;
    const current = () =>
      revision === this.documentListRevision &&
      owner === store.getState('currentUser')?.id &&
      store.getState('activeRoute') === '#/tutor';
    let docs = [];
    let courses = [];
    try {
      const [res, courseList] = await Promise.all([
        sentioAPI.get('/documents'),
        sentioAPI.get('/courses'),
      ]);
      if (!current()) return [];
      docs = res.documents || [];
      courses = courseList.courses || [];
    } catch (e) {
      if (current()) toast('Notes could not load. Retry from the Library.', true);
      return [];
    }

    // Repopulate Left Panel select
    const leftSelect = document.getElementById('f-grounding');
    if (leftSelect) {
      const currentVal = store.getState('activeSession')?.metadata?.document_id || leftSelect.value;
      leftSelect.innerHTML = sourceOptions(docs, courses, currentVal);
      if ([...leftSelect.options].some((o) => o.value === currentVal)) {
        leftSelect.value = currentVal;
      }
    }

    return docs;
  }

  async loadSessionGoals() {
    const revision = ++this.goalListRevision;
    const owner = store.getState('currentUser')?.id;
    const current = () =>
      revision === this.goalListRevision &&
      owner === store.getState('currentUser')?.id &&
      store.getState('activeRoute') === '#/tutor';
    if (!owner) return [];
    let goals = [];
    try {
      const res = await sentioAPI.get(`/students/${encodeURIComponent(owner)}/goals`);
      if (!current()) return [];
      goals = res.goals || [];
    } catch (e) {
      if (current()) toast('Goals could not load. Add or retry them from Today.', true);
      return [];
    }
    const select = document.getElementById('f-goal');
    if (select) {
      const currentVal = store.getState('activeSession')?.metadata?.goal_id || select.value;
      select.innerHTML = `
        <option value="">No goal</option>
        ${goals.map((g) => `<option value="${escapeHtml(g.goal_id)}">${escapeHtml(g.goal_text)}</option>`).join('')}
      `;
      if ([...select.options].some((o) => o.value === currentVal)) select.value = currentVal;
    }
    return goals;
  }

  async createNewSessionDialog() {
    const owner = store.getState('currentUser')?.id;
    const route = store.getState('activeRoute');
    let docs;
    let courses;
    try {
      const [res, courseList] = await Promise.all([
        sentioAPI.get('/documents'),
        sentioAPI.get('/courses'),
      ]);
      docs = res.documents || [];
      courses = courseList.courses || [];
    } catch (error) {
      toast('Notes could not load: ' + error.message, true);
      return;
    }
    if (owner !== store.getState('currentUser')?.id || store.getState('activeRoute') !== route)
      return;
    const modal = document.createElement('sentio-modal');
    modal.setAttribute('title', 'Start studying');
    modal.innerHTML = `
      <div class="stack">
        <p>Choose what you want to understand.</p>
        ${docs.length ? '' : '<p class="notice">Add your notes in the Library first: every answer comes from them.</p>'}
        <div>
          <label class="form-label" for="new-sess-grounding">Study from</label>
<select class="input" id="new-sess-grounding" ${docs.length ? '' : 'disabled'}>
            ${sourceOptions(docs, courses, 'all')}
          </select>
        </div>
        <div>
          <label class="form-label" for="new-sess-topic">Topic</label>
<input class="input" type="text" id="new-sess-topic" placeholder="What would you like to study?" />
        </div>
        <div>
          <label class="form-label" for="new-sess-difficulty">Difficulty</label>
<select class="input" id="new-sess-difficulty">
            <option value="beginner" selected>Beginner</option>
            <option value="intermediate">Intermediate</option>
            <option value="advanced">Advanced</option>
          </select>
        </div>
        <p id="new-sess-error" role="alert"></p>
        <button class="workspace-action primary" id="new-sess-submit-btn" ${docs.length ? '' : 'disabled'}>Start studying</button>
      </div>
    `;

    document.body.appendChild(modal);

    modal.querySelector('#new-sess-submit-btn').onclick = async () => {
      const source = modal.querySelector('#new-sess-grounding');
      const grounding = source.value;
      // The session label is what the learner studies from: a course, a lecture or all notes.
      const subject =
        grounding === 'all'
          ? 'My notes'
          : source.selectedOptions[0].textContent.replace(/^Course: /, '').trim();
      const topic = modal.querySelector('#new-sess-topic').value.trim();
      const difficulty = modal.querySelector('#new-sess-difficulty').value;
      if (owner !== store.getState('currentUser')?.id || route !== store.getState('activeRoute'))
        return;

      if (!topic) {
        toast('Topic cannot be empty', true);
        return;
      }

      const button = modal.querySelector('#new-sess-submit-btn');
      if (button.disabled) return;
      button.disabled = true;
      store.setState('loading', true);
      try {
        const result = await window.startSession({
          subject,
          topic,
          difficulty,
          documentId: grounding,
          isCurrent: () => modal.isConnected,
        });
        if (
          !modal.isConnected ||
          owner !== store.getState('currentUser')?.id ||
          route !== store.getState('activeRoute')
        )
          return;
        if (!result) {
          modal.querySelector('#new-sess-error').textContent =
            'Could not start studying. Check the message and try again.';
          return;
        }
        modal.close();
        window.location.hash = '#/tutor';
      } catch (err) {
        toast('Failed to create session: ' + err.message, true);
      } finally {
        button.disabled = false;
        if (owner === store.getState('currentUser')?.id) store.setState('loading', false);
      }
    };
  }

  // Intercept the legacy appends to display citations inside the new right sidebar
  interceptLegacy() {
    if (this.isIntercepted) return;
    this.isIntercepted = true;

    // Intercept start session
    if (typeof window.startSession === 'function') {
      const originalStartSession = window.startSession;
      window.startSession = async (...args) => {
        const result = await originalStartSession(...args);
        this.loadSessions();
        return result;
      };
    }

    // Intercept end session
    if (typeof window.endSession === 'function') {
      const originalEndSession = window.endSession;
      window.endSession = async (...args) => {
        const result = await originalEndSession(...args);
        this.loadSessions();
        return result;
      };
    }
  }
}
