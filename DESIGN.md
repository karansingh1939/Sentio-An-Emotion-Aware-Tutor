---
name: Sentio
description: A local AI study tutor that answers only from your own notes.
colors:
  ink-indigo: '#465bb2'
  ink-indigo-deep: '#34478f'
  paper-grey: '#f5f6f8'
  sheet-white: '#ffffff'
  tray-grey: '#edf0f5'
  hairline: '#d8dde6'
  graphite: '#202938'
  pencil-grey: '#556174'
  ready-green: '#16704e'
  practising-amber: '#8a6007'
  correction-red: '#b32c40'
  dark-ink-indigo: '#a9baff'
  dark-ink-indigo-soft: '#c3ceff'
  dark-desk: '#161b24'
  dark-sheet: '#1d2430'
  dark-tray: '#293242'
  dark-hairline: '#3c475a'
  dark-chalk: '#edf0f7'
  dark-pencil: '#b8c2d3'
  dark-ready-green: '#75d6ac'
  dark-practising-amber: '#eac476'
  dark-correction-red: '#ff9aab'
  hover-tint: '#e8ecf3'
  press-tint: '#dde3ed'
  dark-hover-tint: '#303a4c'
  dark-press-tint: '#384459'
typography:
  display:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', sans-serif"
    fontSize: '28px'
    fontWeight: 700
    lineHeight: 1.3
    letterSpacing: '-0.025em'
  headline:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', sans-serif"
    fontSize: '24px'
    fontWeight: 700
    lineHeight: 1.3
    letterSpacing: '-0.025em'
  title:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', sans-serif"
    fontSize: '16px'
    fontWeight: 700
    lineHeight: 1.4
  body:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', sans-serif"
    fontSize: '16px'
    fontWeight: 400
    lineHeight: 1.65
  body-small:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', sans-serif"
    fontSize: '14px'
    fontWeight: 400
    lineHeight: 1.6
  label:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', sans-serif"
    fontSize: '13px'
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: '0em'
  stat:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', sans-serif"
    fontSize: '26px'
    fontWeight: 800
    lineHeight: 1.2
  code:
    fontFamily: 'ui-monospace, Consolas, monospace'
    fontSize: '14px'
    fontWeight: 400
    lineHeight: 1.6
rounded:
  sm: '6px'
  md: '8px'
  lg: '12px'
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
    backgroundColor: '{colors.ink-indigo}'
    textColor: '{colors.sheet-white}'
    rounded: '{rounded.md}'
    padding: '8px 16px'
    height: '36px'
  button-secondary:
    backgroundColor: '{colors.sheet-white}'
    textColor: '{colors.graphite}'
    rounded: '{rounded.md}'
    padding: '8px 16px'
    height: '36px'
  button-quiet:
    textColor: '{colors.pencil-grey}'
    padding: '6px 8px'
  button-danger-link:
    textColor: '{colors.correction-red}'
    padding: '6px 8px'
  input:
    backgroundColor: '{colors.tray-grey}'
    textColor: '{colors.graphite}'
    rounded: '{rounded.md}'
    padding: '8px 12px'
  card:
    backgroundColor: '{colors.sheet-white}'
    rounded: '{rounded.lg}'
    padding: '16px 20px'
  nav-link:
    textColor: '{colors.graphite}'
    rounded: '{rounded.md}'
    padding: '10px 16px'
    height: '44px'
  nav-link-active:
    backgroundColor: '{colors.tray-grey}'
    textColor: '{colors.graphite}'
    rounded: '{rounded.md}'
  chip-citation:
    backgroundColor: '{colors.tray-grey}'
    textColor: '{colors.ink-indigo}'
    rounded: '{rounded.pill}'
    padding: '3px 10px'
  badge:
    backgroundColor: '{colors.tray-grey}'
    textColor: '{colors.ink-indigo}'
    rounded: '{rounded.pill}'
    padding: '4px 10px'
  topic-state-ready:
    textColor: '{colors.ready-green}'
    rounded: '{rounded.pill}'
    padding: '3px 10px'
  topic-state-practising:
    textColor: '{colors.practising-amber}'
    rounded: '{rounded.pill}'
    padding: '3px 10px'
  topic-state-review-due:
    textColor: '{colors.ink-indigo}'
    rounded: '{rounded.pill}'
    padding: '3px 10px'
  cited-passage:
    backgroundColor: '{colors.tray-grey}'
    textColor: '{colors.graphite}'
    rounded: '{rounded.md}'
    padding: '12px 16px'
  notice:
    backgroundColor: '{colors.tray-grey}'
    textColor: '{colors.graphite}'
    rounded: '{rounded.md}'
    padding: '16px'
