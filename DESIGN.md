---
name: Sentio
description: A local AI study tutor that answers only from your own notes.
colors:
  accent: '#4d80ff'
  accent-fill: '#3b6aeb'
  night-page: '#0d0f0f'
  night-card: '#141517'
  night-raised: '#1b1c1e'
  night-hairline: '#222428'
  night-text: '#f4f6f8'
  night-text-dim: '#b3b6bc'
  night-muted: '#8e9095'
  night-hover: '#1f2124'
  night-press: '#26282c'
  night-green: '#5fc79a'
  night-amber: '#f19c22'
  night-coral: '#f17e62'
  night-teal: '#27bfa9'
  day-page: '#f3f4f6'
  day-card: '#ffffff'
  day-raised: '#f0f2f5'
  day-hairline: '#e2e5ea'
  day-text: '#15171a'
  day-text-dim: '#4f5560'
  day-muted: '#626975'
  day-accent: '#2f5fe0'
  day-hover: '#eceef2'
  day-press: '#e3e6eb'
  day-green: '#1f8a5b'
  day-amber: '#a0620a'
  day-red: '#c4314a'
  white-pill: '#f8fafa'
typography:
  display:
    fontFamily: "Outfit, system-ui, -apple-system, 'Segoe UI', sans-serif"
    fontSize: '38px'
    fontWeight: 500
    lineHeight: 1.15
    letterSpacing: '-0.01em'
  figure:
    fontFamily: 'Outfit, system-ui, sans-serif'
    fontSize: '40px'
    fontWeight: 500
    lineHeight: 1.1
  title:
    fontFamily: 'Outfit, system-ui, sans-serif'
    fontSize: '16px'
    fontWeight: 500
    lineHeight: 1.4
  body:
    fontFamily: 'Outfit, system-ui, sans-serif'
    fontSize: '16px'
    fontWeight: 400
    lineHeight: 1.65
  body-small:
    fontFamily: 'Outfit, system-ui, sans-serif'
    fontSize: '14px'
    fontWeight: 400
    lineHeight: 1.6
  label:
    fontFamily: 'Outfit, system-ui, sans-serif'
    fontSize: '13px'
    fontWeight: 400
    lineHeight: 1.4
  code:
    fontFamily: 'ui-monospace, Consolas, monospace'
    fontSize: '14px'
    fontWeight: 400
    lineHeight: 1.6
rounded:
  sm: '7px'
  md: '10px'
  block: '12px'
  card: '16px'
  pill: '999px'
spacing:
  xs: '4px'
  sm: '8px'
  md: '12px'
  lg: '16px'
  xl: '24px'
  xxl: '32px'
components:
  button-primary:
    backgroundColor: '{colors.accent-fill}'
    textColor: '#ffffff'
    rounded: '{rounded.md}'
    padding: '0 16px'
    height: '38px'
  button-secondary:
    backgroundColor: '{colors.night-card}'
    textColor: '{colors.night-text}'
    rounded: '{rounded.md}'
    padding: '0 16px'
    height: '38px'
  button-row-pill:
    backgroundColor: '{colors.white-pill}'
    textColor: '#111214'
    rounded: '{rounded.pill}'
    height: '30px'
  input:
    backgroundColor: '{colors.night-raised}'
    textColor: '{colors.night-text}'
    rounded: '{rounded.md}'
    padding: '8px 12px'
  card:
    backgroundColor: '{colors.night-card}'
    rounded: '{rounded.card}'
    padding: '22px 24px'
  tab-track:
    backgroundColor: '{colors.night-card}'
    rounded: '{rounded.pill}'
    padding: '4px'
  tab-active:
    backgroundColor: '{colors.accent-fill}'
    textColor: '#ffffff'
    rounded: '{rounded.pill}'
    height: '34px'
  status-pill:
    rounded: '{rounded.pill}'
    padding: '3px 10px'
  cited-passage:
    backgroundColor: '{colors.night-raised}'
    textColor: '{colors.night-text}'
    rounded: '{rounded.md}'
    padding: '12px 16px'
---

# Design System: Sentio

## Overview

**Creative North Star: "The Night Desk"**

Sentio is a calm, dark study dashboard. A near-black page holds a few dark cards; your notes, your cited answers and your real progress are the only things that ask for attention. One blue accent marks what you can act on. Green, amber and coral mean learning status, nothing else. Big figures and simple charts show progress at a glance, and each figure is real data from your own practice.

The look and the motion follow an Amplo dashboard reference, adapted to Sentio's purpose. The light theme ("The Day Desk") uses the same layout and components on pale grey and white, and every colour has a tuned counterpart in each theme.

**Key Characteristics:**

