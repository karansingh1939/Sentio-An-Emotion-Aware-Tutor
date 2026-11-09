// Settings View Controller for Sentio (ES Module)
import { store } from '../core/store.js';
import { askConfirm, toast } from '../components/ui.js';
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
        <h2 class="page-title">Settings</h2>
        <p class="muted">Manage account recovery and your saved study data.</p>
      </div>

      <div style="margin-top:20px;width:100%;">
        <sentio-card title="Your study data">
          <div class="stack">
            <p class="muted">Download your saved study data, or delete your local account and its records.</p>
            <div style="display:flex;flex-wrap:wrap;gap:12px;margin-top:8px;">
              <button id="export-data-btn" class="workspace-action primary">${window.sentioIcon('download', 16)} Export my data</button>
              <button id="purge-data-btn" class="workspace-action danger">${window.sentioIcon('trash', 16)} Delete my account data</button>
            </div>
          </div>
        </sentio-card>

        <sentio-card title="Camera (optional emotion feature)" class="emotion-only">
          <label><input id="consent-cb" type="checkbox"> Allow the camera to estimate attention and emotion during study. Off by default; you can turn it off at any time.</label>
          <div class="btn-row"><button id="delete-camera-data-btn" class="workspace-action" type="button">Delete camera data</button></div>
        </sentio-card>

        <sentio-card title="Password recovery">
          <p>Save a recovery key so you can reset a forgotten password. Generating a new key replaces your previous key.</p>
          <label for="recovery-current-password">Current password</label>
          <input id="recovery-current-password" type="password" autocomplete="current-password">
          <button id="make-recovery-key" class="workspace-action" type="button">Generate recovery key</button>
          <p id="recovery-error" role="alert"></p><div id="recovery-key-result"></div>
        </sentio-card>
        <sentio-card title="Account">
          <div class="stack">
            <p class="muted">Sign out of your active student session on this machine.</p>
            <button id="signout-btn" class="workspace-action" style="align-self:flex-start;">${window.sentioIcon('logout', 16)} Sign out</button>
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
      cb.checked = Boolean(store.getState('telemetryActive'));
      cb.onchange = async (e) => {
        const allowed = e.target.checked;
        const owner = store.getState('currentUser')?.id;
        try {
          // The server checks this saved consent before accepting any camera data.
          await sentioAPI.post(`/student/${encodeURIComponent(owner)}/consent`, {
            consent_version: 'camera-v1',
            preferences: { telemetry: allowed },
          });
        } catch (error) {
          e.target.checked = !allowed;
          toast(`Camera consent could not be saved: ${error.message}`, true);
          return;
        }
        store.setState('telemetryActive', allowed);
        toast(`Camera consent ${allowed ? 'enabled' : 'disabled'}.`);
      };
    }

    const cameraData = this.container.querySelector('#delete-camera-data-btn');
    if (cameraData) {
      cameraData.onclick = async () => {
        const owner = store.getState('currentUser')?.id;
        if (!owner || cameraData.disabled) return;
        if (
          !(await askConfirm(
            'This removes your saved attention and emotion readings. Your notes, quizzes and flashcards stay.',
            { title: 'Delete all camera data?', confirmLabel: 'Delete camera data', danger: true },
          ))
        )
          return;
        cameraData.disabled = true;
        try {
          await sentioAPI.delete(`/student/${encodeURIComponent(owner)}/telemetry`);
          toast('Your camera data has been deleted.');
        } catch (error) {
          toast('Camera data was not deleted: ' + error.message, true);
        } finally {
          cameraData.disabled = false;
        }
      };
    }

    const expBtn = this.container.querySelector('#export-data-btn');
    if (expBtn) {
      expBtn.onclick = async () => {
        const studentId = store.getState('currentUser')?.id;
        if (!studentId || expBtn.disabled) return;
        // Say what happened next to the button; a corner toast is easy to miss (goldfish F16).
        let status = this.container.querySelector('#export-status');
        if (!status) {
          status = document.createElement('p');
          status.id = 'export-status';
          status.className = 'muted';
          status.setAttribute('role', 'status');
          expBtn.insertAdjacentElement('afterend', status);
        }
        expBtn.disabled = true;
        status.textContent = 'Preparing your data…';
        try {
          const res = await sentioAPI.get(`/student/${studentId}/export`);
          const blob = new Blob([JSON.stringify(res, null, 2)], { type: 'application/json' });
          const name = `sentio-export-${new Date().toISOString().slice(0, 10)}.json`;
          const url = URL.createObjectURL(blob);
          const link = document.createElement('a');
          link.href = url;
          link.download = name;
          document.body.appendChild(link);
          link.click();
          link.remove();
          setTimeout(() => URL.revokeObjectURL(url), 60000);
          const size =
            blob.size < 1024 ? `${blob.size} bytes` : `${Math.ceil(blob.size / 1024)} KB`;
          status.textContent = `Downloaded ${name} (${size}). Look in your Downloads folder.`;
        } catch (e) {
          status.textContent = 'Export failed: ' + e.message;
          toast('Export failed: ' + e.message, true);
        } finally {
          expBtn.disabled = false;
        }
      };
    }

    const purgeBtn = this.container.querySelector('#purge-data-btn');
    if (purgeBtn) {
      purgeBtn.onclick = async () => {
        if (
          !(await askConfirm(
            'Your account, notes, quizzes, flashcards and study history are deleted permanently. This cannot be undone.',
            { title: 'Delete all your data?', confirmLabel: 'Delete everything', danger: true },
          ))
        ) {
          return;
        }
        const studentId = store.getState('currentUser')?.id || 'stu_001';
        try {
          await sentioAPI.delete(`/student/${studentId}/data`);
          toast('Your data has been permanently deleted from the database.');
          store.clearAuth({ signedOut: true });
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
        store.clearAuth({ signedOut: true });
        toast('Signed out successfully.');
      };
    }
  }
}
