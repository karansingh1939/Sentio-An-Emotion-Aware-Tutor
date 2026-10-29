import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import vm from 'node:vm';

const saved = new Map();
const status = {};
const stop = {};
const container = {
  innerHTML: '',
  querySelector: (selector) => (selector === 'button' ? stop : status),
};
let submissions = 0;
let liveContext = { source: 'notes-a' };
let result = {
  status: 'succeeded',
  study_context: { source: 'notes-a' },
  result: { quiz_id: 'saved' },
};
const state = {
  currentUser: { id: 'owner' },
  activeSessionId: 'session',
  activeRoute: '#/quizzes',
};
const context = vm.createContext({
  crypto: { randomUUID: () => 'request-unique-001' },
  localStorage: {
    getItem: (key) => saved.get(key),
    setItem: (key, value) => saved.set(key, value),
    removeItem: (key) => saved.delete(key),
  },
  setTimeout: (callback) => callback(),
});
const imports = {
  './api.js': {
    sentioAPI: {
      post: async () => {
        submissions++;
        return { job_id: 'job' };
      },
      get: async (endpoint) => (endpoint.endsWith('/context') ? liveContext : result),
    },
  },
  './store.js': {
    store: {
      getState: (key) => state[key],
      subscribe: (_, callback) => {
        callback(state.activeRoute);
        return () => {};
      },
    },
  },
};
const module = new vm.SourceTextModule(
  await readFile(new URL('../../src/sentio/static/js/core/jobs.js', import.meta.url), 'utf8'),
  { context },
);
await module.link(
  (specifier) =>
    new vm.SyntheticModule(
      Object.keys(imports[specifier]),
      function () {
        for (const [key, value] of Object.entries(imports[specifier])) this.setExport(key, value);
      },
      { context },
    ),
);
await module.evaluate();
const run = module.namespace.runPracticeJob;
assert.match(
  module.namespace.progressText('preparing semantic index', '/documents/jobs'),
  /notes searchable/,
);
assert.match(
  module.namespace.progressText('extracting document text', '/documents/jobs'),
  /Reading the text/,
);
assert.equal((await run('/quizzes/jobs', {}, container)).quiz_id, 'saved');
assert.equal(saved.size, 0);
saved.set('sentio_job:owner:session:/quizzes/jobs', 'existing');
assert.equal((await run('/quizzes/jobs', {}, container)).quiz_id, 'saved');
assert.equal(submissions, 1, 'Refresh should reconnect without submitting a duplicate');
result = { status: 'cancelled' };
await assert.rejects(run('/quizzes/jobs', {}, container), /stopped before saving/);
assert.equal(saved.size, 0);
console.log('Practice jobs reconnect after refresh and report cancellation without completion.');

const receivedKeys = [];
imports['./api.js'].sentioAPI.post = async (endpoint, body, options) => {
  receivedKeys.push(options.headers['Idempotency-Key']);
  if (receivedKeys.length === 1) throw new Error('Network response lost');
  return { job_id: 'recovered-submission' };
};
result = {
  status: 'succeeded',
  study_context: { source: 'notes-a' },
  result: { quiz_id: 'recovered' },
};
await assert.rejects(run('/quizzes/jobs', {}, container), /response lost/);
assert.equal((await run('/quizzes/jobs', {}, container)).quiz_id, 'recovered');
assert.equal(receivedKeys[0], receivedKeys[1], 'Unknown POST outcome must reuse the submission ID');
assert.equal(saved.size, 0);
liveContext = { source: 'notes-b' };
assert.equal(await run('/quizzes/jobs', {}, container), null);
assert.match(status.textContent, /earlier study sources/);
assert.equal(saved.size, 0);
console.log(
  'Completed practice from earlier sources is retained without painting the current study context.',
);
