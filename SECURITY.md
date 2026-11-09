# Security policy

## Supported scope

Security work targets the current `main` branch. Sentio is a local application under active development, not a reviewed public hosting service. There is no guaranteed response time or support promise for older snapshots.

## Reporting a vulnerability

Use the repository's **Security > Report a vulnerability** option if enabled. If unavailable, contact the maintainer through a private channel already available to you and request a secure reporting channel before sending exploit details. Do not post vulnerabilities, credentials, learner data, or private logs in public issues.

Include the affected commit, a minimal sanitized reproduction, expected versus actual behavior, and potential impact. Share only the data needed to reproduce the problem.

## Operating boundaries

- Keep the application on a trusted local machine/network. Public deployment needs HTTPS, session/token handling, dependency, upload, and storage review.
- Browser bearer tokens currently use local storage. Use a random signing secret for production configurations and keep runtime data/backups private.
- Run one process per persistent home. Stop the application before a full backup; restore into an empty directory.
- Uploaded documents and student answers are untrusted inputs. Citation validation is not proof of answer correctness or prompt-injection resistance.
- Do not use semantic grades for high-stakes decisions. Known false positives and false negatives are recorded in the evaluation reports.
- Camera features are excluded from the supported study interface pending consent, resource-boundary, and physical-device privacy checks.