---

# Design System: Sentio

## Overview

**Creative North Star: "The Quiet Study Desk"**

Sentio looks like a tidy desk for long study sessions. The student's notes and the tutor's cited answers are the only things that should hold attention. The interface stays flat, bordered and plain, using the operating system's own font. Ink Indigo, the single accent, marks only what the student can act on or check: links, citations, the primary action and topics due for review. Everything else is graphite text on pale grey and white sheets separated by hairline borders.

The density suits reading, not a dashboard. Body text is 16px at a generous 1.65 line height, chat answers are wider at 1.8, and the conversation column stays at most 800px wide. Layout is a fixed left sidebar and one working column. Cards are outlined rather than lifted, and status shows as coloured outlines and left rules rather than filled blocks, so a page full of topics stays calm.

The older neon theme still in `styles.css` is retired: near-black backgrounds, cyan glows, scan-line overlays, Syne and JetBrains Mono, uppercase letter-spaced buttons and gradient fills. Its glows, gradients, uppercase labels and scan-lines have been removed. The base layer it left behind in `styles.css` now follows this system, and `workspace.css` refines it. If any of it resurfaces, treat it as a bug, not a pattern to follow.

**Key Characteristics:**

- Flat surfaces separated by 1px hairlines; no shadows at rest.
- One accent (Ink Indigo) for action and evidence; green, amber and red only for learning status and errors.
- System font throughout; hierarchy comes from size and weight, never from case or letter-spacing.
- Pill shapes are reserved for small metadata: citations, badges and topic states.
- Light and dark themes are equal: every colour has a tuned counterpart, not an inversion.

## Colors

A cool, low-saturation grey family with one ink-blue accent and three muted status colours, tuned separately for light and dark themes.

### Primary

- **Ink Indigo** (`ink-indigo`; dark: `dark-ink-indigo`): links, citation chips, inline citations, badges, the primary action button, the focus ring, checkbox and progress accents, the "Review due" topic state and the left rule on cited passages. In dark mode it lightens to a soft periwinkle so it stays readable on the dark desk.
- **Ink Indigo Deep** (`ink-indigo-deep`; dark: `dark-ink-indigo-soft`): the pressed or stronger variant of the accent. Use it rarely.

### Neutral

- **Paper Grey** (`paper-grey`; dark: `dark-desk`): the app background, the desk the sheets lie on.
- **Sheet White** (`sheet-white`; dark: `dark-sheet`): cards, the sidebar, toolbars, chat bubbles, secondary buttons. Also the text colour on the primary button.
- **Tray Grey** (`tray-grey`; dark: `dark-tray`): recessed surfaces: inputs, the active nav item, chips, notices, cited passages, topic rows.
- **Hairline** (`hairline`; dark: `dark-hairline`): every border and divider.
- **Graphite** (`graphite`; dark: `dark-chalk`): primary text.
- **Pencil Grey** (`pencil-grey`; dark: `dark-pencil`): secondary text: subtitles, metadata, helper copy, form labels, quiet links.
- **Hover and Press tints** (`hover-tint`, `press-tint`; dark: `dark-hover-tint`, `dark-press-tint`; CSS `--hover`, `--press`): the one step every control takes when pointed at, and the deeper step when pressed.

