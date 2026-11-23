# Retrieval with student-style questions - 17 November 2026

Question: every earlier test question was written cleanly ("What is the SI unit of
kinetic energy?"). Real learners type "si unit for kinetic enrgy?". If a misspelled or
shorthand question fails retrieval, the evidence gate refuses a question the notes do
answer.

Dataset: `tests/fixtures/evaluation_sloppy_v1` reuses the 12 synthetic documents and
expected passages of `evaluation_v1`. Each of the 22 queries was rewritten by the author
with lowercase, misspellings, shorthand and missing words; `clean_query` keeps the
original. They are not collected from real students.

Change: `BM25Searcher.correct_query` adds, after each word missing from the selected
notes (five letters or more), up to two notes words within edit distance 1 (2 for words of
eight letters or more) that share its first letter. The original word stays. The keyword
search and the evidence gate use the corrected query; embedding search keeps the
learner's wording.

| Run | Keyword | Hybrid (the tutor) | Unanswerable questions with a candidate |
| --- | ---: | ---: | ---: |
| Clean questions, after | 17/18 | 17/18 | 1/4 |
| Student-style, before | 15/18 | 16/18 | 1/4 |
| Student-style, after | 16/18 | 17/18 | 1/4 |

Reports: [before](evaluation-sloppy-before-2026-11-17.json),
[after](evaluation-sloppy-after-2026-11-17.json). The clean-question results are
unchanged from the previous run.

- `derivitive measures what` found nothing before and finds the derivative passage
  after. It is the only case the change fixed.
- `what makes a moving thing change its speed or direction` still fails. It is a
  paraphrase with no shared word; its embedding similarity (0.295) is under the 0.35
  floor, as with the clean paraphrase. Typo correction cannot help it.
- The one unanswerable question with a candidate (`tell me the other learners password`)
  had it before the change too.

Limits: 18 answerable questions, one author, synthetic notes. A one-question gain is
within what a different wording would change. A correction can also match a real word
the notes lack to a different notes word ("measures" to "measured"); with embeddings in
the ranking that did not change the result here, but it can add a weak candidate.
