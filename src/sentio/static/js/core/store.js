// Global State Store for Sentio (ES Module)

class SentioStore {
  constructor() {
    let currentUser = null;
    try {
      currentUser = JSON.parse(localStorage.getItem('sentio_user'));
    } catch {
      localStorage.removeItem('sentio_user');
    }
    this.state = {
      currentUser,
      authToken: localStorage.getItem('sentio_token') || null,
      refreshToken: localStorage.getItem('sentio_refresh_token') || null,
      activeSessionId: localStorage.getItem('sentio_session_id') || null,
      activeSession: null, // Full session object
      activeRoute: '#/dashboard',
      notifications: [],
      loading: false,
      // First visit follows the system setting; a choice made in the app is remembered.
      theme:
        localStorage.getItem('sentio_theme') ||
        (window.matchMedia?.('(prefers-color-scheme: dark)')?.matches ? 'dark' : 'light'),
      telemetryActive: false,
      telemetryLog: [],
      currentMastery: {}, // Topic-wise mastery map
    };
    this.listeners = {};
  }

  // Subscribe to changes in a specific state key
  subscribe(key, callback) {
    if (!this.listeners[key]) {
      this.listeners[key] = [];
    }
    this.listeners[key].push(callback);
    // Immediately call with current value
    callback(this.state[key]);
    return () => {
      this.listeners[key] = this.listeners[key].filter((cb) => cb !== callback);
    };
  }

  // Set state and notify listeners
  setState(key, value) {
    if (this.state[key] !== value) {
      this.state[key] = value;
      this.notify(key, value);

      // Persist specific keys to localStorage
      if (key === 'currentUser') {
        if (value) localStorage.setItem('sentio_user', JSON.stringify(value));
        else localStorage.removeItem('sentio_user');
      } else if (key === 'authToken') {
        if (value) localStorage.setItem('sentio_token', value);
        else localStorage.removeItem('sentio_token');
      } else if (key === 'refreshToken') {
        if (value) localStorage.setItem('sentio_refresh_token', value);
        else localStorage.removeItem('sentio_refresh_token');
      } else if (key === 'activeSessionId') {
        if (value) localStorage.setItem('sentio_session_id', value);
        else localStorage.removeItem('sentio_session_id');
      } else if (key === 'theme') {
        localStorage.setItem('sentio_theme', value);
      }
    }
  }

  // Get state value
  getState(key) {
    return this.state[key];
  }

  // Notify listeners
  notify(key, value) {
    if (this.listeners[key]) {
      this.listeners[key].forEach((callback) => {
        try {
          callback(value);
        } catch (e) {
          console.error(`Error in state listener for key "${key}":`, e);
        }
      });
    }
  }

  // Logout and clear state
  clearAuth() {
    if (typeof window.cleanupSession === 'function') window.cleanupSession();
    this.setState('telemetryActive', false);
    this.setState('telemetryLog', []);
    this.setState('currentMastery', {});
    this.setState('authToken', null);
    this.setState('refreshToken', null);
    this.setState('activeSessionId', null);
    this.setState('activeSession', null);
    this.setState('currentUser', null);
  }
}

export const store = new SentioStore();
