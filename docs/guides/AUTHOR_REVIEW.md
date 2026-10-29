# Author review and student pilot

Status: prepared, not completed. The owner can review the app personally first. This is author review, not independent ground truth or a student learning study. No participant count or learning improvement is claimed.

## Review 12 actual tutor replies

The synthetic grounding dataset is separate from classifier training material. The recorded replies come from the real authenticated HTTP study pipeline with an installed local model. Automatic lexical checks are diagnostics; you decide whether each reply is supported and whether an abstention is justified.

```sh
uv run python scripts/eval/prepare_study_review.py --dataset tests/fixtures/study_grounding_v1.json --report reports/generation/study-grounding-2026-10-12-v4.json --output reports/evidence/review-study-author.html
```

Open the generated HTML locally. Enter your reviewer name. For each reply, read the full source and question, then:

1. **Accept reply** only if it addresses the question without unsupported added facts. Accept abstention only when the notes genuinely lack the answer.
2. **Reject reply** for invented facts, incorrect values, unjustified refusal, or a guessed ambiguous referent.
3. **Unsure** skips a decision and creates no label.
4. Explain the supporting sentence or exact problem. Download your labels when finished; keep the export private.

The packet contains no proposed labels. Its receipts are tied to these exact source/reply texts and are separate from the evidence-classifier annotations. Completing these 12 decisions does not make the classifier's 1,584 pairs reviewed or authorize training/adoption.

## Try the workflow without developer guidance

Use an account with disposable notes. Measure elapsed time with a stopwatch, and record the first confusing step rather than explaining it away. Keep account credentials and uploaded personal material out of reports.

| Task                                    | Success criterion                                         | Record                               |
| --------------------------------------- | --------------------------------------------------------- | ------------------------------------ |
| Register and upload readable notes      | Library shows the saved source                            | Time, assistance needed, confusion   |
| Start studying that source              | Tutor shows the selected source                           | Time, wrong-source incidents         |
| Ask an answerable question              | Reply is supported by the notes                           | Supporting sentence, errors/refusals |
| Ask for a measurement absent from notes | No measurement is invented                                | Exact reply and interpretation       |
| Generate three quiz items/cards         | Requested count appears and source/fallback mode is clear | Time, incorrect items                |
| Review a card and restart the app       | Saved review and study work remain                        | Lost/duplicated work                 |

Record participant IDs rather than names. For an initial self-review, use `author-01` and mark reviewer relationship as `project author`. Report raw times, failed tasks, help required, and the changes made afterward. A single successful run establishes workflow mechanics only.

## Later independent validation

Recruit students with their consent, using non-private notes. Ask them to complete the same tasks without coaching. Have another reviewer independently judge the same replies before seeing author decisions, retain disagreements, and report agreement. Only a separate pre/post study with an appropriate comparison can support a learning-effectiveness claim.
