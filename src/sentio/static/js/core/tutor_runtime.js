const API = `${window.location.origin}/api/v1`;

// ── STATE ───────────────────────────────────
let sessionId = null;
let wsEmotion = null;
let camStream = null;
let cameraEpoch = 0;
let cameraStarting = false;
let camInterval = null;
let durationTimer = null;
let sessionStart = null;
let exchangeCount = 0;
let generationInProgress = false;
let generationRequest = null;
let sessionStartingFor = null;

function getActiveSessionId() {
  if (window.store) return window.store.getState('activeSessionId');
  return (
    sessionId ||
    window.sessionId ||
    (window.store && typeof window.store.getState === 'function'
      ? window.store.getState('activeSessionId')
      : null)
  );
}

window.setLegacySessionId = function (id) {
  sessionId = id;
  window.sessionId = id;
  if (window.store && typeof window.store.setState === 'function') {
    window.store.setState('activeSessionId', id);
  }
};

function getAuthHeaders() {
  const headers = { 'Content-Type': 'application/json' };
  const token =
    window.store && typeof window.store.getState === 'function'
      ? window.store.getState('authToken')
      : localStorage.getItem('sentio_token');
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

// Emotion meta
const EMOTIONS = ['angry', 'disgusted', 'fearful', 'happy', 'neutral', 'sad', 'surprised'];
const EMOTION_EMOJI = {
  angry: '😠',
  disgusted: '🤢',
  fearful: '😨',
  happy: '😊',
  neutral: '😐',
  sad: '😢',
  surprised: '😮',
};
const STATE_COLOR = {
  engaged: 'var(--engaged)',
  curious: 'var(--curious)',
  neutral: 'var(--neutral)',
  struggling: 'var(--struggling)',
  anxious: 'var(--anxious)',
  frustrated: 'var(--frustrated)',
  disengaged: 'var(--disengaged)',
};
const STRATEGY_LABEL = {
  challenge: '🚀 Challenge',
  standard: '📖 Standard',
  explore: '🔭 Explore',
  simplify: '🧩 Simplify',
  reassure: '💚 Reassure',
  reframe: '🔄 Reframe',
  motivate: '⚡ Motivate',
};

// ── INIT BARS ────────────────────────────────
function initBars() {
  const c = document.getElementById('bars-container');
  if (!c) return;
  c.innerHTML = '';
  EMOTIONS.forEach((em) => {
    c.innerHTML += `
      <div class="ebar-row">
        <div class="ebar-label">${em}</div>
        <div class="ebar-track"><div class="ebar-fill" id="bar-${em}" style="width:0%"></div></div>
        <div class="ebar-pct" id="barpct-${em}">--</div>
      </div>`;
  });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initBars);
} else {
  initBars();
}
window.initBars = initBars;

// ── SESSION MANAGEMENT ───────────────────────
async function startSession(options = {}) {
  const studentId = window.store?.getState('currentUser')?.id;
  const route = window.store?.getState('activeRoute');
  const previousSession = getActiveSessionId();
  if (!studentId || sessionStartingFor === studentId) return null;
  const current = () =>
    window.store?.getState('currentUser')?.id === studentId &&
    window.store?.getState('activeRoute') === route &&
    getActiveSessionId() === previousSession &&
    (!options.isCurrent || options.isCurrent());
  if (!current()) return null;
  const subject = options.subject || document.getElementById('f-subject').value;
  const topic = (options.topic ?? document.getElementById('f-topic').value).trim();
  if (!topic) {
    toast('Choose a topic to study.', true);
    return;
  }
  const difficulty = options.difficulty || document.getElementById('f-difficulty').value;
  const grounding =
    options.documentId ??
    (document.getElementById('f-grounding')
      ? document.getElementById('f-grounding').value
      : 'none');

  sessionStartingFor = studentId;
  document.getElementById('start-btn').disabled = true;
  try {
    const data = await window.sentioAPI.post('/sessions', {
      student_id: studentId,
      subject,
      topic,
      difficulty,
      metadata: { document_id: grounding },
    });
    if (!current()) {
      if (
        options.isCurrent &&
        !options.isCurrent() &&
        window.store?.getState('currentUser')?.id === studentId
      ) {
        try {
          await window.sentioAPI.delete(`/sessions/${data.session_id}`);
        } catch {
          if (window.store?.getState('currentUser')?.id === studentId)
            toast(
              'The cancelled session could not close. Close it from your saved sessions.',
              true,
            );
        }
      }
      return null;
    }
    window.setLegacySessionId(data.session_id);
    if (window.store)
      window.store.setState('activeSession', { ...data, metadata: { document_id: grounding } });

    // Set up grounding change listener
    const groundingSelect = document.getElementById('f-grounding');
    if (groundingSelect) {
      groundingSelect.onchange = (event) => window.updateGrounding(event.target.value);
    }

    // UI
    const setupCard = document.getElementById('session-setup-card');
    if (setupCard) setupCard.style.display = 'none';
    const activeBar = document.getElementById('session-active-bar');
    if (activeBar) activeBar.style.display = 'flex';
    const barTopic = document.getElementById('active-bar-topic');
    if (barTopic) barTopic.textContent = `${subject} · ${topic}`;
    const barMeta = document.getElementById('active-bar-meta');
    if (barMeta)
      barMeta.textContent = `${difficulty} · ${grounding === 'none' ? 'General Tutor' : 'Document Grounded'}`;

    const welcome = document.getElementById('welcome');
    if (welcome) welcome.style.display = 'none';
    const startBtn = document.getElementById('start-btn');
    if (startBtn) startBtn.style.display = 'none';
    const endBtn = document.getElementById('end-btn');
    if (endBtn) endBtn.style.display = 'inline-block';
    const msgInput = document.getElementById('msg-input');
    if (msgInput) {
      msgInput.disabled = false;
      msgInput.placeholder = 'Ask your tutor anything... (Enter to send, Shift+Enter for newline)';
      msgInput.focus();
    }
    const sendBtn = document.getElementById('send-btn');
    if (sendBtn) sendBtn.disabled = false;
    const camQuick = document.getElementById('cam-quick-toggle-btn');
    if (camQuick) camQuick.disabled = false;

    if (hasSpeechRec && hasSpeechSynth) {
      const micBtn = document.getElementById('mic-btn');
      if (micBtn) micBtn.disabled = false;
    }
    if (hasSpeechSynth) {
      const playBtn = document.getElementById('play-speech-btn');
      if (playBtn) playBtn.disabled = true;
      const stopBtn = document.getElementById('stop-speech-btn');
      if (stopBtn) stopBtn.disabled = true;
      const speakerBtn = document.getElementById('speaker-btn');
      if (speakerBtn) speakerBtn.disabled = false;
    }
    const connDot = document.getElementById('conn-dot');
    if (connDot) connDot.className = 'dot live';
    const connLabel = document.getElementById('conn-label');
    if (connLabel) connLabel.textContent = 'Session active';
    const sessLabel = document.getElementById('session-label');
    if (sessLabel) sessLabel.textContent = 'ID: ' + data.session_id.slice(0, 8) + '…';
    const camNoSess = document.getElementById('cam-no-session');
    if (camNoSess) camNoSess.style.display = 'none';
    const statDiff = document.getElementById('stat-diff');
    if (statDiff) statDiff.textContent = difficulty;

    sessionStart = Date.now();
    exchangeCount = 0;

    addLog('Session started — ' + subject + '/' + topic, 'var(--accent)');
    startDurationTimer();

    // E7: Camera and Mic remain OFF by default
    const disCam = document.getElementById('disable-cam-btn');
    if (disCam) disCam.disabled = false;
    const disMic = document.getElementById('disable-mic-btn');
    if (disMic) disMic.disabled = false;
    const disAll = document.getElementById('disable-all-tracking-btn');
    if (disAll) disAll.disabled = false;
    const camTog = document.getElementById('cam-toggle-btn');
    if (camTog) camTog.disabled = false;

    if (camNoSess) {
      camNoSess.style.display = 'flex';
      camNoSess.textContent = 'Camera is off. Click CAM ON to start attention tracking.';
    }

    toast('Session started! Ask your first question.');
    return data;
  } catch (e) {
    if (current()) toast('Could not start studying: ' + e.message, true);
    return null;
  } finally {
    if (sessionStartingFor === studentId) sessionStartingFor = null;
    const startBtn = document.getElementById('start-btn');
    if (startBtn) startBtn.disabled = false;
  }
}

