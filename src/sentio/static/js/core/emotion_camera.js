// Optional emotion-aware side feature (see docs/guides/EMOTION.md).
// A classic script loaded after tutor_runtime.js: it shares that script's globals
// (session state, toast, addLog) and stays inactive unless the server enables the
// feature and the learner consents to the camera.

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
    await window.sentioAPI.post(`/sessions/${currentSessionId}/telemetry`, payload);
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
    ['#/tutor', '#/quizzes', '#/flashcards', '#/slides'].includes(
      window.store.getState('activeRoute'),
    );
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

window.initMediaPipe = initMediaPipe;

// Show camera controls only when this installation enables the feature.
fetch(`${API}/ready`)
  .then((response) => (response.ok ? response.json() : null))
  .then((ready) => {
    document.documentElement.dataset.emotion = ready?.camera?.enabled ? 'on' : 'off';
  })
  .catch(() => {
    document.documentElement.dataset.emotion = 'off';
  });