### Status

- **Ready Green** (`ready-green`; dark: `dark-ready-green`): the "Ready" topic state, correct-answer feedback, syllabus progress fill, the live-session dot.
- **Practising Amber** (`practising-amber`; dark: `dark-practising-amber`): the "Practising" topic state only.
- **Correction Red** (`correction-red`; dark: `dark-correction-red`): errors, incorrect-answer feedback, destructive links, the "No notes" syllabus state.

### Named Rules

**The Ink Means Evidence Rule.** Ink Indigo is for things the student can act on or check against their notes. Never use it for decoration, headings or large backgrounds.

**The Status Is Learning Rule.** Green, amber and red describe the student's learning or an error. They never stand in for brand colour or emphasis.

**The Two Desks Rule.** Every colour change ships with its dark-theme counterpart. Both themes are checked; neither is derived by inverting the other.

## Typography

**Display Font:** system-ui (with -apple-system, Segoe UI, sans-serif)
**Body Font:** system-ui (same stack)
**Label/Mono Font:** ui-monospace (with Consolas, monospace) for code and recovery keys only

**Character:** The platform's own font, so Sentio reads like a native study tool rather than a branded product. Hierarchy comes from size steps and weights between 500 and 800, plus slightly tight tracking on large headings.

### Hierarchy

- **Display** (700, 28px, 1.3, −0.025em): the page title in each view header ("Your progress").
- **Headline** (700, 24–26px, 1.3, −0.025em): session-card and welcome titles; 21px at phone width.
- **Title** (700, 16px): card and panel titles, such as "Topic mastery" and "Overview of these notes".
- **Body** (400, 16px, 1.65): default reading text. Tutor answers use 1.8 line height inside a column of at most 800px.
- **Body small** (400, 14px, 1.6): metadata, notices, table cells, helper text, secondary buttons.
- **Label** (600, 13–14px, no extra tracking, sentence case): form labels, topic states, badges, stat labels.
- **Stat** (800, 26px): the single number on a progress stat card.

### Named Rules

**The Sentence Case Rule.** Labels, buttons and headings use sentence case with normal letter-spacing. Uppercase, letter-spaced text belongs to the retired theme.

**The 15px Floor Rule.** Text inputs, selects and textareas render at 15px or larger (the chat input at 16px) so they stay comfortable to type in and don't trigger mobile zoom.

## Layout

The app is a two-column grid: a 220px sidebar and a flexible main column, with a 64px header row. The main column holds an optional sub-navigation strip (12px × 32px padding, hairline below), then the view at 32px padding. Each view opens with a view header (display title plus a 15px Pencil Grey subtitle, 24px below).

- **Spacing rhythm:** 4 / 8 / 12 / 16 / 24 / 32px. Use 8px between related buttons, 16px between list items and cards, 24px between sections and grid columns, and 32px for page gutters.
- **Reading width:** the chat column is capped at 800px and centred. Single-purpose states, such as a running study job, cap at 35rem.
- **Grids:** stat cards use `auto-fit, minmax(200px, 1fr)` with a 16px gap. Today uses two columns (1.45fr / at least 280px) with a 24px gap.
- **Lists over cards:** study lists and metric rows are hairline-divided rows (16px or 12px vertical padding), not stacks of boxes.
- **≤1000px:** the sidebar narrows to 180px, view padding drops to 24px, and Today becomes one column.
- **≤768px:** the study guide and library become a single column; library tables turn into stacked rows with their actions wrapped underneath.
- **≤600px:** the sidebar becomes a top bar with the nav laid out in a row, the brand and the local-only note are hidden, the header moves to a 48px row, page padding is 20px × 16px, and every form grid becomes one column.

Layouts must work at 390px, 768px and desktop widths in both themes.

## Elevation & Depth

Sentio is flat. Depth comes from tone: Paper Grey desk, Sheet White cards, Tray Grey recesses, separated by 1px Hairline borders. `workspace.css` explicitly removes shadows from cards, session cards, chat bubbles and the send button.

