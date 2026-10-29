# Contribution map

This project is maintained by Karan Singh with AI-assisted implementation and corpus drafting. The baseline reuses the original Sentio project; a baseline snapshot is not new authorship of inherited code. The MIT license and upstream credit remain intact.

The following incremental commits make the current engineering contribution reviewable. Each link opens a concrete change, rather than relying on the repository's total line count.

| Contribution                                         | Change                                                                                      | Verification entry points                                        |
| ---------------------------------------------------- | ------------------------------------------------------------------------------------------- | ---------------------------------------------------------------- |
| Local recovery and capability readiness              | [58dc5079](https://github.com/karansingh1939/Sentio-An-Emotion-Aware-Tutor/commit/58dc5079) | `tests/unit/test_local_backup.py`, `tests/integration/test_readiness.py`          |
| Accessible study workspace                           | [54f80442](https://github.com/karansingh1939/Sentio-An-Emotion-Aware-Tutor/commit/54f80442) | `tests/browser/test_workspace_browser.py`                                |
| Durable jobs and cancellable tutor streams           | [1c3ba979](https://github.com/karansingh1939/Sentio-An-Emotion-Aware-Tutor/commit/1c3ba979) | `tests/integration/test_jobs.py`, `tests/integration/test_streaming_turns.py`            |
| Interrupted document publication recovery            | [0b8043cd](https://github.com/karansingh1939/Sentio-An-Emotion-Aware-Tutor/commit/0b8043cd) | `tests/unit/test_document_recovery.py`                                |
| Atomic review receipts and saved practice            | [6b2c9d3c](https://github.com/karansingh1939/Sentio-An-Emotion-Aware-Tutor/commit/6b2c9d3c) | `tests/integration/test_review_receipt.py`, `tests/integration/test_saved_practice.py`   |
| Frozen evidence corpus and experiment/review tooling | [df414a85](https://github.com/karansingh1939/Sentio-An-Emotion-Aware-Tutor/commit/df414a85) | `tests/unit/test_evidence_dataset.py`, `tests/unit/test_evidence_model.py` |
| Standard JWTs and single-use local recovery          | [2e8bad47](https://github.com/karansingh1939/Sentio-An-Emotion-Aware-Tutor/commit/2e8bad47) | `tests/integration/test_password_recovery.py`                                |
| Reproducible package and Docker build checks         | [b2763afc](https://github.com/karansingh1939/Sentio-An-Emotion-Aware-Tutor/commit/b2763afc) | `.github/workflows/ci.yml`                                       |

FastAPI, SQLite, Qdrant, Sentence Transformers, Ollama, pretrained generation/embedding models, scikit-learn, and Playwright are upstream components. No full LLM training or validated emotion model is claimed. The proposed evidence classifier is an offline experiment awaiting reviewed labels.

For an interview, demonstrate one failure, explain the transaction or ownership boundary that prevents it, run its regression, and show the corresponding commit. Use the [development record](DEVELOPMENT_LOG.md) and [architecture](../architecture/ARCHITECTURE.md) for context.
