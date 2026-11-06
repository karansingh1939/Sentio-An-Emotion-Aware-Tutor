// Dev-only sample data for stress-testing the Library and Study screens.
// Loaded only when the page URL carries ?data=… (for example /?data=worst#/documents).
// Real people never add that parameter, so nothing here reaches normal use.
// While a sample set is shown, every write request is refused so the real data stays untouched.

const MODES = [
  ['demo', 'Demo data'],
  ['worst', 'Worst case'],
  ['empty', 'Empty'],
  ['one', 'One'],
  ['many', '1,000 rows'],
];

export function fixtureMode() {
  const mode = new URLSearchParams(window.location.search).get('data');
  return MODES.some(([key]) => key === mode) ? mode : null;
}

// ── Worst case: every row fails differently, within the backend's real limits ──
// Course names: max 80 chars (api/routes/courses.py:16). File names: no limit found.
// Session subject: max 120 (api/schemas.py:59). Goal text: max 500 (planning.py:25).
// Chat message: max 10,000 (api/routes/streaming.py:32).

const longCourse = 'Advanced Topics in Computational Neuroscience and Machine Learning (CS 7643)'; // 77
const worstCourses = [
  { id: 'c-long', name: longCourse },
  { id: 'c-de', name: 'Thermodynamik und Wärmeübertragungsgrundlagen für Maschinenbauingenieure' },
  { id: 'c-cjk', name: '线性代数' },
  { id: 'c-empty', name: 'Bio' },
];

const worstDocs = [
  {
    id: 'd-long',
    filename:
      'Lecture 07 — Neural Coding & Population Dynamics (FINAL, revised) v3 [annotated by TA].pptx',
    status: 'indexed',
    course_id: 'c-long',
  },
  {
    id: 'd-img',
    filename: 'IMG_20251014_091522_whiteboard_eigenvectors_and_eigenvalues_final_FINAL.jpg',
    status: 'processing',
    course_id: 'c-long',
  },
  { id: 'd-short', filename: 'a.pdf', status: 'failed', course_id: 'c-long' },
  {
    id: 'd-vi',
    filename: 'Đặng Thị Ngọc Hân — Ghi chú Vật lý đại cương (chương 1–4).docx',
    status: 'indexed',
    course_id: 'c-de',
  },
  {
    id: 'd-cjk',
    filename: '第三章 特征值与特征向量 课堂笔记.pdf',
    status: 'indexed',
    course_id: 'c-cjk',
  },
  { id: 'd-dup1', filename: 'Week 1 notes.pdf', status: 'indexed', course_id: 'c-cjk' },
  { id: 'd-dup2', filename: 'Week 1 notes.pdf', status: 'indexed', course_id: null },
  {
    id: 'd-html',
    filename: '<script>alert(1)</script> &amp; **bold** notes.txt',
    status: 'indexed',
    course_id: null,
  },
  {
    id: 'd-orphan',
    filename: 'Notes from a course that was deleted.pdf',
    status: 'indexed',
    course_id: 'c-deleted',
  },
];

const topic = (id, title, filename, extra = {}) => ({
  id,
  title,
  filename,
  first_page: 1,
  last_page: 1,
  answers: 0,
  recent_correct: 0,
  recent_total: 0,
  state: 'not_started',
  ...extra,
});

const longFile = worstDocs[0].filename;
const worstTopics = [
  topic(
    't-long',
    'Population coding, tuning curves and the Fisher information bound on decoding accuracy',
    longFile,
    {
      first_page: 12,
      last_page: 1284,
      answers: 1,
      recent_correct: 1,
      recent_total: 1,
      state: 'ready',
      review_on: 1798761600,
    },
  ),
  topic('t-short', 'ICA', longFile, {
    answers: 3,
    recent_correct: 0,
    recent_total: 3,
    state: 'review_due',
    recall: 0.4999,
  }),
  topic('t-german', 'Benachrichtigungseinstellungsverwaltungssystemarchitektur', longFile, {
    state: 'practising',
    answers: 12,
    recent_correct: 7,
    recent_total: 12,
  }),
  topic('t-html', '<b>Spike-timing</b> & "STDP"', longFile),
];

