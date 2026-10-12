import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import vm from 'node:vm';

const malicious = '<img src=x onerror="alert(1)">';
const container = { innerHTML: '', querySelector: () => null, querySelectorAll: () => [] };
const context = vm.createContext({ document: { getElementById: () => container } });
async function loadView(name) {
  const module = new vm.SourceTextModule(
    await readFile(new URL(`../src/sentio/static/js/views/${name}.js`, import.meta.url), 'utf8'),
    { context },
  );
  await module.link(async (specifier) => {
    if (specifier === '../core/html.js') {
      return new vm.SourceTextModule(
        await readFile(new URL('../src/sentio/static/js/core/html.js', import.meta.url), 'utf8'),
        { context },
      );
    }
    const imports = {
      sentioAPI: {},
      store: { getState: () => null },
      toast: () => {},
      runPracticeJob: () => {},
      pendingJobKey: () => '',
    };
    return new vm.SyntheticModule(
      Object.keys(imports),
      function () {
        for (const [key, value] of Object.entries(imports)) this.setExport(key, value);
      },
      { context },
    );
  });
  await module.evaluate();
  return module.namespace;
}

const { QuizzesView } = await loadView('quizzes');
const quiz = new QuizzesView('view');
quiz.quiz = {
  title: malicious,
  questions: [{ question_text: malicious, options: [malicious, 'Safe'] }],
};
quiz.bindQuizEvents = () => {};
quiz.renderQuizActive();
assert.ok(!container.innerHTML.includes(malicious), 'Quiz renders model output as executable HTML');
assert.ok(container.innerHTML.includes('&lt;img'));
quiz.results = {
  total_score: 0,
  passed: false,
  summary: malicious,
  feedback: [
    {
      is_correct: false,
      question_index: 0,
      student_answer: malicious,
      correct_answer: malicious,
      explanation: malicious,
    },
  ],
};
container.querySelector = () => ({});
quiz.renderResults();
assert.ok(
  !container.innerHTML.includes(malicious),
  'Quiz feedback renders student answers as HTML',
);
container.querySelector = () => null;

const { FlashcardsView } = await loadView('flashcards');
const cards = new FlashcardsView('view');
cards.decks = [{ deck_name: malicious, deck_id: 'deck', created_at: 1, due_count: 1 }];
cards.bindDeckEvents = () => {};
cards.renderDeckBrowser();
assert.ok(!container.innerHTML.includes(malicious), 'Deck names render as executable HTML');

const { DocumentsView } = await loadView('documents');
const documents = new DocumentsView('view');
documents.documents = [{ filename: malicious, id: 'doc', category: 'notes', status: 'indexed' }];
documents.bindEvents = () => {};
documents.render();
assert.ok(!container.innerHTML.includes(malicious), 'Document names render as executable HTML');
console.log('Study-tool HTML is escaped.');

const { HistoryView } = await loadView('history');
new HistoryView('view').render([
  { topic: malicious, subject: 'physics', status: 'closed', created_at: 1 },
]);
assert.ok(!container.innerHTML.includes(malicious));
assert.ok(container.innerHTML.includes('physics'));
const { AnalyticsView } = await loadView('analytics');
new AnalyticsView('view').render({ topic_mastery: { [malicious]: 0.7 }, overall_mastery: 0.7 });
assert.ok(!container.innerHTML.includes(malicious));
assert.ok(container.innerHTML.includes('70%'));

const { WhiteboardView } = await loadView('whiteboard');
const board = new WhiteboardView('view');
board.title = malicious;
board.render();
assert.ok(!container.innerHTML.includes(malicious));
board.redraw = () => {};
board.shapes = [{ type: 'text', text: 'Saved sketch' }];
board.undoStack = [JSON.parse(JSON.stringify(board.shapes))];
board.shapes.push({ type: 'text', text: 'New note' });
board.recordState();
board.undo();
assert.equal(board.shapes.length, 1);
assert.equal(board.shapes[0].text, 'Saved sketch');
board.redo();
assert.equal(board.shapes.length, 2);
board.undo();
assert.equal(board.shapes.length, 1);
board.canvas = {
  width: 1000,
  height: 750,
  getBoundingClientRect: () => ({ left: 10, top: 20, width: 500, height: 375 }),
};
assert.equal(board.getMousePos({ clientX: 260, clientY: 207.5 }).x, 500);
assert.equal(board.getMousePos({ clientX: 260, clientY: 207.5 }).y, 375);
board.zoomLevel = 0.5;
assert.equal(board.getMousePos({ clientX: 510, clientY: 395 }).x, 1000);
assert.equal(board.getMousePos({ clientX: 510, clientY: 395 }).y, 750);
console.log(
  'Whiteboard titles are escaped; undo preserves loaded drawings and pointer coordinates scale correctly.',
);
