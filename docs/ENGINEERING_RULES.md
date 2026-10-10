# Sentio Engineering Rules & Standards

This document establishes the mandatory engineering rules, coding standards, and repository practices for the Sentio project. All future development, refactoring, and feature additions must comply with these guidelines.

---

## 1. Engineering Philosophy

Sentio adopts the **"Lazy, Not Negligent"** engineering philosophy, heavily inspired by the Ponytail decision ladder. We believe that **the best code is the code that never had to be written**. Every line of code introduced is a potential bug, a testing requirement, and a maintenance liability.

However, being "lazy" must never mean being negligent. Security controls, input validations, error boundaries, data integrity, and accessibility are absolute requirements that must never be compromised or deferred.

---

## 2. Repository & Folder Rules

- **Strict Structural Organization**: The repository must separate source files (`src/`), tests (`tests/`), data storage (`data/`), and developer utilities (`scripts/`).
- **File Size Constraint**: Code files must not exceed **500 lines**. Modules exceeding this limit must be split.
- **Function Complexity**: Functions must be single-purpose and not exceed **50 lines** of executable code.
- **Nesting Constraint**: Logic nesting (if/for/while) must not exceed **3 levels**. Prefer early exits and guard clauses.
- **Strict Layer Boundaries**: Dependency flow must remain unidirectional downward:
  $$\text{API} \longrightarrow \text{Pedagogical Coordination} \longrightarrow \text{Domain Services} \longrightarrow \text{Persistence}$$
  Lower layers must never import or query higher layers.

---

## 3. Coding Standards & The Decision Ladder

Before writing any new code, every developer and AI agent must climb the **Decision Ladder**, stopping at the first rung that holds:

1. **YAGNI (You Ain't Gonna Need It)**: Does this feature need to exist at all to satisfy the PRD? If not, do not write it.
2. **Codebase Reuse**: Can this be solved using an existing function or database query in the project? (e.g. check `SessionManager` or repository helper classes).
3. **Standard Library Priority**: Can this be solved using Python's standard library (e.g. `math`, `hashlib`, `json`)?
4. **Native Platform Features**: Can this be solved using native web features (e.g. native browser voice recognition instead of external APIs)?
5. **Existing Dependencies**: Can currently installed dependencies (e.g. `Pillow`, `Qdrant`, `SQLAlchemy`) solve the problem?
6. **Write the Minimum Code**: Only when all prior rungs fail, write the minimum, simplest code necessary to satisfy the requirement.

---

## 4. Dependency Rules

- **Zero-Dependency Bias**: Do not add packages to `requirements.txt` unless the standard library or existing dependencies are insufficient.
- **Dependency Audit**: Any new package must be justified by writing a technical note in the PR documenting its licensing, CPU footprint, memory overhead, and security profile.
- **Dev-Prod Separation**: Testing and development tools (e.g. `pytest`, `flake8`) must be isolated in a `requirements-dev.txt` file and never included in production builds.

---

## 5. AI Engineering Rules

- **Centralized Prompt Builder**: All system instructions, user templates, and grounding directives must be centralized in [prompts.py](file:///C:/ai%20project/Sentio-An-Emotion-Aware-Tutor/Sentio-An-Emotion-Aware-Tutor/sentio/ai/prompts.py) and never hardcoded in model calls.
- **Configurable LLM Models**: Model names (e.g. `phi3:mini`) and API endpoints must never be hardcoded in backend services. They must load dynamically from environment variables (`OLLAMA_MODEL`, `DATABASE_URL`).
- **Decoupled Business Logic**: Subsystem services (quizzes, whiteboard rendering, flashcards) must operate independently of the selected LLM provider.

---

## 6. Frontend Rules

- **Decoupled State & Presentation**: Separate API communications and state handlers from visual render logic.
- **Modular Tab HUD**: Re-architect the client UI as a unified single-page application with modular, toggleable tab panels for separate learning tools.
- **No Duplicate API Queries**: Cache profile updates and recommendations locally in browser memory rather than making repeated REST calls.

---

## 7. Backend Rules

- **Clean Route Handlers**: API endpoints in [app.py](file:///C:/ai%20project/Sentio-An-Emotion-Aware-Tutor/Sentio-An-Emotion-Aware-Tutor/sentio/api/app.py) must serve only as gateways, validating inputs and serialization. They must not contain tutoring logic or mathematical calculations.
- **Isolated Persistence**: All database query operations must be encapsulated in repository classes (`AuthRepository`, `SessionPersister`) and never written inline in API routes or business services.

---

## 8. Testing Rules

- **Defect Regression Coverage**: Every bug fix must include a test demonstrating the original failure and validating that the fix resolves it.
- **Automated Commit Gate**: Code merges to `main` are blocked unless all 67 baseline unit and integration tests compile and pass successfully.

---

## 9. Refactoring Rules

- **Incremental Migration**: Refactoring must proceed phase-by-phase (e.g. clean folders first, then adjust imports, then update configs). Do not modify multiple unrelated modules at once.
- **Git Checkpoints**: Commit changes at the end of each refactoring milestone, ensuring tests pass before moving to the next.

---

## 10. Documentation Rules

- **Synchronization**: Code modifications must be accompanied by corresponding updates to the README or API specs in the same commit.
- **Document Hierarchy**: The authoritative document hierarchy is established as follows:
  1. `docs/PRD.md` (Highest priority specification)
  2. `docs/ENGINEERING_RULES.md` (This document; mandatory engineering standards)
  3. `docs/ENGINEERING.md` (Code architecture rules)
  4. `docs/REPOSITORY_PLAN.md` (Refactoring roadmap)
  5. `README.md` (Quick-start guides)
  6. `CHANGELOG.md` (Release log)

---

## 11. Performance Rules

- **Continuous Benchmarking**: Measure execution speeds before and after introducing new database writes, vector searches, or models.
- **Target SLA Budgets**:
  - RAG Retrieval & Fusion: $< 300\text{ ms}$
  - LLM Token Generation: $< 3000\text{ ms}$
  - Visual Whiteboard Render: $< 50\text{ ms}$

---

## 12. Security Rules

- **Safe Configuration Defaults**: Set `ENFORCE_AUTH=True` by default. Access tokens must be validated in all production API requests.
- **Centralized Secrets**: API keys and databases must load from `.env` configurations; hardcoded keys in the repository are strictly forbidden.
- **Input Sanitization**: Run all student chat inputs through input sanitizers to block prompt injection and cross-site scripting (XSS) vectors.
- **Pruned Memory rate limiter**: rate limiter maps must be cleaned or stored in a TTL-enabled cache to prevent memory exhaustion attacks.

---

## 13. Repository Evolution Rules

- **PRD Validation Check**: Before writing code for a new feature, verify that the task directly aligns with a requirement in [docs/PRD.md](file:///C:/ai%20project/Sentio-An-Emotion-Aware-Tutor/Sentio-An-Emotion-Aware-Tutor/docs/PRD.md).
- **Maintain Architectural Boundaries**: Never bypass the unidirectional downward dependency flow for development convenience.
