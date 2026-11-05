# Research: trust in AI study apps, and screens that don't feel cluttered

- **Date:** 2026-11-06.
- **Method:** two `/last30days` runs across Reddit and Hacker News, then web searches.
- **Raw results:** saved in `~/Documents/Last30Days/`.
- **What the community runs returned:** nothing reliable. Reddit blocked the tool's live search (HTTP 403) and the archive results were off-topic, so neither run produced community findings.
- **What the findings below rest on:** studies, university guides and established design sources, cited inline. Several design sources are vendor blogs, so treat their numbers as rules of thumb, not standards. The WCAG contrast ratios are the only formal standard here.

## 1. What makes students trust an AI study tool

- **Made-up citations are the biggest worry.** A 2026 study of 63 students found that the errors they report most are fabricated or wrong citations and confidently wrong answers ([arXiv 2602.17671](https://arxiv.org/pdf/2602.17671)).
- **They use AI anyway, but warily.** A secondhand summary of the UK HEPI 2026 survey reports that about 95% of students use AI and 51% are put off by hallucinations ([Futurense](https://futurense.com/blog/ai-tools-for-students)). Check the HEPI report itself before quoting it.
- **Checkable citations build the habit of verifying.** University guides praise NotebookLM because a citation jumps to the exact page of the source ([NYU](https://wp.nyu.edu/fas-edtech/2026/02/what-is-notebooklm/), [UC Davis](https://iet.ucdavis.edu/aggie-ai/ai-tools/notebooklm)).
- **A citation alone isn't proof.** It points to a file, but the reader still has to judge whether the passage supports the claim ([arXiv 2607.28853](https://arxiv.org/pdf/2607.28853)).

**For Sentio:** the core design already matches the strongest trust signal: answers only from your notes, citations that open the exact passage, and an honest refusal. Next:

1. Show the cited passage directly under the sentence it supports, so students can check it without clicking.
2. Keep the "check the claims against your notes" note on generated explanations.
3. Never show a citation chip that doesn't open a real passage.

## 2. How clear apps avoid feeling cluttered

- **Progressive disclosure.** Show the main options by default and move rarely used ones one step away. Nielsen Norman Group says this improves learnability, efficiency and error rates, but the way to reveal more must be obvious ([NN/G](https://www.nngroup.com/articles/progressive-disclosure/)).
- **Visual complexity.** NN/G names three tools for managing it: progressive disclosure, predictable placement and a clear visual hierarchy ([NN/G video](https://www.nngroup.com/videos/managing-visual-complexity/)).
- **One primary action per screen.** Only the main action gets the solid accent colour; secondary actions are outlined or plain text. Use the accent colour for one job only, because once links, icons and badges all use it, it stops guiding the eye ([ColorFYI](https://colorfyi.com/blog/color-hierarchy-in-ui/), [UX Magic](https://uxmagic.ai/blog/what-is-visual-hierarchy)).
- **A small type scale.** Use 3–6 sizes, each at least 1.25× the one below. 16px body text with a 32–40px main heading is a common starting point. Use weight and spacing as well as size. Squint test: blur your eyes, and the primary action should still stand out ([UX Magic](https://uxmagic.ai/blog/what-is-visual-hierarchy)).
- **Contrast.** WCAG requires 4.5:1 for normal text and 3:1 for large text and controls, and colour must never be the only signal.
- **First-use (empty) screens.**
  - Give one obvious next step, with at most one quiet alternative.
  - Use verb-first labels, such as "Add your notes" rather than "Get started".
  - Show a faint preview of what the filled screen will look like.
  - No jokes on a first-use screen, where users may feel unsure ([Eleken](https://www.eleken.co/blog-posts/empty-state-ux), [72Technologies](https://www.72technologies.com/blog/empty-states-as-onboarding-surface)).

## 3. What this means for Sentio's screens

Proposals, not decisions. Changing a size or colour token also means updating DESIGN.md.

| Screen            | Today                                                                                    | Clearer version                                                                                                                      |
| ----------------- | ---------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| **Library row**   | Five buttons on every file: Study, Study slides, Preview, Topics, Delete                 | Keep **Study** as the one primary button. Put Study slides, Preview, Topics and Delete in a "More" menu.                             |
| **Study toolbar** | Four buttons of equal weight: Try a quiz, Make flashcards, Notes & sessions, End session | Keep the question box as the focus. Group quiz and flashcards under one **Practise** menu, and make End session a quiet text button. |
| **Today**         | Several sections at once                                                                 | Lead with one "Continue" card for the next thing to do (a due review or the last lecture); everything else goes below.               |
| **Empty Library** | A drop box plus an explanation                                                           | One action, "Add your notes", plus a faint preview of a ready lecture row.                                                           |
| **Answers**       | Citation chips under the answer                                                          | Show the cited passage directly under the sentence it supports (from section 1).                                                     |
| **Type sizes**    | 28px page titles, 16px body, many 12–15px sizes                                          | Cut to about 5 sizes: 13 / 16 / 20 / 28 / 36, with 36px only for the one main heading per screen.                                    |
| **Colour**        | Ink Indigo on buttons, links, chips, badges and states                                   | Already close to "one job". Keep the solid indigo fill for the single primary action; links and chips stay indigo text only.         |

**Test it with real students.** Watch 3–4 classmates use Sentio for 15 minutes without helping them. Note where they hesitate or ask "where is…". That shows exactly what to hide and what to bring forward, better than any of the research above.
