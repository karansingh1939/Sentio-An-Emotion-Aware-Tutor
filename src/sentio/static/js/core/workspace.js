import { store } from './store.js';

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
};

export function initWorkspace() {
  const toggle = document.getElementById('theme-toggle');
  store.subscribe('theme', (theme) => {
    const selected = theme === 'dark' ? 'dark' : 'light';
    document.documentElement.dataset.theme = selected;
    toggle.textContent = selected === 'dark' ? 'Light theme' : 'Dark theme';
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
    const parent = route === '#/flashcards' ? '#/quizzes' : route;
    document.querySelectorAll('.nav-link').forEach((link) => {
      const active = link.getAttribute('href') === parent;
      link.classList.toggle('active', active);
      if (active) link.setAttribute('aria-current', 'page');
      else link.removeAttribute('aria-current');
    });
  });
}
