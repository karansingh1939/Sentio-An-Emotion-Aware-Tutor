// Main Application Entry Point for Sentio (ES Module)
import { store } from './core/store.js';
import { sentioAPI } from './core/api.js';
import { router } from './core/router.js';
import { toast } from './components/ui.js';
import { DashboardView } from './views/dashboard.js';
import { SettingsView } from './views/settings.js';
import { DocumentsView } from './views/documents.js';
import { QuizzesView } from './views/quizzes.js';
import { FlashcardsView } from './views/flashcards.js';
import { AnalyticsView } from './views/analytics.js';
import { HistoryView } from './views/history.js';
import { TutorView } from './views/tutor.js';
import { SlidesView } from './views/slides.js';
import { AuthView } from './views/auth.js';
import { initWorkspace } from './core/workspace.js';

// Setup view controllers mapping
const viewControllers = {
  dashboard: new DashboardView('view-dashboard'),
  tutor: new TutorView('view-tutor'),
  settings: new SettingsView('view-settings'),
  documents: new DocumentsView('view-documents'),
  quizzes: new QuizzesView('view-quizzes'),
  flashcards: new FlashcardsView('view-flashcards'),
  analytics: new AnalyticsView('view-analytics'),
  history: new HistoryView('view-history'),
  slides: new SlidesView('view-slides'),
};

// Global App Initialization
function initApp() {
  initWorkspace();
  console.log('Initializing Sentio Web HUD App Shell...');
  window.store = store;
  window.sentioAPI = sentioAPI;
  window.tutorView = viewControllers['tutor'];

  // Initialize auth overlay check
  new AuthView('view-auth').init();

  // Initialize view modules
  Object.values(viewControllers).forEach((view) => {
    try {
      view.init();
    } catch (e) {
      console.error('Failed to initialize view controller:', e);
    }
  });

  store.subscribe('currentUser', (user) => {
    if (user) router.handleRouting();
  });
  router.init();

  // Telemetry consent monitoring based on routing
  store.subscribe('activeRoute', (route) => {
    handleWebcamStateForRoute(route);
  });
  store.subscribe('telemetryActive', () =>
    handleWebcamStateForRoute(store.getState('activeRoute')),
  );
  store.subscribe('currentUser', () => window.stopWebcam?.());
  store.subscribe('activeSessionId', () => window.stopWebcam?.());

  // Global loading overlay toggle
  store.subscribe('loading', (isLoading) => {
    const spinner = document.getElementById('global-spinner');
    if (spinner) {
      spinner.style.display = isLoading ? 'flex' : 'none';
    }
  });
}

// Automatically start/stop webcam depending on route rules
function handleWebcamStateForRoute(route) {
  const telemetryRoutes = ['#/tutor', '#/quizzes', '#/flashcards'];
  const telemetryDot = document.getElementById('telemetry-status-dot');

  if (telemetryRoutes.includes(route)) {
    // If route requires telemetry and consent is enabled, start it
    if (store.getState('telemetryActive')) {
      if (telemetryDot) {
        telemetryDot.className = 'dot live';
        telemetryDot.title = 'Camera telemetry tracking is active';
      }
      // Trigger camera capture start if window.startWebcam exists (from legacy script)
      if (typeof window.startWebcam === 'function' && !window.camStream) {
        window.startWebcam();
      }
    } else {
      window.stopWebcam?.();
      if (telemetryDot) {
        telemetryDot.className = 'dot';
        telemetryDot.title = 'Telemetry consent disabled in Settings';
      }
    }
  } else {
    // Stop camera on dashboard, docs, analytics, history, settings
    if (telemetryDot) {
      telemetryDot.className = 'dot';
      telemetryDot.title = 'Telemetry inactive on this screen';
    }
    if (typeof window.stopWebcam === 'function') {
      window.stopWebcam();
    }
  }
}

// Start application on DOM content ready
// Dev-only sample data for stress tests loads first, and only when the URL carries ?data=….
const samples = new URLSearchParams(window.location.search).has('data')
  ? import('./dev/data_fixtures.js')
  : Promise.resolve();
document.addEventListener('DOMContentLoaded', () => samples.then(initApp));

// Menus built from <details class="row-menu"> close after a choice, on an
// outside click, and on Escape (focus returns to the menu button).
document.addEventListener('click', (event) => {
  document.querySelectorAll('details.row-menu[open]').forEach((menu) => {
    const chose = menu.contains(event.target) && event.target.closest('.row-menu-item');
    if (chose || !menu.contains(event.target)) menu.open = false;
    // Keep keyboard focus on the menu button rather than losing it to the page.
    if (chose) menu.querySelector('summary').focus();
  });
});
document.addEventListener('keydown', (event) => {
  if (event.key !== 'Escape') return;
  const menu = event.target.closest?.('details.row-menu[open]');
  if (!menu) return;
  menu.open = false;
  menu.querySelector('summary').focus();
});
