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
      }
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
  }

  async loadSessions() {
    try {
      const studentId = store.getState('currentUser')?.id || 'stu_001';
      const res = await sentioAPI.get(`/sessions?student_id=${studentId}`);
      this.sessionsList = res.sessions || [];
      this.renderSessionsList();
    } catch (e) {
      console.warn('Failed to load sessions list:', e);
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
    try {
      toast('Resuming tutoring session...');

      // Update global states inside legacy context
      // Load session details to verify status
      const res = await sentioAPI.get(`/sessions/${sessionId}`);
      store.setState('activeSession', res);
      window.setLegacySessionId(sessionId);

      // Load/refresh grounding options
      const docs = await this.loadGroundingDocuments();
      const groundingSelect = document.getElementById('f-grounding');
      if (groundingSelect) {
        const docId = res.metadata?.document_id || 'none';
        groundingSelect.value = docId;

        // Also attach grounding change listener in resume session
        groundingSelect.onchange = async (e) => {
          const sid = store.getState('activeSessionId');
          if (!sid) return;
          const newDocId = e.target.value;
          try {
            await sentioAPI.post(`/sessions/${sid}/grounding`, { document_id: newDocId });
            toast('Grounding source updated mid-session!');
          } catch (err) {
            toast('Failed to update grounding: ' + err.message, true);
          }
        };
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
    let docs = [];
    try {
      const res = await sentioAPI.get('/documents');
      docs = res.documents || [];
    } catch (e) {
      console.warn('Failed to load documents for grounding dropdown:', e);
    }

    // Repopulate Left Panel select
    const leftSelect = document.getElementById('f-grounding');
    if (leftSelect) {
      const currentVal = leftSelect.value;
      leftSelect.innerHTML = `
        <option value="none">General Tutor (No grounding)</option>
        <option value="all">All My Documents</option>
        ${docs.map((d) => `<option value="${escapeHtml(d.id)}">${escapeHtml(d.filename)}</option>`).join('')}
      `;
      if ([...leftSelect.options].some((o) => o.value === currentVal)) {
        leftSelect.value = currentVal;
      }
    }

    return docs;
  }

  async createNewSessionDialog() {
    const docs = await this.loadGroundingDocuments();
    const modal = document.createElement('sentio-modal');
    modal.setAttribute('title', 'Start New Session');
    modal.innerHTML = `
      <div style="display:flex;flex-direction:column;gap:12px;">
        <div>
          <label for="new-sess-subject" style="display:block;font-size:14px;color:var(--text-dim);margin-bottom:6px;">Subject</label>
<select id="new-sess-subject" style="width:100%;background:var(--bg3);border:1px solid var(--border);border-radius:var(--radius);padding:8px;color:var(--text);font-family:var(--mono);font-size:14px;">
            <option value="mathematics">Mathematics</option>
            <option value="physics">Physics</option>
            <option value="computer_science">Computer Science</option>
            <option value="chemistry">Chemistry</option>
            <option value="biology">Biology</option>
          </select>
        </div>
        <div>
          <label for="new-sess-topic" style="display:block;font-size:14px;color:var(--text-dim);margin-bottom:6px;">Topic</label>
<input type="text" id="new-sess-topic" value="thermodynamics" style="width:100%;background:var(--bg3);border:1px solid var(--border);border-radius:var(--radius);padding:8px;color:var(--text);font-family:var(--mono);font-size:14px;" />
        </div>
        <div>
          <label for="new-sess-difficulty" style="display:block;font-size:14px;color:var(--text-dim);margin-bottom:6px;">Difficulty</label>
<select id="new-sess-difficulty" style="width:100%;background:var(--bg3);border:1px solid var(--border);border-radius:var(--radius);padding:8px;color:var(--text);font-family:var(--mono);font-size:14px;">
            <option value="beginner">Beginner</option>
            <option value="intermediate" selected>Intermediate</option>
            <option value="advanced">Advanced</option>
          </select>
        </div>
        <div>
          <label for="new-sess-grounding" style="display:block;font-size:14px;color:var(--text-dim);margin-bottom:6px;">Grounding Source</label>
<select id="new-sess-grounding" style="width:100%;background:var(--bg3);border:1px solid var(--border);border-radius:var(--radius);padding:8px;color:var(--text);font-family:var(--mono);font-size:14px;">
            <option value="none">General Tutor (No grounding)</option>
            <option value="all">All My Documents</option>
            ${docs.map((d) => `<option value="${escapeHtml(d.id)}">${escapeHtml(d.filename)}</option>`).join('')}
          </select>
        </div>
        <button id="new-sess-submit-btn" style="margin-top:10px;background:var(--accent);color:var(--bg);border:none;padding:10px;border-radius:var(--radius);font-family:var(--mono);font-weight:bold;cursor:pointer;">Start Learning</button>
      </div>
    `;

    document.body.appendChild(modal);

    modal.querySelector('#new-sess-submit-btn').onclick = async () => {
      const subject = modal.querySelector('#new-sess-subject').value;
      const topic = modal.querySelector('#new-sess-topic').value.trim();
      const difficulty = modal.querySelector('#new-sess-difficulty').value;
      const grounding = modal.querySelector('#new-sess-grounding').value;
      const studentId = store.getState('currentUser')?.id || 'stu_001';

      if (!topic) {
        toast('Topic cannot be empty', true);
        return;
      }

      modal.close();
      store.setState('loading', true);
      try {
        document.getElementById('f-subject').value = subject;
        document.getElementById('f-topic').value = topic;
        document.getElementById('f-difficulty').value = difficulty;
        document.getElementById('f-grounding').value = grounding;
        await window.startSession();
      } catch (err) {
        toast('Failed to create session: ' + err.message, true);
      } finally {
        store.setState('loading', false);
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
        await originalStartSession(...args);
        this.loadSessions();
      };
    }

    // Intercept end session
    if (typeof window.endSession === 'function') {
      const originalEndSession = window.endSession;
      window.endSession = async (...args) => {
        await originalEndSession(...args);
        store.setState('activeSessionId', null);
        this.loadSessions();
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
        const score = c.similarity_score ? Math.round(c.similarity_score * 100) : 0;
        const textSnippet = c.text || 'Preview snippet unavailable.';

        return `
        <div class="citation-card" style="border:1px solid var(--border);border-radius:var(--radius);padding:10px;background:var(--bg3);display:flex;flex-direction:column;gap:6px;">
          <div style="display:flex;justify-content:space-between;align-items:center;">
            <span style="font-weight:bold;font-size:14px;color:var(--accent);max-width:140px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${escapeHtml(filename)}">
              📄 ${escapeHtml(filename)}
            </span>
            <span style="font-size:14px;color:var(--text-dim);background:var(--border);padding:2px 4px;border-radius:4px;">
              Score: ${score}%
            </span>
          </div>
          <div style="font-size:14px;color:var(--text-dim);">Page: ${escapeHtml(page)}</div>
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
