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
      // Clear the inline value so the stylesheet's flex layout (and scrolling) applies.
      if (mainShell) mainShell.style.display = '';

      // Hide auth screen
      this.container.style.display = 'none';
    }
  }

  render() {
    const mode = this.isRecoverMode ? 'recover' : this.isRegisterMode ? 'register' : 'signin';
    const heading = {
      signin: 'Welcome back',
      register: 'Create your account',
      recover: 'Reset your password',
    }[mode];
    const lead = {
      signin: 'Sign in to your study workspace.',
      register: 'Keep your notes, practice and progress together.',
      recover: 'Use the recovery key you saved when you created your account, or from Settings.',
    }[mode];
    const submitLabel = {
      signin: 'Sign in',
      register: 'Create account',
      recover: 'Reset password',
    }[mode];
    this.container.innerHTML = `
      <div class="auth-shell">
        <section class="auth-main" aria-labelledby="auth-heading">
          <div class="auth-brand">
            ${window.sentioSymbol(28)}
            <svg class="sentio-wordmark" viewBox="0 0 854 100" role="img" aria-label="Sentio"><g fill="none" stroke="currentColor"><path d="M110 4H4V50H106V96H0"/><path d="M270 4H178V96H270M178 50H249"/><path d="M338 100V4L440 96V0"/><path d="M500 4H610M555 4V100"/><path d="M666 0V100"/><rect x="738" y="4" width="112" height="92" rx="10"/></g></svg>
          </div>
          <div class="auth-form-wrap">
            <h1 id="auth-heading" class="auth-heading">${heading}</h1>
            <p class="auth-lead">${lead}</p>

            <form id="auth-form" class="auth-form">
              <div class="auth-field">
                <label class="form-label" for="auth-email">Email address</label>
                <input class="input" type="email" id="auth-email" autocomplete="username" autocapitalize="none" autocorrect="off" spellcheck="false" required placeholder="you@university.edu" />
              </div>
              ${
                mode === 'recover'
                  ? `<div class="auth-field">
                <label class="form-label" for="auth-recovery-key">Recovery key</label>
                <input class="input" id="auth-recovery-key" autocomplete="off" autocapitalize="none" autocorrect="off" spellcheck="false" type="password" />
                <details class="auth-help"><summary>I don’t have a recovery key</summary><p>If you can still sign in, create a key in Settings. Otherwise this local app can’t verify ownership, and it can’t send reset emails. Failed attempts never delete your saved notes.</p></details>
              </div>`
                  : ''
              }
              <div class="auth-field">
                <div class="auth-label-row">
                  <label class="form-label" for="auth-password">${mode === 'recover' ? 'New password' : 'Password'}</label>
                  ${mode === 'signin' ? '<button id="forgot-password-btn" class="link-quiet" type="button">Forgot password?</button>' : ''}
                </div>
                <input class="input" type="password" id="auth-password" autocomplete="${mode === 'signin' ? 'current-password' : 'new-password'}" required />
              </div>
              ${
                mode !== 'signin'
                  ? `<div class="auth-field">
                <label class="form-label" for="auth-confirm-password">Confirm password</label>
                <input class="input" type="password" id="auth-confirm-password" autocomplete="new-password" required />
              </div>`
                  : ''
              }
              <button id="auth-submit-btn" class="workspace-action primary auth-submit" type="submit">${submitLabel}</button>
            </form>
            <p id="auth-error" class="auth-error" role="alert"></p>
            <div id="auth-recovery-result"></div>
            ${mode === 'recover' ? '<button id="back-to-signin" class="link-quiet auth-switch" type="button">Back to sign in</button>' : ''}
            <p class="auth-switch-row">
              ${
                mode === 'register'
                  ? 'Already have an account? <button class="accent-strong" type="button" id="auth-toggle-btn">Sign in</button>'
                  : 'New to Sentio? <button class="accent-strong" type="button" id="auth-toggle-btn">Create an account</button>'
              }
            </p>
          </div>
          <p class="auth-local">${window.sentioIcon('folder', 16)} Your account and notes stay on this computer.</p>
        </section>

        <aside class="auth-aside" aria-label="How Sentio answers">
          <div class="auth-aside-inner">
            <p class="auth-promise">Answers only from your notes.</p>
            <p class="auth-promise-sub">Every explanation cites the slide or page it came from. When your notes don’t cover a question, Sentio says so.</p>
            <div class="auth-example" aria-hidden="true">
              <p class="auth-example-q">What is inertia?</p>
              <div class="auth-example-a">
                <p>Inertia is an object’s resistance to a change in its velocity <span class="cite-chip inline">mechanics.pdf · p.1</span></p>
              </div>
              <blockquote class="cited-passage">Inertia resists changes in velocity. A net force changes velocity. Mass measures inertia.</blockquote>
            </div>
          </div>
        </aside>
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
      toast('Enter your email and password.', true);
      return;
    }

    store.setState('loading', true);
    submit.disabled = true;

    try {
      if (this.isRegisterMode || this.isRecoverMode) {
        const confirmPw = this.container.querySelector('#auth-confirm-password').value;
        if (password !== confirmPw) {
          toast('Those passwords don’t match.', true);
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
        // Keep the email so signing in needs only the password.
        this.container.querySelector('#auth-email').value = email;
        this.container.querySelector('#auth-password')?.focus();
      } else {
        const res = await sentioAPI.post('/auth/login', { email, password });
        this.recoveryKey = null;
        this.container.querySelector('#auth-recovery-result').replaceChildren();

        // Save tokens in global store
        store.setState('authToken', res.access_token);
        store.setState('refreshToken', res.refresh_token);
        store.setState('currentUser', { email, id: res.student_id, role: res.role });

        toast('Signed in.');
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
