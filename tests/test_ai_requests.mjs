import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import vm from 'node:vm';

const timeouts = [];
const cleared = [];
const context = vm.createContext({
  window: { location: { origin: 'http://localhost' } },
  AbortController,
  FormData,
  setTimeout: (_, ms) => {
    timeouts.push(ms);
    return timeouts.length;
  },
  clearTimeout: (id) => cleared.push(id),
  fetch: async () => ({
    ok: true,
    headers: { get: () => 'application/json' },
    json: async () => ({ ok: true }),
  }),
});
const module = new vm.SourceTextModule(
  await readFile(new URL('../src/sentio/static/js/core/api.js', import.meta.url), 'utf8'),
  { context },
);
await module.link(
  () =>
    new vm.SyntheticModule(
      ['store'],
      function () {
        this.setExport('store', { getState: () => null, setState: () => {} });
      },
      { context },
    ),
);
await module.evaluate();
await module.namespace.sentioAPI.get('/subjects');
await module.namespace.sentioAPI.post('/flashcards/generate', {});
assert.deepEqual(timeouts, [30000, 370000]);
assert.equal(cleared.length, 2);

const runtime = await readFile(
  new URL('../src/sentio/static/js/core/tutor_runtime.js', import.meta.url),
  'utf8',
);
const input = { value: 'Explain forces', style: {} };
const button = { disabled: false };
let finish;
let requests = 0;
const errors = [];
const tutor = vm.createContext({
  document: { getElementById: (id) => (id === 'msg-input' ? input : button) },
  window: {},
  API: '/api/v1',
  AbortController,
  generationInProgress: false,
  sessionStart: true,
  durationTimer: 1,
  getActiveSessionId: () => 'session',
  hasSpeechSynth: false,
  recognition: null,
  voiceModeActive: false,
  appendMessage: () => {},
  showTyping: () => {},
  captureFrame: () => null,
  getAuthHeaders: () => ({}),
  toast: (message) => errors.push(message),
  setTimeout: (_, ms) => {
    assert.equal(ms, 200000);
    return 1;
  },
  clearTimeout: () => {},
  fetch: () => {
    requests++;
    return new Promise((resolve) => {
      finish = resolve;
    });
  },
});
vm.runInContext(
  runtime.slice(
    runtime.indexOf('async function sendMessage()'),
    runtime.indexOf('// ── RENDER MESSAGES'),
  ),
  tutor,
);
const pending = tutor.sendMessage();
input.value = 'Duplicate request';
await tutor.sendMessage();
assert.equal(requests, 1);
assert.equal(button.disabled, true);
finish({ ok: false, json: async () => ({ detail: 'AI provider unavailable' }) });
await pending;
assert.deepEqual(errors, ['AI provider unavailable']);
assert.equal(button.disabled, false);
assert.equal(tutor.generationInProgress, false);
console.log('AI requests use provider-compatible deadlines and prevent duplicate generation.');
