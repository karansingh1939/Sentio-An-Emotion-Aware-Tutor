# 002 — Put the toast on the shared motion tokens and make replacement smooth

- **Status**: DONE, merged into `feature/premium-frontend` (commit 8312f678), browser-checked
- **Commit**: 7558734e
- **Severity**: MEDIUM
- **Category**: Easing & duration, Cohesion & tokens, Interruptibility
- **Estimated scope**: 1 file (`src/sentio/static/js/components/ui.js`), about 20 lines

## Problem

`<sentio-toast>` is the main notification component, used by every module view
(sign-in, documents, flashcards, and so on). It has three motion problems.

```js
/* src/sentio/static/js/components/ui.js:5-60 — current (excerpt) */
export class SentioToast extends HTMLElement {
  connectedCallback() {
    ...
    this.duration = parseInt(this.getAttribute('duration')) || 4000;
    this.render();
    setTimeout(() => this.dismiss(), this.duration);
  }

  render() {
    ...
    this.style.transition = 'opacity 0.3s, transform 0.3s';
    this.style.transform = 'translateY(10px)';
    this.style.opacity = '0';
    ...
    requestAnimationFrame(() => {
      this.style.transform = 'translateY(0)';
      this.style.opacity = '1';
    });
  }

  dismiss() {
    this.style.transform = 'translateY(-10px)';
    this.style.opacity = '0';
    this.addEventListener('transitionend', () => this.remove());
  }
}
...
export function toast(message, isError = false) {
  document.querySelectorAll('sentio-toast').forEach((old) => old.remove());
  const el = document.createElement('sentio-toast');
  ...
  document.body.appendChild(el);
}
```

1. **Hard-coded timing, default curve.** `opacity 0.3s, transform 0.3s` uses the
   browser's default `ease` and ignores the project tokens
   (`--dur: 180ms`, `--dur-slow: 320ms`,
   `--ease: cubic-bezier(0.2, 0.8, 0.2, 1)` in
   `src/sentio/static/css/workspace.css:26-28`). It also animates `transform`,
   which `DESIGN.md:350` rules out ("animate only colour, background, border and
   opacity").
2. **Contradictory direction.** It rises in from 10px below, then leaves by
   moving 10px up. It reads as two unrelated motions.
3. **Replacement jumps.** A new toast calls `old.remove()`, so the previous
   toast vanishes in a single frame while the new one is still at opacity 0.
   This happens often (for example a "Saving…" toast followed by "Saved").
   Separately, `transitionend` fires once per transitioned property, so
   `remove()` runs twice. That's harmless but untidy. If `dismiss()` runs before
   the entrance has painted, no transition runs and the toast is never removed.

The other toast, `#toast` in `src/sentio/static/js/core/tutor_runtime.js:923-929`
with CSS at `src/sentio/static/css/styles.css:1251-1271`, already uses
`opacity var(--dur-slow) var(--ease)`. It is compliant and **out of scope**.

## Target

- Entrance: opacity 0 → 1 over `var(--dur-slow)` (320ms), `var(--ease)`.
- Exit: opacity 1 → 0 over `var(--dur)` (180ms), `var(--ease)`. Exits are
  quicker than entrances.
- No `transform` at all.
- A new toast makes existing toasts **fade out** (exit) instead of vanishing.
  The two toasts overlap in the same spot for up to 180ms, which reads as a
  crossfade.
- `dismiss()` can be called more than once safely and always removes the element,
  even when no transition runs.

## Repo conventions to follow

- Tokens: `var(--dur)`, `var(--dur-slow)`, `var(--ease)` (defined in
  `src/sentio/static/css/workspace.css:26-28`). Inline styles can reference them,
  just as this component already does with `var(--radius)` and `var(--bg2)`.
- Exemplar of the target pattern: `src/sentio/static/css/styles.css:1263`,
  `transition: opacity var(--dur-slow) var(--ease);`.
- Prettier 3.6.2: 2-space indent, single quotes.

## Steps

1. In `render()` (`ui.js:30-32`), replace

   ```js
   this.style.transition = 'opacity 0.3s, transform 0.3s';
   this.style.transform = 'translateY(10px)';
   this.style.opacity = '0';
   ```

   with

   ```js
   this.style.transition = 'opacity var(--dur-slow) var(--ease)';
   this.style.opacity = '0';
   ```

2. In `render()` (`ui.js:40-43`), replace the `requestAnimationFrame` block with

   ```js
   requestAnimationFrame(() => {
     this.style.opacity = '1';
   });
   ```

3. Replace the whole `dismiss()` method (`ui.js:46-50`) with

   ```js
   dismiss() {
     if (this.dismissed) return;
     this.dismissed = true;
     this.style.pointerEvents = 'none';
     this.style.transition = 'opacity var(--dur) var(--ease)';
     this.style.opacity = '0';
     this.addEventListener('transitionend', () => this.remove(), { once: true });
     // Fallback: no transition runs if the toast was never visible.
     setTimeout(() => this.remove(), 400);
   }
   ```

   Calling `remove()` on an element that has already been removed does nothing,
   so the fallback is safe.

4. In `toast()` (`ui.js:56`), replace

   ```js
   document.querySelectorAll('sentio-toast').forEach((old) => old.remove());
   ```

   with

   ```js
   document.querySelectorAll('sentio-toast').forEach((old) => old.dismiss());
   ```

## Boundaries

- Do NOT touch `#toast` in `tutor_runtime.js` or `styles.css`, or the `toast()`
  function inside `tutor_runtime.js`.
- Do NOT change the toast's position, colours, icon, message, `duration`
  attribute or the default 4000ms display time.
- Do NOT add stacking (several visible toasts) or any transform.
- Do NOT edit `SentioLoader`, `SentioModal` or the other components in `ui.js`.
- If the excerpts don't match the file (it has changed since 7558734e), STOP and
  report.

## Verification

- **Mechanical**:
  - `npm test`: all suites pass.
  - `npm run format:check`: clean. If only `ui.js` is flagged, run
    `npx prettier --write src/sentio/static/js/components/ui.js`.
  - `grep -n "translateY\|0.3s" src/sentio/static/js/components/ui.js` returns
    nothing.
- **Feel check** (`python scripts/dev/dev_start.py`, then http://localhost:8000):
  - Trigger a toast, for example by signing in with an empty email ("Enter your
    email and password."). It fades in without moving, stays about 4 seconds,
    then fades out faster than it came in.
  - Click the sign-in button 5 times quickly. Each new toast crossfades over the
    previous one, with no blank frame and no jump. After everything settles, only
    one `<sentio-toast>` is left in the DOM (check in DevTools > Elements).
  - In DevTools > Animations at 10% playback, confirm only opacity changes.
  - With DevTools > Rendering > `prefers-reduced-motion: reduce`, toasts still
    appear and are still removed afterwards (the fallback timeout covers this).
- **Done when**: no transform or hard-coded duration remains in `SentioToast`,
  rapid toasts crossfade, and no orphaned `<sentio-toast>` elements are left
  behind.
