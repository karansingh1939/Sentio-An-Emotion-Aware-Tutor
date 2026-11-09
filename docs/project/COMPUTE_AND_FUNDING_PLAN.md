# Sentio: what limits the AI tutor today, and what it would cost to fix

*Prepared 9 November 2026 for teachers, mentors and funders. All timings were measured on
the development laptop on that date. Prices are public listings from the same week and will
change.*

## In one paragraph

Sentio is a study app that answers questions **only from a student's own lecture notes**,
makes quizzes and flashcards from them, and runs **entirely on the student's own computer**:
no account with an AI company, no data leaving the laptop, no cost per question. That privacy
and zero running cost are its point. The price is speed. On an ordinary student laptop
without a graphics card, the AI model writes about **6 to 15 words a second**, so a tutor
answer takes about half a minute and an on-demand quiz takes a minute or more. We have
already removed every free slowdown we could find (below): tutor answers are now about
20% faster at the median and the slowest answer dropped from 58 to 33 seconds, with no loss
of accuracy on our test. What remains is a hardware limit. A smaller model is faster but,
as measured below, not accurate enough. The real ways past the limit are **better
hardware** (one-off cost) or an **online model** (small monthly cost per student). This document sets out the measurements and the options so the choice can be
made with real numbers.

## 1. The machine we measured on

| Part | What the laptop has | Why it matters |
| --- | --- | --- |
| Processor | Intel Core i7-12700H, 14 cores (6 performance + 8 efficiency), 20 threads | Does all AI work, because there is no usable graphics card |
| Graphics | Intel Iris Xe (built into the processor) | Shares system memory; tested below, not faster overall |
| Memory | 16 GB DDR4-3200 (2 × 8 GB, both slots full; supports up to 64 GB) | The 7B model takes 4.7 GB; with a browser and other apps open, **only about 1.7 GB was left free**. If Windows runs out, it swaps to disk and AI speed collapses |
| AI runtime | Ollama 0.40.15, models `qwen2.5:7b` and `qwen2.5:3b` (4-bit) | Free, open-source, runs offline |

## 2. Where the time goes

An AI answer has two phases:

1. **Reading** the prompt (the student's question plus the relevant passages from their
   notes, about 1,100 tokens). Measured: **about 37 tokens a second**, so about 29 seconds
   before the first word appears.
2. **Writing** the answer. Measured: **about 5.5 tokens a second** (a token is about
   three-quarters of a word). Every 100 words costs about 20 seconds.

Writing speed is limited by how fast the processor can stream the model's 4.7 GB of numbers
from memory for every single word. That is a property of the hardware, not of our code.

### What students actually waited for (first-time user test, 9 November)

| Feature | Time | Note |
| --- | --- | --- |
| Tutor answer | about 1 to 2 minutes | 3 paragraphs plus extra fields |
| Quiz, 3 questions | **2 min 20 s** | The first attempt (81 s) had one malformed question, so the whole quiz was thrown away and written again |
| Flashcards | similar to the quiz | |

A student revising for an exam will not wait two minutes for a quiz. This is the problem
this document addresses.

## 3. What we already fixed, at no cost

| Change | Measured effect |
| --- | --- |
| Run the model on physical cores instead of all 20 threads | Writing **5.4 → 6.6–7.1 tokens/s** (about 25–30% faster) |
| Keep the model loaded while the app is open, and load it when the app starts | Removes a 10–35 s reload after 15 idle minutes |
| Put the student's question *after* the notes in the prompt, so the AI runtime can reuse work it already did for the same notes | A follow-up on the same notes started answering in **0.2 s instead of about 29 s** in our test; the gain applies when the retrieved passages repeat |
| Shorter tutor answers (about 150 words unless the student asks for more), no filler fields | Fewer words to write; quality checked below |
| Quizzes and flashcards: keep the valid questions and rewrite only the broken one, instead of the whole batch | Removes the 81 s wasted attempt seen in the test |

### Things we tested and rejected

| Idea | Result on this laptop |
| --- | --- |
| "Flash attention" and a compressed memory cache (common GPU tips) | Reading got **slower** (37 → 28 tokens/s); writing unchanged |
| Using the built-in Intel graphics (Vulkan) | Reading **2× faster**, but writing **slower** (7 → 4 tokens/s); no overall gain, and it uses the same shared memory |

## 4. The options from here

### Option A: a smaller model (free, available now)

`qwen2.5:3b` is the same model family at less than half the size (1.9 GB).

| Model | Tutor answer (measured) | Writing speed | Memory |
| --- | --- | --- | --- |
| `qwen2.5:7b` (tuned) | about 45–55 s | about 7 tokens/s | 4.7 GB |
| `qwen2.5:3b` (tuned) | **about 25 s** | **about 14–15 tokens/s** | **1.9 GB** |

The cost is answer quality, and section 5 shows it is too high for the tutor: the 3B model
failed most of our grounding checks. So this option only helps on very low-memory laptops,
or for simpler tasks.

### Option B: more memory (one-off, about ₹21,000–34,000)

Replacing the two 8 GB modules with a 2 × 16 GB DDR4-3200 kit (32 GB total). Listings seen
this week on Amazon.in and Indian retailers ranged from about ₹21,000 to ₹34,000.

- **What it fixes:** the laptop stops running out of memory when the model, a browser and
  other apps are open, so it never falls into very slow disk swapping, and the larger 7B
  model can always be used.
