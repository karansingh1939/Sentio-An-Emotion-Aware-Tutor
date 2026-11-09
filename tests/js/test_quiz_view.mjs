// Run: node --experimental-vm-modules tests/js/test_quiz_view.mjs
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import vm from 'node:vm';
import {
  describeFocus,
  describeProvenance,
  escapeHtml,
} from '../../src/sentio/static/js/core/html.js';

const fields = Object.fromEntries(
  ['subject', 'topic', 'difficulty'].map((name) => [`#quiz-${name}`, { parentElement: {} }]),
);
fields['#generate-quiz-btn'] = {};
fields['#quiz-context'] = {};
const radio = {};
const container = {
  innerHTML: '',
  querySelector: (selector) => fields[selector] || null,
  querySelectorAll: () => [radio],
};
const session = {
  subject: 'physics',
  topic: "Newton's First Law",
  difficulty: 'beginner',
  status: 'active',
};
let submission;
const context = vm.createContext({
  window: { sentioIcon: () => '', sentioSymbol: () => '' },
  document: { getElementById: () => container },
});
const api = {
  get: async (path) => {
    assert.equal(path, '/sessions/session-a');
    return session;
  },
  post: async (path, body, options) => {
    submission = { path, body, options };
    return { total_score: 1 };
  },
};
const imports = {
  '../core/jobs.js': {
    pendingJobKey: (endpoint) => `job:${endpoint}`,
    runPracticeJob: async (path, body) => {
      submission = { path, body };
      return { questions: [] };
    },
  },
  '../core/html.js': { describeFocus, describeProvenance, escapeHtml },
  '../core/api.js': { sentioAPI: api },
  '../core/store.js': {
    store: { getState: (key) => (key === 'activeSessionId' ? 'session-a' : null) },
  },
  '../components/ui.js': { toast: (message) => assert.fail(message) },
};
const module = new vm.SourceTextModule(
  await readFile(new URL('../../src/sentio/static/js/views/quizzes.js', import.meta.url), 'utf8'),
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
const view = new module.namespace.QuizzesView('quiz-container');
await view.renderSetupForm();
for (const key of ['subject', 'topic', 'difficulty']) {
  assert.equal(fields[`#quiz-${key}`].value, session[key]);
  assert.equal(fields[`#quiz-${key}`].parentElement.hidden, true);
}
assert.equal(fields['#generate-quiz-btn'].disabled, false);
fields['#quiz-num-questions'] = { value: '3' };
view.render = () => {};
await view.generateQuiz();
assert.equal(submission.path, '/quizzes/jobs');
assert.equal(submission.body.topic, session.topic);
assert.equal(submission.body.session_id, 'session-a');

for (const options of [
  ['True', 'False'],
  ['An external net force', 'Nothing', 'Color', 'Name'],
]) {
  view.quiz = { quiz_id: 'quiz-a', questions: [{ options }] };
  view.bindQuizEvents();
  radio.onchange({ target: { value: 'A' } });
  assert.equal(view.answers[0], options[0]);
  view.render = () => {};
  await view.submitQuiz();
  assert.equal(submission.path, '/quizzes/quiz-a/submit');
  assert.equal(submission.body.session_id, 'session-a');
  assert.equal(submission.body.answers[0], options[0]);
  assert.equal(submission.options.timeout, 370000);
}
console.log('Quiz UI contract checks passed (session defaults, MCQ/TF answers, quiz ID).');
