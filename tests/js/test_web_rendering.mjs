import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import vm from 'node:vm';

const malicious = '<img src=x onerror="alert(1)">';
const container = {
  innerHTML: '',
  addEventListener: () => {},
  querySelector: () => null,
  querySelectorAll: () => [],
};
const context = vm.createContext({
  window: { sentioIcon: () => '', sentioSymbol: () => '' },
  document: { getElementById: () => container },
});
async function loadView(name) {
  const module = new vm.SourceTextModule(
    await readFile(new URL(`../../src/sentio/static/js/views/${name}.js`, import.meta.url), 'utf8'),
    { context },
  );
  await module.link(async (specifier) => {
    if (specifier === '../core/html.js') {
      return new vm.SourceTextModule(
        await readFile(new URL('../../src/sentio/static/js/core/html.js', import.meta.url), 'utf8'),
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
  questions: [{ question_id: 'q0', question_text: malicious, options: [malicious, 'Safe'] }],
  provenance: {
    mode: 'source_recall',
    sources: [{ filename: malicious, page: 2 }],
    topics: [{ title: malicious, filename: 'a.pptx', first_page: 2, last_page: 3 }],
    edited: true,
  },
};
quiz.bindQuizEvents = () => {};
quiz.renderQuizActive();
assert.ok(!container.innerHTML.includes(malicious), 'Quiz renders model output as executable HTML');
assert.ok(container.innerHTML.includes('&lt;img'));
assert.ok(container.innerHTML.includes('(slides 2–3)'), 'Quiz names the slides it covers');
assert.ok(container.innerHTML.includes('Quoted from your notes'), 'Fallback quiz is labelled');
assert.ok(container.innerHTML.includes('edited by you'), 'Edited quiz is labelled');
assert.ok(container.innerHTML.includes('id="edit-question-btn"'), 'Saved question can be edited');
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

const { LibraryView, openingTitle } = await loadView('library');
assert.equal(
  openingTitle(' Microprocessor &\nComputer Architecture \nCourse code: X\nWeek 1'),
  'Microprocessor & Computer Architecture',
  'A slide title that wraps onto two lines is kept whole',
);
assert.equal(openingTitle('Stacks\nPush and pop'), 'Stacks', 'A one-line title stops at its line');
assert.equal(openingTitle('Recursion: base cases'), 'Recursion', 'A title stops at a colon');
assert.equal(openingTitle(''), '', 'Empty notes give no title');
const documents = new LibraryView('view');
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
const { ProgressView } = await loadView('progress');
new ProgressView('view').render({ topic_mastery: { [malicious]: 0.7 }, overall_mastery: 0.7 });
assert.ok(!container.innerHTML.includes(malicious));
assert.ok(container.innerHTML.includes('70%'));

const { SlidesView, answerHtml, nudgeAllowed, moodText, moodLabel, slideDocumentId } =
  await loadView('slides');
const slides = new SlidesView('view');
slides.deck = {
  document_id: 'doc',
  filename: malicious,
  slides: [
    {
      number: 1,
      title: malicious,
      text: `${malicious}
second line`,
    },
    { number: 2, title: 'Safe', text: 'Safe' },
  ],
};
slides.bindEvents = () => {};
slides.render();
assert.ok(!container.innerHTML.includes(malicious), 'Slide titles and text render as HTML');
assert.ok(container.innerHTML.includes('&lt;img'));
assert.ok(container.innerHTML.includes('id="slides-view"'));
assert.ok(container.innerHTML.includes('id="slide-text"'));
slides.deck.slides = [];
slides.render();
assert.ok(!container.innerHTML.includes(malicious), 'Slide file names render as HTML');
for (const renderer of [null, (text) => text.replace(/</g, '&lt;')]) {
  const answer = answerHtml(
    {
      text: `${malicious}

second`,
      source_citations: [{ filename: malicious, page: 3 }],
    },
    renderer,
  );
  assert.ok(!answer.includes(malicious), 'Tutor answers and citations render as HTML');
  assert.ok(answer.includes('&lt;img'));
  assert.ok(answer.includes('Slide 3'), 'Citation chips name the slide');
}
assert.equal(moodText('unsure'), 'Camera guess: unsure');
assert.equal(slideDocumentId({ metadata: { document_id: 'd1', mode: 'slides' } }), 'd1');
for (const metadata of [
  { document_id: 'd1' },
  { document_id: 'all', mode: 'slides' },
  { document_id: 'course:c', mode: 'slides' },
  { document_id: 'a,b', mode: 'slides' },
])
  assert.equal(slideDocumentId({ metadata }), null);
assert.ok(nudgeAllowed({}, 'simpler', 1000));
assert.ok(!nudgeAllowed({ simpler: 1000 }, 'simpler', 1000 + 119999));
assert.ok(nudgeAllowed({ simpler: 1000 }, 'simpler', 1000 + 120000));
assert.ok(nudgeAllowed({ simpler: 1000 }, 'break', 2000));
assert.equal(moodLabel({ label: 'unsure', fresh: true }), 'unsure');
assert.equal(moodLabel({ label: 'unsure' }), 'unsure');
assert.equal(moodLabel({ label: 'calm', fresh: false }), '', 'A stale reading shows no chip');
assert.equal(moodLabel({ label: null, fresh: true }), '', 'No label shows no chip');
