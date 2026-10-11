import { escapeHtml } from '../core/html.js';
// Quizzes View Controller for Sentio (ES Module)
import { sentioAPI } from '../core/api.js';
import { store } from '../core/store.js';
import { toast } from '../components/ui.js';
import { runPracticeJob } from '../core/jobs.js';

export class QuizzesView {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
    this.studentId = 'stu_001';
    this.quiz = null;
    this.currentQuestionIdx = 0;
    this.answers = {};
    this.results = null;
    this.isReviewMode = false;
  }

  init() {
    store.subscribe('activeRoute', (route) => {
      if (route === '#/quizzes') {
        this.studentId = store.getState('currentUser')?.id || 'stu_001';
        this.resetQuizState();
        this.render();
      }
    });
  }

  resetQuizState() {
    this.quiz = null;
    this.currentQuestionIdx = 0;
    this.answers = {};
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
    this.container.innerHTML = `
      <div class="view-header" style="margin-bottom:20px;">
        <h2 style="font-family:var(--display);font-weight:800;color:var(--text);margin-bottom:6px;">Interactive Quizzes</h2>
        <p style="color:var(--text-dim);font-size:14px;">Generate adaptive assessments using RAG and student memory context.</p>
      </div>

      <div style="max-width:550px;width:100%;margin:0 auto;">
        <sentio-card title="Configure Quiz Generation">
          <div style="display:flex;flex-direction:column;gap:14px;margin-top:10px;">
            <div>
              <label for="quiz-subject" style="display:block;font-size:14px;color:var(--text-dim);margin-bottom:6px;font-weight:bold;">Subject</label>
<select id="quiz-subject" style="width:100%;background:var(--bg3);border:1px solid var(--border);border-radius:var(--radius);padding:8px 12px;color:var(--text);font-family:var(--mono);font-size:14px;outline:none;">
                <option value="physics">Physics</option>
                <option value="computer_science">Computer Science</option>
                <option value="mathematics">Mathematics</option>
                <option value="chemistry">Chemistry</option>
                <option value="biology">Biology</option>
              </select>
            </div>

            <div>
              <label for="quiz-topic" style="display:block;font-size:14px;color:var(--text-dim);margin-bottom:6px;font-weight:bold;">Topic</label>
<input type="text" id="quiz-topic" value="" placeholder="Choose a study topic" aria-label="Quiz topic" style="width:100%;background:var(--bg3);border:1px solid var(--border);border-radius:var(--radius);padding:8px 12px;color:var(--text);font-family:var(--mono);font-size:14px;outline:none;" />
            </div>

            <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
              <div>
                <label for="quiz-difficulty" style="display:block;font-size:14px;color:var(--text-dim);margin-bottom:6px;font-weight:bold;">Difficulty</label>
<select id="quiz-difficulty" style="width:100%;background:var(--bg3);border:1px solid var(--border);border-radius:var(--radius);padding:8px 12px;color:var(--text);font-family:var(--mono);font-size:14px;outline:none;">
                  <option value="beginner">Beginner</option>
                  <option value="intermediate" selected>Intermediate</option>
                  <option value="advanced">Advanced</option>
                </select>
              </div>
              <div>
                <label for="quiz-num-questions" style="display:block;font-size:14px;color:var(--text-dim);margin-bottom:6px;font-weight:bold;">Number of Questions</label>
<select id="quiz-num-questions" style="width:100%;background:var(--bg3);border:1px solid var(--border);border-radius:var(--radius);padding:8px 12px;color:var(--text);font-family:var(--mono);font-size:14px;outline:none;">
                  <option value="3" selected>3 Questions</option>
                  <option value="5">5 Questions</option>
                  <option value="10">10 Questions</option>
                </select>
              </div>
            </div>

            <button id="generate-quiz-btn" style="margin-top:10px;background:var(--accent);color:var(--bg);border:none;padding:12px;border-radius:var(--radius);font-family:var(--mono);font-weight:bold;cursor:pointer;font-size:14px;transition:opacity 0.2s;">
              ⚡ Generate Dynamic Quiz
            </button>
          </div>
        </sentio-card>
      </div>
    `;

    this.container.querySelector('#generate-quiz-btn').onclick = () => this.generateQuiz();
    const sessionId = store.getState('activeSessionId');
    if (sessionId) {
      const button = this.container.querySelector('#generate-quiz-btn');
      button.disabled = true;
      try {
        const session = await sentioAPI.get(`/sessions/${sessionId}`);
        for (const field of ['subject', 'topic', 'difficulty']) {
          const input = this.container.querySelector(`#quiz-${field}`);
          if (input) input.value = session[field];
          if (input) input.disabled = true;
        }
        button.disabled = false;
      } catch (e) {
        toast('Failed to load quiz session: ' + e.message, true);
      }
    }
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
      <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:60%;gap:12px;">
        <sentio-loader size="36px"></sentio-loader>
        <span style="font-size:14px;color:var(--accent);font-weight:bold;font-family:var(--mono);">AI is custom-crafting your assessment...</span>
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
      <div class="view-header" style="margin-bottom:20px;display:flex;justify-content:space-between;align-items:center;">
        <div>
          <h2 style="font-family:var(--display);font-weight:800;color:var(--text);margin-bottom:6px;">${escapeHtml(this.quiz.title || 'Dynamic Assessment')}</h2>
          <p style="color:var(--text-dim);font-size:14px;">Select your answer and navigate using the controls below.</p>
        </div>
        <span style="font-family:var(--mono);font-size:14px;background:var(--border);padding:4px 8px;border-radius:4px;color:var(--accent);font-weight:bold;">
          Question ${this.currentQuestionIdx + 1} of ${totalQ}
        </span>
      </div>

      <div style="max-width:650px;width:100%;margin:0 auto;display:flex;flex-direction:column;gap:20px;">
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
        </sentio-card>

        <div style="display:flex;justify-content:space-between;align-items:center;">
          <button id="prev-question-btn" ${this.currentQuestionIdx === 0 ? 'disabled style="opacity:0.4;cursor:not-allowed;"' : ''} style="background:none;border:1px solid var(--border);color:var(--text);padding:8px 16px;border-radius:var(--radius);cursor:pointer;font-family:var(--mono);font-size:14px;">
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

    // Save state on change
    const options = this.container.querySelectorAll('input[name="quiz-opt"]');
    options.forEach((opt) => {
      opt.onchange = (e) => {
        const index = e.target.value.charCodeAt(0) - 65;
        this.answers[this.currentQuestionIdx] =
          this.quiz.questions[this.currentQuestionIdx].options[index];
      };
    });

    const textInput = this.container.querySelector('#short-answer-input');
    if (textInput) {
      textInput.oninput = (e) => {
        this.answers[this.currentQuestionIdx] = e.target.value;
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
  }

  async submitQuiz() {
    const activeSessionId = store.getState('activeSessionId');
    this.container.innerHTML = `
      <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:60%;gap:12px;">
        <sentio-loader size="36px"></sentio-loader>
        <span style="font-size:14px;color:var(--accent);font-weight:bold;font-family:var(--mono);">Grading responses and updating student memory...</span>
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
      <div class="view-header" style="margin-bottom:20px;">
        <h2 style="font-family:var(--display);font-weight:800;color:var(--text);margin-bottom:6px;">Assessment Results</h2>
        <p style="color:var(--text-dim);font-size:14px;">Review explanations and pedagogical feedback to improve retention.</p>
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
          <p style="font-size:14px;line-height:1.5;color:var(--text-dim);">${escapeHtml(this.results.summary)}</p>
        </sentio-card>

        <!-- Detailed Feedback -->
        <sentio-card title="Detailed Questions Review">
          <div style="display:flex;flex-direction:column;gap:16px;">
            ${this.results.feedback
              .map((f, idx) => {
                const qOriginal = this.quiz.questions[f.question_index];
                return `
                <div style="border:1px solid var(--border);border-radius:var(--radius);padding:12px;background:var(--bg3);display:flex;flex-direction:column;gap:6px;">
                  <div style="display:flex;justify-content:space-between;align-items:center;">
                    <span style="font-weight:bold;font-size:14px;color:var(--text);">Question ${idx + 1}</span>
                    <span style="color:${f.is_correct ? 'var(--green)' : 'var(--red)'};font-weight:bold;font-size:14px;">
                      ${f.is_correct ? '✅ CORRECT' : '❌ INCORRECT'}
                    </span>
                  </div>
                  <p style="font-size:14px;color:var(--text);line-height:1.4;margin:4px 0;">${escapeHtml(qOriginal.question_text)}</p>
                  <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;font-size:14px;background:var(--bg2);padding:8px;border-radius:var(--radius);border:1px solid var(--border);">
                    <div>Your Answer: <strong style="color:${f.is_correct ? 'var(--green)' : 'var(--red)'};">${f.student_answer || 'N/A'}</strong></div>
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
}
