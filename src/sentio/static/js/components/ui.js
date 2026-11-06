// Reusable Web Components for Sentio UI (ES Module)
import { escapeHtml } from '../core/html.js';

// 1. Toast Notification Component
export class SentioToast extends HTMLElement {
  connectedCallback() {
    this.message = this.getAttribute('message') || '';
    this.isError = this.hasAttribute('error');
    this.duration = parseInt(this.getAttribute('duration')) || 4000;

    this.render();
    setTimeout(() => this.dismiss(), this.duration);
  }

  render() {
    this.style.position = 'fixed';
    this.style.bottom = '20px';
    this.style.right = '20px';
    this.style.zIndex = '10000';
    this.style.display = 'flex';
    this.style.alignItems = 'center';
    this.style.gap = '10px';
    this.style.padding = '12px 18px';
    this.style.borderRadius = 'var(--radius)';
    this.style.background = 'var(--bg2)';
    this.style.border = `1px solid ${this.isError ? 'var(--red)' : 'var(--border)'}`;
    this.style.boxShadow = '0 4px 16px #0001';
    this.style.color = this.isError ? 'var(--red)' : 'var(--text)';
    this.style.fontSize = '14px';
    this.style.transition = 'opacity var(--dur-slow) var(--ease)';
    this.style.opacity = '0';

    this.innerHTML = `
      ${window.sentioIcon(this.isError ? 'alert' : 'check', 16)}
      <span>${escapeHtml(this.message)}</span>
    `;

    // Trigger animate-in
    requestAnimationFrame(() => {
      this.style.opacity = '1';
    });
  }

  dismiss() {
    if (this.dismissed) return;
    this.dismissed = true;
    this.style.pointerEvents = 'none';
    this.style.transition = 'opacity var(--dur) var(--ease)';
    this.style.opacity = '0';
    this.addEventListener('transitionend', () => this.remove(), { once: true });
    // Fallback: no transition runs if the toast was never visible.
    setTimeout(() => this.remove(), 400);
  }
}
customElements.define('sentio-toast', SentioToast);

// Global Toast helper
export function toast(message, isError = false) {
  document.querySelectorAll('sentio-toast').forEach((old) => old.dismiss());
  const el = document.createElement('sentio-toast');
  el.setAttribute('message', message);
  if (isError) el.setAttribute('error', '');
  document.body.appendChild(el);
}

// 2. Global Loader Spinner Component
export class SentioLoader extends HTMLElement {
  connectedCallback() {
    this.style.display = 'inline-block';
    this.style.width = this.getAttribute('size') || '18px';
    this.style.height = this.getAttribute('size') || '18px';
    this.style.border = '2px solid var(--border)';
    this.style.borderTop = '2px solid var(--accent)';
    this.style.borderRadius = '50%';
    this.style.animation = 'spin 0.8s linear infinite';

    // Inject keyframes if not present
    if (!document.getElementById('sentio-spinner-style')) {
      const style = document.createElement('style');
      style.id = 'sentio-spinner-style';
      style.innerHTML = `
        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
      `;
      document.head.appendChild(style);
    }
  }
}
customElements.define('sentio-loader', SentioLoader);

// 3. Card Component
export class SentioCard extends HTMLElement {
  connectedCallback() {
    const title = this.getAttribute('title') || '';
    const outline = this.hasAttribute('outline') ? '1px solid var(--border)' : 'none';
    this.style.display = 'block';
    this.style.background = 'var(--bg2)';
    this.style.border = outline;
    this.style.borderRadius = 'var(--radius)';
    this.style.padding = '16px';
    this.style.marginBottom = '16px';

    const children = this.innerHTML;
    this.innerHTML = `
      ${title ? `<div style="font-family:var(--display);font-weight:700;margin-bottom:12px;color:var(--text);font-size:16px;">${escapeHtml(title)}</div>` : ''}
      <div class="card-content">${children}</div>
    `;
  }
}
customElements.define('sentio-card', SentioCard);

// 4. Modal Dialog Component
export class SentioModal extends HTMLElement {
  connectedCallback() {
    this.previousFocus = document.activeElement;
    this.title = this.getAttribute('title') || 'Alert';
    this.setAttribute('role', 'dialog');
    this.setAttribute('aria-modal', 'true');
    this.setAttribute('aria-label', this.title);
    this.style.position = 'fixed';
    this.style.inset = '0';
    this.style.zIndex = '9999';
    this.style.display = 'flex';
    this.style.alignItems = 'center';
    this.style.justifyContent = 'center';
    this.style.background = 'rgb(22 27 36 / 0.45)';
    this.style.backdropFilter = 'blur(4px)';

    const bodyContent = this.innerHTML;
    this.innerHTML = `
      <div style="background:var(--bg2);border:1px solid var(--border);border-radius:var(--radius-lg);width:90%;max-width:500px;box-shadow:0 12px 32px rgb(0 0 0 / 0.12);display:flex;flex-direction:column;overflow:hidden;">
        <div style="display:flex;align-items:center;justify-content:space-between;padding:16px 20px;border-bottom:1px solid var(--border);background:var(--bg3);">
          <span style="font-family:var(--display);font-weight:700;font-size:16px;">${escapeHtml(this.title)}</span>
          <button id="modal-close-btn" aria-label="Close dialog" style="background:none;border:none;color:var(--text-dim);cursor:pointer;font-size:16px;">&times;</button>
        </div>
        <div style="padding:20px;max-height:70vh;overflow-y:auto;font-family:var(--mono);">
          ${bodyContent}
        </div>
      </div>
    `;

    this.querySelector('#modal-close-btn').onclick = () => this.close();
    this.onKey = (event) => {
      if (Array.from(document.querySelectorAll('sentio-modal')).at(-1) !== this) return;
      if (event.key === 'Escape') {
        event.preventDefault();
        this.close();
      }
      if (event.key === 'Tab') {
        const controls = Array.from(
          this.querySelectorAll('button, input, select, textarea, a[href], [tabindex="0"]'),
        ).filter((el) => !el.disabled && el.getClientRects().length);
        const first = controls[0],
          last = controls.at(-1);
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        }
        if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener('keydown', this.onKey);
    queueMicrotask(() => this.querySelector('#modal-close-btn')?.focus());
  }

  disconnectedCallback() {
    document.removeEventListener('keydown', this.onKey);
    // A choice made inside a closed menu returns focus to that menu's button.
    const closedMenu = this.previousFocus?.closest?.('details:not([open])');
    const target = closedMenu ? closedMenu.querySelector('summary') : this.previousFocus;
    if (target?.isConnected) target.focus();
  }

  close() {
    this.remove();
  }
}
customElements.define('sentio-modal', SentioModal);

// 5. Empty State View Component
export class SentioEmptyState extends HTMLElement {
  connectedCallback() {
    const message = this.getAttribute('message') || 'No records found';
    const icon = this.getAttribute('icon') || 'folder';
    this.style.display = 'flex';
    this.style.flexDirection = 'column';
    this.style.alignItems = 'center';
    this.style.justifyContent = 'center';
    this.style.padding = '40px 20px';
    this.style.color = 'var(--text-dim)';
    this.style.fontFamily = 'var(--mono)';

    this.innerHTML = `
      <div style="margin-bottom:12px;color:var(--text-dim);">${window.sentioIcon(icon, 28)}</div>
      <div style="font-size:14px;text-align:center;">${escapeHtml(message)}</div>
    `;
  }
}
customElements.define('sentio-empty-state', SentioEmptyState);
