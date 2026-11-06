# Amplo dashboard (screen recording)

- **Source:** a 12.6-second screen recording of a social post by `_code_and_chill_`, "Record label ad campaign dashboard" (#dashboard #analytics #dataviz). Karan shared it on 2026-11-06. The app in the post is called **Amplo**, a dark dashboard for a music label's ad campaigns.
- **How it was measured:** frames extracted with ffmpeg at 1 fps, at 10 fps for the whole clip, and at 20 fps for each transition. Colours were sampled from the pixels with Pillow. The dashboard only fills about 870 × 490 px of the recording, so sizes below are scaled up by about 1.65 to a 1440 px-wide screen and are **estimates**. Colours are close but slightly shifted by video compression.
- **Not in the video:** hover states (the cursor never rests on anything long enough), disabled states, a light theme, mobile layouts, and any narration (the audio is background sound, not speech).

## Palette (sampled)

| Role                                                    | Value                                                                   |
| ------------------------------------------------------- | ----------------------------------------------------------------------- |
| Page                                                    | `#0d0f0f` (near black, cool)                                            |
| Card                                                    | `#141517`                                                               |
| Raised area inside a card (Autopilot box, inputs)       | `#1b1c1e`                                                               |
| Card and control border                                 | about `#1a1c1e` (a 1px hairline, barely lighter than the card)          |
| Primary text                                            | `#fdffff`                                                               |
| Muted text (labels, table headers, inactive tabs)       | `#8a8b8f` to `#969799`                                                  |
| Accent (primary buttons, active tab, links, chart line) | `#4d80ff`                                                               |
| White pill button (Join)                                | `#f8fafa` with dark text                                                |
| Positive / live                                         | text `#7bbb9d` on a dark green tint                                     |
| Notification count                                      | `#f17e62` (coral)                                                       |
| Chart series                                            | blue `#4b7ffe`, orange `#f19c22`, teal `#27bfa9`, coral red, lime, cyan |

## Type, spacing, shape (estimated at 1440 px)

- **Typeface:** a geometric sans with a single-storey "g" and round "o". It looks like the Outfit / Plus Jakarta Sans family; it can't be named with certainty at this resolution.
- **Sizes:** page title about 36px, medium weight; big figures (£22,902.25, 75,265) about 34px; card titles 15px; body and table text 13–14px; tab labels 14px; small labels 12px.
- **Spacing:** page gutter about 32px; gap between cards about 16px; card padding about 20–24px.
- **Radius:** cards about 16px; buttons and inputs about 10px; the tab bar, tab pill, status pills and avatars are fully round.
- **Depth:** no visible shadows. Separation comes from three dark tones plus hairlines.

## Screens in order (the flow in the clip)

1. **Overview** (0–1.3s): greeting "Good morning, Imogen" with a one-line status ("4 campaigns live · 5,151 fans yesterday · Glasshouse drops 6 Nov"). Top right: "Weekly report" (secondary) and "+ New campaign" (primary). Cards: Ad wallet (big figure, three sub-figures, an Autopilot suggestion with a Rebalance button), a donut drawn as a vinyl record with a legend, Fans gained (big figure, a green delta pill, a 24h / Week / Month / Year segmented control, an area chart comparing this period with the previous one), a "Campaigns on air" table with On air / All tabs and a white Join pill per row, and a "Next drop" countdown (days / hours / minutes tiles).
2. **Reports** (1.4–3.0s): title and subtitle, "Save view" and "Export CSV" buttons. Left: a Saved views list (star to pin, initials avatar). Right: view name input, metric chips (Fans gained / Reach / Spend / Cost per fan), two segmented controls (group by, time range), a total, horizontal coloured bars per artist, then a table.
3. **Campaigns, list** (3.1–4.2s): an invite inbox (Decline / Let in buttons), a search box, a filter dropdown, status filter chips with counts, and a table with an owner avatar, dates, a budget-spent bar, and status pills.
4. **Campaigns, Board** (4.3–6.9s): kanban columns by status (Draft, In review, Live, Paused, Wrapped). Each column has a status pill, a count and a total. Cards show an initials tile, an artist, a title, a start date, a progress bar, avatars and an amount. A coloured left rule on each card shows its status.
5. The post's video then loops: Overview loads in again (6.9–8.5s), Reports (8.6s), Campaigns (10.3s), Board (11.5s).

## Interactive elements

| Element                                                     | Default                                                                                                    | Active / selected                                                                                    | Hover, click, disabled        |
| ----------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- | ----------------------------- |
| Top tab bar                                                 | Round dark track with a hairline border; muted labels; a small blue dot on tabs with news                  | Blue filled pill behind the label, white text                                                        | Hover not visible in the clip |
| Primary button (+ New, New campaign, Export CSV, Rebalance) | Accent fill, white text, optional leading icon, about 10px radius                                          | —                                                                                                    | Not visible                   |
| Secondary button (Weekly report, Save view)                 | Card-colour fill, hairline border, white text, leading icon                                                | —                                                                                                    | Not visible                   |
| White pill (Join)                                           | Near-white fill, dark text                                                                                 | —                                                                                                    | Not visible                   |
| Segmented control (24h/Week/Month/Year, Board)              | Hairline-bordered track                                                                                    | Lighter grey fill for the chosen item; a blue fill for the main metric chip; an optional count badge | Not visible                   |
| Icon buttons (search with a ⌘K hint, theme, bell)           | Square, hairline border, about 10px radius; the bell has a coral count badge                               | —                                                                                                    | Not visible                   |
| Status pill                                                 | Tinted background with a coloured dot (Live green, In review amber, Paused teal, Wrapped blue, Draft grey) | —                                                                                                    | —                             |
| Avatar                                                      | Round initials with a green presence dot                                                                   | —                                                                                                    | —                             |

## Motion (measured frame by frame)

| What                               | How it moves                                                                                   | Timing (approx.)                            |
| ---------------------------------- | ---------------------------------------------------------------------------------------------- | ------------------------------------------- |
| Active tab pill on a tab change    | Stretches from the old tab to the new one, then shrinks onto the new tab, like a stretchy blob | about 350 ms, ease-out                      |
| Leaving page                       | The content dims to nothing                                                                    | about 150 ms                                |
| Page title                         | Types itself in letter by letter ("Rep", "Repo", "Reports")                                    | about 25–35 ms per letter                   |
| Page content                       | Panels fade in and rise a few pixels, one after another                                        | about 50 ms apart, about 250 ms each        |
| Kanban columns                     | The column shells appear left to right, then their cards fade in, then the progress bars fill  | about 50 ms per column, about 700 ms in all |
| Horizontal bars (Reports, budgets) | Grow from the left to their value                                                              | about 400–500 ms                            |
| Big figures on load                | Count up to their value (£14,491 → £21,255)                                                    | about 600–800 ms                            |
| Donut                              | The ring draws clockwise                                                                       | about 600 ms                                |
| Area chart                         | The line draws left to right, with the fill following                                          | about 600 ms                                |
| Table rows                         | Fade in from top to bottom                                                                     | about 40 ms apart                           |
| First load                         | The tab labels fade in left to right before the content                                        | about 40 ms apart                           |

## How it fits Sentio

What it would replace or meet in Sentio, and where it conflicts with decisions already made, is in the conversation's design breakdown of 2026-11-06. Nothing here changes [DESIGN.md](../../../DESIGN.md) until Karan agrees.
