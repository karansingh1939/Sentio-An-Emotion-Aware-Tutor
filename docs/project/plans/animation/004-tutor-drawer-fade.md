# 004 — Give the tutor side panel an opacity-only arrival

- **Status**: DONE, merged into `feature/premium-frontend` (commit 698d2cd8), browser-checked
- **Commit**: 7558734e
- **Severity**: LOW
- **Category**: Physicality & origin, Cohesion & tokens
- **Estimated scope**: 2 files (`styles.css`, `DESIGN.md`), about 15 lines

## Problem

The tutor screen's side panel (`#tutor-hud-drawer`,
`src/sentio/static/index.html:397`) is a 320px column on the right edge. A
toolbar button opens and closes it through `window.toggleHudDrawer`
(`src/sentio/static/js/views/study.js:122-132 (then named tutor.js)`), which toggles the `.open`
class.

```css
/* src/sentio/static/css/styles.css:911-926 — current */
.hud-drawer {
  width: 320px;
  ...
  display: none;
  ...
  animation: msg-in var(--dur-slow) var(--ease);
}

.hud-drawer.open {
  display: flex;
}
```

It reuses the chat-message keyframe:

```css
/* src/sentio/static/css/styles.css:663-672 — current */
@keyframes msg-in {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
```

So a right-edge panel rises 8px **upwards** as it opens. The motion doesn't
match where the panel lives, and `DESIGN.md:350` allows only colour, background,
border and opacity. The panel already appears in the right place; the movement
adds nothing.

`msg-in` is also used, appropriately, by chat messages, log entries, the
active-session bar and the typing indicator (`styles.css:500, 660, 790, 1202`).
That 8px rise for new arrivals in a vertical feed is good motion, but
`DESIGN.md` doesn't mention it. This plan records it as an allowed exception
rather than removing it.

## Target

```css
/* target — src/sentio/static/css/styles.css */
.hud-drawer {
  ...
  animation: drawer-fade-in var(--dur-slow) var(--ease);
}

@keyframes drawer-fade-in {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}
```

- Opening fades the panel in over 320ms with `var(--ease)`, with no movement.
- Closing stays instant (`display: none`). Animating the exit would need JS and
  isn't worth it for this panel.

## Repo conventions to follow

- Tokens: `var(--dur-slow)` (320ms, "for arrivals" per `DESIGN.md:350`) and
  `var(--ease)`.
- Keyframes in `styles.css` sit next to the rule that uses them. Exemplar:
  `@keyframes msg-in` directly after `.msg` at `styles.css:656-672`.
- The keyframe is named `drawer-fade-in` on purpose, so it can't collide with a
  `fade-in` keyframe another plan adds to `workspace.css`.

## Steps

1. In `src/sentio/static/css/styles.css:921`, inside `.hud-drawer`, change

   ```css
   animation: msg-in var(--dur-slow) var(--ease);
   ```

   to

   ```css
   animation: drawer-fade-in var(--dur-slow) var(--ease);
   ```

2. Directly after the `.hud-drawer.open { display: flex; }` rule
   (`styles.css:924-926`), add:

   ```css
   @keyframes drawer-fade-in {
     from {
       opacity: 0;
     }
     to {
       opacity: 1;
     }
   }
   ```

3. In `DESIGN.md:350`, replace

   ```
   - **Do** animate only colour, background, border and opacity, with the shared timing: `--dur` (180ms) for controls, `--dur-slow` (320ms) for arrivals, and `--ease` (`cubic-bezier(0.2, 0.8, 0.2, 1)`) for both.
   ```

   with

   ```
   - **Do** animate only colour, background, border and opacity, with the shared timing: `--dur` (180ms) for controls, `--dur-slow` (320ms) for arrivals, and `--ease` (`cubic-bezier(0.2, 0.8, 0.2, 1)`) for both. The one exception is new items arriving in a vertical feed (chat messages, session log entries, the active-session bar, the typing indicator), which also rise 8px (`msg-in`).
   ```

## Boundaries

- Do NOT change `@keyframes msg-in` or any of its other users.
- Do NOT change `tutor.js`, the panel's width or layout, or add a close
  animation.
- Do NOT add any transform to the panel.
- If the excerpts don't match (the code has changed since 7558734e), STOP and
  report.

## Verification

- **Mechanical**:
  - `npm run format:check`: clean. If a file you edited is flagged, run
    `npx prettier --write` on it.
  - `npm test`: passes.
- **Feel check** (`python scripts/dev/dev_start.py`, http://localhost:8000,
  start a tutor session):
  - Click the side-panel toggle. The panel fades in without moving. Click again
    and it closes instantly.
  - Toggle it 6 times quickly. Nothing feels laggy or stuck.
  - DevTools > Animations at 10%: the panel shows only an opacity change. A newly
    sent chat message still rises 8px, which is intended.
- **Done when**: `.hud-drawer` no longer uses `msg-in`, the panel fades without
  moving, and `DESIGN.md` documents the feed-arrival exception.
