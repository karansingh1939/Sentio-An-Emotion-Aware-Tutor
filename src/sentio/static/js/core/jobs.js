import { sentioAPI } from './api.js';
import { store } from './store.js';

// A saved job ID lets refresh reconnect without repeating an AI submission.
export function pendingJobKey(endpoint, sessionScoped = true) {
  return `sentio_job:${store.getState('currentUser')?.id}:${sessionScoped ? store.getState('activeSessionId') : 'library'}:${endpoint}`;
}

export async function runPracticeJob(endpoint, body, container, options = {}) {
  const owner = store.getState('currentUser')?.id;
  const session = store.getState('activeSessionId');
  const key = pendingJobKey(endpoint, options.sessionScoped !== false);
  const submissionKey = key + ':submission';
  const route = store.getState('activeRoute');
  let jobId = localStorage.getItem(key);
  let detached = false;
  const unsubscribe = store.subscribe('activeRoute', (next) => {
    detached ||= next !== route;
  });
  container.innerHTML =
    '<div class="study-job"><sentio-loader></sentio-loader><p role="status" aria-live="polite">Preparing practice…</p><button type="button">Stop</button></div>';
  const status = container.querySelector('[role="status"]');
  const stop = container.querySelector('button');
  try {
    if (!jobId) {
      let requestId = localStorage.getItem(submissionKey);
      if (!requestId) {
        requestId = crypto.randomUUID();
        localStorage.setItem(submissionKey, requestId);
      }
      const job = options.submit
        ? await options.submit(requestId)
        : await sentioAPI.post(endpoint, body, { headers: { 'Idempotency-Key': requestId } });
      jobId = job.job_id;
      localStorage.setItem(key, jobId);
    }
    stop.onclick = async () => {
      stop.disabled = true;
      try {
        const response = await sentioAPI.post(`/jobs/${jobId}/cancel`, {});
        status.textContent = response.accepted ? 'Stopping…' : 'Already saved; finishing…';
      } catch (error) {
        status.textContent = error.message;
        stop.disabled = false;
      }
    };
    while (
      !detached &&
      store.getState('currentUser')?.id === owner &&
      (options.sessionScoped === false || store.getState('activeSessionId') === session)
    ) {
      const job = await sentioAPI.get(`/jobs/${jobId}`);
      const current =
        !detached &&
        store.getState('currentUser')?.id === owner &&
        (options.sessionScoped === false || store.getState('activeSessionId') === session);
      if (job.status === 'succeeded') {
        localStorage.removeItem(key);
        localStorage.removeItem(submissionKey);
        if (current && options.sessionScoped !== false && !job.study_context) {
          status.textContent =
            'Practice was saved before source tracking. Open it from saved practice.';
          stop.disabled = true;
          return null;
        }
        if (current && options.sessionScoped !== false && job.study_context) {
          const live = await sentioAPI.get(`/sessions/${session}/context`);
          if (
            detached ||
            owner !== store.getState('currentUser')?.id ||
            session !== store.getState('activeSessionId')
          )
            return null;
          if (JSON.stringify(live) !== JSON.stringify(job.study_context)) {
            status.textContent =
              'Practice was saved for earlier study sources. Open it from saved practice.';
            stop.disabled = true;
            return null;
          }
        }
        return current ? job.result : null;
      }
      if (!current) return null;
      if (['failed', 'cancelled'].includes(job.status)) {
        localStorage.removeItem(key);
        localStorage.removeItem(submissionKey);
        throw new Error(job.error || 'Practice stopped before saving. You can try again.');
      }
      status.textContent = job.stage;
      await new Promise((resolve) => setTimeout(resolve, 650));
    }
    // Background work survives navigation; reopening this tool reconnects.
    return null;
  } catch (error) {
    if ([404, 409, 410].includes(error.status)) {
      localStorage.removeItem(key);
      localStorage.removeItem(submissionKey);
    }
    throw error;
  } finally {
    unsubscribe();
  }
}
