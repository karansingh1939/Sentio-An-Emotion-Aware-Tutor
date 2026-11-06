# 003 — Keep loading indicators alive under reduced motion

- **Status**: DONE, merged into `feature/premium-frontend` (commit e25153b0), browser-checked
- **Commit**: 7558734e
- **Severity**: MEDIUM
- **Category**: Accessibility
- **Estimated scope**: 2 files (`workspace.css`, `DESIGN.md`), about 25 lines

## Problem

The project deliberately turns off motion for users who ask for reduced motion.
`DESIGN.md:348` says: "respect `prefers-reduced-motion`; the workspace already
disables animations and transitions under it". **Keep that decision.** This plan
only adds narrow exceptions for status signals that don't move anything.

```css
/* src/sentio/static/css/workspace.css:467-474 — current */
@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
```

Infinite animations with a 0.01ms duration loop thousands of times per second.
Each one ends up shown at an arbitrary frame and looks frozen. That kills the
only "something is happening" signal in three places:

- **Tutor typing dots**, `src/sentio/static/css/styles.css:800-830`:
  `.typing-dots span { animation: typing-fade 1.2s var(--ease) infinite; }`,
  staggered with `animation-delay: 0.15s` and `0.3s`. The keyframe `typing-fade`
  animates **opacity only** (0.25 → 1 → 0.25).
- **Document "working" badge**, `src/sentio/static/css/workspace.css:1255-1262`:
  `.doc-state.working::before { animation: typing-fade 1.2s var(--ease) infinite; }`
  Same opacity-only keyframe.
- **Spinner** `<sentio-loader>`, `src/sentio/static/js/components/ui.js:62-88`:
  inline style `animation: spin 0.8s linear infinite` (a rotation). It's used for
  file uploads, practice generation, deck loading and the global loading overlay
  (`src/sentio/static/index.html:691`). Under reduced motion it looks like a
  static ring, so a long upload looks stuck.

Reduced motion should mean "no movement", not "no feedback". An opacity pulse
doesn't move anything, so it is the accepted replacement.

## Target

Inside the existing reduced-motion preference, and after the blanket rule:

- `.typing-dots span` and `.doc-state.working::before` keep their normal
  1.2s `typing-fade` duration.
- `sentio-loader` stops rotating and pulses its opacity instead, using a new
  opacity-only keyframe over 1.2s with `var(--ease)`.

```css
/* target — appended to src/sentio/static/css/workspace.css */
@media (prefers-reduced-motion: reduce) {
  /* Opacity-only status pulses don't move anything, so they stay on. */
  .typing-dots span,
  .doc-state.working::before {
    animation-duration: 1.2s !important;
  }
  sentio-loader {
    animation: loader-pulse 1.2s var(--ease) infinite !important;
  }
}
@keyframes loader-pulse {
  0%,
  100% {
    opacity: 0.35;
  }
  50% {
    opacity: 1;
  }
}
```

Why it wins the cascade: among `!important` declarations, the more specific
selector wins. `.typing-dots span` (0,1,1), `.doc-state.working::before`
(0,2,1) and `sentio-loader` (0,0,1) all beat `*` (0,0,0). An `!important`
stylesheet rule also beats the loader's non-important inline `style.animation`.

## Repo conventions to follow

- Tokens: `var(--ease)` = `cubic-bezier(0.2, 0.8, 0.2, 1)`
  (`workspace.css:28`).
- The existing keyframe `typing-fade` (`styles.css:819-828`) is the model for an
  opacity-only pulse. `loader-pulse` follows the same shape.
- Put the new block right **after** the existing reduced-motion block at
  `workspace.css:467-474`, so the reason sits next to the rule it overrides.

## Steps

1. In `src/sentio/static/css/workspace.css`, directly after the closing `}` of
   the `@media (prefers-reduced-motion: reduce)` block at lines 467-474, insert
   the exact CSS in the **Target** section above.
2. In `DESIGN.md:348`, replace the line

   ```
   - **Do** respect `prefers-reduced-motion`; the workspace already disables animations and transitions under it.
   ```

   with

   ```
   - **Do** respect `prefers-reduced-motion`; the workspace already disables animations and transitions under it, except opacity-only loading pulses (typing dots, the document "working" dot, and the spinner, which pulses instead of spinning) so progress stays visible.
   ```

## Boundaries

- Do NOT remove or weaken the blanket `*` rule.
- Do NOT add exceptions for anything that moves (translate, rotate, scale) or for
  decorative loops such as `.active-pulse-dot` (`styles.css:509-516`).
- Do NOT edit `ui.js`. The override is CSS-only.
- If the excerpts don't match (the code has changed since 7558734e), STOP and
  report.

## Verification

- **Mechanical**:
  - `npm run format:check`: clean. If `workspace.css` is flagged, run
    `npx prettier --write src/sentio/static/css/workspace.css`.
  - `npm test`: passes.
- **Feel check** (`python scripts/dev/dev_start.py`, http://localhost:8000).
  Turn on DevTools > Rendering > "Emulate CSS media feature
  prefers-reduced-motion: reduce":
  - Send a tutor message. The three typing dots pulse in a gentle wave, with no
    movement.
  - Upload a document. The spinner doesn't rotate; it pulses between faint and
    full. The document's "working" badge dot pulses.
  - Open a chat message, the flashcard faces or a hover state. These still change
    instantly, so the blanket rule still applies everywhere else.
  - Turn emulation off. The spinner rotates normally again.
- **Done when**: with reduced motion on, all three loading signals visibly pulse
  and nothing else animates. With it off, behaviour is unchanged.