async function endSession() {
  const currentSessionId = getActiveSessionId();
  if (!currentSessionId) return;
  const owner = window.store?.getState('currentUser')?.id;
  try {
    await window.sentioAPI.delete(`/sessions/${currentSessionId}`);
    if (
      owner !== window.store?.getState('currentUser')?.id ||
      currentSessionId !== getActiveSessionId()
    )
      return false;
    cleanupSession();
    toast('Study session saved. Your notes and practice remain available.');
    return true;
  } catch (error) {
    if (owner === window.store?.getState('currentUser')?.id)
      toast('Could not finish the session: ' + error.message + '. Try again.', true);
    return false;
  }
}

function cleanupSession() {
  window.stopGeneration?.();
  document.querySelectorAll('sentio-modal').forEach((modal) => modal.remove());
  document
    .getElementById('chat-messages')
    ?.querySelectorAll('.msg')
    .forEach((message) => message.remove());
  const input = document.getElementById('msg-input');
  if (input) input.value = '';
  window.tutorView?.renderCitations([]);
  sessionId = null;
  window.sessionId = null;
  if (window.store && typeof window.store.setState === 'function') {
    window.store.setState('activeSessionId', null);
    window.store.setState('activeSession', null);
  }
  stopWebcam();
  if (wsEmotion) {
    wsEmotion.close();
    wsEmotion = null;
  }
  clearInterval(durationTimer);
  durationTimer = null;
  sessionStart = null;
  if (telemetryTimer) {
    clearInterval(telemetryTimer);
    telemetryTimer = null;
  }
  resetTelemetryBuffer();
  camActive = false;
  if (recognition && recognitionActive) recognition.stop();
  if (window.speechSynthesis) window.speechSynthesis.cancel();

  const setupCard = document.getElementById('session-setup-card');
  if (setupCard) setupCard.style.display = 'flex';
  const activeBar = document.getElementById('session-active-bar');
  if (activeBar) activeBar.style.display = 'none';
  const welcome = document.getElementById('welcome');
  if (welcome) welcome.style.display = 'flex';

  const startBtn = document.getElementById('start-btn');
  if (startBtn) {
    startBtn.disabled = false;
    startBtn.style.display = 'inline-flex';
  }
  const endBtn = document.getElementById('end-btn');
  if (endBtn) endBtn.style.display = 'none';

  const msgInput = document.getElementById('msg-input');
  if (msgInput) {
    msgInput.disabled = true;
    msgInput.placeholder = 'Start a session above to begin chatting...';
  }
  const sendBtn = document.getElementById('send-btn');
  if (sendBtn) sendBtn.disabled = true;

  const micBtn = document.getElementById('mic-btn');
  if (micBtn) {
    micBtn.disabled = true;
    micBtn.classList.remove('active');
  }
  const playBtn = document.getElementById('play-speech-btn');
  if (playBtn) playBtn.disabled = true;
  const stopBtn = document.getElementById('stop-speech-btn');
  if (stopBtn) stopBtn.disabled = true;
  const speakerBtn = document.getElementById('speaker-btn');
  if (speakerBtn) speakerBtn.disabled = true;

  const camBtn = document.getElementById('cam-toggle-btn');
  if (camBtn) {
    camBtn.disabled = true;
    camBtn.textContent = 'CAM ON';
    camBtn.classList.remove('active');
  }
  const camQuick = document.getElementById('cam-quick-toggle-btn');
  if (camQuick) {
    camQuick.disabled = true;
    camQuick.classList.remove('active');
    const qText = document.getElementById('cam-quick-text');
    if (qText) qText.textContent = 'Enable Camera';
    const qIcon = document.getElementById('cam-quick-icon');
    if (qIcon) qIcon.textContent = '📷';
  }

  // E7: Disable privacy control buttons and reset active indicators
  const disCam = document.getElementById('disable-cam-btn');
  if (disCam) disCam.disabled = true;
  const disMic = document.getElementById('disable-mic-btn');
  if (disMic) disMic.disabled = true;
  const disAll = document.getElementById('disable-all-tracking-btn');
  if (disAll) disAll.disabled = true;
  const camActInd = document.getElementById('cam-active-indicator');
  if (camActInd) camActInd.style.display = 'none';
  const micActInd = document.getElementById('mic-active-indicator');
  if (micActInd) micActInd.style.display = 'none';

  stopTutorSpeech();
  lastTutorResponseText = '';
  voiceModeActive = false;
  camActive = false;
  stopAttentionTrackingLoop();

  const connDot = document.getElementById('conn-dot');
  if (connDot) {
    connDot.className = 'dot';
    connDot.style.boxShadow = 'none';
  }
  const connLabel = document.getElementById('conn-label');
  if (connLabel) connLabel.textContent = 'No session';
  const sessLabel = document.getElementById('session-label');
  if (sessLabel) sessLabel.textContent = '—';
  const camNoSess = document.getElementById('cam-no-session');
  if (camNoSess) {
    camNoSess.style.display = 'flex';
    camNoSess.textContent = 'Start a session to enable attention tracking';
  }
  const camBadge = document.getElementById('cam-badge');
  if (camBadge) {
    camBadge.textContent = 'NO SESSION';
    camBadge.style.color = 'var(--neutral)';
  }

  // Reset attention UI metrics
  const statScore = document.getElementById('stat-attention-score');
  if (statScore) statScore.textContent = '—';
  const statStatus = document.getElementById('stat-focus-status');
  if (statStatus) {
    statStatus.textContent = '—';
    statStatus.style.color = 'var(--text)';
  }
  const statBlinks = document.getElementById('stat-blink-count');
  if (statBlinks) statBlinks.textContent = '0';
  const statPose = document.getElementById('stat-pose-yaw-pitch');
  if (statPose) statPose.textContent = '—';
  const statFps = document.getElementById('stat-tracking-fps');
  if (statFps) statFps.textContent = '-- FPS';
}

