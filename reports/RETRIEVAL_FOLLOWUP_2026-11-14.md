# Retrieval follow-up — 14 November 2026

The [11 October report](AI_EVALUATION_2026-10-11.md) concluded that hybrid search showed
no gain over keyword search. Rerunning it with one added reference mode shows why, and
corrects two points.

Same dataset (v1.0, 12 documents, 18 answerable and 4 unanswerable questions), same
isolated runtime, current code. The new `dense_reference` mode ranks passages by
`all-MiniLM-L6-v2` cosine similarity alone, with no score floor and no keyword filter.
The product never retrieves this way; it is a reference for what the hybrid path removes.

| Mode            | Relevant passage in top 5 |    MRR | Unanswerable questions returning passages |
| --------------- | ------------------------: | -----: | ----------------------------------------: |
| keyword         |                     17/18 | 0.9444 |                                       1/4 |
| hybrid          |                     17/18 | 0.9444 |                                       1/4 |
| dense reference |                     18/18 | 1.0000 |                 not applicable (no floor) |

## What this corrects

1. **Hybrid's missing gain comes from the similarity floor, not from embeddings.** The one
   miss in both product modes is r02, a paraphrase sharing no content word with its source.
   Its cosine similarity to the right passage is 0.321. The hybrid path discards vector
   hits below 0.35 (`MIN_DENSE_SIMILARITY` in `src/sentio/rag/evidence_policy.py`), so the
   passage never reaches ranking. On this corpus the answerable questions score 0.321 to
   0.813 against their passage and the unanswerable ones peak at 0.113.
2. **The negative candidate rate is now 25%, not 75%.** The October figure predates the
   function-word filter in the relevance check. One of four unanswerable questions still
   returns a passage, through a single shared content word.
3. **The corpus cannot test chunking or ranking.** The longest document is 229 characters
   against a 500-character chunk size, so every document is one chunk and each question
   chooses among 12 passages. Every hit is at rank 1, which is why hit rate, recall and MRR
   are identical.

## What it does not show

Twenty-two author-written questions over 12 one-paragraph documents cannot set a threshold
or rank retrieval methods. The floor of 0.35 has not been changed: a lower value separating
this corpus says nothing about lecture-length notes. Choosing it needs a larger corpus with
independent labels, long documents and several relevant passages per question.

Also unchanged from October: the relevance gate passes any passage that shares one content
word with the question. It stops off-topic questions; it does not detect a covered topic
with a missing fact.

## Reproduce

```sh
uv run python scripts/eval/evaluate_retrieval.py --output reports/retrieval-new.json
```

Raw measurements, including each question's similarity scores:
[retrieval-2026-11-14.json](retrieval-2026-11-14.json). Hardware and package versions are
recorded in the file. Query latencies were taken while other work ran on the same machine
and are not comparable with October's.
