# A more premium name, logo and sign-in page

- **Date:** 2026-11-03.
- **Status:** ideas only. Nothing is renamed, and PRODUCT.md still says Sentio.
- **Name checks:** quick web searches for clashes with study and AI apps. This was not a trademark search and not a domain-availability check; do both before choosing.

## Why rename at all

"Sentio" is Latin for "I perceive, I feel". It came from the emotion-aware tutor. That feature is now an optional side feature. What the product actually stands for is answers that come from your own pages, cited and kept on your machine. A name about pages and citations fits the product better.

## Name ideas

| Name            | Meaning and fit                                                                                                                                        | Clashes found                                                                                           |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------- |
| **Recto**       | The right-hand, front page of a book. From Latin _rectus_, "right, straight": answers that are right and come straight from your page. Short and calm. | None in study or AI apps. Recosoft and Rectangle are unrelated.                                         |
| **Folio**       | A leaf of a book, and the page number itself. Every citation chip ("p.12") is literally a folio.                                                       | No study app found, but "Folio" is used widely across other businesses, so a trademark could be harder. |
| **Ibid**        | Short for _ibidem_, "in the same source". It's the scholar's citation word: witty, academic and confident.                                             | No app found. Ibidem (Nota Bene) is a citation-formatting tool, a neighbouring field.                   |
| **Lectern**     | The stand you read from. Fits the "quiet study desk" idea.                                                                                             | Two student hackathon projects used it for AI study tools. Weak clashes, but present.                   |
| Keep **Sentio** | No migration work, and it's already in the code, README and screenshots.                                                                               | —                                                                                                       |

**Ruled out because they clash with close competitors:**

- **Carrel:** CarrelAI, a PDF study workspace.
- **Scholia:** an open-source course study assistant.
- **Gloss:** an iPad AI margin-notes reader, and an open-source local paper reader.
- **Quire:** an academic file organiser.

## Logo directions

The logo should be a drawn mark, not an emoji. The app and sign-in page currently use 🧠, which reads as generic "AI".

- **Recto:** an open book with only the right-hand page filled in Ink Indigo.
- **Folio:** a page with a small rounded bar at the foot, echoing the app's citation chips.
- **Ibid:** a lowercase wordmark with an Ink Indigo dot, a citation's full stop.
- **Lectern:** an angled indigo line on a thin stand.

For all of them: one colour (Ink Indigo), drawn at 16px for the browser tab icon and 32px in the sidebar, with no gradient or glow.

## Sign-in page

### Today

`src/sentio/static/js/views/auth.js`:

- A centred white card with 🧠, "Welcome to Sentio" and "Sign in to your local study workspace".
- Title Case labels and buttons ("Email Address", "Sign In", "Register Account").
- The placeholder `student@sentio.edu`.
- A recovery-key panel after sign-up, and "Forgot password?" as a full-width button.

### Inspiration

From Watermelon's sign-in blocks.

- **[auth-07](https://ui.watermelon.sh/block/auth-07): split screen.** A light form on the left with a small wordmark, a dark halftone cloud image on the right, and one solid black button. The most premium of the set.
- **[auth-12](https://ui.watermelon.sh/block/auth-12): split screen, the other way round.** Artwork on the left and a large left-aligned "Welcome back" on the right, with the password link sitting next to its field.
- **[auth-10](https://ui.watermelon.sh/block/auth-10): a short promise beside the form.** One line of value sits next to the form, such as "your personal hub for clarity".
- **What none of them suit:** Google, GitHub and Apple buttons, and "30-day free trial" lines. Sentio's account is local, so there's nothing to sign in with elsewhere and nothing to try.

### What to take for Sentio

1. **A split layout.** The form goes on one side. The other side shows the product's promise instead of stock art, for example a real cited passage in the app's cited-passage style ("Inertia resists changes in velocity." · mechanics.txt · p.1).
2. **A real logo mark and wordmark** in place of 🧠.
3. **A large left-aligned heading:** "Welcome back", or "Create your account".
4. **Sentence case throughout:** "Email address", "Sign in", "Create account".
5. **A neutral placeholder,** such as `you@university.edu`. The `.edu` domain is fine; the product name is not.
6. **"Forgot password?" as a small link** next to the password field, not a full-width button.
7. **A quiet local note** under the form: "Your account stays on this computer." The recovery-key step stays; it's honest and necessary.
8. **The shared hover, press and timing treatment** from [apple-comparison.md](apple-comparison.md).
