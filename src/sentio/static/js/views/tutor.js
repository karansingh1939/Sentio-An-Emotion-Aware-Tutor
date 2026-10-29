import { escapeHtml } from '../core/html.js';
// Tutor View Controller for Sentio (ES Module)
import { sentioAPI } from '../core/api.js';
import { store } from '../core/store.js';
import { toast } from '../components/ui.js';

export class TutorView {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
    this.sessionsList = [];
    this.currentCitations = [];
    this.resumeRevision = 0;
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
      this.currentCitations = [];
      this.renderSessionsList();
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
            <div style="font-weight:bold;font-size:14px;color:${s.session_id === currentSessionId ? 'var(--accent)' : 'var(--text)'};text-transform:capitalize;">${escapeHtml(topicName)}</div>
            <div style="font-size:14px;color:var(--text-dim);text-transform:capitalize;">${escapeHtml(s.subject)} · ${escapeHtml(difficulty)}</div>
          </div>
          <button class="delete-session-btn" data-id="${escapeHtml(s.session_id)}" style="background:none;border:none;color:var(--red);cursor:pointer;font-size:14px;padding:4px;">&times;</button>
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

    // Bind delete
    listContainer.querySelectorAll('.delete-session-btn').forEach((btn) => {
      btn.onclick = async (e) => {
        e.stopPropagation();
        const id = e.target.dataset.id;
        if (confirm('Are you sure you want to delete this session summary?')) {
          try {
            await sentioAPI.delete(`/sessions/${id}`);
            toast('Session deleted.');
            if (store.getState('activeSessionId') === id) {
              // End active tracking if we delete current session
              if (typeof window.endSession === 'function') window.endSession();
            }
            this.loadSessions();
          } catch (err) {
            toast('Delete failed: ' + err.message, true);
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
        barMeta.textContent = `${res.difficulty || 'intermediate'} · ${isGrounded ? 'Document Grounded' : 'General Tutor'}`;
      }

      const welcome = document.getElementById('welcome');
      if (welcome) welcome.style.display = 'none';
      const startBtn = document.getElementById('start-btn');
      if (startBtn) startBtn.style.display = 'none';
      const endBtn = document.getElementById('end-btn');
      if (endBtn) endBtn.style.display = 'inline-block';
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
      toast('Session loaded successfully!');
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
    try {
      const res = await sentioAPI.get('/documents');
      if (!current()) return [];
      docs = res.documents || [];
    } catch (e) {
      if (current()) toast('Notes could not load. Retry from the Library.', true);
      return [];
    }

    // Repopulate Left Panel select
    const leftSelect = document.getElementById('f-grounding');
    if (leftSelect) {
      const currentVal = store.getState('activeSession')?.metadata?.document_id || leftSelect.value;
      leftSelect.innerHTML = `
        <option value="none">General questions (without notes)</option>
        <option value="all">Search all my notes</option>
        ${docs.map((d) => `<option value="${escapeHtml(d.id)}">${escapeHtml(d.filename)}</option>`).join('')}
      `;
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

  async createNewSessionDialog(options = {}) {
    const owner = store.getState('currentUser')?.id;
    const route = store.getState('activeRoute');
    let docs;
    try {
      docs = (await sentioAPI.get('/documents')).documents || [];
    } catch (error) {
      toast('Notes could not load: ' + error.message, true);
      return;
    }
    if (owner !== store.getState('currentUser')?.id || store.getState('activeRoute') !== route)
      return;
    const modal = document.createElement('sentio-modal');
    modal.setAttribute('title', options.documentId ? 'Study these notes' : 'Start studying');
    modal.innerHTML = `
      <div class="stack">
        <p>${options.documentId ? `Using ${escapeHtml(options.document?.filename || 'your selected notes')}.` : 'Choose what you want to understand.'}</p>
        <div>
          <label class="form-label" for="new-sess-subject">Subject</label>
<select class="input" id="new-sess-subject">
            <option value="mathematics">Mathematics</option>
            <option value="physics">Physics</option>
            <option value="computer_science">Computer Science</option>
            <option value="chemistry">Chemistry</option>
            <option value="biology">Biology</option>
            <option value="history">History</option>
            <option value="literature">Literature</option>
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
        <div>
          <label class="form-label" for="new-sess-grounding">Grounding Source</label>
<select class="input" id="new-sess-grounding">
            <option value="none">General questions (without notes)</option>
            <option value="all">Search all my notes</option>
            ${docs.map((d) => `<option value="${escapeHtml(d.id)}">${escapeHtml(d.filename)}</option>`).join('')}
          </select>
        </div>
        <p id="new-sess-error" role="alert"></p>
        <button class="workspace-action primary" id="new-sess-submit-btn">Start studying</button>
      </div>
    `;

    document.body.appendChild(modal);
    if (options.documentId) {
      const source = modal.querySelector('#new-sess-grounding');
      source.value = options.documentId;
      source.disabled = true;
      source.parentElement.hidden = true;
      modal.querySelector('#new-sess-difficulty').parentElement.hidden = true;
      modal.querySelector('#new-sess-topic').value = (options.document?.filename || '')
        .replace(/\.[^.]+$/, '')
        .replace(/[_-]+/g, ' ');
      if (options.document?.subject)
        modal.querySelector('#new-sess-subject').value = options.document.subject;
    }

    modal.querySelector('#new-sess-submit-btn').onclick = async () => {
      const subject = modal.querySelector('#new-sess-subject').value;
      const topic = modal.querySelector('#new-sess-topic').value.trim();
      const difficulty = modal.querySelector('#new-sess-difficulty').value;
      const grounding = modal.querySelector('#new-sess-grounding').value;
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

    // Intercept appendTutorMessage
    if (typeof window.appendTutorMessage === 'function') {
      const originalAppendTutor = window.appendTutorMessage;
      window.appendTutorMessage = (data) => {
        originalAppendTutor(data);
        if (data.source_citations) {
          this.renderCitations(data.source_citations);
        }
      };
    }
  }

  renderCitations(citations) {
    const container = this.container.querySelector('#tutor-citations-container');
    if (!container) return;

    this.currentCitations = citations;

    if (!citations || citations.length === 0) {
      container.innerHTML = `<sentio-empty-state message="No citations retrieved for this response." icon="📄"></sentio-empty-state>`;
      return;
    }

    container.innerHTML = citations
      .map((c, idx) => {
        const filename = c.filename || 'Source Document';
        const page = c.page || 'N/A';
        const textSnippet = c.text || 'Preview snippet unavailable.';

        return `
        <div class="citation-card" style="border:1px solid var(--border);border-radius:var(--radius);padding:10px;background:var(--bg3);display:flex;flex-direction:column;gap:6px;">
          <div class="row-between">
            <span style="font-weight:bold;font-size:14px;color:var(--accent);max-width:140px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${escapeHtml(filename)}">
              📄 ${escapeHtml(filename)}
            </span>
            <span style="font-size:14px;color:var(--text-dim);background:var(--border);padding:2px 4px;border-radius:4px;">
              Page ${escapeHtml(page)}
            </span>
          </div>
          <div class="muted">Page: ${escapeHtml(page)}</div>
          <details style="margin-top:4px;">
            <summary style="font-size:14px;color:var(--accent);cursor:pointer;outline:none;">Preview Source Text</summary>
            <p style="font-size:14px;color:var(--text);margin-top:6px;line-height:1.4;background:var(--bg2);padding:6px;border-radius:4px;border:1px solid var(--border);max-height:140px;overflow-y:auto;white-space:pre-wrap;">${escapeHtml(textSnippet)}</p>
          </details>
        </div>
      `;
      })
      .join('');
  }
}