- Three dark tones (page, card, raised block) separated by 1px hairlines; no shadows at rest.
- One accent: `#4d80ff` for lines, dots and links, and the slightly deeper `#3b6aeb` for filled controls, so white text on them passes 4.5:1.
- Outfit, a geometric sans, self-hosted from `src/sentio/static/fonts/` (SIL Open Font License). No font requests leave the machine.
- A top bar with round pill tabs; the active tab is a blue pill that stretches to the next tab.
- Big tabular figures, rings and area charts that draw in when a page opens.

## Colors

### Accent

- **Accent** (`--accent`, dark `#4d80ff`, light `#2f5fe0`): links, chart lines, focus rings, dots on tabs with something waiting, the Practising state.
- **Accent fill** (`--accent-fill`, `#3b6aeb` in both themes): primary buttons, the active tab pill, the brand mark. Hover uses `--accent2`.

### Neutral

- **Page** (`--bg`): night `#0d0f0f`, day `#f3f4f6`.
- **Card** (`--bg2`): night `#141517`, day `#ffffff`. Also secondary buttons and the tab track.
- **Raised** (`--bg3`): night `#1b1c1e`, day `#f0f2f5`. Inputs, the next-step tip, countdown tiles, board cards, topic rows.
- **Hairline** (`--border`): night `#222428`, day `#e2e5ea`. Every border and divider.
- **Text** (`--text`), **Text dim** (`--text-dim`), **Muted** (`--text-muted`): headings and body, secondary body, labels and table headers.
- **Hover and Press** (`--hover`, `--press`): the one step every control takes when pointed at, and the deeper step when pressed.
- **White pill** (`--white-pill`): the near-white row action (Review) in dark; it inverts to near-black in light.

### Status

- **Green** (`--green`): Ready, correct answers, positive change.
- **Amber** (`--yellow`): Review due, needs review, a falling figure.
- **Coral / red** (`--red`): errors, incorrect answers, Needs retry, Not in your notes.
- **Blue** (`--accent`): Practising.
- **Muted grey**: Not started.

Each status pill is a tinted background (`--green-soft`, `--amber-soft`, `--red-soft`, `--accent-soft`) with the status colour for its text and dot.

### Named Rules

**The Accent Means Action Rule.** The accent marks what you can act on or check. Never use it for decoration or large backgrounds; the only filled blue areas are buttons, the active tab and the brand mark.

**The Status Is Learning Rule.** Green, amber and coral describe learning or an error. They never stand in for brand colour or emphasis. Board columns, rings, pills and bars all use the same mapping.

**The Two Desks Rule.** Every colour change ships with its light and dark counterpart. Both themes are checked; neither is made by inverting the other. A first visit follows the system setting; the choice made in the app is remembered.

**The Real Data Rule.** Every figure, chart and count comes from the student's own data. Never show sample numbers, invented trends or filler content outside the dev-only sample data toggle (`?data=…`).

## Typography

**Typeface:** Outfit (variable, 100–900), with `system-ui` as the fallback. Code and recovery keys use `ui-monospace`.

### Hierarchy

- **Display** (500, 38px, 1.15, −0.01em): the page title ("Good afternoon", "Library"). 30px below 860px.
- **Figure** (500, 40px, tabular numbers): the one big number on a card ("68% mastery"). Stat tiles use 36px.
- **Title** (500, 16px): card titles.
- **Body** (400, 16px, 1.65). Tutor answers use 1.8 line height in a column of at most 800px.
- **Body small** (400, 13–14px): card subtitles, table cells, metadata.
- **Label** (400, 12–13px, Muted): field labels, table headers, small figure captions. Countdown units are the only uppercase text (11px, 0.08em).

### Named Rules

**The Sentence Case Rule.** Labels, buttons and headings use sentence case with normal letter spacing.

**The 15px Floor Rule.** Text inputs, selects and textareas render at 15px or larger so they stay comfortable to type in. On touch screens they render at 16px, because iOS zooms the page into any field smaller than that.

## Layout

A top bar over one scrolling column.

- **Top bar:** brand at the left; the pill tab track (Today, Library, Study, Review, Progress); then, on the right, the session status pill, the theme button, "+ Add notes" and the account menu (Study history, Settings, "Your notes. Your machine."). Below 860px the tabs move to their own full-width row.
- **Page:** 32px gutters (16px below 860px). Each page opens with the display title, a one-line muted subtitle or status line, and its main actions at the right.
- **Grids:** cards sit 16px apart. Today uses a two-column top row (progress, sessions), a 1.6 : 1 middle row (topics due, goals and plan) and a three-column bottom row; all collapse to one column below 1100px.
- **Library:** List or Board. The Board has four columns (Not started, Practising, Review due, Ready), two below 1100px and one below 600px.
- **Scrolling:** the top bar stays put and each page scrolls inside the main column. Study keeps its own full-height chat layout.