const worstProgress = {
  'c-long': {
    lectures: [{ filename: longFile, topics: worstTopics }],
    summary: { total: 4, ready: 1, review_due: 1, practising: 1, not_started: 1 },
    due: [worstTopics[1]],
    weak: [worstTopics[2]],
  },
  'c-de': {
    lectures: [{ filename: worstDocs[3].filename, topics: [] }],
    summary: { total: 0, ready: 0, review_due: 0, practising: 0, not_started: 0 },
    due: [],
    weak: [],
  },
  'c-cjk': {
    lectures: [
      {
        filename: worstDocs[4].filename,
        topics: [topic('t-cjk', '特征值与特征向量的几何意义', worstDocs[4].filename)],
      },
    ],
    summary: { total: 1, ready: 0, review_due: 0, practising: 0, not_started: 1 },
    due: [],
    weak: [],
  },
  'c-empty': {
    lectures: [],
    summary: { total: 0, ready: 0, review_due: 0, practising: 0, not_started: 0 },
    due: [],
    weak: [],
  },
};

const noSyllabus = {
  items: [],
  topics: [],
  summary: {
    percent_ready: 0,
    ready: 0,
    review_due: 0,
    practising: 0,
    not_started: 0,
    no_notes: 0,
  },
};
const worstSyllabus = {
  'c-long': {
    summary: {
      percent_ready: 100,
      ready: 1,
      review_due: 0,
      practising: 0,
      not_started: 0,
      no_notes: 1,
    },
    topics: worstTopics,
    items: [
      {
        id: 's1',
        unit: 'Unit 3: Encoding, decoding and information-theoretic limits of neural populations',
        title: 'Population coding and the Cramér–Rao bound',
        status: 'ready',
        link_mode: 'auto',
        linked_topic_id: null,
        topics: [worstTopics[0]],
      },
      {
        id: 's2',
        unit: 'Unit 3: Encoding, decoding and information-theoretic limits of neural populations',
        title: 'Dimensionality reduction',
        status: 'no_notes',
        link_mode: 'none',
        linked_topic_id: null,
        topics: [],
      },
    ],
  },
};

const longSubject =
  'Advanced Topics in Computational Neuroscience and Machine Learning (CS 7643) — revision for the final exam, weeks 1–12'; // 120
const worstSessions = [
  {
    session_id: 's-long',
    topic: 'eigenvectors_and_eigenvalues_of_symmetric_matrices_and_the_spectral_theorem',
    subject: longSubject,
    difficulty: 'advanced',
    status: 'active',
  },
  { session_id: 's-none', topic: '', subject: 'Bio', difficulty: null, status: 'ended' },
  {
    session_id: 's-cjk',
    topic: '特征值',
    subject: '线性代数',
    difficulty: 'beginner',
    status: 'ended',
  },
];

const citation = (filename, page) => ({ filename, page, text: 'Quoted passage from the notes.' });
const pastedMessage = `Here is the paragraph from my notes I don't understand, pasted exactly: ${'The Fisher information of a population of independent Poisson neurons is the sum of the individual Fisher informations, each proportional to the squared derivative of the tuning curve divided by the firing rate. '.repeat(9)}Can you explain it step by step?`;

const worstTurns = [
  {
    message:
      'What does this mean? https://example.com/courses/cs7643/lectures/week-07/neural-coding/slides?section=population-dynamics&highlight=fisher-information',
    response: {
      text: `The Fisher information sets a lower bound on decoding error [${longFile} Page 12]. In short: **steeper tuning curves carry more information**.\n\n\`\`\`python\nfisher = sum((tuning_curve_derivative(s) ** 2) / tuning_curve(s) for s in stimulus_values_across_the_whole_population)\n\`\`\``,
      strategy: 'simplify',
      answer_mode: 'generated',
      follow_up: 'Would you like to work through a two-neuron example with concrete firing rates?',
      source_citations: [
        citation(longFile, 12),
        citation(longFile, 1284),
        citation('a.pdf', 1),
        citation('第三章 特征值与特征向量 课堂笔记.pdf', 3),
        citation(worstDocs[1].filename, 1),
        citation('Week 1 notes.pdf', 2),
        citation('Week 1 notes.pdf', 2),
        citation(worstDocs[3].filename, 44),
        citation(longFile, 13),
        citation(longFile, 14),
        citation(longFile, 15),
        citation(longFile, 16),
      ],
    },
  },
  {
    message: pastedMessage,
    response: {
      text: 'Benachrichtigungseinstellungsverwaltungssystemarchitektur is one long word, so this sentence tests how the bubble wraps an unbreakable German compound.',
      strategy: 'a_strategy_the_frontend_does_not_know',
      answer_mode: 'source_excerpt',
      source_citations: [],
    },
  },
  {
    message: '<script>alert(1)</script> &amp; **bold**',
    response: { text: 'Ok.', strategy: 'standard', source_citations: [] },
  },
];

