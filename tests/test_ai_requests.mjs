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

async function authClient(fetcher) {
  const state = {
    currentUser: { id: 'owner-a' },
    authToken: 'expired',
    refreshToken: 'refresh-a',
    loading: false,
  };
  let logouts = 0;
  const sandbox = vm.createContext({
    window: { location: { origin: 'http://localhost' } },
    AbortController,
    FormData,
    setTimeout: () => 1,
    clearTimeout: () => {},
    toast: () => {},
    fetch: (...args) => fetcher(state, ...args),
  });
  const apiModule = new vm.SourceTextModule(
    await readFile(new URL('../src/sentio/static/js/core/api.js', import.meta.url), 'utf8'),
    { context: sandbox },
  );
  await apiModule.link(
    () =>
      new vm.SyntheticModule(
        ['store'],
        function () {
          this.setExport('store', {
            getState: (key) => state[key],
            setState: (key, value) => {
              state[key] = value;
            },
            clearAuth: () => {
              logouts++;
              state.authToken = null;
              state.currentUser = null;
            },
          });
        },
        { context: sandbox },
      ),
  );
  await apiModule.evaluate();
  return { api: apiModule.namespace.sentioAPI, state, logouts: () => logouts };
}
const reply = (ok, data, status = 200) => ({
  ok,
  status,
  headers: { get: () => 'application/json' },
  json: async () => data,
});
let releaseRefresh,
  refreshCalls = 0;
const concurrent = await authClient((state, url, options) => {
  if (url.endsWith('/auth/refresh')) {
    refreshCalls++;
    return new Promise((resolve) => {
      releaseRefresh = resolve;
    });
  }
  return Promise.resolve(
    options.headers.Authorization === 'Bearer renewed'
      ? reply(true, { ok: true })
      : reply(false, { detail: 'Expired' }, 401),
  );
});
const left = concurrent.api.get('/left'),
  right = concurrent.api.get('/right');
await new Promise((resolve) => setImmediate(resolve));
assert.equal(refreshCalls, 1);
releaseRefresh(reply(true, { access_token: 'renewed' }));
await Promise.all([left, right]);
assert.equal(concurrent.state.authToken, 'renewed');
assert.equal(concurrent.logouts(), 0);
assert.equal(concurrent.api.pending, 0);

let lateRefresh;
const switched = await authClient((state, url) =>
  url.endsWith('/auth/refresh')
    ? new Promise((resolve) => {
        lateRefresh = resolve;
      })
    : Promise.resolve(reply(false, {}, 401)),
);
const oldRequest = switched.api.get('/private');
await new Promise((resolve) => setImmediate(resolve));
Object.assign(switched.state, {
  currentUser: { id: 'owner-b' },
  authToken: 'new-account',
  refreshToken: 'refresh-b',
});
lateRefresh(reply(true, { access_token: 'old-account-renewed' }));
await assert.rejects(oldRequest, /account changed/);
assert.equal(switched.state.authToken, 'new-account');
assert.equal(switched.logouts(), 0);

let lateBody;
const bodyChanged = await authClient(() =>
  Promise.resolve({
    ok: true,
    headers: { get: () => 'application/json' },
    json: () =>
      new Promise((resolve) => {
        lateBody = resolve;
      }),
  }),
);
const oldBody = bodyChanged.api.get('/private');
await new Promise((resolve) => setImmediate(resolve));
Object.assign(bodyChanged.state, {
  currentUser: { id: 'owner-b' },
  authToken: 'new-account',
  refreshToken: 'refresh-b',
});
lateBody({ private_old_account: true });
await assert.rejects(oldBody, /account changed/);
console.log(
  'Concurrent refresh is shared; late refresh and private response bodies cannot replace a new account.',
);
