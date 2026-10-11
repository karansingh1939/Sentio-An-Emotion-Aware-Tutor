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
let result = { status: 'succeeded', result: { quiz_id: 'saved' } };
const state = {
  currentUser: { id: 'owner' },
  activeSessionId: 'session',
  activeRoute: '#/quizzes',
};
const context = vm.createContext({
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
      get: async () => result,
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
  await readFile(new URL('../src/sentio/static/js/core/jobs.js', import.meta.url), 'utf8'),
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
assert.equal((await run('/quizzes/jobs', {}, container)).quiz_id, 'saved');
assert.equal(saved.size, 0);
saved.set('sentio_job:owner:session:/quizzes/jobs', 'existing');
assert.equal((await run('/quizzes/jobs', {}, container)).quiz_id, 'saved');
assert.equal(submissions, 1, 'Refresh should reconnect without submitting a duplicate');
result = { status: 'cancelled' };
await assert.rejects(run('/quizzes/jobs', {}, container), /stopped before saving/);
assert.equal(saved.size, 0);
console.log('Practice jobs reconnect after refresh and report cancellation without completion.');
