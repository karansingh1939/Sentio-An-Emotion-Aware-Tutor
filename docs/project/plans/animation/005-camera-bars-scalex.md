# 005 — Animate the emotion and engagement bars with transform instead of width

- **Status**: DONE, merged into `feature/premium-frontend` (commit b3cc9579), browser-checked
- **Commit**: 7558734e
- **Severity**: LOW
- **Category**: Performance
- **Estimated scope**: 3 files (`styles.css`, `tutor_runtime.js`, `index.html`), about 15 lines

## Problem

The tutor side panel shows emotion bars and an engagement bar for the optional
camera feature. They update every time new camera or tutor state arrives, and
they animate `width`, which forces the page layout to be recalculated on every
frame of every update:

```css
/* src/sentio/static/css/styles.css:400-405 — current */
.ebar-fill {
  height: 100%;
  border-radius: 3px;
  background: var(--accent2);
  transition: width var(--dur-slow) var(--ease);
}
```

```css
/* src/sentio/static/css/styles.css:1148-1160 — current */
.engage-track {
  height: 4px;
  background: var(--bg3);
  border-radius: 2px;
  margin-bottom: 14px;
}

.engage-fill {
  height: 100%;
  border-radius: 2px;
  background: var(--accent);
  transition: width var(--dur-slow) var(--ease);
}
```

JS writers:

```js
/* src/sentio/static/js/core/tutor_runtime.js:75 — current (inside initBars) */
<div class="ebar-track"><div class="ebar-fill" id="bar-${em}" style="width:0%"></div></div>

/* src/sentio/static/js/core/tutor_runtime.js:820-821 — current */
const engageBar = document.getElementById('engage-bar');
if (engageBar) engageBar.style.width = engage + '%';

/* src/sentio/static/js/core/tutor_runtime.js:867-872 — current */
const p = Math.round(data.emotion_scores[em] * 100);
if (fill) fill.style.width = p + '%';
...
if (fill) fill.style.width = '0%';
```

```html
<!-- src/sentio/static/index.html:517 — current -->
<div class="engage-fill" id="engage-bar" style="width: 50%"></div>
```

`engage` is an integer from 0 to 100 (`tutor_runtime.js:~798-802`,
`Math.round(... * 100)`).

## Target

Each fill is always full width and is scaled horizontally from its left edge.
Only `transform` animates, which the browser can do without recalculating
layout:

```css
/* target */
.ebar-fill {
  width: 100%;
  height: 100%;
  background: var(--accent2);
  transform: scaleX(0);
  transform-origin: left center;
  transition: transform var(--dur-slow) var(--ease);
}
.engage-track {
  ...existing declarations...
  overflow: hidden;
}
.engage-fill {
  width: 100%;
  height: 100%;
  background: var(--accent);
  transform: scaleX(0.5);
  transform-origin: left center;
  transition: transform var(--dur-slow) var(--ease);
}
```

The fills drop their own `border-radius`, because a scaled radius gets squashed.
The rounded left end now comes from the track's `overflow: hidden` clipping.
`.ebar-track` already has it (`styles.css:392-398`); `.engage-track` gets it
added. The right end of a partly filled bar becomes square. That's acceptable at
4-5px high, but check it in the feel check.

Scale value = percentage ÷ 100, written as `scaleX(<0..1>)`.

## Repo conventions to follow

- Tokens: `var(--dur-slow)`, `var(--ease)` (`src/sentio/static/css/workspace.css:27-28`).
- Exemplar of a transform transition already in the codebase:
  `src/sentio/static/css/workspace.css:1541`,
  `transition: transform var(--dur) var(--ease);`.
- `tutor_runtime.js` is a classic script (not a module). Use plain string
  concatenation as the surrounding code does.

## Steps

1. `src/sentio/static/css/styles.css:400-405`: replace the `.ebar-fill` rule with
   the target `.ebar-fill` rule above.
2. `src/sentio/static/css/styles.css:1148-1153`: add `overflow: hidden;` as the
   last declaration in `.engage-track`.
3. `src/sentio/static/css/styles.css:1155-1160`: replace the `.engage-fill` rule
   with the target `.engage-fill` rule above.
4. `src/sentio/static/js/core/tutor_runtime.js:75`: change `style="width:0%"` to
   `style="transform:scaleX(0)"`.
5. `src/sentio/static/js/core/tutor_runtime.js:821`: change it to

   ```js
   if (engageBar) engageBar.style.transform = 'scaleX(' + engage / 100 + ')';
   ```

6. `src/sentio/static/js/core/tutor_runtime.js:868`: change it to

   ```js
   if (fill) fill.style.transform = 'scaleX(' + p / 100 + ')';
   ```

7. `src/sentio/static/js/core/tutor_runtime.js:871`: change it to

   ```js
   if (fill) fill.style.transform = 'scaleX(0)';
   ```

8. `src/sentio/static/index.html:517`: change `style="width: 50%"` to
   `style="transform: scaleX(0.5)"`.
9. Run `grep -rn "ebar-fill\|engage-bar\|bar-' + em" src/sentio/static` and
   confirm no other code sets `.style.width` on these elements. If any does,
   STOP and report.

## Boundaries

- Do NOT change the percentage text (`barpct-*`, `stat-engage`), the colours, or
  the track sizes.
- Do NOT change how `engage` or the emotion scores are calculated.
- Do NOT touch any other progress bar in the app.
- If the excerpts don't match (the code has changed since 7558734e), STOP and
  report.

## Verification

- **Mechanical**:
  - `npm test`: passes.
  - `npm run format:check`: clean. If a file you edited is flagged, run
    `npx prettier --write` on it.
  - `grep -n "style.width" src/sentio/static/js/core/tutor_runtime.js` shows no
    lines for `fill` or `engageBar`.
- **Feel check**: the bars only change with the optional camera feature. Start a
  tutor session, open the side panel and send a message. The engagement bar
  starts half full and glides to its new value. If camera consent is available
  in Settings, enable it and watch the emotion bars glide from the left as
  scores change.
  - A bar at 0% is invisible, and a bar at 100% fills the track exactly.
  - The left end is rounded and the right end of a partial bar is square. That's
    expected; report it if it looks wrong next to the track.
  - DevTools > Performance: record while the bars update. You should see no
    purple "Layout" blocks caused by the bars.
- **Done when**: the bars animate only `transform`, look the same at rest
  (apart from the square right end), and tests pass.
