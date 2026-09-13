# AGENTS.md — BYOD

## Mission

Build **BYOD — Bring Your Own Documents**, a local-first reading and study assistant.

Users add course documents once. BYOD parses, chunks, embeds, and stores them locally, then answers questions and generates review material grounded in those documents using an LLM provider selected by the user.

The authoritative product and architecture specification is:

`docs/BYOD_SPEC.md`

Read it before making architectural, dependency, data-model, ingestion, retrieval, provider, security, or UI decisions.

---

## Operating mode

Work autonomously within the requested scope.

### Agent progress memory

Read `AGENT_MEMORY.md` before starting or resuming work. After every work loop
(inspection, implementation, verification, or blocker investigation), append a
dated entry recording the scope, changes, checks actually run and their results,
blockers, and the next concrete step. Record blocked and failed loops too.
Update the current status so another agent can resume without repeating work.
Never record secrets, document text, prompts, or retrieved context in this file.
Memory is a progress record; it does not override this file or `docs/BYOD_SPEC.md`.

For non-trivial tasks:

1. Inspect the relevant existing code first.
2. Identify the layer being changed.
3. State a concise implementation plan.
4. Implement the change.
5. Run the relevant layer gate.
6. Run regression checks.
7. Fix failures caused by your changes.
8. Review the diff for scope creep and security violations.
9. Report what changed and what was verified.

Do not stop merely to ask whether you should continue with obvious implementation steps.

Stop and report the blocker only when:

- the requested task conflicts with a hard constraint;
- proceeding would require an architectural decision not covered by the specification;
- required credentials, files, services, or dependencies are unavailable;
- multiple materially different approaches exist and the choice would significantly alter the architecture.

Do not silently substitute a different architecture when blocked.

---

## Hard constraints

These are non-negotiable.

- BYOD runs entirely on the user's machine.
- No hosted backend.
- No telemetry or analytics.
- No account system.
- No cloud database.
- Runtime network calls are limited to the configured LLM provider, plus the one-time local embedding-model download.
- Embeddings are always generated locally.
- Never call a provider embedding endpoint.
- API keys are stored only through the OS keychain.
- Never store API keys in SQLite, config files, logs, browser storage, or frontend state.
- Never return an API key to the frontend after it has been configured.
- Documents and extracted document text remain local except for retrieved context explicitly sent to the configured LLM provider for a user request.
- Never log document text, prompts, retrieved context, or secrets.
- No greeting messages.
- No onboarding wizard.
- No suggested-prompt chips.

If a requested implementation violates one of these constraints, do not implement it.

---

## Explicit non-goals

Do not add these unless the user explicitly changes scope:

- multi-user support;
- authentication;
- sharing or synchronization;
- Electron or Tauri packaging;
- Docker as the primary execution path;
- autonomous agents or multi-step planning inside BYOD itself;
- provider/model marketplace functionality;
- provider auto-discovery beyond specified behavior;
- full mobile redesign;
- OCR in v1.

Do not interpret an interesting adjacent feature as permission to build it.

---

## Required stack

### Backend

- Python 3.11+
- FastAPI
- SQLite through Python `sqlite3`

### Frontend

- TypeScript
- React
- Vite
- Tailwind CSS
- CSS variables for design tokens

### Retrieval

- `sqlite-vec`
- ONNX Runtime
- local embedding model

### Documents

- PDF: PyMuPDF
- DOCX: python-docx
- PPTX: python-pptx

### Development / packaging

- `uv`
- PyInstaller later

Do not add a default dependency unless existing dependencies or the standard library cannot reasonably provide the required functionality.

Document the justification for every new dependency.

Heavy optional functionality such as OCR or Docling must remain optional.

---

## Architecture

Maintain one Python application process.

FastAPI serves:

- the JSON API;
- the compiled React application.

Expected structure:

```text
byod/
  cli.py
  app.py
  config.py

  ingest/
    parsers/
      pdf.py
      docx.py
      pptx.py
    normalize.py
    chunk.py
    jobs.py

  index/
    embed.py
    store.py

  retrieve/
    search.py

  llm/
    base.py
    providers/
      anthropic.py
      openai.py
      ollama.py
    keys.py

  db/
    schema.sql
    migrations.py
    queries.py

  api/
    workspaces.py
    documents.py
    chat.py
    settings.py

  ui/
```

