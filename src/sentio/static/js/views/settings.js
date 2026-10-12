// Settings View Controller for Sentio (ES Module)
import { store } from '../core/store.js';
import { toast } from '../components/ui.js';
import { sentioAPI } from '../core/api.js';
import { showRecoveryKey } from '../components/recovery.js';

export class SettingsView {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
  }

  init() {
    store.subscribe('currentUser', () => {
      this.render();
      this.bindEvents();
    });
  }

  render() {
    this.container.innerHTML = `
      <div class="view-header">
        <h2 style="font-family:var(--display);font-weight:800;color:var(--text);margin-bottom:6px;">Settings</h2>
        <p style="color:var(--text-dim);font-size:14px;">Manage account recovery and your saved study data.</p>
      </div>

      <div style="margin-top:20px;width:100%;">
        <sentio-card title="Your study data">
          <div style="display:flex;flex-direction:column;gap:12px;">
            <p style="color:var(--text-dim);font-size:14px;">Download your saved study data, or delete your local account and its records.</p>
            <div style="display:flex;gap:12px;margin-top:8px;">
              <button id="export-data-btn" style="background:var(--accent);color:var(--bg);border:none;padding:8px 16px;border-radius:var(--radius);font-family:var(--mono);cursor:pointer;font-size:14px;font-weight:bold;">📥 Export My Data</button>
              <button id="purge-data-btn" style="background:none;color:var(--red);border:1px solid var(--red);padding:8px 16px;border-radius:var(--radius);font-family:var(--mono);cursor:pointer;font-size:14px;font-weight:bold;">🗑️ Purge My Account Data</button>
            </div>
          </div>
        </sentio-card>

        <sentio-card title="Password recovery">
          <p>Save a recovery key so you can reset a forgotten password. Generating a new key replaces your previous key.</p>
          <label for="recovery-current-password">Current password</label>
          <input id="recovery-current-password" type="password" autocomplete="current-password">
          <button id="make-recovery-key" class="workspace-action" type="button">Generate recovery key</button>
          <p id="recovery-error" role="alert"></p><div id="recovery-key-result"></div>
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
    const keyButton = this.container.querySelector('#make-recovery-key');
    const owner = store.getState('currentUser')?.id;
    keyButton.onclick = async () => {
      if (keyButton.disabled || !owner) return;
      keyButton.disabled = true;
      try {
        const result = await sentioAPI.post('/auth/recovery-key', {
          current_password: this.container.querySelector('#recovery-current-password').value,
        });
        if (owner !== store.getState('currentUser')?.id) return;
        this.container.querySelector('#recovery-current-password').value = '';
        showRecoveryKey(this.container.querySelector('#recovery-key-result'), result.recovery_key);
      } catch (error) {
        if (owner === store.getState('currentUser')?.id)
          this.container.querySelector('#recovery-error').textContent = error.message;
      } finally {
        keyButton.disabled = false;
      }
    };
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