- **What it does not fix:** it does not make the model write faster. Speed is set by memory
  *bandwidth*, which stays the same.

Recommended only together with Option A or C, not on its own.

### Option C: a graphics card (one-off, about ₹26,000–42,000 for the card)

A desktop graphics card with 12 GB of its own memory (for example an NVIDIA RTX 3060 12 GB,
listed new in India at about ₹26,000–42,000 this year; used cards are cheaper but
unverified) holds the whole 7B model in fast memory. Graphics cards are widely reported to
run 7B models several times faster than a laptop processor. We have not measured one
ourselves, so this needs a test before purchase. It also needs a desktop PC to put it in.

This is the right option for a **shared machine**: one school computer could serve the app
to a classroom over the local network, keeping all student data inside the school.

### Option D: an online model (small monthly cost per student)

The app could send questions to a hosted model instead. Answers would take a few seconds.
Estimated usage for one active student on one study day: about 20 tutor questions plus 2
quizzes and 2 flashcard decks, which is about 30,000 tokens read and 8,000 written.

| Service (list price this week) | Read / write price per million tokens | Cost per active student per month (30 days) |
| --- | --- | --- |
| Google Gemini 2.5 Flash-Lite | $0.10 / $0.40 | about **$0.19 (≈ ₹16)** |
| Anthropic Claude Haiku 4.5 | $1 / $5 | about **$2.10 (≈ ₹180)** |
| Free tiers (Google AI Studio, Groq) | $0, with daily limits | $0 for a small pilot |

(Conversion at about ₹85 to the dollar. Usage is our estimate; a real pilot would measure
it.)

**Trade-offs we will not hide:**

- Student notes would leave the laptop. That needs consent, and free tiers in particular may
  allow the provider to use the data to improve its products. For private notes, a paid tier
  with a no-training agreement is the honest choice.
- It needs an internet connection and an ongoing budget.
- Free-tier limits change often and can end without notice; they are fine for a pilot, not
  for a promise to students.

## 5. Quality check of the faster settings

Speed is worthless if answers get worse, so we re-ran Sentio's grounding test: 12 questions
over real uploaded notes, through the real app. Four questions the notes answer, six asking
for facts the notes do **not** contain (the tutor must refuse rather than guess), and two
ambiguous ones (it should ask what the student means).

| Setup | Answered correctly from notes | Refused when notes lacked the fact | Ambiguous handled | Invented an outside fact | Median / slowest answer |
| --- | ---: | ---: | ---: | ---: | ---: |
| `qwen2.5:7b`, before (29 Oct) | 3 / 4 | 6 / 6 | 1 / 2 | 0 | 24.3 s / 58.2 s |
| `qwen2.5:7b`, **tuned (9 Nov)** | **4 / 4** | **6 / 6** | 1 / 2 | **0** | **20.2 s / 32.9 s** |
| `qwen2.5:3b`, tuned (9 Nov) | 1 / 4 | 0 / 6 | 0 / 2 | 1 | 8.9 s / 17.9 s |

- The tuned 7B model is **faster and no worse**; on this small test it did one question better.
- The 3B model is fast but **not trustworthy as a tutor**: it mostly failed to produce a
  checked answer (the app then shows quoted passages instead) and once used an outside
  fact. We keep the 7B model as the default. Option A is therefore *not* a free fix for the
  tutor; it may still suit simpler jobs such as drafting flashcards, which we have not
  tested yet.
- Limits: 12 synthetic cases, one run each, checked by keyword rules rather than a human
  marker. A one-question difference is not statistically meaningful.

**Quiz timing after the fixes.** One valid 3-question quiz now takes **60–70 seconds** on
this laptop (the model writes 340–480 tokens at about 7 tokens a second), down from 2 min
20 s when a whole batch was thrown away. That is still too slow to make on demand, which
is why the next stage below makes quizzes in the background before the student asks.

## 6. Our plan, and what funding would unlock

| Stage | What | Cost | Result |
| --- | --- | --- | --- |
| Now (done) | Free tuning in section 3 | ₹0 | Tutor median 24 → 20 s, slowest 58 → 33 s; quiz 2 min 20 s → about 1 min; no loss of accuracy |
| Next (no cost) | Make quizzes and flashcards **in the background right after notes are uploaded**, so they are ready before the student asks; let a student's question jump ahead of background work | ₹0, development time | Quizzes open instantly in normal use |
| With about ₹25,000 | 32 GB memory for the development and demo laptop | one-off | Reliable demos with the better 7B model and a browser open |
| With about ₹60,000–80,000 | A desktop with a 12 GB graphics card as a **school AI server** | one-off | Fast answers for a classroom, data stays in school |
| Optional | Opt-in online model for students who choose speed over keeping notes on their device | about ₹16–180 per active student per month | Answers in seconds on any laptop |

The app works today on a laptop with no extra spending. Funding decides how fast it is and
how many students one setup can serve.

## How these numbers were measured

- Tutor timings: a realistic Sentio tutor request (system instructions, five passages from a
  student's notes, a question, structured answer), sent directly to Ollama with temperature 0.
  Two runs with a fresh prompt and two with a reused prompt per setting.
- First-time user test: a separate AI agent with no knowledge of the project used the app in
  a browser as a new student would, with made-up Biology notes; times come from the server log.
- Prices: public list prices and Indian retail listings seen on 9 November 2026. Check them
  again before buying anything.