Do not reorganize this architecture without a clear reason and explicit approval when the change is material.

---

## Critical architecture invariant

Everything above `ingest/normalize.py` operates on the normalized `Block` model.

Code in:

- `retrieve/`
- `index/`
- `llm/`
- `api/`

must never:

- import document parsers;
- inspect file extensions;
- contain PDF/DOCX/PPTX-specific retrieval logic.

Adding a new document format should require:

1. a parser;
2. a chunking rule;

and should not require changes throughout the application.

---

## Ingestion

Never parse or embed documents inside an HTTP request handler.

Ingestion runs through the background job queue.

The request path should:

1. accept the operation;
2. enqueue the ingest job;
3. return a job ID;
4. allow the frontend to poll status.

### Idempotency

Hash file contents when documents are added.

If the same content hash already exists in the same workspace, skip duplicate ingestion.

Re-adding a directory must be safe.

Re-indexing must be safe to run repeatedly.

### Embedding versions

Persist embedding model name and version with indexed documents.

Never allow vectors produced by incompatible embedding models to coexist silently in the same logical index.

If the configured model changes, surface that re-indexing is required.

---

## Parsing rules

### PPTX

- Parse natively with `python-pptx`.
- Never convert PPTX to PDF.
- Preserve speaker notes.
- Sort shapes by `(top, left)` before concatenating their text.

### PDF

Use heading-aware structural extraction where possible.

### DOCX

Preserve heading hierarchy.

Parser output must normalize into the shared `Block` representation.

---

## Chunking

### PPTX

One chunk per slide.

Include:

- deck title;
- slide title;
- body;
- speaker notes under `Speaker notes:`.

### PDF

Target roughly:

- 600 tokens;
- 15% overlap.

Preserve heading paths.

Never split a table.

### DOCX

Split first by heading structure and then by token budget.

Prefix the heading path.

### All formats

Drop chunks containing fewer than 20 tokens.

---

## Retrieval

Retrieval order:

1. filter by `workspace_id`;
2. apply `document_id` or `doc_type` filters when specified;
3. perform vector search;
4. retrieve approximately the top 20 candidates;
5. assemble context with filename and locator metadata.

Retrieval results supplied to the model must make citations possible.

The answering prompt must require citations formatted as:

```text
[filename, locator]
```

If the retrieved documents do not support an answer, the model should say so rather than inventing one.

---

## LLM providers

All providers implement the common `LLMProvider` interface.

Required initial providers:

- OpenAI;
- Anthropic;
- Ollama.

Provider choice affects reasoning only.

Provider choice must never affect embedding generation.

Ollama may be detected through:

```text
localhost:11434
```

Store API keys through `keyring`.

When saving a key:

1. validate it with a minimal provider request;
2. store it in the OS keychain;
3. return only configuration status.

Never return the key itself.

---

## Data ownership

SQLite is the persistent source of truth for:

- workspaces;
- documents;
- chunks;
- chats;
- messages;
- citations.

Do not store chat history in:

- `localStorage`;
- IndexedDB;
- another browser persistence mechanism.

Citations should reference persisted chunks so the UI can navigate back to the originating page or slide.

---

## UI rules

The application is a dark reading interface.

Purple is an accent, not body-copy color.

Follow the design tokens and layout defined in `docs/BYOD_SPEC.md`.

### Voice

Do not add:

- greetings;
- assistant introductions;
- onboarding copy;
- motivational empty states;
- suggested prompts.

Empty chat state should show only the workspace context specified by the design.

Use direct UI copy.

Prefer:

```text
Add documents
```

over:

```text
Submit
```

Errors must describe:

1. what failed;
2. what the user can do.

Example:

```text
Couldn't reach Anthropic. Check your key in Settings.
```

Do not use apology language in product UI.

### Accessibility

Every interactive control requires visible keyboard focus.

Respect `prefers-reduced-motion`.

Streaming output must not cause disruptive layout reflow.

Citations must be keyboard reachable.

---

## Development workflow

Before editing:

1. read `docs/BYOD_SPEC.md`;
2. inspect relevant existing implementation;
3. inspect tests for the affected layer;
4. check for more-specific nested `AGENTS.md` instructions.

Prefer modifying existing abstractions over creating parallel implementations.