Layouts must work at 390px, 768px and desktop widths in both themes.

## Elevation & Depth

Flat. Depth comes from tone: page, card, raised block, separated by hairlines.

### Shadow Vocabulary

- **Toast float** (`0 4px 16px #0001`): on transient toasts.
- **Dialog float** (`0 12px 32px rgb(0 0 0 / 0.12)`): dialogs, over a scrim (`rgb(22 27 36 / 0.45)`) with a 4px backdrop blur.

### Named Rules

**The Flat Desk Rule.** Cards, buttons and bubbles never cast shadows. Floating, transient UI (toasts, dialogs) is the only exception.

## Shapes

- **Cards and board columns:** 16px.
- **Raised blocks inside cards** (tip, countdown tiles, board cards, topic rows, notices): 12px.
- **Buttons, inputs, icon buttons:** 10px. Segmented options: 7px inside a 10px track.
- **Round:** the tab track, the tab pill, status pills, the white row pill, avatars and badges.

## Components

### Buttons

- **Primary:** accent fill, white text, weight 500, 38px tall, 10px radius. One per area.
- **Secondary:** card fill, hairline border, text colour.
- **Row pill:** the white pill ("Review") at the end of a table row or board card, 30px tall.
- **Icon button:** 38px square, hairline border, muted icon that brightens on hover (theme toggle).
- **Hover:** secondary buttons take `--hover` and a muted border; primary takes `--accent2`; the row pill dims slightly. Hover styles apply only with a mouse (`hover: hover` and `pointer: fine`).
- **Press:** `--press` fill, or 88% opacity for primary.
- **Focus:** a 3px accent outline offset by 3px on every interactive element. Never remove it.
- **Disabled:** 45% opacity and a not-allowed cursor.

### Segmented control

A hairline-bordered track with options inside. The chosen option gets the `--press` fill and text colour; others are muted and brighten on hover. Used for chart ranges, the Library List/Board switch and report sorting. Options are buttons with `aria-pressed`.

### Chips and pills

- **Citation chip:** raised pill, accent text, 12.5px. Clicking opens the exact cited passage. Duplicates merge; after four, the rest wait behind "+N more".
- **Badge:** accent-soft pill with accent text, for counts and metadata.
- **Status pill:** tinted background with a coloured dot (see Status).

### Cards / Containers

- **Card:** card fill, 1px hairline, 16px radius, 22px × 24px padding, a 16px weight-500 title and an optional 13px muted subtitle.
- **Stat tile:** a card with a 13px muted label above a 36px figure.
- **Board column:** page-colour fill with a hairline, a status pill and a count at the top; board cards are raised blocks with a 3px status-coloured left rule, the lecture tile and name, the topic, a progress bar, and Review / Practise actions.

### Data display

- **Big figure:** 40px tabular numbers; it counts up when the page opens.
- **Ring:** topics split into Strong (≥80%, green), Building (40–79%, blue) and Needs review (under 40%, amber), with the count in the middle and a legend below. It draws clockwise on entry.
- **Area chart:** a 2.5px accent line over an accent fade, with the previous period as a dashed muted line. It draws left to right on entry.
- **Meter:** a 6px round track with a status-coloured fill that grows from the left.
- **Table:** muted 12.5px headers, hairline rows, a raised row on hover, the row action at the right.
- **Lecture tile:** a 30px rounded square with the lecture's two initials, tinted one of four accent colours chosen from the file name.

### Inputs / Fields

Raised fill, 1px hairline, 10px radius, 8px × 12px padding, at least 15px text (16px on touch). Labels sit above the field in 13px muted text. Checkboxes and radios are native, tinted with the accent fill.

### Navigation

- **Tabs:** a round track on the card fill; labels are 14px muted text that brightens on hover. The active tab is a blue pill with white text. A small accent dot follows a tab label when something is waiting there (Review while topics are due).
- **Sub-navigation** (Quizzes / Flashcards, Progress / History): round text tabs under the top bar; the current one gets a card fill and hairline.
- **Account menu:** the initials button opens a menu with Study history, Settings and the local-data note.

### Brand

- **Wordmark:** `SENTIO` in custom wide geometric capitals with one thin, even stroke. Source: `src/sentio/static/img/sentio-wordmark.svg`; inline copies use `currentColor`.
- **Symbol:** the wordmark's O, filled, with its top-right page corner cut off. In the top bar it sits white inside a 34px accent-fill rounded square. Sources: `img/sentio-symbol.svg`, `img/favicon.svg`, and `window.sentioSymbol()`.

