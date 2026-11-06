// Centralized API Client Layer for Sentio (ES Module)
import { store } from './store.js';

export const API_BASE = `${window.location.origin}/api/v1`;

class SentioAPIClient {
  constructor() {
    this.defaultTimeout = 30000; // 30 seconds
    this.pending = 0;
    this.refreshRequest = null;
  }

  sameIdentity(owner, refreshToken) {
    return (
      store.getState('currentUser')?.id === owner && store.getState('refreshToken') === refreshToken
    );
  }

  async refreshAccess(owner, refreshToken, signal) {
    if (this.refreshRequest?.owner === owner && this.refreshRequest?.token === refreshToken) {
      return this.refreshRequest.promise;
    }
    const operation = { owner, token: refreshToken };
    operation.promise = (async () => {
      const response = await fetch(`${API_BASE}/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshToken }),
        signal,
      });
      if (!response.ok) {
        const failure = new Error('Session refresh failed. Retry shortly.');
        failure.status = response.status;
        throw failure;
      }
      const data = await response.json();
      if (!this.sameIdentity(owner, refreshToken))
        throw new Error('The account changed while this request was running.');
      if (typeof data.access_token !== 'string' || !data.access_token)
        throw new Error('Session refresh returned an invalid response.');
      store.setState('authToken', data.access_token);
    })().finally(() => {
      if (this.refreshRequest === operation) this.refreshRequest = null;
    });
    this.refreshRequest = operation;
    return operation.promise;
  }

  // Common request handler. With `stream: true` the Response is returned unread and the
  // caller's signal stays connected, so a streamed body can still be cancelled.
  async request(endpoint, options = {}) {
    // Dev-only sample data (?data=…): GETs may come from fixtures, and writes are refused.
    const sample = globalThis.sentioFixtures;
    if (sample?.active()) {
      const method = (options.method || 'GET').toUpperCase();
      if (method === 'GET') {
        const data = sample.fixtureFor(endpoint);
        if (data !== undefined) return structuredClone(data);
      } else if (!endpoint.startsWith('/auth/')) {
        throw new Error('Saving is off while sample data is shown. Switch to Demo data first.');
      }
    }
    const url = endpoint.startsWith('http') ? endpoint : `${API_BASE}${endpoint}`;

    // Setup AbortController for timeouts/cancellations
    const controller = new AbortController();
    const cancel = () => controller.abort();
    if (options.signal?.aborted) cancel();
    options.signal?.addEventListener('abort', cancel, { once: true });
    const generationTimeout = endpoint.endsWith('/generate') ? 370000 : this.defaultTimeout;
    const id = setTimeout(() => controller.abort(), options.timeout || generationTimeout);

    const headers = {
      ...options.headers,
    };

    if (!(options.body instanceof FormData)) {
      headers['Content-Type'] = 'application/json';
    }

    // Inject Auth token if available
    const token = store.getState('authToken');
    const owner = store.getState('currentUser')?.id;
    const refreshToken = store.getState('refreshToken');
    const needsSession = ![
      '/auth/login',
      '/auth/register',
      '/auth/reset-password',
      '/auth/refresh',
      '/auth/logout',
    ].includes(endpoint);
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const fetchOptions = {
      ...options,
      headers,
      signal: controller.signal,
    };

    // Background polls (such as the camera mood) do not show the loading overlay.
    const quiet = options.background;
    if (!quiet) {
      this.pending++;
      store.setState('loading', true);
    }

    try {
      const response = await fetch(url, fetchOptions);
      if (!this.sameIdentity(owner, refreshToken))
        throw new Error('The account changed while this request was running.');

      if (!response.ok) {
        if (
          needsSession &&
          response.status === 401 &&
          token !== store.getState('authToken') &&
          !options._isRetry
        )
          return this.request(endpoint, { ...options, _isRetry: true });
        if (needsSession && response.status === 401 && !options._isRetry) {
          if (refreshToken) {
            try {
              await this.refreshAccess(owner, refreshToken, controller.signal);
              return this.request(endpoint, { ...options, _isRetry: true });
            } catch (err) {
              if (!this.sameIdentity(owner, refreshToken))
                throw new Error('The account changed while this request was running.');
              if (token !== store.getState('authToken'))
                return this.request(endpoint, { ...options, _isRetry: true });
              if (err.status !== 401) throw err;
            }
          }
          // Logout user on failure
          store.clearAuth();
          toast('Session expired. Please log in again.', true);
        }

        let errorMessage = `API Error: ${response.status} ${response.statusText}`;
        try {
          const jsonErr = await response.json();
          errorMessage = jsonErr.detail || errorMessage;
        } catch (_) {}
        const failure = new Error(errorMessage);
        failure.status = response.status;
        throw failure;
      }

      if (options.stream) return response;
      // Handle raw responses or JSON
      const contentType = response.headers.get('content-type');
      if (contentType && contentType.includes('application/json')) {
        const data = await response.json();
        if (!this.sameIdentity(owner, refreshToken))
          throw new Error('The account changed while this request was running.');
        return data;
      }
      return response;
    } catch (error) {
      if (error.name === 'AbortError') {
        if (options.signal?.aborted) throw error;
        throw new Error('Request timed out');
      }
      throw error;
    } finally {
      clearTimeout(id);
      if (!options.stream) options.signal?.removeEventListener('abort', cancel);
      if (!quiet) {
        this.pending--;
        store.setState('loading', this.pending > 0);
      }
    }
  }

  // Get helper
  get(endpoint, options = {}) {
    return this.request(endpoint, { ...options, method: 'GET' });
  }

  // Post helper
  post(endpoint, body, options = {}) {
    return this.request(endpoint, {
      ...options,
      method: 'POST',
      body: JSON.stringify(body),
    });
  }

  // Delete helper
  delete(endpoint, options = {}) {
    return this.request(endpoint, { ...options, method: 'DELETE' });
  }
}

export const sentioAPI = new SentioAPIClient();
