# Animation plans

Written by an `improve-animations` audit at commit `7558734e` (2026-11-06).
Each plan stands alone: hand any of them to an agent with no other context.
All five plans are done. They were checked in the browser on 2026-11-06 and were merged into `feature/premium-frontend` (fast-forward to `b3cc9579`).

| # | Plan | Severity | Status |
|---|---|---|---|
| 001 | [Replace the broken 3D flashcard flip with a short fade](001-flashcard-flip-fade.md) | LOW (re-rated, see the plan) | DONE, merged into `feature/premium-frontend` |
| 002 | [Put the toast on the shared motion tokens and make replacement smooth](002-toast-motion.md) | MEDIUM | DONE, merged |
| 003 | [Keep loading indicators alive under reduced motion](003-reduced-motion-loading-signals.md) | MEDIUM | DONE, merged |
| 004 | [Give the tutor side panel an opacity-only arrival](004-tutor-drawer-fade.md) | LOW | DONE, merged |
| 005 | [Animate the emotion and engagement bars with transform instead of width](005-camera-bars-scalex.md) | LOW | DONE, merged |

## Recommended order

1. **001** is done. It was re-rated after review: the blank-card problem never
   reached the live app. It is now cleanup plus a short reveal fade.
2. **002**: toasts appear across every view.
3. **003**: a small CSS-only change with a big effect for people who use reduced
   motion.
4. **004**, then **005**: polish. 005 affects only the optional camera feature.

## Dependencies and overlap

- No plan needs another plan's result. They can run in any order.
- **001** and **003** both append to the end of
  `src/sentio/static/css/workspace.css`. If they run in parallel, expect a
  trivial merge conflict at the end of that file. Keep both blocks.
- **003** and **004** both edit `DESIGN.md`, but on different lines (348 and
  350).
- **004** and **005** both edit `src/sentio/static/css/styles.css`, but in
  different rules (`.hud-drawer` vs `.ebar-fill` / `.engage-*`).
- Keyframe names don't collide: 001 adds `fade-in` (workspace.css), 003 adds
  `loader-pulse`, 004 adds `drawer-fade-in`.

## Left alone on purpose

- No press-scale on buttons and no bounce, because `DESIGN.md:350,360` rule them
  out.
- The blanket reduced-motion rule stays. 003 adds only narrow exceptions for
  status pulses.
- The row menus and the global spinner overlay appear without animation. They're
  used constantly, so that's correct.
- The 8px rise on chat messages and log entries is kept. 004 records it in
  `DESIGN.md` as the one allowed exception.

## Not planned yet

- A small celebration when a flashcard review deck is finished (a rare,
  rewarding moment). That screen hasn't been checked yet. Run
  `improve-animations plan <description>` once you've decided what it should be.
