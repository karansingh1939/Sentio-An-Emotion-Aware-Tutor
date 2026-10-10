// Auth View Controller for Sentio (ES Module)
import { sentioAPI } from '../core/api.js';
import { store } from '../core/store.js';
import { toast } from '../components/ui.js';

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
            ${this.isRegisterMode ? 'Create Student Account' : 'Welcome to Sentio'}
          </h2>
          <p style="color:var(--text-dim);font-size:11px;margin-top:6px;">
            ${this.isRegisterMode ? 'Register to start your emotion-aware tutoring journey' : 'Login using your student credentials'}
          </p>
        </div>

        <div style="display:flex;flex-direction:column;gap:12px;margin-top:10px;">
          <div>
            <label style="display:block;font-size:10px;color:var(--text-dim);margin-bottom:6px;font-weight:bold;">Email Address</label>
            <input type="email" id="auth-email" placeholder="student@sentio.edu" style="width:100%;background:var(--bg3);border:1px solid var(--border);border-radius:var(--radius);padding:10px 12px;color:var(--text);font-family:var(--mono);font-size:11px;outline:none;" />
          </div>

          <div>
            <label style="display:block;font-size:10px;color:var(--text-dim);margin-bottom:6px;font-weight:bold;">Password</label>
            <input type="password" id="auth-password" placeholder="••••••••" style="width:100%;background:var(--bg3);border:1px solid var(--border);border-radius:var(--radius);padding:10px 12px;color:var(--text);font-family:var(--mono);font-size:11px;outline:none;" />
          </div>

          ${
            this.isRegisterMode
              ? `
            <div>
              <label style="display:block;font-size:10px;color:var(--text-dim);margin-bottom:6px;font-weight:bold;">Confirm Password</label>
              <input type="password" id="auth-confirm-password" placeholder="••••••••" style="width:100%;background:var(--bg3);border:1px solid var(--border);border-radius:var(--radius);padding:10px 12px;color:var(--text);font-family:var(--mono);font-size:11px;outline:none;" />
            </div>
          `
              : ''
          }

          <button id="auth-submit-btn" style="margin-top:10px;background:var(--accent);color:var(--bg);border:none;padding:12px;border-radius:var(--radius);font-family:var(--mono);font-weight:bold;cursor:pointer;font-size:11px;">
            ${this.isRegisterMode ? 'Register Account' : 'Sign In'}
          </button>
        </div>

        <div style="text-align:center;font-size:11px;color:var(--text-dim);margin-top:10px;">
          ${
            this.isRegisterMode
              ? `
            Already have an account? <span id="auth-toggle-btn" style="color:var(--accent);cursor:pointer;font-weight:bold;text-decoration:underline;">Sign In</span>
          `
              : `
            New to Sentio? <span id="auth-toggle-btn" style="color:var(--accent);cursor:pointer;font-weight:bold;text-decoration:underline;">Create Account</span>
          `
          }
        </div>
      </div>
    `;

    this.bindEvents();
  }

  bindEvents() {
    const toggle = this.container.querySelector('#auth-toggle-btn');
    if (toggle) {
      toggle.onclick = () => {
        this.isRegisterMode = !this.isRegisterMode;
        this.render();
      };
    }

    const submit = this.container.querySelector('#auth-submit-btn');
    if (submit) {
      submit.onclick = () => this.handleSubmit();
    }
  }

  async handleSubmit() {
    const email = this.container.querySelector('#auth-email').value.trim();
    const password = this.container.querySelector('#auth-password').value;

    if (!email || !password) {
      toast('Please fill in all fields', true);
      return;
    }

    store.setState('loading', true);

    try {
      if (this.isRegisterMode) {
        const confirmPw = this.container.querySelector('#auth-confirm-password').value;
        if (password !== confirmPw) {
          toast('Passwords do not match', true);
          return;
        }

        await sentioAPI.post('/auth/register', { email, password });
        toast('Registration successful! Please sign in.');
        this.isRegisterMode = false;
        this.render();
      } else {
        const res = await sentioAPI.post('/auth/login', { email, password });

        // Save tokens in global store
        store.setState('authToken', res.access_token);
        store.setState('refreshToken', res.refresh_token);
        store.setState('currentUser', { email, id: res.student_id, role: res.role });

        toast('Welcome back to Sentio!');
      }
    } catch (e) {
      toast(e.message, true);
    } finally {
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
