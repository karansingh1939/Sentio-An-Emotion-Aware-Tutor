// Auth View Controller for Sentio (ES Module)
import { sentioAPI } from '../core/api.js';
import { store } from '../core/store.js';
import { toast } from '../components/ui.js';
import { showRecoveryKey } from '../components/recovery.js';

export class AuthView {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
    this.isRegisterMode = false;
  }

  init() {
    // Monitor auth changes to show/hide the auth container
    store.subscribe('authToken', (token) => {
      this.checkAuth(token);
    });

    // Check initial auth state
    this.checkAuth(store.getState('authToken'));
  }

  checkAuth(token) {
    const appShell = document.getElementById('sidebar');
    const headerShell = document.querySelector('header');
    const mainShell = document.getElementById('main-content');

    if (!token) {
      // Hide main app shell
      if (appShell) appShell.style.display = 'none';
      if (headerShell) headerShell.style.display = 'none';
      if (mainShell) mainShell.style.display = 'none';

      // Show auth screen
      this.container.style.display = 'flex';
      this.render();
    } else {
      // Show main app shell
      if (appShell) appShell.style.display = 'flex';
      if (headerShell) headerShell.style.display = 'flex';
      if (mainShell) mainShell.style.display = 'block';

      // Hide auth screen
      this.container.style.display = 'none';
    }
  }

  render() {
    this.container.innerHTML = `
      <div style="background:var(--bg2);border:1px solid var(--border);border-radius:var(--radius-lg);padding:30px;width:100%;max-width:400px;box-shadow:0 10px 30px rgba(0,0,0,0.3);display:flex;flex-direction:column;gap:16px;">
        <div style="text-align:center;">
          <span style="font-size:36px;">🧠</span>
          <h2 style="font-family:var(--display);font-weight:800;color:var(--text);margin-top:10px;">
            ${this.isRecoverMode ? 'Reset your password' : this.isRegisterMode ? 'Create Student Account' : 'Welcome to Sentio'}
          </h2>
          <p style="color:var(--text-dim);font-size:14px;margin-top:6px;">
            ${this.isRecoverMode ? 'Use the recovery key you saved when creating your account or in Settings.' : this.isRegisterMode ? 'Keep your notes, practice and progress together' : 'Sign in to your local study workspace'}
          </p>
        </div>

        <form id="auth-form" style="display:flex;flex-direction:column;gap:12px;margin-top:10px;">
          <div>
            <label for="auth-email" style="display:block;font-size:14px;color:var(--text-dim);margin-bottom:6px;font-weight:bold;">Email Address</label>
<input type="email" id="auth-email" autocomplete="username" required placeholder="student@sentio.edu" style="width:100%;background:var(--bg3);border:1px solid var(--border);border-radius:var(--radius);padding:10px 12px;color:var(--text);font-family:var(--mono);font-size:14px;outline:none;" />
          </div>

          ${this.isRecoverMode ? '<div><label for="auth-recovery-key">Recovery key</label><input id="auth-recovery-key" autocomplete="off" type="password"><details><summary>I do not have a recovery key</summary><p>If you can still sign in, create a key in Settings. Otherwise this local app cannot verify ownership. It cannot send reset emails. Your saved notes are not deleted by failed recovery attempts.</p></details></div>' : ''}
          <div>
            <label for="auth-password" style="display:block;font-size:14px;color:var(--text-dim);margin-bottom:6px;font-weight:bold;">${this.isRecoverMode ? 'New password' : 'Password'}</label>
<input type="password" id="auth-password" autocomplete="${this.isRegisterMode || this.isRecoverMode ? 'new-password' : 'current-password'}" required placeholder="••••••••" style="width:100%;background:var(--bg3);border:1px solid var(--border);border-radius:var(--radius);padding:10px 12px;color:var(--text);font-family:var(--mono);font-size:14px;outline:none;" />
          </div>

          ${
            this.isRegisterMode || this.isRecoverMode
              ? `
            <div>
              <label for="auth-confirm-password" style="display:block;font-size:14px;color:var(--text-dim);margin-bottom:6px;font-weight:bold;">Confirm Password</label>
<input type="password" id="auth-confirm-password" autocomplete="new-password" required placeholder="••••••••" style="width:100%;background:var(--bg3);border:1px solid var(--border);border-radius:var(--radius);padding:10px 12px;color:var(--text);font-family:var(--mono);font-size:14px;outline:none;" />
            </div>
          `
              : ''
          }

          <button id="auth-submit-btn" style="margin-top:10px;background:var(--accent);color:var(--bg);border:none;padding:12px;border-radius:var(--radius);font-family:var(--mono);font-weight:bold;cursor:pointer;font-size:14px;">
            ${this.isRecoverMode ? 'Reset password' : this.isRegisterMode ? 'Register Account' : 'Sign In'}
          </button>
        </form>
        <p id="auth-error" role="alert"></p><div id="auth-recovery-result"></div>
        ${!this.isRegisterMode && !this.isRecoverMode ? '<button id="forgot-password-btn" type="button">Forgot password?</button>' : ''}
        ${this.isRecoverMode ? '<button id="back-to-signin" type="button">Back to sign in</button>' : ''}

        <div style="text-align:center;font-size:14px;color:var(--text-dim);margin-top:10px;">
          ${
            this.isRegisterMode
              ? `
            Already have an account? <button type="button" id="auth-toggle-btn" style="color:var(--accent);cursor:pointer;font-weight:bold;text-decoration:underline;">Sign In</button>
          `
              : `
            New to Sentio? <button type="button" id="auth-toggle-btn" style="color:var(--accent);cursor:pointer;font-weight:bold;text-decoration:underline;">Create Account</button>
          `
          }
        </div>
      </div>
    `;

    this.bindEvents();
    if (this.recoveryKey)
      showRecoveryKey(this.container.querySelector('#auth-recovery-result'), this.recoveryKey);
  }

  bindEvents() {
    const toggle = this.container.querySelector('#auth-toggle-btn');
    if (toggle) {
      toggle.onclick = () => {
        this.isRecoverMode = false;
        this.isRegisterMode = !this.isRegisterMode;
        this.render();
      };
    }
    this.container.querySelector('#forgot-password-btn')?.addEventListener('click', () => {
      this.isRecoverMode = true;
      this.render();
    });
    this.container.querySelector('#back-to-signin')?.addEventListener('click', () => {
      this.isRecoverMode = false;
      this.render();
    });

    const submit = this.container.querySelector('#auth-submit-btn');
    if (submit) {
      this.container.querySelector('#auth-form').onsubmit = (event) => {
        event.preventDefault();
        this.handleSubmit();
      };
    }
  }

  async handleSubmit() {
    const email = this.container.querySelector('#auth-email').value.trim();
    const password = this.container.querySelector('#auth-password').value;
    const submit = this.container.querySelector('#auth-submit-btn');
    if (submit.disabled) return;

    if (!email || !password) {
      toast('Please fill in all fields', true);
      return;
    }

    store.setState('loading', true);
    submit.disabled = true;

    try {
      if (this.isRegisterMode || this.isRecoverMode) {
        const confirmPw = this.container.querySelector('#auth-confirm-password').value;
        if (password !== confirmPw) {
          toast('Passwords do not match', true);
          return;
        }

        const result = this.isRecoverMode
          ? await sentioAPI.post('/auth/reset-password', {
              email,
              recovery_key: this.container.querySelector('#auth-recovery-key').value.trim(),
              new_password: password,
            })
          : await sentioAPI.post('/auth/register', { email, password });
        this.recoveryKey = result.recovery_key;
        toast(
          this.isRecoverMode
            ? 'Password reset. Save your new key and sign in.'
            : 'Account created. Save your recovery key and sign in.',
        );
        this.isRegisterMode = false;
        this.isRecoverMode = false;
        this.render();
      } else {
        const res = await sentioAPI.post('/auth/login', { email, password });
        this.recoveryKey = null;
        this.container.querySelector('#auth-recovery-result').replaceChildren();

        // Save tokens in global store
        store.setState('authToken', res.access_token);
        store.setState('refreshToken', res.refresh_token);
        store.setState('currentUser', { email, id: res.student_id, role: res.role });

        toast('Welcome back to Sentio!');
      }
    } catch (e) {
      this.container.querySelector('#auth-error').textContent = e.message;
      toast(e.message, true);
    } finally {
      submit.disabled = false;
      store.setState('loading', false);
    }
  }

  async logout() {
    const refreshToken = store.getState('refreshToken');
    if (refreshToken) {
      try {
        await sentioAPI.post('/auth/logout', { refresh_token: refreshToken });
      } catch (e) {
        console.warn('Logout request failed:', e);
      }
    }

    // Clear local credentials
    store.clearAuth();
    toast('Logged out successfully.');
  }
}
