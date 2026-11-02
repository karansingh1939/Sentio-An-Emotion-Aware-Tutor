import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import vm from 'node:vm';

const source = await readFile(
  new URL('../../src/sentio/static/js/core/tutor_runtime.js', import.meta.url),
  'utf8',
);
const functions = source.slice(
  source.indexOf('function renderMarkdown('),
  source.indexOf('function showTyping('),
);
const context = vm.createContext({});
vm.runInContext(functions, context);
assert.equal(
  context.renderMarkdown('<img src=x onerror="alert(1)">'),
  '&lt;img src=x onerror="alert(1)"&gt;',
);
assert.equal(context.renderMarkdown('**Safe**'), '<strong>Safe</strong>');
assert.equal(
  context.renderMarkdown('```html\n<b>example</b>\n```'),
  '<pre><code>&lt;b&gt;example&lt;/b&gt;</code></pre>',
);
console.log('Tutor rendering escapes HTML and preserves formatting.');

let renderedTutor;
context.document = {
  createElement: () => ({}),
  getElementById: () => ({
    insertBefore: (element) => {
      renderedTutor = element.innerHTML;
    },
  }),
};
context.STRATEGY_LABEL = {};
context.window = {};
context.timeNow = () => '';
vm.runInContext(
  source.slice(
    source.indexOf('function appendTutorMessage('),
    source.indexOf('function renderMarkdown('),
  ),
  context,
);
context.appendTutorMessage({ text: 'Quoted notes', answer_mode: 'source_excerpt' });
assert.match(renderedTutor, /Source excerpt: relevant passages, not a generated explanation/);
context.appendTutorMessage({
  text: 'A generated claim',
  answer_mode: 'ollama',
  source_citations: [{}],
});
assert.match(renderedTutor, /Generated explanation: check the claims against your notes/);

const cameraSource = await readFile(
  new URL('../../src/sentio/static/js/core/emotion_camera.js', import.meta.url),
  'utf8',
);
const cameraFunctions = cameraSource.slice(
  cameraSource.indexOf('async function startWebcam()'),
  cameraSource.indexOf('async function toggleWebcamDirect()'),
);
let resolvePermission;
let stopped = 0;
const state = { currentUser: { id: 'learner' }, telemetryActive: true, activeRoute: '#/tutor' };
const cameraContext = vm.createContext({
  cameraEpoch: 0,
  cameraStarting: false,
  camStream: null,
  camActive: false,
  faceLandmarker: null,
  telemetryTimer: null,
  resetTelemetryBuffer: () => {},
  startFrameStream: () => {},
  stopFrameStream: () => {},
  clearInterval: () => {},
  window: { store: { getState: (key) => state[key] } },
  navigator: {
    mediaDevices: {
      getUserMedia: () =>
        new Promise((resolve) => {
          resolvePermission = resolve;
        }),
    },
  },
  document: { getElementById: () => null },
  getActiveSessionId: () => 'session',
  initMediaPipe: async () => {
    throw new Error('Optional model unavailable');
  },
  startTrackingLoop: () => {
    throw new Error('Tracking must not start');
  },
  stopTrackingLoop: () => {},
  stopAttentionTrackingLoop: () => {},
  addLog: () => {},
  toast: () => {},
});
vm.runInContext(cameraFunctions, cameraContext);
const lateGrant = cameraContext.startWebcam();
cameraContext.stopWebcam();
state.activeRoute = '#/dashboard';
resolvePermission({ getTracks: () => [{ stop: () => stopped++ }] });
await lateGrant;
assert.equal(stopped, 1);
assert.equal(cameraContext.window.camStream, null);
assert.equal(cameraContext.camActive, false);
state.activeRoute = '#/tutor';
const failedModel = cameraContext.startWebcam();
resolvePermission({ getTracks: () => [{ stop: () => stopped++ }] });
await failedModel;
assert.ok(stopped >= 2);
assert.equal(cameraContext.window.camStream, null);
assert.equal(cameraContext.camActive, false);
assert.equal(cameraContext.cameraStarting, false);
state.telemetryActive = false;
await cameraContext.startWebcam();
assert.equal(cameraContext.camStream, null);
console.log('Late camera grants and unavailable optional models stop media tracks.');