const worstGoals = [
  {
    goal_id: 'g-long',
    goal_text:
      'Be able to derive the Cramér–Rao bound for a population of independent Poisson neurons from first principles, explain every step without looking at my notes, and apply it to the two exam questions from 2023 and 2024 that Professor Wiśniewska-Kowalczyk said would be similar to this year’s, including the part about correlated noise and how it changes the bound when neighbouring neurons share inputs, which I got wrong in the mock exam and want to get right before the final on 12 December.',
  },
  { goal_id: 'g-short', goal_text: 'Pass' },
];

const worstSession = {
  session_id: 's-long',
  subject: longSubject,
  topic: worstSessions[0].topic,
  difficulty: 'advanced',
  status: 'active',
  metadata: { document_id: 'd-long', goal_id: 'g-long' },
  learning_state: 'neutral',
  total_exchanges: 1284,
  duration_minutes: 1284,
};

const worstOverview = {
  summary:
    'These slides cover how populations of neurons encode a stimulus, how well that stimulus can be decoded, and the information-theoretic limits on decoding accuracy.',
  key_concepts: [
    'Fisher information',
    'customer-feedback-from-enterprise-onboarding-style-very-long-concept-label',
    'Poisson noise',
    'ICA',
    'Tuning curves',
    'Cramér–Rao',
    'STDP',
    'PCA',
    'Decoding',
    'Correlated variability',
    'Population vector',
    'Bayes',
  ],
  suggested_questions: [
    'Why does a steeper tuning curve carry more Fisher information, and what happens at the peak where the slope is zero?',
    'What is ICA?',
  ],
};

// ── One of everything ──
const oneDocs = [{ id: 'd1', filename: 'Week 1 notes.pdf', status: 'indexed', course_id: 'c1' }];
const oneCourses = [{ id: 'c1', name: 'Biology' }];
const oneTopic = topic('t1', 'Cell structure', 'Week 1 notes.pdf', {
  answers: 1,
  recent_correct: 1,
  recent_total: 1,
  state: 'review_due',
  recall: 0.5,
});

// ── 1,000 rows ──
const manyDocs = Array.from({ length: 1000 }, (_, i) => ({
  id: `m${i}`,
  filename: `Lecture ${i + 1} — week ${Math.floor(i / 3) + 1} slides.pdf`,
  status: i % 17 === 0 ? 'failed' : i % 11 === 0 ? 'processing' : 'indexed',
  course_id: i < 40 ? 'mc' : null,
}));
const manySessions = Array.from({ length: 1000 }, (_, i) => ({
  session_id: `ms${i}`,
  topic: `topic_${i + 1}`,
  subject: 'Biology',
  difficulty: 'beginner',
  status: i === 0 ? 'active' : 'ended',
}));

const emptySummary = { total: 0, ready: 0, review_due: 0, practising: 0, not_started: 0 };
const DATA = {
  worst: {
    documents: worstDocs,
    courses: worstCourses,
    progress: (id) => worstProgress[id],
    syllabus: (id) => worstSyllabus[id] || noSyllabus,
    sessions: worstSessions,
    session: (id) => (id === 's-long' ? worstSession : undefined),
    turns: (id) => (id === 's-long' ? worstTurns : undefined),
    goals: worstGoals,
    overview: worstOverview,
    lectureTopics: (id) =>
      id === 'd-long'
        ? worstTopics
        : id === 'd-cjk'
          ? worstProgress['c-cjk'].lectures[0].topics
          : [],
  },
  empty: {
    documents: [],
    courses: [],
    progress: () => undefined,
    syllabus: () => noSyllabus,
    sessions: [],
    session: () => undefined,
    turns: () => undefined,
    goals: [],
    overview: null,
  },
  one: {
    documents: oneDocs,
    courses: oneCourses,
    progress: () => ({
      lectures: [{ filename: 'Week 1 notes.pdf', topics: [oneTopic] }],
      summary: { total: 1, ready: 0, review_due: 1, practising: 0, not_started: 0 },
      due: [oneTopic],
      weak: [],
    }),
    syllabus: () => noSyllabus,
    sessions: [
      {
        session_id: 's1',
        topic: 'cells',
        subject: 'Biology',
        difficulty: 'beginner',
        status: 'active',
      },
    ],
    session: (id) =>
      id === 's1'
        ? {
            session_id: 's1',
            subject: 'Biology',
            topic: 'cells',
            difficulty: 'beginner',
            status: 'active',
            metadata: { document_id: 'd1', goal_id: 'g1' },
            total_exchanges: 1,
            duration_minutes: 1,
          }
        : undefined,
    turns: (id) =>
      id === 's1'
        ? [
            {
              message: 'What is a cell?',
              response: {
                text: 'The basic unit of life [Week 1 notes.pdf Page 1].',
                strategy: 'standard',
                source_citations: [citation('Week 1 notes.pdf', 1)],
              },
            },
          ]
        : undefined,
    goals: [{ goal_id: 'g1', goal_text: 'Learn cell structure' }],
    overview: {
      summary: 'One lecture on cells.',
      key_concepts: ['Cell'],
      suggested_questions: ['What is a cell?'],
    },
    lectureTopics: (id) => (id === 'd1' ? [oneTopic] : []),
  },
  many: {
    documents: manyDocs,
    courses: [{ id: 'mc', name: 'Biology' }],
    progress: () => ({ lectures: [], summary: emptySummary, due: [], weak: [] }),
    syllabus: () => noSyllabus,
    sessions: manySessions,
    session: () => undefined,
    turns: () => undefined,
    goals: Array.from({ length: 1000 }, (_, i) => ({
      goal_id: `mg${i}`,
      goal_text: `Goal ${i + 1}`,
    })),
    overview: null,
  },
};

