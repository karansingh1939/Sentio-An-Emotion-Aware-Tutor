# Sentio engineering contract

## Product and boundaries

Follow docs/project/PRD.md and docs/project/tasks/plan.md. Keep the local CPU-compatible study journey
working at each checkpoint. API → coordinator → services → repositories.
SQL belongs in repositories. Prefer existing helpers, stdlib and installed
packages; justify additions. Split modules by responsibility, not arbitrary size.

## Reliability and privacy

Preserve learner data. Snapshot and verify restore before migrations. Migrations
are versioned and transactional. Ownership comes from authenticated identity.
Validate inputs, file paths, output schemas and citation identities. Keep secrets,
learner files, model caches, backups and logs out of Git. No remote publishing.
Bound background work and retention. Errors are actionable and distinguish missing
data from unavailable services. Cancellation never claims completed learning.
Camera is experimental, explicit opt-in, lazy-loaded and stopped on revocation.

## AI and experiments

Centralize prompts. Models and endpoints are configured, not hardcoded in services.
Separate fixture tests from live generation/quality measurements. Freeze test
splits; tune only on development data. Record provenance, hashes, configurations,
actual metrics and failures. AI-drafted labels are not reviewed ground truth.
No unmeasured accuracy claims. Retrieval target remains <300ms; measure first
visible answer and full generation separately rather than promise 3s CPU answers.
Adopt changes only through the approved comparison gate.

## Frontend

Shared session/source context; separate state, API and rendering. Accessible
controls, keyboard focus, safe text rendering, light/dark themes, responsive layouts.
Essential studying works offline after dependencies/models are installed.
No external CDN dependence on core paths. Optional tools load on demand.

## Workflow

Use feature branches and small verified checkpoints. Update task records and
continuation after each milestone. Add meaningful regressions before behavior
changes. Existing tests must not be disabled to get green.
Commands: uv sync --locked; npm ci; npm test; uv run python scripts/dev/run_tests.py -q;
uv run ruff check src scripts tests; uv run ruff format --check src scripts tests;
npm run format:check; uv lock --check; uv build.
Use pyproject.toml/uv.lock and package.json/package-lock.json, not requirements files.
Browser-check important journeys at 390/768/desktop in both themes. Record skipped
optional live checks honestly. Document changed interfaces and recovery commands.
