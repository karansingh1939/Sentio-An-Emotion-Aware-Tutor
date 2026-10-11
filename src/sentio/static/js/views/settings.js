// Settings View Controller for Sentio (ES Module)
import { store } from '../core/store.js';
import { toast } from '../components/ui.js';
import { sentioAPI } from '../core/api.js';

export class SettingsView {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
  }

  init() {
    this.render();
    this.bindEvents();
  }

  render() {
    this.container.innerHTML = `
      <div class="view-header">
        <h2 style="font-family:var(--display);font-weight:800;color:var(--text);margin-bottom:6px;">Settings</h2>
        <p style="color:var(--text-dim);font-size:14px;">Configure your profile, view logs, or manage privacy and GDPR controls.</p>
      </div>

      <div style="margin-top:20px;width:100%;">
        <sentio-card title="Privacy & GDPR Actions">
          <div style="display:flex;flex-direction:column;gap:12px;">
            <p style="color:var(--text-dim);font-size:14px;">Under GDPR, you have the right to export your personal learning data or delete all historical records from our database.</p>
            <div style="display:flex;gap:12px;margin-top:8px;">
              <button id="export-data-btn" style="background:var(--accent);color:var(--bg);border:none;padding:8px 16px;border-radius:var(--radius);font-family:var(--mono);cursor:pointer;font-size:14px;font-weight:bold;">📥 Export My Data</button>
              <button id="purge-data-btn" style="background:none;color:var(--red);border:1px solid var(--red);padding:8px 16px;border-radius:var(--radius);font-family:var(--mono);cursor:pointer;font-size:14px;font-weight:bold;">🗑️ Purge My Account Data</button>
            </div>
          </div>
        </sentio-card>

        <sentio-card title="Preferences">
          <div style="display:flex;align-items:center;justify-content:between;">
            <div>
              <div style="font-weight:bold;font-size:14px;">Telemetry Tracking Consent</div>
              <div style="color:var(--text-dim);font-size:14px;margin-top:2px;">Allow attention and emotion detection webcam processing.</div>
            </div>
            <input type="checkbox" id="consent-cb" ${store.getState('telemetryActive') ? 'checked' : ''} style="width:16px;height:16px;cursor:pointer;" />
          </div>
        </sentio-card>

        <sentio-card title="Account Actions">
          <div style="display:flex;flex-direction:column;gap:12px;">
            <p style="color:var(--text-dim);font-size:14px;">Sign out of your active student session on this machine.</p>
            <button id="signout-btn" style="background:none;border:1px solid var(--red);color:var(--red);padding:8px 16px;border-radius:var(--radius);font-family:var(--mono);cursor:pointer;font-size:14px;font-weight:bold;align-self:flex-start;transition:background 0.2s;">🚪 Sign Out of Sentio</button>
          </div>
        </sentio-card>
      </div>
    `;
  }

  bindEvents() {
    const cb = this.container.querySelector('#consent-cb');
    if (cb) {
      cb.onchange = (e) => {
        store.setState('telemetryActive', e.target.checked);
        toast(`Telemetry consent updated: ${e.target.checked ? 'ENABLED' : 'DISABLED'}`);
      };
    }

    const expBtn = this.container.querySelector('#export-data-btn');
    if (expBtn) {
      expBtn.onclick = async () => {
        const studentId = store.getState('currentUser')?.id || 'stu_001';
        try {
          const res = await sentioAPI.get(`/student/${studentId}/export`);
          // Download raw JSON
          const dataStr =
            'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(res, null, 2));
          const dlAnchor = document.createElement('a');
          dlAnchor.setAttribute('href', dataStr);
          dlAnchor.setAttribute('download', `sentio_export_${studentId}.json`);
          document.body.appendChild(dlAnchor);
          dlAnchor.click();
          dlAnchor.remove();
          toast('GDPR export download started!');
        } catch (e) {
          toast('Export failed: ' + e.message, true);
        }
      };
    }

    const purgeBtn = this.container.querySelector('#purge-data-btn');
    if (purgeBtn) {
      purgeBtn.onclick = async () => {
        if (
          !confirm(
            'Are you absolutely sure you want to delete ALL of your data? This action is permanent and cannot be undone.',
          )
        ) {
          return;
        }
        const studentId = store.getState('currentUser')?.id || 'stu_001';
        try {
          await sentioAPI.delete(`/student/${studentId}/data`);
          toast('Your data has been permanently deleted from the database.');
          store.clearAuth();
        } catch (e) {
          toast('Purge failed: ' + e.message, true);
        }
      };
    }

    const signoutBtn = this.container.querySelector('#signout-btn');
    if (signoutBtn) {
      signoutBtn.onclick = async () => {
        const refreshToken = store.getState('refreshToken');
        if (refreshToken) {
          try {
            await sentioAPI.post('/auth/logout', { refresh_token: refreshToken });
          } catch (e) {
            console.warn('Logout request failed:', e);
          }
        }
        store.clearAuth();
        toast('Signed out successfully.');
      };
    }
  }
}
