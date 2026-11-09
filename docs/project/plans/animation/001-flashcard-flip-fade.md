# 001 — Replace the broken 3D flashcard flip with a short fade

- **Status**: DONE, merged into `feature/premium-frontend` (commit eb8460de)
- **Commit**: 7558734e
- **Severity**: HIGH
- **Category**: Purpose & frequency, Physicality & origin (plus a dead animation)
- **Estimated scope**: 3 files (`styles.css`, `workspace.css`, `flashcards.js`), about 30 lines

## Correction (found while reviewing the change)

The blank-card claim in section A below is wrong for the live app.
`src/sentio/static/css/workspace.css:515-526` loads later and already sets
`transform: none` on `.flashcard-inner.flipped` and on both faces. So the 3D
turn never ran, and the faces swapped instantly with no blank frame. What this
plan actually does: it removes dead 3D code, fixes the dead `fadeIn` on the
rating panel, and adds a 180ms opacity fade to the reveal. The `transform: none`
overrides at `workspace.css:515-526` are now redundant but harmless. They were
left in place because they're out of scope.

## Problem

Two related problems on the flashcard review screen.

### A. The card goes blank for half of every flip

Clicking the card (or pressing Enter or Space on it) runs this handler:

```js
/* src/sentio/static/js/views/flashcards.js:456-473 — current */
trigger.onclick = () => {
  this.isFlipped = !this.isFlipped;

  trigger.setAttribute('aria-expanded', String(this.isFlipped));
  this.container.querySelector('.flashcard-front').hidden = this.isFlipped;
  this.container.querySelector('.flashcard-back').hidden = !this.isFlipped;

  // Toggle panels
  const panel = this.container.querySelector('#rating-controls-panel');
  const inner = this.container.querySelector('.flashcard-inner');

  if (this.isFlipped) {
    inner.classList.add('flipped');
    if (panel) panel.style.display = 'flex';
  } else {
    inner.classList.remove('flipped');
    if (panel) panel.style.display = 'none';
  }
};
```

`hidden` is forced to `display: none !important` by
`src/sentio/static/css/workspace.css:476-478`. So the face that is leaving
disappears at once, and only the arriving face takes part in the 3D turn:

```css
/* src/sentio/static/css/styles.css:1282-1312 — current */
/* ── FLASHCARD INTERACTIVE FLIP ANIMATIONS ── */
.flashcard-inner {
  transition: transform var(--dur-slow) var(--ease);
  transform-style: preserve-3d;
  position: relative;
  width: 100%;
  height: 220px;
}
.flashcard-inner.flipped {
  transform: rotateY(180deg);
}
.flashcard-front,
.flashcard-back {
  backface-visibility: hidden;
  ...
}
.flashcard-back {
  transform: rotateY(180deg);
  background: var(--bg3) !important;
}
```

The back face is pre-rotated 180° and has `backface-visibility: hidden`, so for
the first ~90° of the 320ms turn nothing is visible at all. The user sees an
empty box, then the answer swings in. Flipping back has the same gap.

Flipping happens on every card, dozens of times per review session, often from
the keyboard. Motion this frequent should be minimal. The project's
`DESIGN.md:350` also says to "animate only colour, background, border and
opacity", so a 3D rotation breaks the house rule as well.

### B. The rating panel's fade references a keyframe that doesn't exist

```html
<!-- src/sentio/static/js/views/flashcards.js:422 — current (excerpt) -->
<div id="rating-controls-panel" style="display:${this.isFlipped ? 'flex' : 'none'};flex-direction:column;gap:12px;background:var(--bg3);border:1px solid var(--border);border-radius:var(--radius-lg);padding:16px;animation:fadeIn 0.3s;">
```

There is no `@keyframes fadeIn` anywhere in the project, so this does nothing
and the panel pops in with no transition.

## Target

- No rotation. The arriving face and the rating panel fade in from opacity 0 to
  1 over `var(--dur)` (180ms) with `var(--ease)`.
- The leaving face disappears at once (it already does, through `hidden`).
- One shared keyframe, `fade-in`, defined once in `workspace.css`:

```css
/* target — new, in src/sentio/static/css/workspace.css */
@keyframes fade-in {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}
.flashcard-front,
.flashcard-back,
.flashcard-reveal {
  animation: fade-in var(--dur) var(--ease);
}
```

A CSS animation restarts every time an element changes from `display: none` to
displayed. So this plays each time a face is un-hidden and each time the panel
gets `display: flex`. No JS change is needed to trigger it.

## Repo conventions to follow

- Motion tokens live in `:root` at `src/sentio/static/css/workspace.css:26-28`:
  `--dur: 180ms; --dur-slow: 320ms; --ease: cubic-bezier(0.2, 0.8, 0.2, 1);`.
  Use these tokens and never hard-code a duration or curve.
- `workspace.css` loads after `styles.css` (`src/sentio/static/index.html:8-9`)
  and holds the newer rules. New rules go there.
