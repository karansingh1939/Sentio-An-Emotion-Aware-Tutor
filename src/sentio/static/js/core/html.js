// Escape text and quoted attributes before inserting API or model content into HTML.
export function escapeHtml(value) {
  return String(value ?? '').replace(
    /[&<>"']/g,
    (char) =>
      ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;',
      })[char],
  );
}

// Slides for PowerPoint lectures, pages for everything else.
export function pageLabel(filename, page) {
  return `${/\.pptx$/i.test(filename || '') ? 'Slide' : 'Page'} ${page}`;
}

export const MAX_PRACTICE_TOPICS = 5;

// How well a practised topic is remembered, for its progress line.
export function topicMemory(topic) {
  if (topic.state === 'review_due') return `about ${Math.round(topic.recall * 100)}% remembered`;
  if (topic.state !== 'ready') return '';
  const date = new Date(topic.review_on * 1000);
  const year = date.getFullYear() === new Date().getFullYear() ? undefined : 'numeric';
  return `review by ${date.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year })}`;
}

export function pageRange(topic) {
  const label = pageLabel(topic.filename, '').trim().toLowerCase();
  return topic.first_page === topic.last_page
    ? `${label} ${topic.first_page}`
    : `${label}s ${topic.first_page}–${topic.last_page}`;
}

// Which topics a quiz was built from. Callers escape the result.
export function describeFocus(provenance) {
  const topics = provenance?.topics || [];
  return topics.length
    ? `From: ${topics.map((topic) => `${topic.title} (${pageRange(topic)})`).join(', ')}`
    : '';
}

// Plain-text account of how saved practice was made. Callers escape the result.
export function describeProvenance(provenance) {
  if (!provenance) return '';
  const pages = (provenance.sources || [])
    .map((source) => `${source.filename} ${pageLabel(source.filename, source.page).toLowerCase()}`)
    .join(', ');
  const from = pages ? ` from ${pages}` : '';
  const made =
    provenance.mode === 'source_recall'
      ? `Quoted from your notes${from} because generated practice could not be verified`
      : `Made by the local AI${from || ' without notes'}`;
  return provenance.edited ? `${made} · edited by you` : made;
}
