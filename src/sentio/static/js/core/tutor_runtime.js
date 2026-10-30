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
  const subject = options.subject || 'My notes';
  const topic = (options.topic ?? document.getElementById('f-topic').value).trim();
  if (!topic) {
    toast('Choose a topic to study.', true);
    return;
  }
  const difficulty = options.difficulty || document.getElementById('f-difficulty').value;
  const grounding =
    options.documentId ??
    (document.getElementById('f-grounding') ? document.getElementById('f-grounding').value : 'all');
  const goalId = options.goalId ?? (document.getElementById('f-goal')?.value || '');
  const metadata = { document_id: grounding, ...(goalId ? { goal_id: goalId } : {}) };

  sessionStartingFor = studentId;
  document.getElementById('start-btn').disabled = true;
  try {
    const data = await window.sentioAPI.post('/sessions', {
      student_id: studentId,
      subject,
      topic,
      difficulty,
      metadata,
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
    if (window.store) window.store.setState('activeSession', { ...data, metadata });

    // Set up grounding and goal change listeners
    const groundingSelect = document.getElementById('f-grounding');
    if (groundingSelect) {
      groundingSelect.onchange = (event) => window.updateGrounding(event.target.value);
    }
    const goalSelect = document.getElementById('f-goal');
    if (goalSelect) goalSelect.onchange = (event) => window.updateSessionGoal(event.target.value);

    // UI
    const setupCard = document.getElementById('session-setup-card');
    if (setupCard) setupCard.style.display = 'none';
    const activeBar = document.getElementById('session-active-bar');
    if (activeBar) activeBar.style.display = 'flex';
    const barTopic = document.getElementById('active-bar-topic');
    if (barTopic) barTopic.textContent = `${subject} · ${topic}`;
    const barMeta = document.getElementById('active-bar-meta');
    if (barMeta)
      barMeta.textContent = `${difficulty} · ${grounding === 'none' ? 'Not linked to notes' : 'From your notes'}`;

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
  let sourcesPreview = null;
  let data = null;
  try {
    const res = await window.sentioAPI.post(
      `/sessions/${currentSessionId}/chat/stream`,
      { message: msg, request_id: requestId },
      { signal: controller.signal, stream: true },
    );
    await readTutorEvents(res, (kind, value) => {
      if (getActiveSessionId() !== currentSessionId) return;
      if (kind === 'delta') {
        showTyping(false);
        if (!partial) partial = appendMessage('tutor', '');
        const bubble = partial.querySelector('.msg-bubble');
        bubble.style.whiteSpace = 'pre-wrap';
        bubble.textContent += value.text;
        partial.querySelector('.msg-meta').textContent = 'Tutor · Draft answer';
      } else if (kind === 'sources') {
        sourcesPreview?.remove();
        sourcesPreview = appendSourcesPreview(value.sources);
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
    sourcesPreview?.remove();
    window.localStorage?.removeItem(pendingKey);
    showTyping(false);

    if (data.text) {
      exchangeCount++;
      appendTutorMessage(data);
      if (data.difficulty_change) appendDifficultyNotice(data.difficulty_change, currentSessionId);
      updateStatePanel(data);
      addLog(
        'Exchange ' + exchangeCount + ' — state: ' + (data.learning_state || 'neutral'),
        STATE_COLOR[data.learning_state] || 'var(--text-dim)',
      );

      // Store response for replay
      lastTutorResponseText = data.text;
      const playBtn = document.getElementById('play-speech-btn');
      if (playBtn) playBtn.disabled = false;
    } else {
      toast('No response from tutor. Check server logs.', true);
      if (voiceModeActive) {
        restartVoiceCapture();
      }
    }
  } catch (e) {
    sourcesPreview?.remove();
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
    return (await window.sentioAPI.post(`/sessions/${sid}/chat/${requestId}/cancel`, {})).accepted;
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
    await window.sentioAPI.post(`/sessions/${sid}/grounding`, { document_id: documentId });
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
window.updateSessionGoal = async (goalId) => {
  const owner = window.store?.getState('currentUser')?.id;
  const sid = getActiveSessionId();
  await window.stopGeneration();
  if (!sid || getActiveSessionId() !== sid || owner !== window.store?.getState('currentUser')?.id)
    return;
  try {
    await window.sentioAPI.post(`/sessions/${sid}/goal`, { goal_id: goalId || null });
    if (getActiveSessionId() !== sid || owner !== window.store?.getState('currentUser')?.id) return;
    const context = window.store?.getState('activeSession') || {};
    window.store?.setState('activeSession', {
      ...context,
      metadata: { ...context.metadata, goal_id: goalId || null },
    });
    toast(goalId ? 'Session goal updated.' : 'Session goal cleared.');
  } catch (error) {
    if (getActiveSessionId() !== sid || owner !== window.store?.getState('currentUser')?.id) return;
    document.getElementById('f-goal').value =
      window.store?.getState('activeSession')?.metadata?.goal_id || '';
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
      <div class="msg-bubble">${linkCitations(renderMarkdown(data.text), data.source_citations)}</div>
      ${sourceChips(data.source_citations)}
      ${extra}
    </div>`;
  div.citations = data.source_citations || [];
  div.onclick = openCitation;
  container.insertBefore(div, document.getElementById('typing-indicator'));
  container.scrollTop = container.scrollHeight;
}

// ── CITATIONS ────────────────────────────────
// Pin the session to a level the learner chose; quiz streaks stop moving it.
window.setSessionDifficulty = async (sessionId, level) => {
  await window.sentioAPI.post(`/sessions/${sessionId}/difficulty`, { difficulty: level });
  const meta = document.getElementById('active-bar-meta');
  if (meta) meta.textContent = [level, ...meta.textContent.split(' · ').slice(1)].join(' · ');
  const session = window.store?.getState('activeSession');
  if (session?.session_id === sessionId)
    window.store.setState('activeSession', { ...session, difficulty: level });
};

// Every automatic level change is visible, says why, and can be undone.
window.difficultyNotice = (change, sessionId) => {
  const notice = document.createElement('p');
  notice.className = 'difficulty-notice';
  notice.setAttribute('role', 'status');
  notice.innerHTML = `Difficulty is now <strong>${escHtml(change.to)}</strong> (${escHtml(change.reason_text)}). <button type="button" class="link-quiet">Undo</button>`;
  notice.querySelector('button').onclick = async () => {
    try {
      await window.setSessionDifficulty(sessionId, change.from);
      notice.textContent = `Difficulty stays ${change.from}. Ask in chat to change it.`;
    } catch (error) {
      toast('Difficulty not changed: ' + error.message, true);
    }
  };
  return notice;
};

function appendDifficultyNotice(change, sessionId) {
  document.getElementById('chat-messages').appendChild(window.difficultyNotice(change, sessionId));
}

// "slide 4" for PowerPoint lectures, "p.4" for other notes.
function slideOrPage(citation) {
  return /\.pptx$/i.test(citation.filename || '') ? `slide ${citation.page}` : `p.${citation.page}`;
}

function sourceChips(citations) {
  if (!citations?.length) return '';
  return `<div class="source-row">${citations
    .map(
      (c, i) =>
        `<button type="button" class="cite-chip" data-cite="${i}">${escHtml(c.filename)} · ${escHtml(slideOrPage(c))}</button>`,
    )
    .join('')}</div>`;
}

function linkCitations(html, citations) {
  (citations || []).forEach((c, i) => {
    const reference = escHtml(`[${c.filename} Page ${c.page}]`);
    html = html
      .split(reference)
      .join(
        `<button type="button" class="cite-chip inline" data-cite="${i}">${escHtml(`[${c.filename} ${slideOrPage(c)}]`)}</button>`,
      );
  });
  return html;
}

function appendSourcesPreview(citations) {
  const container = document.getElementById('chat-messages');
  const div = document.createElement('div');
  div.className = 'msg tutor sources-preview';
  div.innerHTML = `<div class="msg-body"><div class="msg-meta">Found in your notes · writing the answer…</div>${sourceChips(citations)}</div>`;
  div.citations = citations || [];
  div.onclick = openCitation;
  container.insertBefore(div, document.getElementById('typing-indicator'));
  container.scrollTop = container.scrollHeight;
  return div;
}

function showCitation(citation) {
  const modal = document.createElement('sentio-modal');
  modal.setAttribute('title', `${citation.filename} · ${slideOrPage(citation)}`);
  const passage = document.createElement('blockquote');
  passage.className = 'cited-passage';
  passage.textContent = citation.text || 'The passage text is not available.';
  modal.appendChild(passage);
  document.body.appendChild(modal);
}

function openCitation(event) {
  const chip = event.target.closest('.cite-chip');
  const citation = chip && this.citations?.[Number(chip.dataset.cite)];
  if (citation) showCitation(citation);
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
  return String(s ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
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

window.cleanupSession = cleanupSession;
