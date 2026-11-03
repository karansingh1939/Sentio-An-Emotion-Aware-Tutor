# Sentio compared with Apple's design and workflow

- **Checked:** 2026-11-03, against Apple's [MacBook Air page](https://www.apple.com/macbook-air/). Apple's styles were measured from the live page.
- **Sources for Sentio:** [DESIGN.md](../../../DESIGN.md) and [PRODUCT.md](../../../PRODUCT.md).
- **See also:** the saved [Watermelon hero-13](watermelon-hero-13.md) reference.

## Visual design

|                 | Apple (MacBook Air page)                                                          | Sentio app today                                      | Watermelon hero-13                      |
| --------------- | --------------------------------------------------------------------------------- | ----------------------------------------------------- | --------------------------------------- |
| Background      | White, alternating with `#f5f5f7` sections                                        | `#f5f6f8` page with white cards                       | Near-black with glowing colour bands    |
| Text colour     | `#1d1d1f`, with `#6e6e73` for secondary text                                      | `#202938`, with `#556174` for secondary text          | White, and 55% white for secondary text |
| Font            | SF Pro Display and Text                                                           | System font (renders as SF Pro on a Mac)              | Inter                                   |
| Headline weight | 600                                                                               | 700                                                   | 300                                     |
| Headline size   | 56–80px on the product page; 17–21px for card text                                | 28px page titles (an app, not a marketing page)       | Large and thin                          |
| Accent          | One blue (`#0071e3`), on Buy and Shop buttons only                                | One indigo (`#465bb2`), on actions and citations only | Blue-to-orange spectrum                 |
| Buttons         | Fully rounded pills                                                               | 8px corners                                           | Pills                                   |
| Depth           | Mostly flat; a few full-bleed dark panels for drama                               | Flat, hairline borders                                | Glow and grain                          |
| Proof           | Numbered footnotes on every claim (for example "Up to 18 hours of battery life¹") | Caveats written next to every result                  | Unbacked badges and "100+ projects"     |

**Takeaway:** Sentio's app is already close to Apple's system. The near-white backgrounds, near-black text, a single blue accent and the system font are almost the same. The real gaps are on the marketing side: Apple uses much bigger headlines, short punchy lines, product imagery as the hero, and pill-shaped buy buttons. Hero-13 is the furthest from both.

## Page workflow, from first visit to action

| Step            | Apple                                                                                          | What Sentio would need                                                                                           |
| --------------- | ---------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| 1. First screen | Product name, a 64px one-line promise ("Might takes flight."), a large product image, and Buy  | "Sentio", a one-line promise ("Answers only from your notes."), a large Study screenshot, and "Get it on GitHub" |
| 2. Highlights   | "Get the highlights": a row of cards, one fact each                                            | Cited answers, refusal when the notes don't cover it, quizzes, flashcards, runs locally                          |
| 3. Deep dives   | One topic per section (Design, Performance, AI, macOS, Continuity), each with an 80px headline | Retrieval with citations, practice and review, topic mastery, syllabus progress, privacy                         |
| 4. Privacy      | A dedicated section ("Great powers come with great privacy.")                                  | Your strongest real claim: the model, the database and the files stay on your machine                            |
| 5. Evidence     | Numbered footnotes at the bottom explain each claim                                            | The model comparison and grounding tests, footnoted as synthetic, author-labelled experiments                    |
| 6. Action       | Buy, with a sticky sub-navigation that keeps Buy visible                                       | Quick start (install uv and Ollama, then clone), with "Get it on GitHub" kept visible                            |

## How Apple designs, and what Sentio already shares

This section comes from Apple's public Human Interface Guidelines and how its products behave. It is not inside knowledge of Apple's internal process.

- **Content first, interface second.** The interface steps back so the content leads. Sentio does the same with the student's notes and its cited passages.
- **One clear primary action per screen.** Apple uses a blue Buy button. Sentio uses one indigo primary button.
- **Light and dark as equals.** Apple tunes both. Sentio's Two Desks Rule says the same.
- **Accessibility built in.** Apple relies on Dynamic Type, VoiceOver and Reduce Motion. Sentio has keyboard focus, a 15px floor for text inputs, reduced-motion support and layouts tested at 390px. It does not scale text to the user's preferred size yet.
- **Honest claims.** Apple footnotes its numbers. Sentio's rule is never to invent evidence. That is the same discipline, so Sentio can borrow Apple's footnote pattern directly.
- **Where Apple goes further:**
  - Product photography and motion tied to scrolling.
  - A larger type scale with very short headlines.
  - A consistent sticky product bar.
  - Comparison tables for each model.

## Why Apple feels premium as you move the cursor

Measured from the live page's stylesheets. Apple has no custom cursor and no glows. The premium feel comes from small, consistent responses to what you do.

|                          | Apple (MacBook Air page)                                                                                      | Sentio today                                                                                    |
| ------------------------ | ------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| Hover states             | 129 hover rules; nearly everything you can point at responds                                                  | 13, mostly in the legacy layer; citation chips, topic rows, study links and cards don't respond |
| Press (`:active`) states | Buttons respond when pressed                                                                                  | None                                                                                            |
| Keyboard focus styles    | 49 rules                                                                                                      | 5, sharing one strong outline                                                                   |
| Timing                   | A small set reused everywhere: 240ms and 320ms, with 80ms delays so menus don't flicker as you pass over them | A mix of 0.2s, 0.3s, 0.4s and 0.6s, plus `transition: all`                                      |
| Easing                   | Apple's own gentle curve, `cubic-bezier(0.4, 0, 0.6, 1)`, applied to colour and opacity                       | The browser default `ease`, and one bouncy overshoot on a legacy element                        |
| Scroll                   | A sticky product bar, scroll-linked effects and 8 videos that play as you reach them                          | No scroll behaviour                                                                             |
| Reduced motion           | 40 rules, tuned per element                                                                                   | One global rule that switches all motion off                                                    |

**What makes motion feel like "AI slop":** everything fading or sliding in on load, glows, bouncy overshoot, `transition: all`, and random durations. Each one alone is small; together they make an interface feel generated rather than designed.

**What makes it feel premium:**

- Every element you can point at answers.
- Every answer uses the same timing and curve.
- Motion changes colour and opacity, not size.
- Menus wait a moment before opening, so passing the cursor over them doesn't set them off.
- The page moves only when you scroll, never on its own.

**For Sentio:**

1. Add two shared motion values to `:root`: a duration (around 240ms) and Apple-like easing.
2. Use them for every transition, replacing `all`.
3. Give citation chips, topic rows, study links, cards and buttons a quiet hover state (a step in tone) and a press state.
4. Remove the bouncy legacy curve.
5. Keep the global reduced-motion rule as a safety net.

## If the landing page followed Apple

- Light page; at most one dark, full-width panel for a single dramatic moment, such as privacy.
- Headlines of 56–80px at weight 600, one short line each, in the system font.
- One indigo pill for the primary action. The app keeps its 8px corners.
- Real screenshots of Sentio as the hero imagery.
- Numbered footnotes for every measured result.
