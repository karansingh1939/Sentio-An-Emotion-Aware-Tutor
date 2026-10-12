import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import vm from 'node:vm';

const source = await readFile(
  new URL('../src/sentio/static/js/core/tutor_runtime.js', import.meta.url),
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

const cameraFunctions = source.slice(
  source.indexOf('async function startWebcam()'),
  source.indexOf('async function toggleWebcamDirect()'),
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
