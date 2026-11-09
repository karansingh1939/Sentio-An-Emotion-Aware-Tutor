// Client-side Router for Sentio (ES Module)
import { store } from './store.js';

class SentioRouter {
  constructor() {
    this.routes = [
      '#/dashboard',
      '#/tutor',
      '#/documents',
      '#/quizzes',
      '#/flashcards',
      '#/analytics',
      '#/history',
      '#/slides',
      '#/settings',
    ];
    this.defaultRoute = '#/dashboard';
  }

  init() {
    window.addEventListener('hashchange', () => this.handleRouting());
    // Initial route load
    this.handleRouting();
  }

  handleRouting() {
    let hash = window.location.hash;
    const aliases = {
      '#/today': '#/dashboard',
      '#/library': '#/documents',
      '#/study': '#/tutor',
      '#/review': '#/quizzes',
      '#/progress': '#/analytics',
    };
    if (aliases[hash]) {
      window.location.replace(aliases[hash]);
      return;
    }
    if (!hash || !this.routes.includes(hash)) {
      hash = this.defaultRoute;
      window.location.hash = hash;
      return;
    }

    // Auth & Session Check
    const token = store.getState('authToken');
    if (!token) return;

    // We will bypass auth check if backend has authentication disabled (which we check dynamically)
    // For now, update route state
    this.updateViewVisibility(hash);
    if (store.getState('activeRoute') === hash) store.notify('activeRoute', hash);
    else store.setState('activeRoute', hash);
  }

  updateViewVisibility(activeHash) {
    const viewId = activeHash.substring(2); // e.g. '#/tutor' -> 'tutor'

    // Hide all view elements
    document.querySelectorAll('.view-container').forEach((view) => {
      view.style.display = 'none';
    });

    // Show the active view element
    const activeView = document.getElementById(`view-${viewId}`);
    if (activeView) {
      activeView.style.display = 'flex'; // Or block depending on CSS layout
    } else {
      console.warn(`View container "view-${viewId}" not found in document.`);
    }

    // Update active class on nav links
    document.querySelectorAll('.nav-link').forEach((link) => {
      if (link.getAttribute('href') === activeHash) {
        link.classList.add('active');
      } else {
        link.classList.remove('active');
      }
    });
  }

  navigateTo(route) {
    if (this.routes.includes(route)) {
      window.location.hash = route;
    }
  }
}

export const router = new SentioRouter();
