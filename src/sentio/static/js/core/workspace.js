import { store } from './store.js';
import { moveTabPill, watchView } from './motion.js';

const SUN =
  '<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>';
const MOON =
  '<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z"/></svg>';

const groups = {
  '#/quizzes': [
    ['#/quizzes', 'Quizzes'],
    ['#/flashcards', 'Flashcards'],
  ],
  '#/flashcards': [
    ['#/quizzes', 'Quizzes'],
    ['#/flashcards', 'Flashcards'],
  ],
  '#/analytics': [
    ['#/analytics', 'Progress'],
    ['#/history', 'History'],
  ],
  '#/history': [
    ['#/analytics', 'Progress'],
    ['#/history', 'History'],
  ],
  '#/slides': [
    ['#/documents', 'Library'],
    ['#/tutor', 'Study'],
    ['#/slides', 'Study slides'],
  ],
};

export function initWorkspace() {
  const toggle = document.getElementById('theme-toggle');
  store.subscribe('theme', (theme) => {
    const selected = theme === 'dark' ? 'dark' : 'light';
    document.documentElement.dataset.theme = selected;
    // Match the phone's status bar to the sheet colour at the top of the page.
    const bar = getComputedStyle(document.documentElement).getPropertyValue('--bg2').trim();
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content', bar);
    // The icon shows the theme you would switch to.
    toggle.innerHTML = selected === 'dark' ? SUN : MOON;
    const label = selected === 'dark' ? 'Switch to light theme' : 'Switch to dark theme';
    toggle.setAttribute('aria-label', label);
    toggle.title = label;
    toggle.setAttribute('aria-pressed', String(selected === 'dark'));
  });
  toggle.onclick = () =>
    store.setState('theme', store.getState('theme') === 'dark' ? 'light' : 'dark');
  store.subscribe('activeRoute', (route) => {
    const tools = document.getElementById('workspace-tools');
    const links = groups[route] || [];
    tools.innerHTML = links
      .map(
        ([href, label]) =>
          `<a href="${href}" ${route === href ? 'aria-current="page"' : ''}>${label}</a>`,
      )
      .join('');
    tools.hidden = !links.length;
    const parent =
      route === '#/flashcards' ? '#/quizzes' : route === '#/slides' ? '#/documents' : route;
    document.querySelectorAll('.nav-link').forEach((link) => {
      const active = link.getAttribute('href') === parent;
      link.classList.toggle('active', active);
      if (active) link.setAttribute('aria-current', 'page');
      else link.removeAttribute('aria-current');
    });
    moveTabPill(document.querySelector('#sidebar .nav-links'));
    // Views swap in their loading line synchronously; animate once real content arrives.
    if (route) queueMicrotask(() => watchView(document.getElementById(`view-${route.slice(2)}`)));
  });
  // Initials from the account email, for the account button.
  store.subscribe('currentUser', (user) => {
    const button = document.querySelector('.account-btn');
    if (button) button.textContent = (user?.email || '··').slice(0, 2).toUpperCase();
  });
  window.addEventListener('resize', () =>
    moveTabPill(document.querySelector('#sidebar .nav-links'), { instant: true }),
  );
  document.fonts?.ready.then(() =>
    moveTabPill(document.querySelector('#sidebar .nav-links'), { instant: true }),
  );
}