### Icons

Drawn line icons from `src/sentio/static/js/core/icons.js`, on a 24px grid with a 1.75 stroke and round caps and joins, inheriting the text colour. Never use emoji as icons; the optional camera feature's emotion faces are the only exception.

### Sign In

A split screen: the form with the lockup, a 34px "Welcome back" heading, sentence-case labels, "Forgot password?" as a quiet link, a full-width primary button and "Your account and notes stay on this computer."; beside it, a full-height accent panel with the promise "Answers only from your notes." above an example question, cited answer and cited passage. Below 860px the panel stacks under the form.

### Cited Passage (signature)

A quoted excerpt from the student's notes: a raised block with a 3px accent left rule, 10px radius, 12px × 16px padding, whitespace preserved. Use it whenever source text is shown.

### Answer Feedback and Notices

A raised block with a 4px left rule: green for correct, coral for incorrect or error, none for a neutral notice. Fallbacks and refusals use the same plain treatment and never look like a success.

## Motion

All motion lives in `src/sentio/static/js/core/motion.js` (behaviour) and the end of `src/sentio/static/css/theme.css` (keyframes). Shared easing: `--ease` (`cubic-bezier(0.2, 0.8, 0.2, 1)`) for colour changes and `--ease-out` (`cubic-bezier(0.23, 1, 0.32, 1)`) for movement. Durations: `--dur` (180ms) for controls, `--dur-slow` (320ms) for arrivals.

| What          | When                                                                         | How                                                                           |
| ------------- | ---------------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| Tab pill      | Every page change                                                            | Stretches from the old tab to cover both, then settles on the new one; 360ms. |
| Page fade     | Every page change                                                            | The new page fades in over 160ms.                                             |
| Typed title   | First visit to a page in a session                                           | The title types itself in, at most about 420ms in all.                        |
| Panel stagger | First visit to a page in a session                                           | Cards rise 8px and fade in, 50ms apart, 260ms each, up to 14 panels.          |
| Count-up      | When a page opens                                                            | Big figures count from 0 over 700ms.                                          |
| Draw-in       | When a page opens                                                            | Rings draw clockwise and chart lines left to right over 700ms.                |
| Bars          | When they render                                                             | Meters grow from the left over 520ms.                                         |
| Board columns | When the board loads                                                         | Columns rise in, 50ms apart.                                                  |
| Feed items    | New chat messages, log entries, the active-session bar, the typing indicator | Rise 8px and fade in (`msg-in`).                                              |

Everything else changes colour, background, border or opacity only. No bounce or overshoot.

## Do's and Don'ts

### Do:

- **Do** separate surfaces with 1px hairlines and tonal steps (page → card → raised).
- **Do** use the accent only for actions, links, chart lines, focus and the Practising state.
- **Do** show sources as citation chips and cited passages with the 3px accent left rule.
- **Do** keep every interactive element's 3px accent focus outline at a 3px offset.
- **Do** define and check each colour in both themes.
- **Do** keep text inputs at 15px or larger (16px on touch) and tap targets at least 34px tall.
- **Do** respect `prefers-reduced-motion`: the tab pill moves instantly, titles appear at once, panels only fade, figures appear at their value, and the workspace disables other animations and transitions, except opacity-only loading pulses (typing dots, the document "working" dot, and the spinner, which pulses instead of spinning) so progress stays visible.
- **Do** respect `prefers-reduced-transparency` (dialog scrims drop their blur and get more opaque) and `prefers-contrast: more` (hairlines take the muted text colour in both themes).
- **Do** keep the global loading indicator a small corner spinner: it never blurs the page, and it appears only after 300ms so quick requests don't flash it.
- **Do** give every control a hover state (`--hover`, mouse only) and a press state (`--press`).
- **Do** keep a page's full entrance to its first visit in a session; repeat visits get the pill and a quick fade only.

### Don't:

- **Don't** add drop shadows or glows to cards, buttons or bubbles; only toasts and dialogs float.
- **Don't** reuse the retired neon theme: cyan-on-black, scan-line overlays, glows, gradient buttons, Syne or JetBrains Mono.
- **Don't** set buttons or labels in uppercase with letter spacing (countdown units are the one exception).
- **Don't** use green, amber or coral as decoration or brand colour; they mean learning status or error.
- **Don't** put white text on `#4d80ff`; filled controls use `--accent-fill`.
- **Don't** show figures, charts or trends that aren't the student's real data.
- **Don't** let the optional camera / emotion UI bring its own visual language into the main study flow.
- **Don't** use `transition: all`, bounce or overshoot curves.
- **Don't** end interface copy with exclamation marks, or write "successfully".
