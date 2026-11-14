# Retrieval on public benchmarks — 14 November 2026

Sentio's own retrieval fixtures are 12 one-paragraph documents, too small to rank methods
(see the [retrieval follow-up](../../reports/RETRIEVAL_FOLLOWUP_2026-11-14.md)). This
experiment runs the tutor's retrieval code on two public benchmarks with thousands of
passages and independent relevance labels.

## Setup

| Dataset                                        | Passages | Questions | What it is                                                                                 |
| ---------------------------------------------- | -------: | --------: | ------------------------------------------------------------------------------------------ |
| [SciQ](https://allenai.org/data/sciq)          |   12,241 |       884 | School science questions, each written from one support paragraph, which is the gold label |
| [SciFact](https://github.com/beir-cellar/beir) |    5,183 |       300 | Scientific claims with human relevance judgements over paper abstracts (BEIR test split)   |

The keyword searcher, the hybrid ranker and the merge-filter-rank step are imported from
`sentio.rag`; `hybrid` below is the tutor's path with its real settings (20 candidates from
each retriever, similarity floor 0.35, relevance gate, 0.75/0.25 weighted sum). The vector
store is the one stand-in: embeddings are scored with an exact dot product in place of
Qdrant. Scores are nDCG@10 with 95% bootstrap intervals over questions; p-values are paired
bootstrap tests against `hybrid` on the same questions.

## Results

| Embedding model     | Method                     |         SciQ nDCG@10 |    p |      SciFact nDCG@10 |    p |
| ------------------- | -------------------------- | -------------------: | ---: | -------------------: | ---: |
| none                | keyword (BM25)             | 0.837 [0.818, 0.854] | .000 | 0.645 [0.596, 0.692] | .002 |
| `all-MiniLM-L6-v2`  | dense                      | 0.656 [0.632, 0.679] | .000 | 0.645 [0.598, 0.691] | .000 |
| `all-MiniLM-L6-v2`  | **hybrid (the tutor)**     | 0.778 [0.757, 0.800] |    — | 0.692 [0.646, 0.738] |    — |
| `all-MiniLM-L6-v2`  | hybrid, floor and gate off | 0.778 [0.757, 0.800] | 1.00 | 0.690 [0.643, 0.736] |  .63 |
| `all-MiniLM-L6-v2`  | rank fusion                | 0.786 [0.766, 0.806] |  .14 | 0.677 [0.630, 0.722] |  .12 |
| `e5-small-v2`       | dense                      | 0.775 [0.753, 0.796] |  .63 | 0.687 [0.642, 0.730] |  .76 |
| `e5-small-v2`       | rank fusion                | 0.827 [0.808, 0.845] | .000 | 0.696 [0.651, 0.739] |  .77 |
| `bge-small-en-v1.5` | dense                      | 0.760 [0.738, 0.781] |  .02 | 0.713 [0.669, 0.756] |  .14 |
| `bge-small-en-v1.5` | rank fusion                | 0.823 [0.803, 0.841] | .000 | 0.693 [0.648, 0.736] |  .97 |

Check on the harness itself: SciFact is a standard benchmark with published reference
scores. Dense search with `all-MiniLM-L6-v2` scores 0.645 here and Sentio's BM25 scores
0.645; the published figures are about 0.645 for that model and 0.665 for BEIR's Lucene
BM25, so the harness is not inflating results.

## What it shows

1. **The tutor's hybrid is not uniformly better than keyword search.** On SciQ it is
   worse than BM25 alone (0.778 against 0.837, p < 0.001). On SciFact it is better (0.692
   against 0.645, p = 0.002). Short questions that reuse the passage's words favour
   keywords; claims paraphrasing an abstract favour embeddings.
2. **The embedding model costs more than the fusion method.** With `all-MiniLM-L6-v2`,
   dense search is the weakest method on SciQ and drags the hybrid down. Rank fusion with
   `e5-small-v2` or `bge-small-en-v1.5`, both the same 384 dimensions, is within the
   interval of the best method on both datasets. No other configuration tested is.
3. **The 0.35 similarity floor does not change ranking here.** Switching the floor and
   the relevance gate off gives the same scores, because keyword search re-admits the
   affected passages. With `all-MiniLM-L6-v2` the gold passage scores under the floor for
   2.5% of SciQ questions and 10.3% of SciFact questions.
4. **A similarity floor is specific to its model.** Gold passages score 0.28 to 0.78 with
   `all-MiniLM-L6-v2` (5th to 95th percentile, SciFact) but 0.81 to 0.91 with
   `e5-small-v2`, where a floor of 0.35 removes nothing. Changing the model means choosing
   the floor again.
5. **Rebuilding the keyword index per question dominates search time.**
   `KnowledgeBase.retrieve` rebuilds it on every question. Building took 443 ms for the
   SciQ passages and 555 ms for SciFact's longer ones, against a median 15 to 42 ms for
   the keyword search itself.

## What it does not show

- Neither dataset is lecture slides or student notes, and every question has an answer in
  the corpus, so nothing here measures refusal of unanswerable questions.
- Passages are indexed whole. Sentio's 500-character chunking is not exercised.
- One run on one laptop while other work used the CPU; timings are indicative only.
- The tutor's settings have not been changed. The evidence supports trying rank fusion
  with a newer small embedding model, which also means re-indexing existing notes and
  re-choosing the floor; that change needs its own before-and-after run on course material.

## Reproduce

The datasets are licensed CC BY-NC (SciQ 3.0, SciFact 2.0) and are not redistributed here.
Download them into a git-ignored folder, then run each dataset. The embedding models must
already be in the local Hugging Face cache.

```sh
mkdir -p tmp/public-data && cd tmp/public-data
curl -LO https://ai2-public-datasets.s3.amazonaws.com/sciq/SciQ.zip
curl -LO https://public.ukp.informatik.tu-darmstadt.de/thakur/BEIR/datasets/scifact.zip
unzip SciQ.zip && mv "SciQ dataset-2 3" sciq && unzip scifact.zip && cd ../..
uv run python scripts/eval/evaluate_public_retrieval.py --dataset sciq --data tmp/public-data \
  --models all-MiniLM-L6-v2 intfloat/e5-small-v2 BAAI/bge-small-en-v1.5 --output reports/new-sciq.json
```

Raw results: [SciQ](../../reports/retrieval-public-sciq-2026-11-14.json),
[SciFact](../../reports/retrieval-public-scifact-2026-11-14.json).
