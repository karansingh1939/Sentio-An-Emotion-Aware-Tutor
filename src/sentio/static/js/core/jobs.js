import { sentioAPI } from './api.js';
import { store } from './store.js';

// A saved job ID lets refresh reconnect without repeating an AI submission.
export async function runPracticeJob(endpoint, body, container) {
  const owner = store.getState('currentUser')?.id;
  const session = store.getState('activeSessionId');
  const key = `sentio_job:${owner}:${session}:${endpoint}`;
  const route = store.getState('activeRoute');
  let jobId = localStorage.getItem(key);
  let unsubscribe = () => {};
  let detached = false;
  container.innerHTML =
    '<div class="study-job"><sentio-loader></sentio-loader><p role="status" aria-live="polite">Preparing practice…</p><button type="button">Stop</button></div>';
  const status = container.querySelector('[role="status"]');
  const stop = container.querySelector('button');
  try {
    if (!jobId) {
      const job = await sentioAPI.post(endpoint, body);
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
    unsubscribe = store.subscribe('activeRoute', (next) => {
      detached = next !== route;
    });
    while (
      !detached &&
      store.getState('currentUser')?.id === owner &&
      store.getState('activeSessionId') === session
    ) {
      const job = await sentioAPI.get(`/jobs/${jobId}`);
      if (job.status === 'succeeded') {
        localStorage.removeItem(key);
        return job.result;
      }
      if (['failed', 'cancelled'].includes(job.status)) {
        localStorage.removeItem(key);
        throw new Error(job.error || 'Practice stopped before saving. You can try again.');
      }
      status.textContent = job.stage;
      await new Promise((resolve) => setTimeout(resolve, 650));
    }
    // Background work survives navigation; reopening this tool reconnects.
    return null;
  } finally {
    unsubscribe();
  }
}
