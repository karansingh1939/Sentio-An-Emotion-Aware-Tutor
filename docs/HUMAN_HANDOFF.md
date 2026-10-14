# Human-only handoff

The agent has implemented and checked the supported local portfolio scope and
prepared the review material. The agent can handle import, training, analysis,
and repairs when actual feedback is available. The wider feature roadmap remains
separate from this hiring-readiness pass. Do not claim independent validation,
trained-model gains, or student learning benefits before measuring them.

## 1. Review actual answers

Open `reports/evidence/review-study-2026-10-14.html`. Enter your reviewer ID,
read the original question, actual model reply and full notes, then accept,
reject or skip with a reason. There are 12 replies. Download the JSON when done.
These are author judgments; they do not replace independent review.

## 2. Label evidence if you want the classifier trained

Open `reports/evidence/review-evidence-2026-10-14.html`. The review page hides
proposed labels. Label a passage as sufficient only when it alone answers the
whole question; explain the supporting sentence or missing information. Work
in batches and skip uncertain cases. Download your JSON to preserve progress.

The frozen corpus has 1,584 question/passage pairs across training, validation,
and test groups. Completing only the 12 answer reviews does not label this
corpus. Training currently requires complete reviewed coverage. The agent can
run the training/calibration/baseline pipeline after actual receipts are supplied,
and report failed results if the model does not meet the adoption gate.

CPU features are already prepared in the ignored local file
`datasets/evidence_v1/features-cpu-2026-10-14.json`; no model download is needed
to start review. Review files and annotations remain private by default.

## 3. Get real people to try it

Ask students to complete the six tasks in [the pilot protocol](AUTHOR_REVIEW.md)
without coaching. Record completion times, confusion, mistakes and help needed,
using participant IDs and disposable notes. Ask another knowledgeable reviewer
to independently check the answers before seeing your decisions. The agent can
prepare forms and analyze results, but cannot create actual participants or
independent human judgments.

You must also be able to explain your own contributions during interviews.
Use [the contribution map](CONTRIBUTIONS.md) to choose one failure/fix/test to
demonstrate. An automated demo proves workflow mechanics, not your understanding
or student learning.