// ── SEND MESSAGE ─────────────────────────────
async function sendMessage() {
  const input = document.getElementById('msg-input');
  const msg = input.value.trim();
  const currentSessionId = getActiveSessionId();
  if (!msg || !currentSessionId || generationInProgress) return;
  generationInProgress = true;
  const controller = new AbortController();
  const generationTimer = setTimeout(() => controller.abort(), 200000);
  const sendButton = document.getElementById('send-btn');
  if (sendButton) sendButton.disabled = true;

  if (!sessionStart) {
    sessionStart = Date.now();
  }
  if (!durationTimer) {
    startDurationTimer();
  }

  // Cancel any active speech synthesis first
  if (hasSpeechSynth && window.speechSynthesis) {
    window.speechSynthesis.cancel();
  }

  // Stop recognition while waiting for response
  if (recognition && recognitionActive) {
    try {
      recognition.stop();
    } catch (e) {}
  }

  input.value = '';
  input.style.height = 'auto';
  appendMessage('student', msg);
  showTyping(true);

  const pendingKey = `sentio_turn:${currentSessionId}`;
  let pending;
  try {
    pending = JSON.parse(window.localStorage?.getItem(pendingKey) || 'null');
  } catch (_) {}
  const requestId =
    pending?.message === msg
      ? pending.request_id
      : globalThis.crypto?.randomUUID?.() || `${Date.now()}_${Math.random().toString(36).slice(2)}`;
  window.localStorage?.setItem(pendingKey, JSON.stringify({ request_id: requestId, message: msg }));
  generationRequest = { controller, sessionId: currentSessionId, requestId, stopped: false };
  const stopButton = document.getElementById('stop-generation-btn');
  if (stopButton) stopButton.hidden = false;
  let partial = null;
  let data = null;
  try {
    const res = await fetch(`${API}/sessions/${currentSessionId}/chat/stream`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ message: msg, request_id: requestId }),
      signal: controller.signal,
    });
    if (!res.ok) {
      const error = await res.json();
      throw new Error(error.detail || 'Tutor generation failed. Please retry.');
    }
    await readTutorEvents(res, (kind, value) => {
      if (getActiveSessionId() !== currentSessionId) return;
      if (kind === 'delta') {
        showTyping(false);
        if (!partial) partial = appendMessage('tutor', '');
        const bubble = partial.querySelector('.msg-bubble');
        bubble.style.whiteSpace = 'pre-wrap';
        bubble.textContent += value.text;
        partial.querySelector('.msg-meta').textContent = 'Tutor · Draft answer';
      } else if (kind === 'status') {
        const progress = document.querySelector('#typing-indicator > span');
        if (progress) progress.textContent = value.stage;
      } else if (kind === 'complete') {
        data = value;
      } else if (kind === 'cancelled' || kind === 'error') {
        throw new Error(value.detail);
      }
    });
    if (!data)
      throw new Error('The connection ended before the answer was saved. Retry this question.');
    if (getActiveSessionId() !== currentSessionId) return;
    partial?.remove();
    window.localStorage?.removeItem(pendingKey);
    showTyping(false);

    if (data.text) {
      exchangeCount++;
      appendTutorMessage(data);
      updateStatePanel(data);
      addLog(
        'Exchange ' + exchangeCount + ' — state: ' + (data.learning_state || 'neutral'),
        STATE_COLOR[data.learning_state] || 'var(--text-dim)',
      );

      // Store response for replay
      lastTutorResponseText = data.text;
      const playBtn = document.getElementById('play-speech-btn');
      if (playBtn) playBtn.disabled = false;

      // Play the tutor response aloud
      speakText(data.text);
    } else {
      toast('No response from tutor. Check server logs.', true);
      if (voiceModeActive) {
        restartVoiceCapture();
      }
    }
  } catch (e) {
    if (getActiveSessionId() !== currentSessionId) {
      partial?.remove();
      return;
    }
    showTyping(false);
    if (partial) partial.querySelector('.msg-meta').textContent = 'Tutor · Incomplete answer';
    input.value = msg;
    toast(
      e.name === 'AbortError'
        ? generationRequest?.stopped
          ? 'Answer stopped before completion.'
          : 'Generation timed out. Retry this question.'
        : e.message,
      true,
    );
    if (voiceModeActive) {
      restartVoiceCapture();
    }
  } finally {
    clearTimeout(generationTimer);
    if (!data) window.cancelTutorRequest?.(currentSessionId, requestId);
    generationRequest = null;
    if (stopButton) stopButton.hidden = true;
    generationInProgress = false;
    if (sendButton && getActiveSessionId() === currentSessionId) sendButton.disabled = false;
  }
}
window.sendMessage = sendMessage;

async function readTutorEvents(response, onEvent) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  try {
    while (true) {
      const { value, done } = await reader.read();
      buffer += done ? decoder.decode() : decoder.decode(value, { stream: true });
      let end;
      while ((end = buffer.indexOf('\n\n')) >= 0) {
        const block = buffer.slice(0, end);
        buffer = buffer.slice(end + 2);
        const kind = block.match(/^event: (.+)$/m)?.[1];
        const payload = block
          .split('\n')
          .filter((line) => line.startsWith('data: '))
          .map((line) => line.slice(6))
          .join('\n');
        if (kind && payload) onEvent(kind, JSON.parse(payload));
      }
      if (done) break;
    }
  } finally {
    reader.releaseLock();
  }
}

window.cancelTutorRequest = async (sid, requestId) => {
  try {
    const response = await fetch(`${API}/sessions/${sid}/chat/${requestId}/cancel`, {
      method: 'POST',
      headers: getAuthHeaders(),
    });
    return response.ok && (await response.json()).accepted;
  } catch (_) {
    return false;
  }
};
window.stopGeneration = async () => {
  const request = generationRequest;
  if (!request) return;
  const accepted = await window.cancelTutorRequest(request.sessionId, request.requestId);
  if (accepted && generationRequest === request) {
    request.stopped = true;
    request.controller.abort();
  }
};
window.updateGrounding = async (documentId) => {
  const owner = window.store?.getState('currentUser')?.id;
  const sid = getActiveSessionId();
  await window.stopGeneration();
  if (!sid || getActiveSessionId() !== sid || owner !== window.store?.getState('currentUser')?.id)
    return;
  try {
    const response = await fetch(`${API}/sessions/${sid}/grounding`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ document_id: documentId }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || 'Source update failed.');
    if (getActiveSessionId() !== sid || owner !== window.store?.getState('currentUser')?.id) return;
    const context = window.store?.getState('activeSession') || {};
    window.store?.setState('activeSession', {
      ...context,
      metadata: { ...context.metadata, document_id: documentId },
    });
    toast('Study source updated.');
  } catch (error) {
    if (getActiveSessionId() !== sid || owner !== window.store?.getState('currentUser')?.id) return;
    document.getElementById('f-grounding').value =
      window.store?.getState('activeSession')?.metadata?.document_id || 'none';
    toast(error.message, true);
  }
};

