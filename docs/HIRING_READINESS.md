# Hiring-readiness remediation

## Completion pass - 14 October 2026

The supported local-app hiring-readiness scope has implementation and automated
verification. This is not completion of every feature in the wider study-overhaul
roadmap or a validated AI teaching release. The 12 October hosted run passed both
Linux tests and actual Compose startup, authenticated storage, restart and outage
checks. The completion pass also fixes closed session dialogs activating late
responses and closes the unused session; a real Chromium regression covers this.

Prepared cached CPU features for all 1,584 evidence pairs and two local review
pages. No completed human receipts have been supplied. Training, calibration and
adoption remain gated on actual labels and measured quality. Remaining human
actions are in [the handoff](HUMAN_HANDOFF.md).

The repository addresses the engineering and presentation gaps identified during portfolio review. This ledger distinguishes completed changes from evidence that requires actual reviewers or students.

| Finding                                     | Work completed                                                                                                                                     | Remaining evidence                                                                                                                              |
| ------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| Personal contribution unclear               | Prominent README contribution summary and commit/test [contribution map](CONTRIBUTIONS.md); original attribution retained                          | The author must be able to explain and demonstrate these changes in an interview                                                                |
| Emotion/ML identity exceeds validated scope | Package describes the study workspace; normal prompts and UI avoid camera-accuracy claims; experiments remain explicitly separate                  | Reviewed labels and any trained/calibrated evidence-model result; emotion accuracy is not claimed                                               |
| AI answer/grading reliability               | User-data prompt boundaries, exact reference strings, deterministic numeric grading, clear result modes, and 12 real HTTP stress-test observations | [Recorded refusals and ambiguity failures](STUDY_QUALITY_2026-10-12.md), author semantic review, independent labels, wider/repeated evaluations |
| Docker/recovery unverified                  | Compose health checks, loopback binding, image/CLI checks, and isolated live-container startup/auth/restart/provider-outage smoke test in CI       | Full Compose tutoring with installed model, inference/resource measurements, and wider load tests                                               |
| No demonstrated student benefit             | [Author review packet and pilot protocol](AUTHOR_REVIEW.md) prepared for the owner                                                                 | Actual self-review, uncoached student trials, independent answer review, and a separate learning study                                          |

Use this ledger with the latest GitHub Actions result. A configured test is not a passed test until that run succeeds. Do not replace missing human evidence with AI-generated reviewers, annotations, user counts, or testimonials.
