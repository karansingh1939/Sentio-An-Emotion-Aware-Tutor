// Shared motion for Sentio (ES Module).
// Timings follow DESIGN.md:
// - Every page change: the tab pill stretches to the new tab and the page fades in (under 300 ms).
// - The first visit to a page in a session also types its title and brings panels in one by one.
// - Figures count up, bars fill and chart lines draw only when the page enters.
// People who ask for reduced motion get instant changes and plain fades.

const reduced = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const EASE = 'cubic-bezier(0.23, 1, 0.32, 1)';
const seen = new Set(JSON.parse(sessionStorage.getItem('sentio_seen_views') || '[]'));

// ── Tab pill ─────────────────────────────────────────────────────
// Stretches from the current tab to cover both, then settles on the new one.
export function moveTabPill(nav, { instant = false } = {}) {
  const pill = nav?.querySelector('.tab-pill');
  const link = nav?.querySelector('.nav-link.active');
  if (!pill) return;
  if (!link) {
    pill.style.opacity = '0';
    return;
  }
  const to = { left: link.offsetLeft, width: link.offsetWidth };
  const from = { left: pill.offsetLeft, width: pill.offsetWidth };
  pill.getAnimations().forEach((a) => a.cancel());
  pill.style.opacity = '1';
  pill.style.left = `${to.left}px`;
  pill.style.width = `${to.width}px`;
  if (instant || reduced() || !from.width || from.left === to.left) return;
  const left = Math.min(from.left, to.left);
  const right = Math.max(from.left + from.width, to.left + to.width);
  pill.animate(
    [
      { left: `${from.left}px`, width: `${from.width}px` },
      { left: `${left}px`, width: `${right - left}px`, offset: 0.45 },
      { left: `${to.left}px`, width: `${to.width}px` },
    ],
    { duration: 360, easing: EASE },
  );
}

// ── Numbers ──────────────────────────────────────────────────────
// <span data-count="68" data-suffix="%">68%</span> counts from 0 to the value.
export function countUp(root) {
  root.querySelectorAll('[data-count]').forEach((el) => {
    const target = Number(el.dataset.count);
    const suffix = el.dataset.suffix || '';
    const format = (n) => Math.round(n).toLocaleString() + suffix;
    if (!Number.isFinite(target) || reduced()) {
      el.textContent = format(target || 0);
      return;
    }
    const start = performance.now();
    const duration = 700;
    const step = (now) => {
      const t = Math.min(1, (now - start) / duration);
      el.textContent = format(target * (1 - Math.pow(1 - t, 3)));
      if (t < 1 && el.isConnected) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  });
}

// ── Chart strokes ────────────────────────────────────────────────
// SVG paths and circles marked data-draw trace themselves in.
export function drawStrokes(root) {
  root.querySelectorAll('[data-draw]').forEach((el) => {
    if (reduced() || typeof el.getTotalLength !== 'function') return;
    const length = el.getTotalLength();
    const dash = el.getAttribute('stroke-dasharray');
    el.animate(
      dash
        ? [{ strokeDasharray: `0 ${length}` }, { strokeDasharray: dash }]
        : [
            { strokeDasharray: `${length}`, strokeDashoffset: `${length}` },
            { strokeDasharray: `${length}`, strokeDashoffset: '0' },
          ],
      { duration: 700, easing: EASE, delay: Number(el.dataset.draw) || 0, fill: 'backwards' },
    );
  });
}

// ── Typed title ──────────────────────────────────────────────────
function typeTitle(heading) {
  const text = heading.textContent;
  if (!text || reduced()) return;
  heading.setAttribute('aria-label', text);
  const perLetter = Math.max(14, Math.min(32, 420 / text.length));
  let shown = 0;
  heading.textContent = '';
  const timer = setInterval(() => {
    shown += 1;
    heading.textContent = text.slice(0, shown);
    if (shown >= text.length || !heading.isConnected) {
      clearInterval(timer);
      heading.textContent = text;
      heading.removeAttribute('aria-label');
    }
  }, perLetter);
}

// ── Page entrance ────────────────────────────────────────────────
// Panels that should arrive one by one: the view header, then cards, groups and rows.
const PANELS = [
  ':scope > .view-header',
  ':scope > .today-heading',
  ':scope > .notice',
  ':scope > .stat-grid > .stat',
  ':scope > .today-grid > sentio-card',
  ':scope > .today-grid > section',
  ':scope .today-side > sentio-card',
  ':scope > sentio-card',
  ':scope > * > sentio-card',
  ':scope > div > .course-group',
  ':scope .enter-item',
].join(', ');

export function enterView(view) {
  if (!view) return;
  const route = view.id;
  const first = !seen.has(route);
  if (first) {
    seen.add(route);
    sessionStorage.setItem('sentio_seen_views', JSON.stringify([...seen]));
  }
  view.classList.remove('enter-fade');
  void view.offsetWidth;
  view.classList.add('enter-fade');
  countUp(view);
  drawStrokes(view);
  if (!first || reduced()) return;
  const heading = view.querySelector('.view-header h2, .today-heading h2, .page-title');
  if (heading) typeTitle(heading);
  [...view.querySelectorAll(PANELS)].slice(0, 14).forEach((panel, index) => {
    panel.classList.remove('enter-rise');
    panel.style.animationDelay = `${60 + index * 50}ms`;
    panel.classList.add('enter-rise');
    panel.addEventListener('animationend', () => (panel.style.animationDelay = ''), {
      once: true,
    });
  });
}

// Run the entrance once a view has rendered its real content (not the loading line).
export function watchView(view) {
  if (!view) return;
  const ready = () => view.querySelector('.view-header, .today-heading, #chat-area');
  if (ready()) {
    enterView(view);
    return;
  }
  const observer = new MutationObserver(() => {
    if (!ready()) return;
    observer.disconnect();
    enterView(view);
  });
  observer.observe(view, { childList: true, subtree: true });
  setTimeout(() => observer.disconnect(), 4000);
}

// For views that redraw part of a page in place (for example a chart range switch).
window.sentioMotion = { countUp, drawStrokes };