// ── RENDER MESSAGES ──────────────────────────
function appendMessage(role, text) {
  const container = document.getElementById('chat-messages');
  const div = document.createElement('div');
  div.className = 'msg ' + role;
  div.innerHTML = `
    <div class="msg-avatar">${role === 'tutor' ? '🧠' : '🎓'}</div>
    <div class="msg-body">
      <div class="msg-meta">${role === 'tutor' ? 'Tutor' : 'You'} · ${timeNow()}</div>
      <div class="msg-bubble">${escHtml(text)}</div>
    </div>`;
  container.insertBefore(div, document.getElementById('typing-indicator'));
  container.scrollTop = container.scrollHeight;
  return div;
}

function appendTutorMessage(data) {
  const container = document.getElementById('chat-messages');
  const strategy = STRATEGY_LABEL[data.strategy] || data.strategy || '';
  const div = document.createElement('div');
  div.className = 'msg tutor';

  let extra = '';
  const answerLabel =
    data.answer_mode === 'source_excerpt'
      ? 'Source excerpt: relevant passages, not a generated explanation.'
      : data.source_citations?.length
        ? 'Generated explanation: check the claims against your notes.'
        : '';
  if (answerLabel) extra += `<div class="msg-encouragement">${answerLabel}</div>`;
  if (data.encouragement)
    extra += `<div class="msg-encouragement">${escHtml(data.encouragement)}</div>`;
  if (data.follow_up) extra += `<div class="msg-followup">🤔 ${escHtml(data.follow_up)}</div>`;

  div.innerHTML = `
    <div class="msg-avatar">🧠</div>
    <div class="msg-body">
      <div class="msg-meta">
        Tutor · ${timeNow()}
        <span class="msg-strategy-badge">${strategy}</span>
      </div>
      <div class="msg-bubble">${renderMarkdown(data.text)}</div>
      ${extra}
    </div>`;
  container.insertBefore(div, document.getElementById('typing-indicator'));
  container.scrollTop = container.scrollHeight;
}