// Live frames: one authenticated socket, bare base64 JPEG, one frame in flight, closed on stop.
const frameSource = cameraSource.slice(
  cameraSource.indexOf('const FRAME_INTERVAL_MS'),
  cameraSource.indexOf('async function startWebcam()'),
);
const sockets = [];
class FakeSocket {
  static OPEN = 1;
  static CLOSING = 2;
  constructor(url) {
    this.url = url;
    this.sent = [];
    this.readyState = 1;
    sockets.push(this);
  }
  send(data) {
    this.sent.push(JSON.parse(data));
  }
  close() {
    this.readyState = 3;
  }
}
const timers = [];
let disabled = 0;
const toasts = [];
let moodError = null;
let authToken = 'secret-token';
const subscriptions = [];
const frameContext = vm.createContext({
  WebSocket: FakeSocket,
  wsEmotion: null,
  camStream: {},
  camActive: true,
  getActiveSessionId: () => 'session 1',
  addLog: () => {},
  disableCamera: () => disabled++,
  toast: (message) => toasts.push(message),
  setInterval: (callback) => timers.push(callback) && timers.length,
  clearInterval: () => {},
  window: {
    sentioAPI: {
      get: async () => {
        if (moodError) throw moodError;
      },
    },
    location: { protocol: 'http:', host: 'localhost:8000' },
    store: {
      getState: (key) => (key === 'authToken' ? authToken : null),
      subscribe: (key, callback) => {
        subscriptions.push(callback);
        callback(authToken);
      },
    },
  },
  document: {
    getElementById: () => ({ videoWidth: 640, videoHeight: 480 }),
    createElement: () => {
      const canvas = {
        getContext: () => ({ drawImage: () => {} }),
        toDataURL: () => 'data:image/jpeg;base64,QUJD',
      };
      return canvas;
    },
  },
});
vm.runInContext(frameSource, frameContext);
vm.runInContext('startFrameStream()', frameContext);
const [socket] = sockets;
assert.equal(socket.url, 'ws://localhost:8000/api/v1/ws/session%201');
assert.ok(!socket.url.includes('secret-token'), 'The token is never in the URL');
socket.onopen();
assert.deepEqual(socket.sent, [{ access_token: 'secret-token' }]);
timers[0]();
timers[0]();
assert.deepEqual(socket.sent.slice(1), [{ frame_b64: 'QUJD' }], 'One frame awaits its reply');
socket.onmessage();
timers[0]();
assert.equal(socket.sent.length, 3);
vm.runInContext('stopFrameStream()', frameContext);
assert.equal(socket.readyState, 3);
assert.equal(frameContext.wsEmotion, null);
vm.runInContext('startFrameStream()', frameContext);
// A refusal is settled by one mood request: a renewed token needs nothing more here,
// a 403 means consent is missing, so the camera goes off once with an explanation.
sockets[1].onclose({ code: 1008 });
await new Promise((resolve) => setTimeout(resolve));
assert.equal(sockets.length, 2, 'A refused stream is not reopened');
assert.equal(frameContext.wsEmotion, null);
assert.equal(disabled, 0, 'A refusal with consent in place leaves the camera alone');
moodError = Object.assign(new Error('consent'), { status: 403 });
vm.runInContext('startFrameStream()', frameContext);
sockets[2].onclose({ code: 1008 });
await new Promise((resolve) => setTimeout(resolve));
assert.equal(disabled, 1);
assert.deepEqual(toasts, ['Camera mood needs camera consent in Settings.']);
assert.equal(sockets.length, 3);
moodError = null;
console.log('Camera frames go over one authenticated socket and stop with the camera.');

// A renewed token reopens the stream once; an inactive camera or a cleared token opens nothing.
vm.runInContext('startFrameStream()', frameContext);
vm.runInContext('startFrameStream()', frameContext);
assert.equal(subscriptions.length, 1, 'Only one token subscription exists');
const open = sockets.length;
const current = sockets.at(-1);
authToken = 'renewed-token';
subscriptions[0](authToken);
assert.equal(sockets.length, open + 1, 'A new token reopens exactly one socket');
assert.equal(current.readyState, 3);
sockets.at(-1).onopen();
assert.deepEqual(sockets.at(-1).sent, [{ access_token: 'renewed-token' }]);
subscriptions[0](authToken);
assert.equal(sockets.length, open + 1, 'The same token does not reconnect');
authToken = '';
subscriptions[0](authToken);
assert.equal(frameContext.wsEmotion, null, 'A cleared token only stops the stream');
assert.equal(sockets.length, open + 1);
frameContext.camActive = false;
authToken = 'later-token';
subscriptions[0](authToken);
assert.equal(sockets.length, open + 1, 'A token change while the camera is off opens nothing');
console.log('A renewed login token reopens the camera frame stream once.');
