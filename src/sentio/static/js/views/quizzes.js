import { describeProvenance, escapeHtml } from '../core/html.js';
// Quizzes View Controller for Sentio (ES Module)
import { sentioAPI } from '../core/api.js';
import { store } from '../core/store.js';
import { toast } from '../components/ui.js';
import { runPracticeJob } from '../core/jobs.js';

function renderCheck(result) {
  if (!result) return '';
  return `<div class="answer-feedback ${result.is_correct ? 'correct' : 'incorrect'}" role="status"><strong>${result.is_correct ? 'Correct' : `Not quite. Answer: ${escapeHtml(result.correct_answer)}`}</strong><p>${escapeHtml(result.explanation)}</p></div>`;
}

export class QuizzesView {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
    this.studentId = 'stu_001';
    this.quiz = null;
    this.currentQuestionIdx = 0;
    this.answers = {};
    this.checks = {};
    this.results = null;
    this.isReviewMode = false;
    this.revision = 0;
  }

  init() {
    store.subscribe('activeRoute', (route) => {
      if (route === '#/quizzes') {
        this.studentId = store.getState('currentUser')?.id || 'stu_001';
        this.resetQuizState();
        this.render();
      } else this.revision++;
    });
  }

  resetQuizState() {
    this.quiz = null;
    this.currentQuestionIdx = 0;
    this.answers = {};
    this.checks = {};
    this.results = null;
    this.isReviewMode = false;
  }

  render() {
    if (this.results) {
      this.renderResults();
    } else if (this.quiz) {
      this.renderQuizActive();
    } else {
      this.renderSetupForm();
    }
  }

  async renderSetupForm() {
    const revision = ++this.revision;
    const owner = store.getState('currentUser')?.id;
    this.container.innerHTML = `
      <div class="view-header view-header">
        <h2 class="page-title">Check your understanding</h2>
        <p class="muted">Answer questions, read the explanations, then revisit anything you missed.</p>
      </div>

      <div style="max-width:550px;width:100%;margin:0 auto;">
        <sentio-card title="Make a quiz">
          <p id="quiz-context" role="status">${store.getState('activeSessionId') ? 'Loading your study topic…' : 'First choose Study beside a document in your Library. Saved quizzes below can be used at any time.'}</p>
          ${store.getState('activeSessionId') ? '<a href="#/tutor">Change what you are studying</a>' : '<a class="workspace-action" href="#/documents">Choose notes</a>'}
          <div style="display:flex;flex-direction:column;gap:14px;margin-top:10px;">
            <div>
              <label class="form-label" for="quiz-subject">Subject</label>
<select class="input" id="quiz-subject">
                <option value="physics">Physics</option>
                <option value="computer_science">Computer Science</option>
                <option value="mathematics">Mathematics</option>
                <option value="chemistry">Chemistry</option>
                <option value="biology">Biology</option>
              </select>
            </div>

            <div>
              <label class="form-label" for="quiz-topic">Topic</label>
<input class="input" type="text" id="quiz-topic" value="" placeholder="Choose a study topic" aria-label="Quiz topic" />
            </div>

            <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
              <div>
                <label class="form-label" for="quiz-difficulty">Difficulty</label>
<select class="input" id="quiz-difficulty">
                  <option value="beginner">Beginner</option>
                  <option value="intermediate" selected>Intermediate</option>
                  <option value="advanced">Advanced</option>
                </select>
              </div>
              <div>
                <label class="form-label" for="quiz-num-questions">Number of Questions</label>
<select class="input" id="quiz-num-questions">
                  <option value="1">1 Question</option>
                  <option value="3" selected>3 Questions</option>
                  <option value="5">5 Questions</option>
                </select>
              </div>
            </div>

            <button id="generate-quiz-btn" style="margin-top:10px;background:var(--accent);color:var(--bg);border:none;padding:12px;border-radius:var(--radius);font-family:var(--mono);font-weight:bold;cursor:pointer;font-size:14px;transition:opacity 0.2s;">
              Make a quiz
            </button>
          </div>
        </sentio-card>
      </div>
    `;

    this.container.innerHTML +=
      '<div id="saved-practice"><p role="status">Loading saved practice and mistakes…</p></div>';
    this.loadSavedPractice(revision, owner);
    this.container.querySelector('#generate-quiz-btn').onclick = () => this.generateQuiz();
    const sessionId = store.getState('activeSessionId');
    this.container.querySelector('#generate-quiz-btn').disabled = !sessionId;
    for (const field of ['subject', 'topic', 'difficulty']) {
      this.container.querySelector(`#quiz-${field}`).parentElement.hidden = true;
    }
    if (sessionId) {
      const button = this.container.querySelector('#generate-quiz-btn');
      button.disabled = true;
      try {
        const session = await sentioAPI.get(`/sessions/${sessionId}`);
        if (revision !== this.revision || store.getState('currentUser')?.id !== owner) return;
        for (const field of ['subject', 'topic', 'difficulty']) {
          const input = this.container.querySelector(`#quiz-${field}`);
          if (input) input.value = session[field];
          if (input) input.disabled = true;
        }
        this.container.querySelector('#quiz-context').textContent =
          `Practising ${session.topic}. Uses the same notes as your study session.`;
        button.disabled = session.status !== 'active';
        if (session.status !== 'active')
          this.container.querySelector('#quiz-context').textContent =
            'This study session has ended. Choose notes to start a new one, or use saved quizzes below.';
      } catch (e) {
        toast('Failed to load quiz session: ' + e.message, true);
      }
    }
  }

  async loadSavedPractice(revision, owner) {
    const panel = this.container.querySelector('#saved-practice');
    if (!panel) return;
    const [quizzes, feedback] = await Promise.allSettled([
      sentioAPI.get('/quizzes?limit=20'),
      sentioAPI.get('/study/feedback'),
    ]);
    if (
      revision !== this.revision ||
      store.getState('currentUser')?.id !== owner ||
      store.getState('activeRoute') !== '#/quizzes'
    )
      return;
    panel.innerHTML = `<sentio-card title="Saved quizzes">${quizzes.status === 'fulfilled' ? `<ul class="study-list">${(quizzes.value.quizzes || []).map((quiz) => `<li><button class="workspace-action saved-quiz" data-id="${escapeHtml(quiz.quiz_id)}">${escapeHtml(quiz.title)}</button>${quiz.provenance ? `<br><small>${escapeHtml(describeProvenance(quiz.provenance))}</small>` : ''}</li>`).join('') || '<li>No saved quizzes yet.</li>'}</ul>` : '<p role="alert">Saved quizzes unavailable. Reopen Review to retry.</p>'}</sentio-card><sentio-card title="Mistake review">${feedback.status === 'fulfilled' ? `<p>${escapeHtml(feedback.value.summary)}</p><ul class="study-list">${feedback.value.mistakes.map((mistake) => `<li><strong>${escapeHtml(mistake.topic)}</strong><p>${escapeHtml(mistake.question_text)}</p><small>Your answer: ${escapeHtml(mistake.student_answer)}</small><p>Revisit the explanation in your saved quiz or study notes before trying again.</p></li>`).join('')}</ul>` : '<p role="alert">Practice evidence unavailable.</p>'}</sentio-card>`;
    panel.querySelectorAll('.saved-quiz').forEach((button) => {
      button.onclick = async () => {
        button.disabled = true;
        try {
          const quiz = await sentioAPI.get(`/quizzes/${button.dataset.id}`);
          if (
            revision !== this.revision ||
            store.getState('currentUser')?.id !== owner ||
            store.getState('activeRoute') !== '#/quizzes'
          )
            return;
          this.quiz = quiz;
          this.answers = {};
          this.checks = {};
          this.currentQuestionIdx = 0;
          this.results = null;
          this.render();
        } catch (error) {
          toast(error.message, true);
          button.disabled = false;
        }
      };
    });
  }

  async generateQuiz() {
    const subject = this.container.querySelector('#quiz-subject').value;
    const topic = this.container.querySelector('#quiz-topic').value.trim();
    const difficulty = this.container.querySelector('#quiz-difficulty').value;
    const numQuestions = parseInt(this.container.querySelector('#quiz-num-questions').value, 10);
    const activeSessionId = store.getState('activeSessionId');

    if (!topic) {
      toast('Topic cannot be empty', true);
      return;
    }

    if (!activeSessionId) {
      toast('Please start or resume a tutoring session first to generate a quiz.', true);
      return;
    }

    this.container.innerHTML = `
      <div class="center-state">
        <sentio-loader size="36px"></sentio-loader>
        <span class="accent-strong">AI is custom-crafting your assessment...</span>
      </div>
    `;

    try {
      const res = await runPracticeJob(
        '/quizzes/jobs',
        {
          student_id: this.studentId,
          session_id: activeSessionId,
          subject,
          topic,
          difficulty,
          num_questions: numQuestions,
        },
        this.container,
      );
      if (!res) return;

      this.quiz = res;
      this.currentQuestionIdx = 0;
      this.answers = {};
      this.checks = {};
      this.render();
    } catch (e) {
      toast('Failed to generate quiz: ' + e.message, true);
      this.resetQuizState();
      this.render();
    }
  }

  renderQuizActive() {
    const q = this.quiz.questions[this.currentQuestionIdx];
    const totalQ = this.quiz.questions.length;
    const selectedAns = this.answers[this.currentQuestionIdx] || '';

    this.container.innerHTML = `
      <div class="view-header view-header row-between">
        <div>
          <h2 class="page-title">${escapeHtml(this.quiz.title || 'Dynamic Assessment')}</h2>
          <p class="muted">Select your answer and navigate using the controls below.</p>
          ${this.quiz.provenance ? `<p class="practice-provenance"><small>${escapeHtml(describeProvenance(this.quiz.provenance))}</small></p>` : ''}
        </div>
        <span class="badge">
          Question ${this.currentQuestionIdx + 1} of ${totalQ}
        </span>
      </div>

      <div style="max-width:650px;width:100%;margin:0 auto;display:flex;flex-direction:column;gap:20px;">
        ${q.question_id ? '<div class="card-toolbar"><span></span><button class="workspace-action" type="button" id="edit-question-btn">Edit this question</button></div>' : ''}
        <sentio-card title="Concept Check">
          <p style="font-size:13px;line-height:1.5;color:var(--text);margin-bottom:16px;font-weight:500;">
            ${escapeHtml(q.question_text)}
          </p>

          <div style="display:flex;flex-direction:column;gap:10px;">
            ${
              q.options
                ? q.options
                    .map((opt, idx) => {
                      const char = String.fromCharCode(65 + idx); // A, B, C...
                      const isChecked = selectedAns === opt;
                      return `
                <label style="border:1px solid ${isChecked ? 'var(--accent)' : 'var(--border)'};background:${isChecked ? 'rgba(0,200,255,0.05)' : 'var(--bg3)'};border-radius:var(--radius);padding:12px;display:flex;align-items:center;gap:12px;cursor:pointer;transition:border-color 0.2s, background 0.2s;">
                  <input type="radio" name="quiz-opt" value="${char}" ${isChecked ? 'checked' : ''} style="accent-color:var(--accent);" />
                  <span style="font-family:var(--mono);font-size:14px;font-weight:bold;color:var(--accent);">${char}.</span>
                  <span style="font-size:14px;color:var(--text);">${escapeHtml(opt)}</span>
                </label>
              `;
                    })
                    .join('')
                : `
              <input type="text" id="short-answer-input" value="${escapeHtml(selectedAns)}" placeholder="Type your answer here..." style="width:100%;background:var(--bg3);border:1px solid var(--border);border-radius:var(--radius);padding:10px;color:var(--text);font-family:var(--mono);font-size:14px;outline:none;" />
            `
            }
          </div>
          ${q.question_id ? `<div class="btn-row quiz-check"><button class="workspace-action" type="button" id="check-answer-btn" ${selectedAns ? '' : 'disabled'}>Check answer</button></div>` : ''}
          ${renderCheck(this.checks[this.currentQuestionIdx])}
        </sentio-card>

        <div class="row-between">
          <button id="prev-question-btn" class="workspace-action" ${this.currentQuestionIdx === 0 ? 'disabled' : ''}>
            ◀ Previous
          </button>
          
          ${
            this.currentQuestionIdx === totalQ - 1
              ? `
            <button id="submit-quiz-btn" style="background:var(--green);color:var(--bg);border:none;padding:8px 20px;border-radius:var(--radius);font-weight:bold;cursor:pointer;font-family:var(--mono);font-size:14px;">
              Submit Quiz
            </button>
          `
              : `
            <button id="next-question-btn" style="background:var(--accent);color:var(--bg);border:none;padding:8px 20px;border-radius:var(--radius);font-weight:bold;cursor:pointer;font-family:var(--mono);font-size:14px;">
              Next ▶
            </button>
          `
          }
        </div>
      </div>
    `;

    this.bindQuizEvents();
  }

  bindQuizEvents() {
    const totalQ = this.quiz.questions.length;
    const editButton = this.container.querySelector('#edit-question-btn');
    if (editButton) editButton.onclick = () => this.editCurrentQuestion();

    // Save state on change
    const options = this.container.querySelectorAll('input[name="quiz-opt"]');
    options.forEach((opt) => {
      opt.onchange = (e) => {
        const index = e.target.value.charCodeAt(0) - 65;
        this.answers[this.currentQuestionIdx] =
          this.quiz.questions[this.currentQuestionIdx].options[index];
        this.clearCheck();
      };
    });

    const textInput = this.container.querySelector('#short-answer-input');
    if (textInput) {
      textInput.oninput = (e) => {
        this.answers[this.currentQuestionIdx] = e.target.value;
        this.clearCheck();
      };
    }

    // Nav actions
    const prev = this.container.querySelector('#prev-question-btn');
    if (prev && this.currentQuestionIdx > 0) {
      prev.onclick = () => {
        this.currentQuestionIdx--;
        this.render();
      };
    }

    const next = this.container.querySelector('#next-question-btn');
    if (next && this.currentQuestionIdx < totalQ - 1) {
      next.onclick = () => {
        this.currentQuestionIdx++;
        this.render();
      };
    }

    const submit = this.container.querySelector('#submit-quiz-btn');
    if (submit) {
      submit.onclick = () => this.submitQuiz();
    }

    const check = this.container.querySelector('#check-answer-btn');
    if (check) check.onclick = () => this.checkAnswer();
  }

  // An edited answer invalidates its earlier check.
  clearCheck() {
    delete this.checks[this.currentQuestionIdx];
    this.container.querySelector('.answer-feedback')?.remove();
    const check = this.container.querySelector('#check-answer-btn');
    if (check) check.disabled = !this.answers[this.currentQuestionIdx]?.trim();
  }

  async checkAnswer() {
    const quiz = this.quiz;
    const index = this.currentQuestionIdx;
    const question = quiz.questions[index];
    const button = this.container.querySelector('#check-answer-btn');
    button.disabled = true;
    try {
      const result = await sentioAPI.post(
        `/quizzes/${quiz.quiz_id}/questions/${question.question_id}/check`,
        { answer: this.answers[index] },
      );
      if (this.quiz !== quiz) return;
      this.checks[index] = result;
      if (this.currentQuestionIdx === index) this.render();
    } catch (error) {
      toast(error.message, true);
      button.disabled = false;
    }
  }

  async submitQuiz() {
    const revision = this.revision;
    const owner = store.getState('currentUser')?.id;
    const activeSessionId = this.quiz?.session_id || store.getState('activeSessionId');
    this.container.innerHTML = `
      <div class="center-state">
        <sentio-loader size="36px"></sentio-loader>
        <span class="accent-strong">Grading responses and updating student memory...</span>
      </div>
    `;

    try {
      const res = await sentioAPI.post(
        `/quizzes/${this.quiz.quiz_id}/submit`,
        {
          session_id: activeSessionId,
          answers: this.answers,
        },
        { timeout: 180000 * (this.quiz.questions.length + 1) + 10000 },
      );
      if (
        revision !== this.revision ||
        owner !== store.getState('currentUser')?.id ||
        store.getState('activeRoute') !== '#/quizzes'
      )
        return;
      this.results = res;
      this.render();
    } catch (e) {
      toast('Failed to submit quiz: ' + e.message, true);
      this.render();
    }
  }

  renderResults() {
    const correctCount = this.results.feedback.filter((f) => f.is_correct).length;
    const totalQ = this.results.feedback.length;
    const scorePct = Math.round(this.results.total_score * 100);
    const passed = this.results.passed;

    this.container.innerHTML = `
      <div class="view-header view-header">
        <h2 class="page-title">Assessment Results</h2>
        <p class="muted">Review explanations and pedagogical feedback to improve retention.</p>
      </div>

      <div style="max-width:700px;width:100%;margin:0 auto;display:flex;flex-direction:column;gap:20px;">
        <!-- Summary Scorecard -->
        <sentio-card title="Grading Summary">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;">
            <div>
              <div style="font-size:32px;font-weight:bold;color:${passed ? 'var(--green)' : 'var(--red)'};">${scorePct}%</div>
              <div style="font-size:14px;color:var(--text-dim);margin-top:4px;">Correct answers: <strong>${correctCount} of ${totalQ}</strong></div>
            </div>
            <span style="background:${passed ? 'rgba(78,205,196,0.1)' : 'rgba(255,80,96,0.1)'};color:${passed ? 'var(--green)' : 'var(--red)'};border:1px solid ${passed ? 'rgba(78,205,196,0.2)' : 'rgba(255,80,96,0.2)'};padding:6px 12px;border-radius:20px;font-size:14px;font-weight:bold;font-family:var(--mono);">
              ${passed ? 'PASSED' : 'RETRY ADVISED'}
            </span>
          </div>
          <p class="muted">${escapeHtml(this.results.summary)}</p>
          ${this.quiz.questions.some((q) => q.question_type === 'short_answer') ? '<p class="muted">Short-answer scores are practice feedback. AI grading can misjudge valid wording; compare your answer with the reference and explanation below.</p>' : ''}
        </sentio-card>

        <!-- Detailed Feedback -->
        <sentio-card title="Detailed Questions Review">
          <div class="stack stack-lg">
            ${this.results.feedback
              .map((f, idx) => {
                const qOriginal = this.quiz.questions[f.question_index];
                return `
                <div style="border:1px solid var(--border);border-radius:var(--radius);padding:12px;background:var(--bg3);display:flex;flex-direction:column;gap:6px;">
                  <div class="row-between">
                    <span style="font-weight:bold;font-size:14px;color:var(--text);">Question ${idx + 1}</span>
                    <span style="color:${f.is_correct ? 'var(--green)' : 'var(--red)'};font-weight:bold;font-size:14px;">
                      ${f.is_correct ? '✅ CORRECT' : '❌ INCORRECT'}
                    </span>
                  </div>
                  <p style="font-size:14px;color:var(--text);line-height:1.4;margin:4px 0;">${escapeHtml(qOriginal.question_text)}</p>
                  <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;font-size:14px;background:var(--bg2);padding:8px;border-radius:var(--radius);border:1px solid var(--border);">
                    <div>Your Answer: <strong style="color:${f.is_correct ? 'var(--green)' : 'var(--red)'};">${escapeHtml(f.student_answer || 'N/A')}</strong></div>
                    <div>Correct Answer: <strong style="color:var(--green);">${escapeHtml(f.correct_answer)}</strong></div>
                  </div>
                  <details style="margin-top:6px;">
                    <summary style="font-size:14px;color:var(--accent);cursor:pointer;outline:none;">Explanation</summary>
                    <p style="font-size:14px;color:var(--text-dim);line-height:1.4;margin-top:6px;">${escapeHtml(f.explanation)}</p>
                  </details>
                </div>
              `;
              })
              .join('')}
          </div>
        </sentio-card>

        <button id="close-quiz-btn" style="background:var(--accent);color:var(--bg);border:none;padding:12px;border-radius:var(--radius);font-weight:bold;cursor:pointer;font-family:var(--mono);font-size:14px;">
          Return to Learning Center
        </button>
      </div>
    `;

    this.container.querySelector('#close-quiz-btn').onclick = () => {
      this.resetQuizState();
      this.render();
    };
  }

  editCurrentQuestion() {
    const quiz = this.quiz;
    const question = quiz.questions[this.currentQuestionIdx];
    const owner = store.getState('currentUser')?.id;
    const revision = this.revision;
    const choices = ['multiple_choice', 'true_false'].includes(question.question_type);
    const modal = document.createElement('sentio-modal');
    modal.setAttribute('title', 'Edit question');
    modal.innerHTML = `<form><label for="edit-question-text">Question</label><textarea id="edit-question-text" maxlength="2000" required>${escapeHtml(question.question_text)}</textarea>${choices ? `<label for="edit-question-options">Options, one per line</label><textarea id="edit-question-options" required>${escapeHtml((question.options || []).join('\n'))}</textarea>` : ''}<label for="edit-question-answer">Correct answer${choices ? ' (must match an option exactly)' : ''}</label><input id="edit-question-answer" maxlength="1000" required value="${escapeHtml(question.correct_answer)}"><label for="edit-question-explanation">Explanation</label><textarea id="edit-question-explanation" maxlength="5000">${escapeHtml(question.explanation)}</textarea><p><small>Earlier results keep their grades. New answers use this correction.</small></p><button class="workspace-action primary" type="submit">Save question</button><p role="status"></p></form>`;
    document.body.appendChild(modal);
    modal.querySelector('form').onsubmit = async (event) => {
      event.preventDefault();
      const body = {
        question_text: modal.querySelector('#edit-question-text').value.trim(),
        options: choices
          ? modal
              .querySelector('#edit-question-options')
              .value.split('\n')
              .map((option) => option.trim())
              .filter(Boolean)
          : null,
        correct_answer: modal.querySelector('#edit-question-answer').value.trim(),
        explanation: modal.querySelector('#edit-question-explanation').value.trim(),
        expected_revision: quiz.revision ?? 0,
      };
      if (!body.question_text || !body.correct_answer) return;
      const button = modal.querySelector('button[type="submit"]');
      button.disabled = true;
      try {
        await sentioAPI.request(`/quizzes/${quiz.quiz_id}/questions/${question.question_id}`, {
          method: 'PUT',
          body: JSON.stringify(body),
        });
        const updated = await sentioAPI.get(`/quizzes/${quiz.quiz_id}`);
        modal.close();
        if (
          revision === this.revision &&
          owner === store.getState('currentUser')?.id &&
          store.getState('activeRoute') === '#/quizzes' &&
          this.quiz === quiz
        ) {
          this.quiz = updated;
          this.render();
          toast('Question saved.');
        }
      } catch (error) {
        modal.querySelector('[role="status"]').textContent = error.message;
        button.disabled = false;
      }
    };
  }
}
