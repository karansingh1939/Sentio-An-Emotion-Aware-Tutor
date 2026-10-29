# Contributing to Sentio

Start with the [README](README.md), [setup guide](docs/guides/SETUP.md), and [architecture](docs/architecture/ARCHITECTURE.md). Check the [release handoff](docs/archive/RELEASE_HANDOFF.md) for unfinished capabilities before expanding scope.

## Development workflow

1. Create a short-lived branch for one change.
2. Add a regression test when changing behavior or fixing a bug.
3. Run the relevant checks below; keep existing quality gates intact.
4. Open a pull request describing the problem, resulting behavior, and verification.

Use descriptive commits such as `fix: prevent duplicate review submissions`. Separate refactors from behavior changes. Update public interfaces, setup instructions, or evaluation methodology in the same change that alters them.

## Checks

```sh
uv sync --locked
uv run playwright install chromium
npm ci
uv run ruff check src scripts tests
uv run ruff format --check src scripts tests
npm run format:check
npm test
uv run python scripts/dev/run_tests.py -q
uv build
```

CI additionally installs the OCR extra and Tesseract, runs live synthetic OCR evaluation, and builds the Docker image. Deterministic provider fixtures test software behavior; they do not measure model accuracy. Run the documented live evaluation separately when altering generation, retrieval, or grading.

## Data and evaluation rules

- Never commit learner uploads, accounts, databases, logs, secrets, backups, model caches, or weights.
- Use synthetic or explicitly authorized fixtures. Keep ownership and isolation checks.
- Preserve failed experiment outputs. Record dataset/model versions, hardware, commands, and limitations with measured results.
- Keep exact-answer checks separate from semantic grading measurements. Do not invent accuracy or learning improvements.
- Retain upstream license and attribution. Explain repository contributions separately from reused models and libraries.

Report ordinary bugs through the repository issue template, with sanitized reproduction steps. Report security concerns privately using [SECURITY.md](SECURITY.md).