### Shadow Vocabulary

- **Toast float** (`box-shadow: 0 4px 16px #0001`): on transient toasts that sit above content.
- **Dialog float** (`box-shadow: 0 12px 32px rgb(0 0 0 / 0.12)`): dialogs, over a light scrim (`rgb(22 27 36 / 0.45)`) with a 4px backdrop blur.

### Named Rules

**The Flat Desk Rule.** Surfaces never cast shadows at rest or on hover. To separate something, use a hairline border or a step in tone. Floating, transient UI (toasts, dialogs) is the only exception, and its shadow stays faint.

## Shapes

Gentle corners with a clear split by size. Small controls and recessed surfaces use 8px (`rounded.md`); larger containers such as stat cards, the notes overview and the study guide use 12px (`rounded.lg`); sub-navigation tabs use 6px (`rounded.sm`). Pills (`rounded.pill`) are only for small inline metadata: citation chips, badges, topic states, provenance tags and the difficulty notice (dashed border).

Left rules carry meaning: a 3px Ink Indigo rule marks a quoted passage from the notes, and a 4px green or red rule marks answer feedback or an error notice. Borders are always 1px Hairline unless they carry status.

## Components

### Buttons

Plain and quiet; the primary action is the one solid block of colour in its area.

- **Shape:** gently rounded (8px), at least 36px tall; nav items at least 44px.
- **Primary:** Ink Indigo fill and border, Sheet White text, weight 650, 8px × 16px padding.
- **Secondary:** Sheet White fill, Hairline border, Graphite text, 14px. This is the default look of any unstyled button.
- **Quiet / link:** no border or fill. Pencil Grey underlined for low-priority actions; Correction Red for destructive actions.
- **Focus:** a 3px Ink Indigo outline offset by 3px on every interactive element. Never remove it.
- **Disabled:** 55% opacity and a not-allowed cursor.

### Chips

- **Citation chip:** Tray Grey pill, Ink Indigo text, 12.5px at weight 600, Hairline border. Clicking opens the exact cited passage. The inline variant sits within a sentence at the surrounding text size and weight 500.
- **Badge:** Tray Grey pill, Ink Indigo 13px at weight 650; used for metadata such as answer mode.
- **Topic state:** an outlined pill with no fill. The border and text colour show the state: Pencil Grey for Not started, amber for Practising, green for Ready, Ink Indigo for Review due, red for No notes.

### Cards / Containers

- **Corner Style:** 8px for generic cards, 12px for stat cards and overview panels.
- **Background:** Sheet White on the Paper Grey desk.
- **Shadow Strategy:** none (see the Flat Desk Rule).
- **Border:** 1px Hairline, always.
- **Internal Padding:** 16px; stat cards use 16px × 20px.

### Inputs / Fields

- **Style:** Tray Grey fill, 1px Hairline border, 8px radius, 8px × 12px padding, at least 15px text.
- **Labels:** above the field, 14px at weight 600, Pencil Grey, sentence case.
- **Focus:** the shared 3px Ink Indigo outline.
- **Checkboxes / radios:** native, 18px, tinted Ink Indigo.

### Navigation

- **Sidebar:** the Sentio lockup (Ink Indigo symbol plus the graphite wordmark, linking to Today) above the nav links (15px, 10px × 16px, 8px radius). The active item gets a Tray Grey fill and weight 650, without changing colour. Study history, Settings, the theme toggle and "Your notes. Your machine." sit at the bottom.
- **Sub-navigation:** 14px text tabs; the current tab gets a Tray Grey fill, Graphite text and weight 650.
- **Mobile:** the nav becomes an equal-width row of 13px links in a top bar.

### Brand

