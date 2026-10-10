import { escapeHtml } from '../core/html.js';
// Dashboard View Controller for Sentio (ES Module)
import { store } from '../core/store.js';
import { sentioAPI } from '../core/api.js';
import { toast } from '../components/ui.js';

export class DashboardView {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
    this.studentId = 'stu_001';
  }

  async init() {
    // Listen to route changes to refresh dashboard when opened
    store.subscribe('activeRoute', (route) => {
      if (route === '#/dashboard') {
        this.studentId = store.getState('currentUser')?.id || 'stu_001';
        this.loadDashboardData();
      }
    });
  }

  async loadDashboardData() {
    this.container.innerHTML = `
      <div style="display:flex;align-items:center;justify-content:center;height:60%;">
        <sentio-loader size="32px"></sentio-loader>
      </div>
    `;

    try {
      const [profile, recs, historyData] = await Promise.all([
        sentioAPI.get(`/student/${escapeHtml(this.studentId)}/profile`).catch((e) => {
          console.warn('Profile fetch failed:', e);
          return null;
        }),
        sentioAPI.get(`/student/${escapeHtml(this.studentId)}/recommendations`).catch((e) => {
          console.warn('Recommendations fetch failed:', e);
          return [];
        }),
        sentioAPI.get(`/students/${escapeHtml(this.studentId)}/history`).catch((e) => {
          console.warn('History fetch failed:', e);
          return { sessions: [] };
        }),
      ]);

      this.render(profile, recs, historyData?.sessions || []);
    } catch (e) {
      this.container.innerHTML = `
        <div style="padding:40px;text-align:center;">
          <div style="font-size:24px;margin-bottom:12px;">⚠️</div>
          <div style="color:var(--red);font-weight:bold;">Failed to load Dashboard data</div>
          <div style="color:var(--text-dim);font-size:11px;margin-top:8px;">${escapeHtml(e.message)}</div>
          <button id="retry-dash-btn" style="margin-top:16px;background:var(--accent);color:var(--bg);border:none;padding:8px 16px;border-radius:var(--radius);cursor:pointer;font-family:var(--mono);">Retry</button>
        </div>
      `;
      const btn = this.container.querySelector('#retry-dash-btn');
      if (btn) btn.onclick = () => this.loadDashboardData();
    }
  }

  render(profile, recs, sessions) {
    const streak = profile?.learning_streak || 0;
    const overallMastery = profile?.overall_mastery ? Math.round(profile.overall_mastery * 100) : 0;
    const weakTopics = profile?.weak_concepts || [];

    // Sort topic mastery
    const topicMasteryList = profile?.topic_mastery ? Object.entries(profile.topic_mastery) : [];

    this.container.innerHTML = `
      <div class="view-header" style="margin-bottom:20px;">
        <h2 style="font-family:var(--display);font-weight:800;color:var(--text);margin-bottom:6px;">Dashboard</h2>
        <p style="color:var(--text-dim);font-size:11px;">Learning performance overview for student ID: <strong style="color:var(--accent);">${escapeHtml(this.studentId)}</strong></p>
      </div>

      <!-- Core scorecards -->
      <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(220px, 1fr));gap:16px;width:100%;margin-bottom:20px;">
        <sentio-card title="🔥 Learning Streak">
          <div style="font-size:28px;color:var(--orange);font-weight:bold;font-family:var(--display);">${streak} Days</div>
          <p style="color:var(--text-dim);font-size:11px;margin-top:4px;">Keep studying daily to maintain your streak!</p>
        </sentio-card>

        <sentio-card title="🏆 Overall Mastery">
          <div style="font-size:28px;color:var(--green);font-weight:bold;font-family:var(--display);">${overallMastery}%</div>
          <div style="width:100%;background:var(--border);height:6px;border-radius:3px;margin-top:10px;overflow:hidden;">
            <div style="width:${overallMastery}%;background:var(--green);height:100%;"></div>
          </div>
        </sentio-card>

        <sentio-card title="🧠 Preferred Style">
          <div style="font-size:22px;color:var(--accent);font-weight:bold;text-transform:capitalize;font-family:var(--display);">${escapeHtml(profile?.preferred_explanation_style || 'Standard')}</div>
          <p style="color:var(--text-dim);font-size:11px;margin-top:4px;">Difficulty: <span style="color:var(--accent);text-transform:capitalize;">${escapeHtml(profile?.preferred_difficulty || 'Intermediate')}</span></p>
        </sentio-card>
      </div>

      <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;width:100%;margin-bottom:20px;">
        <!-- Left Column: Topic mastery and weak areas -->
        <div style="display:flex;flex-direction:column;gap:20px;">
          <sentio-card title="📖 Concept Mastery">
            ${
              topicMasteryList.length === 0
                ? `
              <sentio-empty-state message="No concepts studied yet. Start a session!" icon="📝"></sentio-empty-state>
            `
                : `
              <div style="display:flex;flex-direction:column;gap:12px;">
                ${topicMasteryList
                  .map(([topic, mastery]) => {
                    const pct = Math.round(mastery * 100);
                    const color =
                      pct >= 80 ? 'var(--green)' : pct >= 50 ? 'var(--yellow)' : 'var(--red)';
                    return `
                    <div>
                      <div style="display:flex;justify-content:space-between;margin-bottom:4px;font-size:11px;">
                        <span style="text-transform:capitalize;font-weight:500;">${escapeHtml(topic.replace(/_/g, ' '))}</span>
                        <span style="color:${color};font-weight:bold;">${pct}%</span>
                      </div>
                      <div style="width:100%;background:var(--border);height:4px;border-radius:2px;overflow:hidden;">
                        <div style="width:${pct}%;background:${color};height:100%;"></div>
                      </div>
                    </div>
                  `;
                  })
                  .join('')}
              </div>
            `
            }
          </sentio-card>

          ${
            weakTopics.length > 0
              ? `
            <sentio-card title="⚠️ Weak Areas Detected">
              <div style="display:flex;flex-wrap:wrap;gap:8px;">
                ${weakTopics
                  .map(
                    (topic) => `
                  <span style="background:rgba(255,80,96,0.1);color:var(--red);border:1px solid rgba(255,80,96,0.2);padding:4px 8px;border-radius:var(--radius);font-size:10px;text-transform:capitalize;">
                    ${escapeHtml(topic.replace(/_/g, ' '))}
                  </span>
                `,
                  )
                  .join('')}
              </div>
            </sentio-card>
          `
              : ''
          }
        </div>

        <!-- Right Column: Study Recommendations -->
        <div style="display:flex;flex-direction:column;gap:20px;">
          <sentio-card title="🚀 Recommended Actions">
            ${
              recs.length === 0
                ? `
              <sentio-empty-state message="All caught up! No recommendations." icon="🎉"></sentio-empty-state>
            `
                : `
              <div style="display:flex;flex-direction:column;gap:12px;">
                ${recs
                  .slice(0, 4)
                  .map((rec) => {
                    const iconMap = {
                      review_flashcards: '🗂️',
                      take_quiz: '📝',
                      start_tutoring: '🧠',
                      review_prerequisites: '🔄',
                      increase_challenge: '🚀',
                    };
                    const labelMap = {
                      review_flashcards: 'Review Flashcards',
                      take_quiz: 'Take Quiz',
                      start_tutoring: 'Start Tutoring',
                      review_prerequisites: 'Review Prerequisites',
                      increase_challenge: 'Increase Challenge',
                    };
                    return `
                    <div style="border:1px solid var(--border);border-radius:var(--radius);padding:10px 14px;background:var(--bg3);display:flex;flex-direction:column;gap:6px;">
                      <div style="display:flex;justify-content:space-between;align-items:center;">
                        <span style="font-weight:bold;font-size:12px;color:var(--accent);">
                          ${iconMap[rec.action] || '⚡'} ${escapeHtml(labelMap[rec.action] || rec.action)}
                        </span>
                        <span style="font-size:9px;color:var(--text-dim);background:var(--border);padding:2px 6px;border-radius:4px;">
                          Score: ${Math.round(rec.priority_score * 100)}
                        </span>
                      </div>
                      <p style="font-size:11px;color:var(--text-dim);line-height:1.4;">${escapeHtml(rec.explanation)}</p>
                    </div>
                  `;
                  })
                  .join('')}
              </div>
            `
            }
          </sentio-card>
        </div>
      </div>

      <!-- Bottom Row: Session history log -->
      <div style="width:100%;">
        <sentio-card title="📜 Recent Study History">
          ${
            sessions.length === 0
              ? `
            <sentio-empty-state message="No past session history. Let's start learning!" icon="📜"></sentio-empty-state>
          `
              : `
            <div style="overflow-x:auto;">
              <table style="width:100%;border-collapse:collapse;font-size:11px;text-align:left;">
                <thead>
                  <tr style="border-bottom:1px solid var(--border);color:var(--text-dim);">
                    <th style="padding:10px;">Session ID</th>
                    <th style="padding:10px;">Subject</th>
                    <th style="padding:10px;">Duration</th>
                    <th style="padding:10px;">Dominant Emotion</th>
                    <th style="padding:10px;">Estimated Retention</th>
                  </tr>
                </thead>
                <tbody>
                  ${sessions
                    .slice(0, 5)
                    .map(
                      (s) => `
                    <tr style="border-bottom:1px solid var(--border);color:var(--text);">
                      <td style="padding:10px;font-family:var(--mono);">${s.session_id.slice(0, 8)}…</td>
                      <td style="padding:10px;text-transform:capitalize;">${escapeHtml(s.subject)}</td>
                      <td style="padding:10px;">${s.duration_min ? s.duration_min.toFixed(1) : 0} mins</td>
                      <td style="padding:10px;text-transform:capitalize;">${escapeHtml(s.dominant_emotion || 'Neutral')}</td>
                      <td style="padding:10px;color:var(--green);font-weight:bold;">${s.estimated_retention ? Math.round(s.estimated_retention * 100) : 0}%</td>
                    </tr>
                  `,
                    )
                    .join('')}
                </tbody>
              </table>
            </div>
          `
          }
        </sentio-card>
      </div>
    `;
  }
}