- Exemplar of a token-based animation: `src/sentio/static/css/styles.css:660`,
  `animation: msg-in var(--dur-slow) var(--ease);`.
- Formatting uses Prettier 3.6.2 (`.prettierrc.json`): 2-space indent, single
  quotes in JS.

## Steps

1. In `src/sentio/static/css/styles.css`, replace the block at lines 1282-1312
   (from the comment `/* ── FLASHCARD INTERACTIVE FLIP ANIMATIONS ── */` to the
   end of the `.flashcard-back` rule) with:

   ```css
   /* ── FLASHCARD FACES ── */
   .flashcard-inner {
     position: relative;
     width: 100%;
     height: 220px;
   }
   .flashcard-front,
   .flashcard-back {
     position: absolute;
     top: 0;
     left: 0;
     width: 100%;
     height: 100%;
     display: flex;
     flex-direction: column;
     justify-content: center;
     align-items: center;
     border-radius: var(--radius-lg);
     padding: 24px;
     box-sizing: border-box;
   }
   .flashcard-back {
     background: var(--bg3) !important;
   }
   ```

   This removes: the `transition` and `transform-style` on `.flashcard-inner`,
   the whole `.flashcard-inner.flipped` rule, `backface-visibility: hidden`, and
   `transform: rotateY(180deg)` on `.flashcard-back`. Keep every other
   declaration exactly as it was.

2. At the end of `src/sentio/static/css/workspace.css`, append:

   ```css
   /* ── Flashcard reveal: the arriving face and the rating panel fade in ── */
   @keyframes fade-in {
     from {
       opacity: 0;
     }
     to {
       opacity: 1;
     }
   }
   .flashcard-front,
   .flashcard-back,
   .flashcard-reveal {
     animation: fade-in var(--dur) var(--ease);
   }
   ```

   If a `@keyframes fade-in` already exists in `workspace.css`, because another
   plan added it, do not add a second one. Add only the selector rule.

3. In `src/sentio/static/js/views/flashcards.js:386`, remove
   `perspective:1000px;` from the inline `style` of `#flashcard-flip-trigger`.
   The result is:

   ```html
   <div id="flashcard-flip-trigger" role="button" tabindex="0" aria-label="Show or hide the answer" aria-expanded="${this.isFlipped}" style="cursor:pointer;width:100%;">
   ```

4. In `src/sentio/static/js/views/flashcards.js:422`, on
   `#rating-controls-panel`, add `class="flashcard-reveal"` and delete
   `animation:fadeIn 0.3s;` from the inline style. The result is:

   ```html
   <div id="rating-controls-panel" class="flashcard-reveal" style="display:${this.isFlipped ? 'flex' : 'none'};flex-direction:column;gap:12px;background:var(--bg3);border:1px solid var(--border);border-radius:var(--radius-lg);padding:16px;">
   ```

5. Leave the click handler at `flashcards.js:456-473` unchanged. It still adds
   and removes the `flipped` class, which now has no CSS effect. That's harmless,
   and removing it is out of scope.

## Boundaries

- Do NOT change the click or keyboard handler logic, `aria-expanded`, the
  `hidden` toggling, or the rating buttons.
- Do NOT touch any other `.flashcard-*` styling (colours, borders, fonts).
- Do NOT add translate, scale or rotate. `DESIGN.md:350` allows only colour,
  background, border and opacity.
- Do NOT add new dependencies or change the `prefers-reduced-motion` block at
  `workspace.css:467-474`.
- If any excerpt above doesn't match the file (the code has changed since
  commit 7558734e), STOP and report instead of improvising.

## Verification

- **Mechanical**:
  - `npm test` from the repo root: all suites pass.
  - `npm run format:check`: no files reported. If it fails only on the files you
    edited, run `npx prettier --write <those files>`. Do not reformat other
    files.
  - Search: `grep -rn "fadeIn\|rotateY\|backface-visibility" src/sentio/static`
    returns nothing.
- **Feel check** (run the app with `python scripts/dev/dev_start.py`, open
  http://localhost:8000, sign in, open Flashcards and start a review):
  - Click the card. The question vanishes and the answer fades in over ~180ms.
    There is never an empty box.
  - The rating panel fades in at the same moment as the answer.
  - Click again. The question fades back in and the rating panel disappears.
  - Press Enter and Space on the focused card. Same behaviour, no lag.
  - Spam-click the card 10 times quickly. It never shows a blank card and never
    feels like it's queuing.
  - Rate a card. The next card's question fades in once (that's expected,
    because the view re-renders).
  - In DevTools > Animations, set playback to 10%. You should see only opacity
    changing, with no rotation and no movement.
  - In DevTools > Rendering, emulate `prefers-reduced-motion: reduce`. The faces
    swap instantly, which is the project's existing reduced-motion behaviour.
- **Done when**: no rotation code remains, the flip shows no blank frame at 10%
  playback, and tests and the format check pass.
