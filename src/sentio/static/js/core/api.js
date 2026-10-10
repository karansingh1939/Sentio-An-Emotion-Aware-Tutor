// Centralized API Client Layer for Sentio (ES Module)
import { store } from './store.js';

export const API_BASE = `${window.location.origin}/api/v1`;

class SentioAPIClient {
  constructor() {
    this.defaultTimeout = 30000; // 30 seconds
  }

  // Common request handler
  async request(endpoint, options = {}) {
    const url = endpoint.startsWith('http') ? endpoint : `${API_BASE}${endpoint}`;

    // Setup AbortController for timeouts/cancellations
    const controller = new AbortController();
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
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const fetchOptions = {
      ...options,
      headers,
      signal: controller.signal,
    };

    store.setState('loading', true);

    try {
      const response = await fetch(url, fetchOptions);
      clearTimeout(id);

      if (!response.ok) {
        if (response.status === 401 && !options._isRetry) {
          const refreshToken = store.getState('refreshToken');
          if (refreshToken) {
            try {
              const refreshRes = await fetch(`${API_BASE}/auth/refresh`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ refresh_token: refreshToken }),
              });
              if (refreshRes.ok) {
                const refreshData = await refreshRes.json();
                store.setState('authToken', refreshData.access_token);
                // Retry request
                return this.request(endpoint, { ...options, _isRetry: true });
              }
            } catch (err) {
              console.warn('Refresh token invalid:', err);
            }
          }
          // Logout user on failure
          store.setState('authToken', null);
          store.setState('refreshToken', null);
          store.setState('currentUser', null);
          toast('Session expired. Please log in again.', true);
        }

        let errorMessage = `API Error: ${response.status} ${response.statusText}`;
        try {
          const jsonErr = await response.json();
          errorMessage = jsonErr.detail || errorMessage;
        } catch (_) {}
        throw new Error(errorMessage);
      }

      // Handle raw responses or JSON
      const contentType = response.headers.get('content-type');
      if (contentType && contentType.includes('application/json')) {
        return await response.json();
      }
      return response;
    } catch (error) {
      clearTimeout(id);
      if (error.name === 'AbortError') {
        throw new Error('Request timed out');
      }
      throw error;
    } finally {
      store.setState('loading', false);
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

  // Fetch streaming responses (specifically for tutor chat responses)
  async fetchStream(endpoint, body, onChunk, onDone, onError) {
    const url = `${API_BASE}${endpoint}`;
    const token = store.getState('authToken');
    const headers = {
      'Content-Type': 'application/json',
    };
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 200000);
    try {
      const response = await fetch(url, {
        method: 'POST',
        headers,
        body: JSON.stringify(body),
        signal: controller.signal,
      });

      if (!response.ok) {
        let errMessage = `Error ${response.status}`;
        try {
          const errData = await response.json();
          errMessage = errData.detail || errMessage;
        } catch (_) {}
        throw new Error(errMessage);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        onChunk(chunk);
      }
      if (onDone) onDone();
    } catch (error) {
      if (onError) onError(error);
      else console.error('Streaming response error:', error);
    } finally {
      clearTimeout(timer);
    }
  }
}

export const sentioAPI = new SentioAPIClient();