function renderMarkdown(text) {
  if (!text) return '';
  text = escHtml(text);
  // Code blocks
  text = text.replace(
    /```(\w+)?\n([\s\S]*?)```/g,
    (_, lang, code) => `<pre><code>${code.trim()}</code></pre>`,
  );
  // Inline code
  text = text.replace(/`([^`]+)`/g, '<code>$1</code>');
  // Bold
  text = text.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  // Line breaks
  text = text.replace(/\n/g, '<br>');
  return text;
}

function escHtml(s) {
  if (!s) return '';
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function showTyping(show) {
  document.getElementById('typing-indicator').classList.toggle('show', show);
  const c = document.getElementById('chat-messages');
  c.scrollTop = c.scrollHeight;
}

// ── STATE PANEL ──────────────────────────────
function updateStatePanel(data) {
  const state = data.learning_state || 'neutral';
  const emotion = data.detected_emotion || 'neutral';
  const color = STATE_COLOR[state] || 'var(--neutral)';
  const engage = Math.round(
    (data.engagement_score !== undefined && data.engagement_score !== null
      ? data.engagement_score
      : 0.5) * 100,
  );
  const hasConfidence =
    data.emotion_confidence !== undefined &&
    data.emotion_confidence !== null &&
    data.emotion_confidence > 0;
  const conf = hasConfidence ? Math.round(data.emotion_confidence * 100) + '%' : '—';
  const diff = data.difficulty || '—';
  const strategy = data.strategy || 'standard';

  const stateIcon = document.getElementById('state-icon');
  if (stateIcon) stateIcon.textContent = EMOTION_EMOJI[emotion] || '😐';
  const stateName = document.getElementById('state-name');
  if (stateName) {
    stateName.textContent = state;
    stateName.style.color = color;
  }
  const stateStrat = document.getElementById('state-strategy');
  if (stateStrat) stateStrat.textContent = 'Strategy: ' + (STRATEGY_LABEL[strategy] || strategy);
  const engageBar = document.getElementById('engage-bar');
  if (engageBar) engageBar.style.width = engage + '%';
  const statEngage = document.getElementById('stat-engage');
  if (statEngage) statEngage.textContent = engage + '%';
  const statConf = document.getElementById('stat-conf');
  if (statConf) statConf.textContent = conf;
  const statDiff = document.getElementById('stat-diff');
  if (statDiff) statDiff.textContent = diff;
  if (data.total_exchanges !== undefined) {
    exchangeCount = data.total_exchanges;
  }
  const statExchanges = document.getElementById('stat-exchanges');
  if (statExchanges) statExchanges.textContent = exchangeCount;

  // Synchronize duration if provided
  if (!durationTimer) {
    startDurationTimer(data.duration_minutes || 0);
  }

  // Highlight active strategy chip
  document.querySelectorAll('.strat-chip').forEach((c) => {
    c.classList.toggle('active', c.dataset.s === strategy);
  });

  // Update cam badge
  const camBadge = document.getElementById('cam-badge');
  if (camBadge) {
    camBadge.textContent = state.toUpperCase();
    camBadge.style.color = color;
  }

  // Topics
  if (data.topics_covered && data.topics_covered.length) {
    const el = document.getElementById('topics-chips');
    if (el) {
      el.innerHTML = data.topics_covered
        .map((t) => `<span class="topic-chip">${escHtml(t)}</span>`)
        .join('');
    }
  }

  // Emotion bars
  const hasScores = data.emotion_scores && Object.keys(data.emotion_scores).length > 0;
  EMOTIONS.forEach((em) => {
    const fill = document.getElementById('bar-' + em);
    const pct = document.getElementById('barpct-' + em);
    if (hasScores && typeof data.emotion_scores[em] === 'number') {
      const p = Math.round(data.emotion_scores[em] * 100);
      if (fill) fill.style.width = p + '%';
      if (pct) pct.textContent = p + '%';
    } else {
      if (fill) fill.style.width = '0%';
      if (pct) pct.textContent = '--';
    }
  });
}
window.updateStatePanel = updateStatePanel;
window.setExchangeCount = function (n) {
  exchangeCount = n;
  const el = document.getElementById('stat-exchanges');
  if (el) el.textContent = n;
};

// ── TELEMETRY AGGREGATION & TRANSMISSION ──────
let telemetryBuffer = {
  attentionScores: [],
  focusedList: [],
  eyeOpennesses: [],
  headPitches: [],
  headYaws: [],
};
let telemetryTimer = null;

function resetTelemetryBuffer() {
  telemetryBuffer = {
    attentionScores: [],
    focusedList: [],
    eyeOpennesses: [],
    headPitches: [],
    headYaws: [],
  };
}

async function sendAggregatedTelemetry() {
  const currentSessionId = getActiveSessionId();
  if (!currentSessionId || !camActive) return;

  const counts = telemetryBuffer.attentionScores.length;
  if (counts === 0) return;

  const avg = (arr) => arr.reduce((a, b) => a + b, 0) / arr.length;
  const avgFocused = avg(telemetryBuffer.focusedList) >= 0.5 ? 1 : 0;

  const payload = {
    attention_score: parseFloat(avg(telemetryBuffer.attentionScores).toFixed(4)),
    focused: avgFocused,
    eye_openness: parseFloat(avg(telemetryBuffer.eyeOpennesses).toFixed(4)),
    head_pose_pitch: parseFloat(avg(telemetryBuffer.headPitches).toFixed(4)),
    head_pose_yaw: parseFloat(avg(telemetryBuffer.headYaws).toFixed(4)),
    emotion: focusStatus,
  };

  resetTelemetryBuffer();
  console.log('Dispatching aggregated telemetry:', payload);
  dispatchTelemetryWithRetry(payload, 3, 1000);
}

async function dispatchTelemetryWithRetry(payload, retriesLeft, delay) {
  const currentSessionId = getActiveSessionId();
  if (!currentSessionId) return;

  try {
    const res = await fetch(`${API}/sessions/${currentSessionId}/telemetry`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      throw new Error('Telemetry endpoint returned status ' + res.status);
    }
    console.log('Telemetry sent successfully');
  } catch (err) {
    console.warn(`Failed to send telemetry. Retries left: ${retriesLeft}. Error:`, err);
    if (retriesLeft > 0) {
      setTimeout(() => {
        dispatchTelemetryWithRetry(payload, retriesLeft - 1, delay * 2);
      }, delay);
    } else {
      console.error('Telemetry transmission failed permanently.');
      addLog('Telemetry network failure', 'var(--red)');
    }
  }
}

// ── WEBCAM & ATTENTION TRACKING ───────────────
let camActive = false;
let faceLandmarker = null;
let filesetResolver = null;
let trackingLoopActive = false;
let frameSkipCount = 5;
let lastVideoTime = -1;
let attentionScore = 1.0;
let focusStatus = 'focused';
let lookAwayCount = 0;
let blinkCount = 0;

let wasEyesClosed = false;
const EAR_THRESHOLD = 0.22;
const leftEyeIndices = [263, 362, 386, 374, 385, 373];
const rightEyeIndices = [33, 133, 159, 145, 158, 144];

// E7: Privacy Consent Global State
let pendingConsentFeature = null;
let pendingConsentCallback = null;

function checkConsentAndActivate(feature, callback) {
  if (window.store?.getState('telemetryActive')) {
    callback();
  } else {
    pendingConsentFeature = feature;
    pendingConsentCallback = callback;
    const modal = document.getElementById('privacy-consent-modal');
    if (modal) {
      modal.style.display = 'flex';
    } else {
      pendingConsentCallback = null;
      toast('Enable optional camera consent in Settings first.', true);
    }
  }
}

function acceptPrivacyConsent() {
  window.store?.setState('telemetryActive', true);
  const modal = document.getElementById('privacy-consent-modal');
  if (modal) modal.style.display = 'none';
  toast('Privacy consent granted. Activating feature...');
  if (pendingConsentCallback) {
    pendingConsentCallback();
  }
  pendingConsentFeature = null;
  pendingConsentCallback = null;
}

function declinePrivacyConsent() {
  const modal = document.getElementById('privacy-consent-modal');
  if (modal) modal.style.display = 'none';
  toast('Privacy consent declined. Tracking remains disabled.', true);
  const camQuick = document.getElementById('cam-quick-toggle-btn');
  if (camQuick) {
    camQuick.classList.remove('active');
    const qText = document.getElementById('cam-quick-text');
    if (qText) qText.textContent = 'Enable Camera';
    const qIcon = document.getElementById('cam-quick-icon');
    if (qIcon) qIcon.textContent = '📷';
  }
  pendingConsentFeature = null;
  pendingConsentCallback = null;
}

function disableCamera() {
  stopWebcam();
  camActive = false;

  const btn = document.getElementById('cam-toggle-btn');
  if (btn) {
    btn.textContent = 'CAM OFF';
    btn.classList.remove('active');
  }
  const camQuick = document.getElementById('cam-quick-toggle-btn');
  if (camQuick) {
    camQuick.classList.remove('active');
    const qText = document.getElementById('cam-quick-text');
    if (qText) qText.textContent = 'Enable Camera';
    const qIcon = document.getElementById('cam-quick-icon');
    if (qIcon) qIcon.textContent = '📷';
  }

  const camNoSess = document.getElementById('cam-no-session');
  if (camNoSess) {
    camNoSess.style.display = 'flex';
    camNoSess.textContent = 'Camera disabled';
  }
  const camBadge = document.getElementById('cam-badge');
  if (camBadge) {
    camBadge.textContent = 'DISABLED';
    camBadge.style.color = 'var(--text-dim)';
  }
  const camActInd = document.getElementById('cam-active-indicator');
  if (camActInd) camActInd.style.display = 'none';

  // Reset metrics
  const statScore = document.getElementById('stat-attention-score');
  if (statScore) statScore.textContent = '—';
  const statStatus = document.getElementById('stat-focus-status');
  if (statStatus) {
    statStatus.textContent = '—';
    statStatus.style.color = 'var(--text)';
  }
  const statPose = document.getElementById('stat-pose-yaw-pitch');
  if (statPose) statPose.textContent = '—';
  const statFps = document.getElementById('stat-tracking-fps');
  if (statFps) statFps.textContent = '-- FPS';

  toast('Camera disabled. Attention tracking stopped.');
  addLog('Camera disabled', 'var(--text-dim)');
}

function disableMicrophone() {
  voiceModeActive = false;
  const micBtn = document.getElementById('mic-btn');
  if (micBtn) {
    micBtn.classList.remove('active');
  }
  if (recognition) {
    try {
      recognition.stop();
    } catch (e) {
      console.error('Failed to stop speech recognition:', e);
    }
  }
  if (window.speechSynthesis) {
    window.speechSynthesis.cancel();
  }
  const micActInd = document.getElementById('mic-active-indicator');
  if (micActInd) micActInd.style.display = 'none';

  toast('Microphone disabled. Voice mode stopped.');
  addLog('Microphone disabled', 'var(--text-dim)');
}

function disableAllTracking() {
  disableCamera();
  disableMicrophone();
  toast('All tracking and recording disabled.');
  addLog('All tracking disabled', 'var(--red)');
}

async function startWebcam() {
  if (camStream || cameraStarting || !window.store?.getState('telemetryActive')) return;
  const owner = window.store.getState('currentUser')?.id;
  const activeSession = getActiveSessionId();
  if (!owner || !activeSession) return;
  const epoch = ++cameraEpoch;
  cameraStarting = true;
  let acquired = null;
  const stillCurrent = () =>
    epoch === cameraEpoch &&
    window.store.getState('telemetryActive') &&
    window.store.getState('currentUser')?.id === owner &&
    getActiveSessionId() === activeSession &&
    ['#/tutor', '#/quizzes', '#/flashcards'].includes(window.store.getState('activeRoute'));
  try {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      throw new Error('MediaDevices API not supported');
    }
    acquired = await navigator.mediaDevices.getUserMedia({
      video: { width: 320, height: 240, facingMode: 'user' },
      audio: false,
    });
    if (!stillCurrent()) {
      acquired.getTracks().forEach((track) => track.stop());
      return;
    }
    camStream = acquired;
    window.camStream = camStream;
    const video = document.getElementById('cam-video');
    if (video) video.srcObject = camStream;
    if (!faceLandmarker) await initMediaPipe();
    if (!stillCurrent()) {
      acquired.getTracks().forEach((track) => track.stop());
      return;
    }
    if (!faceLandmarker) throw new Error('Optional camera model unavailable');
    if (faceLandmarker) startAttentionTrackingLoop();
    addLog('Camera started', 'var(--green)');
    camActive = true;
    const camActInd = document.getElementById('cam-active-indicator');
    if (camActInd) camActInd.style.display = 'flex';
    const btn = document.getElementById('cam-toggle-btn');
    if (btn) {
      btn.disabled = false;
      btn.textContent = 'CAM ON';
      btn.classList.add('active');
    }
    const camQuick = document.getElementById('cam-quick-toggle-btn');
    if (camQuick) {
      camQuick.classList.add('active');
      const qText = document.getElementById('cam-quick-text');
      if (qText) qText.textContent = 'Camera Active';
      const qIcon = document.getElementById('cam-quick-icon');
      if (qIcon) qIcon.textContent = '🟢';
    }
  } catch (e) {
    if (acquired) acquired.getTracks().forEach((track) => track.stop());
    if (epoch !== cameraEpoch) return;
    stopWebcam();
    addLog('Camera access denied/unavailable — standard tutoring active', 'var(--yellow)');
    toast(
      'Camera permission or optional local camera assets are unavailable. Text tutoring remains active.',
      false,
    );
    camActive = false;
    const camActInd = document.getElementById('cam-active-indicator');
    if (camActInd) camActInd.style.display = 'none';
    const btn = document.getElementById('cam-toggle-btn');
    if (btn) {
      btn.disabled = false;
      btn.textContent = 'CAM OFF';
      btn.classList.remove('active');
    }
    const camQuick = document.getElementById('cam-quick-toggle-btn');
    if (camQuick) {
      camQuick.classList.remove('active');
      const qText = document.getElementById('cam-quick-text');
      if (qText) qText.textContent = 'Enable Camera';
      const qIcon = document.getElementById('cam-quick-icon');
      if (qIcon) qIcon.textContent = '📷';
    }
  } finally {
    if (epoch === cameraEpoch) cameraStarting = false;
  }
}

function stopWebcam() {
  cameraEpoch++;
  cameraStarting = false;
  if (telemetryTimer) clearInterval(telemetryTimer);
  telemetryTimer = null;
  resetTelemetryBuffer();
  stopAttentionTrackingLoop();
  camActive = false;
  window.camStream = null;
  if (camStream) {
    camStream.getTracks().forEach((t) => t.stop());
    camStream = null;
    const video = document.getElementById('cam-video');
    if (video) video.srcObject = null;
  }
  const camActInd = document.getElementById('cam-active-indicator');
  if (camActInd) camActInd.style.display = 'none';
  stopAttentionTrackingLoop();
}

async function toggleWebcamDirect() {
  const currentSessionId = getActiveSessionId();
  if (!currentSessionId) {
    toast('Start a session first before enabling camera.', true);
    return;
  }

  if (camActive) {
    disableCamera();
  } else {
    checkConsentAndActivate('camera', async () => {
      const camNoSess = document.getElementById('cam-no-session');
      if (camNoSess) camNoSess.style.display = 'none';
      await startWebcam();
      if (camStream) {
        camActive = true;
        const btn = document.getElementById('cam-toggle-btn');
        if (btn) {
          btn.textContent = 'CAM ON';
          btn.classList.add('active');
        }
        startAttentionTrackingLoop();

        // Reset buffer and start sending telemetry
        resetTelemetryBuffer();
        if (telemetryTimer) clearInterval(telemetryTimer);
        telemetryTimer = setInterval(sendAggregatedTelemetry, 10000);
      }
    });
  }
}

async function initMediaPipe() {
  try {
    if (!window.FilesetResolver || !window.FaceLandmarker) {
      const vision = await import('/static/vendor/mediapipe/vision_bundle.mjs');
      window.FilesetResolver = vision.FilesetResolver;
      window.FaceLandmarker = vision.FaceLandmarker;
    }
    filesetResolver = await window.FilesetResolver.forVisionTasks('/static/vendor/mediapipe/wasm');
    try {
      faceLandmarker = await window.FaceLandmarker.createFromOptions(filesetResolver, {
        baseOptions: {
          modelAssetPath: '/static/vendor/mediapipe/face_landmarker.task',
          delegate: 'GPU',
        },
        runningMode: 'VIDEO',
        numFaces: 1,
      });
    } catch (gpuErr) {
      console.warn('MediaPipe GPU delegate unavailable, falling back to CPU:', gpuErr);
      faceLandmarker = await window.FaceLandmarker.createFromOptions(filesetResolver, {
        baseOptions: {
          modelAssetPath: '/static/vendor/mediapipe/face_landmarker.task',
          delegate: 'CPU',
        },
        runningMode: 'VIDEO',
        numFaces: 1,
      });
    }
    window.faceLandmarker = faceLandmarker;
    console.log('MediaPipe FaceLandmarker successfully initialized!');
  } catch (e) {
    console.error('Failed to initialize MediaPipe FaceLandmarker:', e);
  }
}

function startAttentionTrackingLoop() {
  if (trackingLoopActive) return;
  trackingLoopActive = true;
  requestAnimationFrame(processFrame);
}

function stopAttentionTrackingLoop() {
  trackingLoopActive = false;
}

async function processFrame() {
  if (!trackingLoopActive || !camStream || !faceLandmarker) {
    trackingLoopActive = false;
    return;
  }

  const video = document.getElementById('cam-video');
  if (video && video.readyState >= 2) {
    let now = video.currentTime;
    if (now !== lastVideoTime) {
      lastVideoTime = now;

      const startTime = performance.now();
      try {
        const results = faceLandmarker.detectForVideo(video, startTime);
        if (results && results.faceLandmarks && results.faceLandmarks.length > 0) {
          const landmarks = results.faceLandmarks[0];
          analyzeLandmarks(landmarks);
        } else {
          updateFocusState(false, 0.0, 0.0, 0.0);
        }
      } catch (err) {
        console.error('Error during face landmark detection:', err);
      }

      const duration = performance.now() - startTime;
      adjustFPS(duration);
    }
  }

  if (trackingLoopActive) {
    setTimeout(
      () => {
        requestAnimationFrame(processFrame);
      },
      1000 / (30 / frameSkipCount),
    );
  }
}

function calculateDistance(p1, p2) {
  return Math.sqrt(Math.pow(p1.x - p2.x, 2) + Math.pow(p1.y - p2.y, 2) + Math.pow(p1.z - p2.z, 2));
}

function calculateEAR(landmarks, eyeIndices) {
  const dHorizontal = calculateDistance(landmarks[eyeIndices[0]], landmarks[eyeIndices[1]]);
  const dVertical1 = calculateDistance(landmarks[eyeIndices[2]], landmarks[eyeIndices[3]]);
  const dVertical2 = calculateDistance(landmarks[eyeIndices[4]], landmarks[eyeIndices[5]]);

  if (dHorizontal === 0) return 0;
  return (dVertical1 + dVertical2) / (2.0 * dHorizontal);
}

function getEyeOpenness(landmarks) {
  const leftEAR = calculateEAR(landmarks, leftEyeIndices);
  const rightEAR = calculateEAR(landmarks, rightEyeIndices);
  return (leftEAR + rightEAR) / 2.0;
}

function analyzeLandmarks(landmarks) {
  const currentEAR = getEyeOpenness(landmarks);

  if (currentEAR < EAR_THRESHOLD) {
    if (!wasEyesClosed) {
      wasEyesClosed = true;
      blinkCount++;
      document.getElementById('stat-blink-count').textContent = blinkCount;
    }
  } else {
    wasEyesClosed = false;
  }

  const nose = landmarks[1];
  const leftEye = landmarks[362];
  const rightEye = landmarks[133];
  const forehead = landmarks[10];
  const chin = landmarks[152];

  const eyeWidth = calculateDistance(leftEye, rightEye);
  const faceHeight = calculateDistance(forehead, chin);

  if (eyeWidth === 0 || faceHeight === 0) return;

  const eyeMidX = (leftEye.x + rightEye.x) / 2;
  const rawYaw = (nose.x - eyeMidX) / eyeWidth;

  const faceMidY = (forehead.y + chin.y) / 2;
  const rawPitch = (nose.y - faceMidY) / faceHeight;

  const yaw = rawYaw * 80;
  const pitch = rawPitch * 80;

  const lookingAway = Math.abs(yaw) > 18 || Math.abs(pitch) > 15;

  let score = 1.0;
  if (lookingAway) {
    score -= 0.6;
    focusStatus = 'looking_away';
  } else if (currentEAR < 0.15) {
    score -= 0.3;
    focusStatus = 'eyes_closed';
  } else {
    focusStatus = 'focused';
  }

  attentionScore = Math.max(0.0, score);
  updateFocusState(true, attentionScore, yaw, pitch);

  if (camActive) {
    telemetryBuffer.attentionScores.push(attentionScore);
    telemetryBuffer.focusedList.push(focusStatus === 'focused' ? 1 : 0);
    telemetryBuffer.eyeOpennesses.push(currentEAR);
    telemetryBuffer.headPitches.push(pitch);
    telemetryBuffer.headYaws.push(yaw);
  }
}

function updateFocusState(detected, score, yaw, pitch) {
  const scorePct = Math.round(score * 100);
  document.getElementById('stat-attention-score').textContent = scorePct + '%';

  const statusEl = document.getElementById('stat-focus-status');
  if (!detected) {
    statusEl.textContent = 'No Face Detected';
    statusEl.style.color = 'var(--red)';
    document.getElementById('stat-pose-yaw-pitch').textContent = '—';

    if (camActive) {
      telemetryBuffer.attentionScores.push(0.0);
      telemetryBuffer.focusedList.push(0);
      telemetryBuffer.eyeOpennesses.push(0.0);
      telemetryBuffer.headPitches.push(0.0);
      telemetryBuffer.headYaws.push(0.0);
    }
  } else {
    if (focusStatus === 'focused') {
      statusEl.textContent = 'Focused';
      statusEl.style.color = 'var(--green)';
    } else if (focusStatus === 'looking_away') {
      statusEl.textContent = 'Looking Away';
      statusEl.style.color = 'var(--red)';
    } else if (focusStatus === 'eyes_closed') {
      statusEl.textContent = 'Eyes Closed';
      statusEl.style.color = 'var(--yellow)';
    }
    document.getElementById('stat-pose-yaw-pitch').textContent =
      Math.round(yaw) + '° / ' + Math.round(pitch) + '°';
  }

  const badge = document.getElementById('cam-badge');
  if (badge) {
    if (!detected) {
      badge.textContent = 'NO FACE';
      badge.style.color = 'var(--red)';
    } else {
      badge.textContent = focusStatus.toUpperCase().replace('_', ' ');
      badge.style.color = focusStatus === 'focused' ? 'var(--green)' : 'var(--yellow)';
    }
  }
}

function adjustFPS(duration) {
  if (duration > 60) {
    frameSkipCount = Math.min(15, frameSkipCount + 1);
  } else if (duration < 20) {
    frameSkipCount = Math.max(3, frameSkipCount - 1);
  }
  const currentFPS = Math.round(30 / frameSkipCount);
  document.getElementById('stat-tracking-fps').textContent = currentFPS + ' FPS';
}

function captureFrame() {
  const video = document.getElementById('cam-video');
  const canvas = document.getElementById('cam-canvas');
  if (!video.videoWidth) return null;
  canvas.width = 320;
  canvas.height = 240;
  const ctx = canvas.getContext('2d');
  ctx.save();
  ctx.scale(-1, 1);
  ctx.drawImage(video, -320, 0, 320, 240);
  ctx.restore();
  return canvas.toDataURL('image/jpeg', 0.6).split(',')[1];
}

// ── DURATION TIMER ────────────────────────────
function startDurationTimer(initialMinutes = 0) {
  if (durationTimer) clearInterval(durationTimer);
  if (!sessionStart || initialMinutes > 0) {
    sessionStart = Date.now() - Math.round(initialMinutes * 60 * 1000);
  }
  const tick = () => {
    if (!sessionStart) return;
    const secs = Math.floor((Date.now() - sessionStart) / 1000);
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    const el = document.getElementById('stat-duration');
    if (el) el.textContent = m + 'm ' + s + 's';
  };
  tick();
  durationTimer = setInterval(tick, 1000);
}
window.startDurationTimer = startDurationTimer;

// ── SESSION LOG ───────────────────────────────
function addLog(msg, color) {
  const container = document.getElementById('log-entries');
  // Clear placeholder
  if (
    container.children.length === 1 &&
    container.children[0].querySelector('.log-time').textContent === '--:--'
  ) {
    container.innerHTML = '';
  }
  const div = document.createElement('div');
  div.className = 'log-entry';
  div.innerHTML = `
    <span class="log-time">${timeNow()}</span>
    <div class="log-dot" style="background:${color}"></div>
    <span>${msg}</span>`;
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

// ── TOAST ─────────────────────────────────────
function toast(msg, isError) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.style.borderColor = isError ? 'var(--red)' : 'var(--border)';
  el.classList.add('show');
  setTimeout(() => el.classList.remove('show'), 3000);
}

// ── HELPERS ───────────────────────────────────
function timeNow() {
  return new Date().toLocaleTimeString('en-GB', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

// Auto-resize textarea
document.getElementById('msg-input').addEventListener('input', function () {
  this.style.height = 'auto';
  this.style.height = Math.min(this.scrollHeight, 120) + 'px';
});

// Enter to send (Shift+Enter for newline)
document.getElementById('msg-input').addEventListener('keydown', function (e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

// ── SPEECH DETECTION & VOICE TOGGLE ──────────
const hasSpeechRec = 'webkitSpeechRecognition' in window || 'SpeechRecognition' in window;
const hasSpeechSynth = 'speechSynthesis' in window;
let voiceModeActive = false;
let recognition = null;
let recognitionActive = false;

function checkSpeechSupport() {
  const micBtn = document.getElementById('mic-btn');
  if (!hasSpeechRec || !hasSpeechSynth) {
    console.warn('Speech APIs not supported in this browser.');
    if (micBtn) {
      micBtn.style.display = 'none';
    }
    toast('Voice features not supported by this browser. Defaulting to text-only mode.', false);
  }
}

function initSpeechRecognition() {
  if (!hasSpeechRec) return;
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  recognition = new SpeechRecognition();
  recognition.continuous = false;
  recognition.interimResults = false;
  recognition.lang = 'en-US';

  recognition.onstart = () => {
    console.log('Speech recognition started');
    recognitionActive = true;
    document.getElementById('mic-active-indicator').style.display = 'flex';
    // Barge-in: if mic capture starts while speech is playing, immediately cancel speech
    if (hasSpeechSynth && window.speechSynthesis && window.speechSynthesis.speaking) {
      window.speechSynthesis.cancel();
      const stopBtn = document.getElementById('stop-speech-btn');
      if (stopBtn) stopBtn.disabled = true;
    }
  };

  recognition.onend = () => {
    console.log('Speech recognition ended');
    recognitionActive = false;
    document.getElementById('mic-active-indicator').style.display = 'none';
    // If voiceModeActive is still true and we are not currently waiting for tutor response (typing-indicator is not visible),
    // we should restart recognition so the user can continue speaking.
    if (
      voiceModeActive &&
      !document.getElementById('typing-indicator').classList.contains('show')
    ) {
      setTimeout(() => {
        if (
          voiceModeActive &&
          !recognitionActive &&
          !document.getElementById('typing-indicator').classList.contains('show')
        ) {
          try {
            recognition.start();
          } catch (e) {
            console.error('Failed to restart speech recognition:', e);
          }
        }
      }, 400);
    }
  };

  recognition.onresult = (event) => {
    const transcript = event.results[0][0].transcript;
    console.log('Speech transcript:', transcript);
    if (transcript.trim()) {
      const msgInput = document.getElementById('msg-input');
      msgInput.value = transcript;
      msgInput.style.height = 'auto';
      msgInput.style.height = Math.min(msgInput.scrollHeight, 120) + 'px';
      sendMessage();
    }
  };

  recognition.onerror = (event) => {
    console.error('Speech recognition error:', event.error);
    if (event.error === 'not-allowed') {
      toast('Microphone permission was denied. Defaulting to text-only mode.', true);
      voiceModeActive = false;
      const micBtn = document.getElementById('mic-btn');
      if (micBtn) {
        micBtn.classList.remove('active');
      }
      document.getElementById('mic-active-indicator').style.display = 'none';
    }
  };
}

function restartVoiceCapture() {
  if (
    voiceModeActive &&
    recognition &&
    !recognitionActive &&
    !document.getElementById('typing-indicator').classList.contains('show')
  ) {
    if (window.speechSynthesis && window.speechSynthesis.speaking) {
      return;
    }
    try {
      recognition.start();
    } catch (e) {
      console.error('Failed to start voice capture:', e);
    }
  }
}

function toggleVoice() {
  if (!hasSpeechRec || !hasSpeechSynth) return;
  if (!sessionId) {
    toast('Start a session first!', true);
    return;
  }
  voiceModeActive = !voiceModeActive;
  const micBtn = document.getElementById('mic-btn');
  micBtn.classList.toggle('active', voiceModeActive);

  if (voiceModeActive) {
    toast('Voice mode activated. Speaking tutor enabled.');
    addLog('Voice mode enabled', 'var(--accent)');
    if (recognition && !recognitionActive) {
      try {
        recognition.start();
      } catch (e) {
        console.error('Failed to start speech recognition:', e);
      }
    }
  } else {
    toast('Voice mode deactivated.');
    addLog('Voice mode disabled', 'var(--text-dim)');
    if (recognition) {
      try {
        recognition.stop();
      } catch (e) {
        console.error('Failed to stop speech recognition:', e);
      }
    }
    if (window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }
  }
}

// ── SPEECH SYNTHESIS & VOICE CONTROLS ────────
let ttsMuted = localStorage.getItem('sentio_tts_muted') === 'true';
let lastTutorResponseText = '';
let currentUtterance = null;

function initSpeechSynthesis() {
  const speakerBtn = document.getElementById('speaker-btn');
  if (!hasSpeechSynth) {
    console.warn('Speech synthesis not supported in this browser.');
    if (speakerBtn) speakerBtn.style.display = 'none';
    const playBtn = document.getElementById('play-speech-btn');
    if (playBtn) playBtn.style.display = 'none';
    const stopBtn = document.getElementById('stop-speech-btn');
    if (stopBtn) stopBtn.style.display = 'none';
    return;
  }

  // Initialize speaker button icon based on saved preference
  if (speakerBtn) {
    speakerBtn.textContent = ttsMuted ? '🔇' : '🔊';
    speakerBtn.title = ttsMuted ? 'Unmute Tutor Voice' : 'Mute Tutor Voice';
  }
}

function toggleMute() {
  if (!hasSpeechSynth) return;
  ttsMuted = !ttsMuted;
  localStorage.setItem('sentio_tts_muted', ttsMuted ? 'true' : 'false');

  const speakerBtn = document.getElementById('speaker-btn');
  if (speakerBtn) {
    speakerBtn.textContent = ttsMuted ? '🔇' : '🔊';
    speakerBtn.title = ttsMuted ? 'Unmute Tutor Voice' : 'Mute Tutor Voice';
  }

  if (ttsMuted) {
    stopTutorSpeech();
  } else {
    toast('Voice unmuted.');
  }
}

function speakText(text) {
  if (!hasSpeechSynth || ttsMuted || !text) return;

  if (window.speechSynthesis) {
    window.speechSynthesis.cancel();
  }

  const cleanText = text
    .replace(/`([^`]+)`/g, '$1')
    .replace(/\*\*([^*]+)\*\*/g, '$1')
    .replace(/[*#_`~]/g, '')
    .trim();

  if (!cleanText) return;

  currentUtterance = new SpeechSynthesisUtterance(cleanText);
  currentUtterance.lang = 'en-US';

  currentUtterance.onstart = () => {
    console.log('TTS playback started');
    const stopBtn = document.getElementById('stop-speech-btn');
    if (stopBtn) stopBtn.disabled = false;
  };

  currentUtterance.onend = () => {
    console.log('TTS playback finished');
    const stopBtn = document.getElementById('stop-speech-btn');
    if (stopBtn) stopBtn.disabled = true;
    currentUtterance = null;

    if (
      voiceModeActive &&
      !document.getElementById('typing-indicator').classList.contains('show')
    ) {
      restartVoiceCapture();
    }
  };

  currentUtterance.onerror = (event) => {
    console.error('TTS error:', event.error);
    const stopBtn = document.getElementById('stop-speech-btn');
    if (stopBtn) stopBtn.disabled = true;
    currentUtterance = null;
  };

  window.speechSynthesis.speak(currentUtterance);
}

function stopTutorSpeech() {
  if (!hasSpeechSynth) return;
  if (window.speechSynthesis) {
    window.speechSynthesis.cancel();
  }
  const stopBtn = document.getElementById('stop-speech-btn');
  if (stopBtn) stopBtn.disabled = true;
  toast('Speech playback stopped.');
}

function replayLastTutorResponse() {
  if (!hasSpeechSynth) return;
  if (!lastTutorResponseText) {
    toast('No tutor response to replay yet.', true);
    return;
  }
  if (ttsMuted) {
    toggleMute();
  }
  speakText(lastTutorResponseText);
}

// Run check and initialization on script load
checkSpeechSupport();
initSpeechRecognition();
initSpeechSynthesis();
window.initMediaPipe = initMediaPipe;

window.cleanupSession = cleanupSession;