Use repository search before assuming functionality does not exist.

Keep changes tightly scoped to the requested task.

Do not perform opportunistic refactors unless they are required to implement the requested change safely.

---

## Layer boundaries

Work one layer at a time whenever practical.

Do not implement downstream functionality on top of an unverified upstream layer.

Expected sequence:

```text
DB
↓
parsers
↓
normalization
↓
chunking
↓
embeddings
↓
vector store
↓
retrieval
↓
providers
↓
API
↓
UI
```

---

## Verification gates

A layer is not complete until its gate passes.

### Parsers

```bash
byod debug parse <file>
```

Verify against:

- one real PDF;
- one real DOCX;
- one real PPTX.

PPTX output must contain speaker notes.

### Chunker

```bash
byod debug chunk <file>
```

Verify:

- locators exist;
- token counts are visible;
- no chunk is under 20 tokens;
- no chunk exceeds the configured budget.

### Embeddings

```bash
byod debug embed "text"
```

Verify:

- expected dimensions;
- valid vector norm.

### Vector store

```bash
byod debug search <workspace> "query"
```

Verify top-k results contain:

- scores;
- locators.

### Retrieval

Use the search command and verify metadata filters reduce the candidate set appropriately.

### Providers

```bash
byod debug llm --provider <provider>
```

Verify a one-line completion streams successfully.

### API

```bash
pytest
```

Routes require happy-path and error-path coverage.

### UI

The frontend must:

- build cleanly;
- have no TypeScript errors;
- have no new console errors;
- remain keyboard navigable.

---

## Definition of done

Before declaring a task complete, run all checks relevant to the files changed.

At minimum:

```bash
pytest
ruff check .
mypy .
```

For frontend changes, also run the project's frontend build and type-check commands.

Completion requires:

- relevant layer gate passes;
- applicable tests pass;
- Ruff passes on changed Python code;
- mypy passes on changed Python code;
- TypeScript compilation succeeds for frontend changes;
- no unsupported dependency was introduced;
- no sensitive information appears in logs;
- no architecture invariant was violated.

If the full suite cannot run because of an environmental limitation, run the largest valid subset and explicitly report what could not be verified.

Do not claim a check passed unless you ran it.

---

## Testing policy

Fixture documents belong in:

```text
tests/fixtures/
```

Maintain:

- a real three-page PDF;
- a five-slide PPTX with notes on at least two slides;
- a DOCX containing nested headings.

Parser and chunker tests should assert structural properties rather than exact extracted prose.

Never mock document parsers.

Mock only the LLM provider when appropriate.

Every bug fix should begin with or include a regression test that reproduces the failure.

---

## Forbidden implementations

Reject changes that introduce any of the following unless the product specification is intentionally changed:

- cloud embeddings;
- chat history in browser storage;
- PPTX-to-PDF conversion;
- a separate vector database server;
- greeting messages;
- onboarding modals;
- suggested-prompt chips;
- purple paragraph/body text;
- document parsing inside request handlers;
- embeddings inside request handlers;
- logging documents, prompts, retrieved context, or API keys;
- file-extension-specific logic above the ingestion layer.

---

## Build order

For greenfield implementation, follow this order:

1. Skeleton + database
2. Ingest
3. Index
4. Retrieval
5. Providers
6. API
7. UI

Do not start milestone N+1 until the gate for milestone N succeeds.

For an existing repository, do not rebuild completed milestones. Inspect their implementation and tests, then work only on the requested scope.

---

## Codex completion report

At the end of a coding task, provide a concise report containing:

### Changed

- files modified;
- major behavior added or corrected.

### Verified

- tests run;
- linters/type checks run;
- layer-specific gate run.

### Remaining

Only include this section when there are:

- known failures;
- environmental limitations;
- deliberate follow-up work;
- unresolved architecture questions.

Do not list speculative enhancements.

---

## Priority order

When instructions conflict, use this order:

1. user's current explicit task;
2. hard constraints in this file;
3. `docs/BYOD_SPEC.md`;
4. more-specific nested `AGENTS.md` instructions for implementation details;
5. existing code conventions;
6. reasonable engineering judgment.

A user request does not implicitly waive a hard security/privacy constraint. If the user explicitly requests an architectural change that contradicts a hard constraint, surface the conflict before implementing it.