// Returns sample data for a GET path, or undefined to let the real server answer.
export function fixtureFor(endpoint) {
  const mode = fixtureMode();
  if (!mode || mode === 'demo') return undefined;
  const set = DATA[mode];
  const path = endpoint.split('?')[0];
  let m;
  if (path === '/documents') return { documents: set.documents };
  if (path === '/documents/capabilities') return { ocr_available: true };
  if (path === '/courses') return { courses: set.courses };
  if ((m = path.match(/^\/courses\/([^/]+)\/progress$/)))
    return set.progress(decodeURIComponent(m[1]));
  if ((m = path.match(/^\/courses\/([^/]+)\/syllabus$/)))
    return set.syllabus(decodeURIComponent(m[1]));
  if ((m = path.match(/^\/documents\/([^/]+)\/overview$/))) return { overview: set.overview };
  if ((m = path.match(/^\/documents\/([^/]+)\/topics$/))) {
    const id = decodeURIComponent(m[1]);
    const doc = set.documents.find((d) => d.id === id);
    const topics = (set.lectureTopics?.(id) || []).map((t) => ({ ...t, document_id: id }));
    return doc && { document_id: id, filename: doc.filename, topics };
  }
  if (path === '/sessions') return { sessions: set.sessions };
  if ((m = path.match(/^\/sessions\/([^/]+)\/turns$/))) {
    const turns = set.turns(decodeURIComponent(m[1]));
    return turns && { turns };
  }
  if ((m = path.match(/^\/sessions\/([^/]+)$/))) return set.session(decodeURIComponent(m[1]));
  if (/^\/students\/[^/]+\/goals$/.test(path)) return { goals: set.goals };
  return undefined;
}

// A plain segmented control, bottom centre. It is test chrome, not part of the design.
function mountToggle() {
  const mode = fixtureMode();
  if (!mode || document.getElementById('dev-data-toggle')) return;
  const bar = document.createElement('div');
  bar.id = 'dev-data-toggle';
  bar.setAttribute('role', 'group');
  bar.setAttribute('aria-label', 'Sample data (dev only)');
  bar.style.cssText =
    'position:fixed;left:50%;bottom:calc(12px + env(safe-area-inset-bottom, 0px));transform:translateX(-50%);z-index:30000;display:flex;gap:2px;padding:3px;border-radius:999px;background:#e4e6ea;box-shadow:0 1px 4px #0002;font:500 12px system-ui,sans-serif;';
  for (const [key, label] of MODES) {
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = label;
    button.setAttribute('aria-pressed', String(key === mode));
    button.style.cssText = `all:unset;cursor:pointer;padding:5px 10px;border-radius:999px;color:#202938;white-space:nowrap;${key === mode ? 'background:#fff;box-shadow:0 1px 2px #0002;' : ''}`;
    button.onclick = () => {
      // A sample session must not be restored once real data is back on screen.
      const sampleIds = new Set(
        Object.values(DATA).flatMap((set) => set.sessions.map((s) => s.session_id)),
      );
      if (sampleIds.has(localStorage.getItem('sentio_session_id')))
        localStorage.removeItem('sentio_session_id');
      const url = new URL(window.location.href);
      url.searchParams.set('data', key);
      window.location.replace(url.toString());
    };
    bar.appendChild(button);
  }
  document.body.appendChild(bar);
}

// app.js imports this file only when ?data=… is present; api.js reads this hook.
globalThis.sentioFixtures = {
  active: () => Boolean(fixtureMode()) && fixtureMode() !== 'demo',
  fixtureFor,
};

if (fixtureMode()) {
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mountToggle);
  else mountToggle();
}
