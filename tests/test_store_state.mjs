import assert from 'node:assert/strict';

const values = new Map([
  ['sentio_user', 'corrupt JSON'],
  ['sentio_session_id', 'previous-session'],
]);
globalThis.localStorage = {
  getItem: (key) => values.get(key) ?? null,
  setItem: (key, value) => values.set(key, value),
  removeItem: (key) => values.delete(key),
};
let cleanupCount = 0;
globalThis.window = { cleanupSession: () => cleanupCount++ };
const { store } = await import('../src/sentio/static/js/core/store.js');
assert.equal(store.getState('currentUser'), null);
store.setState('currentUser', { id: 'owner' });
store.setState('activeSession', { id: 'session' });
store.setState('telemetryActive', true);
store.setState('currentMastery', { private: 1 });
store.clearAuth();
assert.equal(store.getState('activeSessionId'), null);
assert.equal(store.getState('activeSession'), null);
assert.equal(store.getState('telemetryActive'), false);
assert.deepEqual(store.getState('currentMastery'), {});
assert.equal(cleanupCount, 1);
assert.equal(values.has('sentio_session_id'), false);
console.log('Corrupt saved state and logout cleanup are handled.');