- **Wordmark:** `SENTIO` in custom wide geometric capitals with one thin, even stroke and generous spacing: a squared S, an E with a shorter middle bar, and an O drawn as a rounded rectangle. Source: `src/sentio/static/img/sentio-wordmark.svg`. Inline copies use `currentColor`, with the stroke thickened to 10 units when shown at 12px tall so it stays crisp.
- **Symbol:** the wordmark's O, filled, with its top-right page corner cut off at about a third of its height. One solid Ink Indigo shape. Sources: `img/sentio-symbol.svg`, `img/favicon.svg` (lightens in dark mode), and `window.sentioSymbol()` for inline use.
- **Placement:** the lockup in the sidebar and on sign-in; the symbol alone as the tab icon and inside the tutor's message avatar.

### Icons

Drawn line icons from `src/sentio/static/js/core/icons.js`, on a 24px grid with a 1.75 stroke and round caps and joins, inheriting the text colour. Never use emoji as icons. The only exception is the optional camera feature's emotion faces, which describe detected emotions.

### Sign In

A split screen. On one side, the form: the lockup, a 34px "Welcome back" heading, sentence-case labels, "Forgot password?" as a quiet link beside the password label, a full-width primary button, and "Your account and notes stay on this computer." On the other side, a full-height Ink Indigo panel (an indigo tint in dark mode) states the promise, "Answers only from your notes.", above a real-style example: a question, a cited answer and a cited passage. Below 860px the panel stacks under the form.

### Status Pills and Uploads

- **Library status:** outlined pills: green for Ready to study, red for Needs retry, and a pulsing dot for Processing.
- **Uploads:**
  - Files can be dropped anywhere on the Library page; the page gets a dashed Ink Indigo outline while a file is held over it.
  - Each file in a batch gets its own row with its state.
  - Failed files can be retried with one click, without choosing them again.

### Cited Passage (signature)

A quoted excerpt from the student's notes: Tray Grey block, 3px Ink Indigo left rule, 8px radius, 12px × 16px padding, whitespace preserved. This is where the product's central promise, evidence before answers, shows up visually. Use it whenever source text is shown.

### Answer Feedback and Notices

A Tray Grey block with a 4px left rule: green for correct, red for incorrect or error, none for a neutral notice. The explanation follows in Pencil Grey. Fallbacks and refusals use the same honest, plain treatment and are never made to look like a success.

## Do's and Don'ts

### Do:

- **Do** separate surfaces with 1px Hairline borders and tonal steps (Paper Grey → Sheet White → Tray Grey).
- **Do** use Ink Indigo only for actions, links, citations, focus and the Review due state.
- **Do** show sources as citation chips and cited passages with the 3px Ink Indigo left rule.
- **Do** keep every interactive element's 3px Ink Indigo focus outline at a 3px offset.
- **Do** define and check each colour in both the light and the dark theme.
- **Do** keep text inputs at 15px or larger and nav targets at least 44px tall.
- **Do** respect `prefers-reduced-motion`; the workspace already disables animations and transitions under it.
- **Do** give every control a hover state (`--hover`) and a press state (`--press`). The primary action darkens to Ink Indigo Deep instead.
- **Do** animate only colour, background, border and opacity, with the shared timing: `--dur` (180ms) for controls, `--dur-slow` (320ms) for arrivals, and `--ease` (`cubic-bezier(0.2, 0.8, 0.2, 1)`) for both.

### Don't:

- **Don't** add drop shadows or glows to cards, buttons or bubbles; only toasts and dialogs float.
- **Don't** reuse the retired neon theme: cyan-on-black, scan-line overlays, glows, gradient buttons, Syne or JetBrains Mono.
- **Don't** set buttons or labels in uppercase with letter-spacing.
- **Don't** use green, amber or red as decoration or brand colour; they mean learning status or error.
- **Don't** use pill shapes for primary buttons or large containers; pills are for small metadata.
- **Don't** let the optional camera / emotion UI bring its own visual language into the main study flow.
- **Don't** use `transition: all`, bounce or overshoot curves, or a different duration per element.
- **Don't** end interface copy with exclamation marks, or write "successfully".
