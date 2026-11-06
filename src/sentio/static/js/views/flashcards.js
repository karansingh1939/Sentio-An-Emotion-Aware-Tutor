import { describeProvenance, escapeHtml } from '../core/html.js';
// Flashcards View Controller for Sentio (ES Module)
import { sentioAPI } from '../core/api.js';
import { store } from '../core/store.js';
import { toast } from '../components/ui.js';
import { runPracticeJob } from '../core/jobs.js';

const RATINGS = [
  ['again', 1, 'I could not recall the answer', 'Again'],
  ['hard', 3, 'I recalled it with difficulty', 'Hard'],
  ['good', 4, 'I recalled the answer', 'Good'],
  ['easy', 5, 'I recalled it immediately', 'Easy'],
];

function formatDays(days) {
  if (days < 30) return days === 1 ? '1 day' : `${days} days`;
  if (days < 365) return `${Math.round(days / 30)} mo`;
  return `${(days / 365).toFixed(1)} yr`;
}

export class FlashcardsView {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
    this.studentId = 'stu_001';
    this.decks = [];
    this.activeDeckId = null;
    this.dueCards = [];
    this.currentCardIdx = 0;
    this.isFlipped = false;
    this.revision = 0;
    this.ratingInProgress = false;
  }

  init() {
    store.subscribe('activeRoute', (route) => {
      if (route === '#/flashcards') {
        this.revision++;
        this.studentId = store.getState('currentUser')?.id || 'stu_001';
        this.resetState();
        this.loadDecks();
      } else this.revision++;
    });
  }

  resetState() {
    this.activeDeckId = null;
    this.dueCards = [];
    this.currentCardIdx = 0;
    this.isFlipped = false;
  }

  async loadDecks() {
    const revision = this.revision;
    const owner = store.getState('currentUser')?.id;
    this.container.innerHTML = `
      <div class="center-state">
        <sentio-loader size="32px"></sentio-loader>
      </div>
    `;

    try {
      const sessionId = store.getState('activeSessionId');
      const [decksRes, dueRes, session] = await Promise.all([
        sentioAPI.get(`/flashcards/decks?student_id=${this.studentId}`),
        sentioAPI.get(`/flashcards/reviews/due?student_id=${this.studentId}`),
        sessionId ? sentioAPI.get(`/sessions/${sessionId}`) : Promise.resolve(null),
      ]);
      if (
        store.getState('activeRoute') !== '#/flashcards' ||
        revision !== this.revision ||
        owner !== store.getState('currentUser')?.id ||
        sessionId !== store.getState('activeSessionId')
      )
        return;
      if (session) store.setState('activeSession', session);

      this.decks = decksRes.decks || [];
      // Combine due count stats
      const dueMap = {};
      (dueRes.cards || []).forEach((c) => {
        dueMap[c.deck_id] = (dueMap[c.deck_id] || 0) + 1;
      });

      this.decks = this.decks.map((d) => ({
        ...d,
        due_count: dueMap[d.deck_id] || 0,
      }));

      this.render();
    } catch (e) {
      if (
        revision !== this.revision ||
        owner !== store.getState('currentUser')?.id ||
        store.getState('activeRoute') !== '#/flashcards'
      )
        return;
      this.container.innerHTML = `<p role="alert">Saved cards could not be loaded: ${escapeHtml(e.message)}</p><button class="workspace-action" id="retry-card-load">Retry</button>`;
      this.container.querySelector('#retry-card-load').onclick = () => this.loadDecks();
    }
  }

  render() {
    if (this.activeDeckId) {
      this.renderReviewSession();
    } else {
      this.renderDeckBrowser();
    }
  }

  renderDeckBrowser() {
    this.container.innerHTML = `
      <div class="view-header view-header row-between">
        <div>
          <h2 class="page-title">Flashcard decks</h2>
          <p class="muted">Spaced repetition scheduled by FSRS, a memory model fitted on real review data.</p>
        </div>
        <button id="show-create-deck-modal" style="background:var(--accent);color:var(--bg);border:none;padding:8px 16px;border-radius:var(--radius);cursor:pointer;font-family:var(--mono);font-size:14px;font-weight:bold;">
          + Create Deck
        </button>
      </div>

      <div style="display:grid;grid-template-columns:1fr 340px;gap:20px;width:100%;">
        <!-- Left: Decks Listing -->
        <div class="stack stack-lg">
          <sentio-card title="Your decks">
            ${
              this.decks.length === 0
                ? `
              <sentio-empty-state message="No flashcard decks created yet. Create a deck to start reviewing." icon="cards"></sentio-empty-state>
            `
                : `
              <div style="display:grid;grid-template-columns:repeat(auto-fill, minmax(200px, 1fr));gap:14px;">
                ${this.decks
                  .map(
                    (d) => `
                  <div class="deck-item-card" data-id="${escapeHtml(d.deck_id)}" style="border:1px solid var(--border);border-radius:var(--radius-lg);padding:16px;background:var(--bg3);cursor:pointer;position:relative;transition:border-color 0.2s, box-shadow 0.2s;">
                    <h3 style="font-size:13px;font-weight:bold;margin-bottom:6px;color:var(--text);">${escapeHtml(d.deck_name)}</h3>
                    <div style="font-size:14px;color:var(--text-dim);margin-bottom:12px;">Created: ${new Date(d.created_at * 1000).toLocaleDateString()}</div>
                    
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-top:10px;">
                      <span style="font-size:14px;font-weight:bold;font-family:var(--mono);color:${d.due_count > 0 ? 'var(--orange)' : 'var(--green)'};">
                        ${d.due_count} Due Cards
                      </span>
                      <button class="start-review-btn" data-id="${escapeHtml(d.deck_id)}" ${d.due_count === 0 ? 'disabled style="opacity:0.4;cursor:not-allowed;"' : 'style="background:var(--accent);color:var(--bg);border:none;padding:4px 8px;border-radius:var(--radius);font-family:var(--mono);font-size:14px;font-weight:bold;cursor:pointer;"'}>
                        Review
                      </button>
                    </div>
                  </div>
                `,
                  )
                  .join('')}
              </div>
            `
            }
          </sentio-card>
        </div>

        <!-- Right: AI Flashcard Generator Form -->
        <div>
          <sentio-card title="Create practice cards">
            <p style="font-size:14px;color:var(--text-dim);line-height:1.4;margin-bottom:12px;">${store.getState('activeSession')?.status === 'active' ? 'Turn your current study topic into question-and-answer cards. Review them again when they are due.' : 'First choose Study beside your notes in Library. Your saved cards remain available.'}</p>
            ${store.getState('activeSession')?.status === 'active' ? '<a href="#/tutor">Change what you are studying</a>' : '<a class="workspace-action" href="#/documents">Choose notes</a>'}
            
            <div class="stack">
              <div>
                <label class="form-label" for="gen-deck-select">Deck</label>
<select class="input" id="gen-deck-select">
                  ${this.decks.map((d) => `<option value="${escapeHtml(d.deck_id)}">${escapeHtml(d.deck_name)}</option>`).join('')}
                  ${this.decks.length === 0 ? `<option value="">No decks available</option>` : ''}
                </select>
              </div>

              <div>
                <label class="form-label" for="gen-topic-input">Study topic</label>
<input class="input" type="text" id="gen-topic-input" readonly value="${escapeHtml(store.getState('activeSession')?.topic || '')}" placeholder="e.g. recursion" />
              </div>

              <div>
                <label class="form-label" for="gen-cards-num">Number of Cards</label>
<select class="input" id="gen-cards-num">
                  <option value="1">1 Card</option>
                <option value="3" selected>3 Cards</option>
                <option value="5">5 Cards</option>
                </select>
              </div>

              <button id="generate-flashcards-btn" ${store.getState('activeSession')?.status === 'active' ? '' : 'disabled'} style="background:var(--accent);color:var(--bg);border:none;padding:10px;border-radius:var(--radius);font-family:var(--mono);font-size:14px;font-weight:bold;cursor:pointer;transition:opacity 0.2s;">
                Make cards
              </button>
            </div>
          </sentio-card>
        </div>
      </div>
    `;

    this.bindDeckEvents();
  }

  bindDeckEvents() {
    // Show Create Deck Dialog
    const createBtn = this.container.querySelector('#show-create-deck-modal');
    if (createBtn) {
      createBtn.onclick = () => this.showCreateDeckDialog();
    }

    // Start reviews
    this.container.querySelectorAll('.start-review-btn').forEach((btn) => {
      btn.onclick = (e) => {
        const deckId = e.currentTarget.dataset.id;
        this.startReview(deckId);
      };
    });

    // Ingestion generator trigger
    const genBtn = this.container.querySelector('#generate-flashcards-btn');
    if (genBtn) {
      genBtn.onclick = () => this.generateFlashcards();
    }
  }

  showCreateDeckDialog() {
    const modal = document.createElement('sentio-modal');
    modal.setAttribute('title', 'Create Flashcard Deck');
    modal.innerHTML = `
      <div class="stack">
        <div>
          <label class="form-label" for="create-deck-name">Deck name</label>
<input class="input" type="text" id="create-deck-name" placeholder="e.g. Calculus Formulas" />
        </div>
        <button class="workspace-action primary" id="create-deck-submit">Create</button>
      </div>
    `;
    document.body.appendChild(modal);

    modal.querySelector('#create-deck-submit').onclick = async () => {
      const name = modal.querySelector('#create-deck-name').value.trim();
      if (!name) {
        toast('Deck name cannot be empty', true);
        return;
      }

      modal.close();
      store.setState('loading', true);
      try {
        await sentioAPI.post('/flashcards/decks', {
          student_id: this.studentId,
          deck_name: name,
        });
        toast('Deck created');
        this.loadDecks();
      } catch (err) {
        toast('Failed to create deck: ' + err.message, true);
      } finally {
        store.setState('loading', false);
      }
    };
  }

  async generateFlashcards() {
    let deckId = this.container.querySelector('#gen-deck-select').value;
    const owner = store.getState('currentUser')?.id;
    const sessionId = store.getState('activeSessionId');
    const revision = this.revision;
    const topic = this.container.querySelector('#gen-topic-input').value.trim();
    const numCards = parseInt(this.container.querySelector('#gen-cards-num').value, 10);

    if (!sessionId || store.getState('activeSession')?.status !== 'active') {
      toast('Choose Study beside your notes before making new cards.', true);
      return;
    }

    if (!topic) {
      toast('Concept topic cannot be empty', true);
      return;
    }

    this.container.innerHTML = `
      <div class="center-state">
        <sentio-loader size="36px"></sentio-loader>
        <span class="accent-strong">Extracting concepts and generating spaced cards...</span>
      </div>
    `;

    try {
      if (!deckId) {
        const created = await sentioAPI.post('/flashcards/decks', {
          student_id: owner,
          deck_name: topic,
        });
        if (
          owner !== store.getState('currentUser')?.id ||
          sessionId !== store.getState('activeSessionId') ||
          revision !== this.revision
        )
          return;
        deckId = created.deck_id;
      }
      const result = await runPracticeJob(
        '/flashcards/jobs',
        {
          student_id: this.studentId,
          deck_id: deckId,
          topic_id: topic,
          num_cards: numCards,
          session_id: sessionId,
        },
        this.container,
      );
      if (!result) return;

      toast('Your cards are ready to review.');
      this.resetState();
      this.loadDecks();
    } catch (e) {
      toast('Generation failed: ' + e.message, true);
      this.resetState();
      this.loadDecks();
    }
  }

  async startReview(deckId) {
    const revision = this.revision;
    const owner = store.getState('currentUser')?.id;
    store.setState('loading', true);
    try {
      const res = await sentioAPI.get(
        `/flashcards/reviews/due?student_id=${this.studentId}&deck_id=${deckId}`,
      );
      if (
        revision !== this.revision ||
        owner !== store.getState('currentUser')?.id ||
        store.getState('activeRoute') !== '#/flashcards'
      )
        return;
      this.dueCards = res.cards || [];
      this.activeDeckId = deckId;
      this.currentCardIdx = 0;
      this.isFlipped = false;
      this.render();
    } catch (e) {
      toast('Failed to retrieve due cards: ' + e.message, true);
    } finally {
      store.setState('loading', false);
    }
  }

  renderReviewSession() {
    if (this.dueCards.length === 0 || this.currentCardIdx >= this.dueCards.length) {
      this.container.innerHTML = `
        <div style="padding:40px;text-align:center;max-width:500px;margin:0 auto;display:flex;flex-direction:column;gap:16px;align-items:center;justify-content:center;height:60%;">
          <div style="color:var(--green);">${window.sentioIcon('done', 40)}</div>
          <h3 style="font-weight:700;color:var(--text);font-size:18px;">All caught up</h3>
          <p style="color:var(--text-dim);font-size:14px;line-height:1.5;">You've completed all due cards in this deck. Come back later for scheduled repetitions.</p>
          <button id="finish-review-btn" class="workspace-action primary">
            Close review
          </button>
        </div>
      `;
      this.container.querySelector('#finish-review-btn').onclick = () => {
        this.resetState();
        this.loadDecks();
      };
      return;
    }

    const card = this.dueCards[this.currentCardIdx];
    const total = this.dueCards.length;

    this.container.innerHTML = `
      <div class="view-header view-header row-between">
        <div>
          <h2 class="page-title">Review your cards</h2>
          <p class="muted">Recall your answer, reveal the card, then choose how easily you remembered it.</p>
        </div>
        <span class="badge">
          Card ${this.currentCardIdx + 1} of ${total}
        </span>
      </div>

      <div style="max-width:550px;width:100%;margin:0 auto;display:flex;flex-direction:column;gap:20px;">
        <div class="card-toolbar">
          ${card.provenance ? `<p class="practice-provenance"><small>${escapeHtml(describeProvenance(card.provenance))}</small></p>` : '<span></span>'}
          <button class="workspace-action" type="button" id="edit-current-card">Edit this card</button>
        </div>
        <!-- Flip Card Arena -->
        <div id="flashcard-flip-trigger" role="button" tabindex="0" aria-label="Show or hide the answer" aria-expanded="${this.isFlipped}" style="cursor:pointer;width:100%;">
          <div class="flashcard-inner ${this.isFlipped ? 'flipped' : ''}">
            <!-- Front -->
            <div class="flashcard-front" ${this.isFlipped ? 'hidden' : ''} style="border:1px solid var(--border);background:var(--bg2);">
              <span style="font-size:14px;color:var(--accent);font-family:var(--mono);margin-bottom:12px;font-weight:bold;">QUESTION / TERM</span>
              <p style="font-size:14px;color:var(--text);text-align:center;line-height:1.5;font-weight:500;">
                ${escapeHtml(card.front_text)}
              </p>
              <span style="font-size:14px;color:var(--text-dim);margin-top:20px;">Tap or press Enter to show the answer</span>
            </div>
            
            <!-- Back -->
            <div class="flashcard-back" ${this.isFlipped ? '' : 'hidden'} style="border:1px solid var(--accent);">
              <span style="font-size:14px;color:var(--green);font-family:var(--mono);margin-bottom:12px;font-weight:bold;">EXPLANATION / ANSWER</span>
              <p style="font-size:13px;color:var(--text);text-align:center;line-height:1.5;">
                ${escapeHtml(card.back_text)}
              </p>
              <div style="margin-top:14px;display:flex;flex-wrap:wrap;gap:6px;justify-content:center;">
                ${(card.tags
                  ? typeof card.tags === 'string'
                    ? JSON.parse(card.tags)
                    : card.tags
                  : []
                )
                  .map(
                    (t) => `
                  <span style="background:var(--border);color:var(--text-dim);padding:2px 6px;border-radius:4px;font-size:14px;">#${escapeHtml(t)}</span>
                `,
                  )
                  .join('')}
              </div>
            </div>
          </div>
        </div>

        <!-- Feedback / Rating Panel (Visible only when flipped) -->
        <div id="rating-controls-panel" class="flashcard-reveal" style="display:${this.isFlipped ? 'flex' : 'none'};flex-direction:column;gap:12px;background:var(--bg3);border:1px solid var(--border);border-radius:var(--radius-lg);padding:16px;">
          <label style="display:block;font-size:14px;color:var(--text-dim);text-align:center;font-weight:bold;">How well did you recall this concept?</label>
          
          <div class="review-ratings">
            ${RATINGS.map(
              ([name, score, title, label]) => `
              <button class="workspace-action rate-btn${name === 'good' ? ' primary' : ''}" data-score="${score}" title="${title}">
                ${label}${card.next_intervals ? `<small class="rate-interval">${formatDays(card.next_intervals[name])}</small>` : ''}
              </button>`,
            ).join('')}
          </div>
          <p class="muted">Each button shows when the card comes back. Your rating schedules review; it is not a test score.</p>
        </div>

        <button id="tutor-abort-review" style="background:none;border:1px solid var(--border);color:var(--red);padding:6px;border-radius:var(--radius);font-family:var(--mono);font-size:14px;cursor:pointer;margin-top:10px;">
          Back to my cards
        </button>
      </div>
    `;

    this.bindReviewEvents();
  }

  bindReviewEvents() {
    const edit = this.container.querySelector('#edit-current-card');
    if (edit) edit.onclick = () => this.editCurrentCard();
    const trigger = this.container.querySelector('#flashcard-flip-trigger');
    if (trigger) {
      trigger.onkeydown = (event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          trigger.click();
        }
      };
      trigger.onclick = () => {
        this.isFlipped = !this.isFlipped;

        trigger.setAttribute('aria-expanded', String(this.isFlipped));
        this.container.querySelector('.flashcard-front').hidden = this.isFlipped;
        this.container.querySelector('.flashcard-back').hidden = !this.isFlipped;

        // Toggle panels
        const panel = this.container.querySelector('#rating-controls-panel');
        const inner = this.container.querySelector('.flashcard-inner');

        if (this.isFlipped) {
          inner.classList.add('flipped');
          if (panel) panel.style.display = 'flex';
        } else {
          inner.classList.remove('flipped');
          if (panel) panel.style.display = 'none';
        }
      };
    }

    // Quality buttons
    this.container.querySelectorAll('.rate-btn').forEach((btn) => {
      btn.onclick = async (e) => {
        e.stopPropagation();
        const score = parseInt(btn.dataset.score, 10);
        if (this.ratingInProgress) return;
        this.ratingInProgress = true;
        const revision = this.revision;
        const owner = store.getState('currentUser')?.id;
        const card = this.dueCards[this.currentCardIdx];
        const key = `sentio_review:${owner}:${card.card_id}`;
        let requestId = localStorage.getItem(key);
        this.container.querySelectorAll('.rate-btn').forEach((button) => {
          button.disabled = true;
        });

        store.setState('loading', true);
        try {
          let confirmed = false;
          if (requestId) {
            try {
              const receipt = await sentioAPI.get(
                `/flashcards/${card.card_id}/reviews/${requestId}`,
              );
              localStorage.removeItem(key);
              localStorage.removeItem(key + ':score');
              confirmed = receipt.result.next_review_at > Date.now() / 1000;
              requestId = null;
            } catch (error) {
              if (error.status !== 404) throw error;
            }
          }
          if (revision !== this.revision || owner !== store.getState('currentUser')?.id) return;
          if (!confirmed) {
            const previousScore = localStorage.getItem(key + ':score');
            if (requestId && previousScore !== null && Number(previousScore) !== score)
              throw new Error(
                'The previous rating still needs confirmation. Retry the same rating.',
              );
            if (!requestId) {
              requestId = crypto.randomUUID();
              localStorage.setItem(key, requestId);
            }
            localStorage.setItem(key + ':score', String(score));
            await sentioAPI.post(`/flashcards/${card.card_id}/review`, {
              quality_score: score,
              request_id: requestId,
            });
            localStorage.removeItem(key);
            localStorage.removeItem(key + ':score');
          }
          if (
            revision !== this.revision ||
            owner !== store.getState('currentUser')?.id ||
            store.getState('activeRoute') !== '#/flashcards'
          )
            return;

          this.isFlipped = false;
          this.currentCardIdx++;
          this.render();
        } catch (err) {
          toast('Review failed: ' + err.message, true);
        } finally {
          this.ratingInProgress = false;
          this.container.querySelectorAll('.rate-btn').forEach((button) => {
            button.disabled = false;
          });
          store.setState('loading', false);
        }
      };
    });

    const abort = this.container.querySelector('#tutor-abort-review');
    if (abort) {
      abort.onclick = () => {
        this.resetState();
        this.loadDecks();
      };
    }
  }

  editCurrentCard() {
    const card = this.dueCards[this.currentCardIdx];
    const owner = store.getState('currentUser')?.id;
    const revision = this.revision;
    const modal = document.createElement('sentio-modal');
    modal.setAttribute('title', 'Edit flashcard');
    modal.innerHTML = `<form><label for="card-front">Question or term</label><textarea id="card-front" maxlength="2000" required>${escapeHtml(card.front_text)}</textarea><label for="card-back">Answer and explanation</label><textarea id="card-back" maxlength="5000" required>${escapeHtml(card.back_text)}</textarea><button class="workspace-action primary" type="submit">Save card</button><p role="status"></p></form>`;
    document.body.appendChild(modal);
    modal.querySelector('form').onsubmit = async (event) => {
      event.preventDefault();
      const front = modal.querySelector('#card-front').value.trim();
      const back = modal.querySelector('#card-back').value.trim();
      if (!front || !back) return;
      const button = modal.querySelector('button[type="submit"]');
      button.disabled = true;
      try {
        await sentioAPI.request(`/flashcards/${card.card_id}`, {
          method: 'PATCH',
          body: JSON.stringify({ front_text: front, back_text: back }),
        });
        card.front_text = front;
        card.back_text = back;
        if (card.provenance) card.provenance = { ...card.provenance, edited: true };
        modal.close();
        if (
          revision === this.revision &&
          owner === store.getState('currentUser')?.id &&
          store.getState('activeRoute') === '#/flashcards'
        )
          this.render();
      } catch (error) {
        modal.querySelector('[role="status"]').textContent = error.message;
        button.disabled = false;
      }
    };
  }
}
