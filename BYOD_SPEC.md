# BYOD — Technical Specification

Version 0.1 · Draft

Companion to `CLAUDE.md`. That file holds the rules and constraints for building. This file holds what gets built: behavior, contracts, schemas, and acceptance criteria.

---

## 1. Product definition

### 1.1 Summary

BYOD is a local desktop application that indexes a user's course documents once and answers questions grounded in them, with citations back to the exact page or slide. The user supplies their own LLM provider credentials. Nothing leaves the machine except prompts sent to that provider.

### 1.2 Primary user

A university student with 4–6 concurrent courses, each producing 10–40 documents per semester: lecture slide decks, assigned readings, syllabi, and lab handouts. They currently paste the same files into a chat interface repeatedly.

### 1.3 Success criteria

The project succeeds if the author uses it for four consecutive weeks of real coursework without falling back to pasting documents into a chat window. Every other metric is secondary.

### 1.4 User stories

| # | As a user I want to… | So that… | Milestone |
|---|---|---|---|
| U1 | Create a workspace per course | Retrieval is scoped to one subject | M1 |
| U2 | Add a folder of files at once | Setup takes one action per course | M2 |
| U3 | See ingest progress per file | I know when it's ready and what failed | M2 |
| U4 | Ask a question and get an answer citing slides and pages | I can verify before trusting it | M5 |
| U5 | Click a citation and see the source text | I can read the surrounding context | M6 |
| U6 | Choose my provider and model | I use the subscription I already pay for | M5 |
| U7 | Return days later and find my chats | I continue where I stopped | M6 |
| U8 | Restrict a question to one document | I ask about this week's lecture only | M4 |
| U9 | Remove a document | Outdated material stops appearing | M2 |
| U10 | Re-add a folder without duplicates | I can sync a course folder freely | M2 |

---

## 2. Scope

### 2.1 In scope for v1

PDF, DOCX, PPTX ingest · per-course workspaces · local ONNX embeddings · `sqlite-vec` retrieval · grounded chat with citations · Anthropic, OpenAI, and Ollama providers · persistent chat history · document management.

### 2.2 Deferred

Section summaries and synthesis-mode routing (v1.1) · flashcard generation and scheduling (v1.2) · OCR for scanned PDFs (opt-in extra) · reranking · export.

### 2.3 Out of scope

Auth, multi-user, sync, sharing, cloud storage, telemetry, agents, packaged installers beyond an optional Windows exe.

---

## 3. System overview

Single Python process. FastAPI serves the JSON API under `/api` and the compiled React bundle at `/`. CLI entry point binds `127.0.0.1` on a free port, opens the browser, and runs until interrupted.

```
Browser (React/TS)
      │ HTTP, localhost only
┌─────▼──────────────────────────────────────┐
│ FastAPI                                    │
│  ┌──────────┐                              │
│  │ routers  │──► retrieve ──► index ──┐    │
│  └────┬─────┘        │                │    │
│       │              └──► llm ──────► │ ───┼──► provider API
│  ┌────▼─────┐                         │    │
│  │ job queue│──► ingest ──► index ────┤    │
│  └──────────┘                         │    │
│                                  ┌────▼──┐ │
│                                  │SQLite │ │
│                                  └───────┘ │
└────────────────────────────────────────────┘
```

### 3.1 Filesystem layout

Resolved by `platformdirs`, application name `byod`.

```
<data_dir>/
  byod.db              # SQLite: metadata, chunks, vectors, chats
  models/
    <model-name>/      # ONNX model + tokenizer, downloaded on first run
  logs/
    byod.log           # rotating, 5 files x 2 MB
  config.json          # non-secret settings
```

API keys live in the OS keychain under service `byod`, username `<provider>`. Never in `config.json`.

Source documents are **not copied** into the data directory. Paths are referenced. If a file moves, the document is marked `missing` and excluded from retrieval until re-added.

---

## 4. Data model

### 4.1 Schema

```sql
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE workspaces (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE documents (
    id            INTEGER PRIMARY KEY,
    workspace_id  INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    filename      TEXT NOT NULL,
    path          TEXT NOT NULL,
    doc_type      TEXT NOT NULL CHECK (doc_type IN ('pdf','docx','pptx')),
    content_hash  TEXT NOT NULL,
    unit_count    INTEGER,              -- pages or slides
    chunk_count   INTEGER NOT NULL DEFAULT 0,
    status        TEXT NOT NULL DEFAULT 'pending'
                  CHECK (status IN ('pending','indexed','failed','missing')),
    error         TEXT,
    embed_model   TEXT,
    embed_version TEXT,
    ingested_at   TEXT,
    UNIQUE (workspace_id, content_hash)
);

CREATE TABLE chunks (
    id           INTEGER PRIMARY KEY,
    document_id  INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    ordinal      INTEGER NOT NULL,
    text         TEXT NOT NULL,
    locator      TEXT NOT NULL,
    block_type   TEXT NOT NULL,
    token_count  INTEGER NOT NULL
);
CREATE INDEX idx_chunks_document ON chunks(document_id);

CREATE VIRTUAL TABLE chunk_vectors USING vec0(
    chunk_id  INTEGER PRIMARY KEY,
    embedding FLOAT[768]
);

CREATE TABLE chats (
    id           INTEGER PRIMARY KEY,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    title        TEXT NOT NULL DEFAULT 'Untitled',
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE messages (
    id         INTEGER PRIMARY KEY,
    chat_id    INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    role       TEXT NOT NULL CHECK (role IN ('user','assistant')),
    content    TEXT NOT NULL,
    provider   TEXT,
    model      TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_messages_chat ON messages(chat_id, id);

CREATE TABLE citations (
    message_id INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    chunk_id   INTEGER NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
    rank       INTEGER NOT NULL,
    PRIMARY KEY (message_id, chunk_id)
);

CREATE TABLE schema_version (version INTEGER NOT NULL);
```

Vector dimensionality is fixed at schema creation. Changing embedding models with different dims requires a migration that drops and rebuilds `chunk_vectors`.

### 4.2 Migrations

`db/migrations.py` holds an ordered list of `(version, sql)` applied in a transaction on startup. Forward-only. Each release bumps the version even when the change is additive.

---

## 5. Ingest

### 5.1 Pipeline

```
file path
  → hash check (skip if known)
  → parser        → Block[]
  → normalizer    → validated Block[]
  → chunker       → Chunk[]
  → embedder      → vectors
  → store         → documents, chunks, chunk_vectors (one transaction)
```

A failure at any stage marks the document `failed` with the error message and leaves no partial rows.

### 5.2 Parser contracts

```python
def parse(path: Path) -> list[Block]: ...
```

**PDF (`PyMuPDF`).** Extract text blocks per page with `page.get_text("blocks")`. `locator = f"p. {page_num}"`. Emit `block_type="heading"` when a block's dominant font size exceeds the page median by 20% or more, otherwise `"body"`. If a page yields fewer than 30 characters, record it as likely scanned — if more than half a document's pages qualify, fail with `SCANNED_PDF` and a message pointing to the OCR extra.

**DOCX (`python-docx`).** Walk paragraphs in order. Map `Heading 1..6` styles to `block_type="heading"` with a depth. Maintain a heading stack; `locator` is the joined path, e.g. `Ch 3 > Methods`. Tables emit one block each, serialized as pipe-delimited rows.

**PPTX (`python-pptx`).** For each slide: sort shapes by `(top, left)` before reading. Emit the title placeholder as `heading`, remaining text frames as `body`, tables as `table`, and `slide.notes_slide.notes_text_frame.text` as `notes` when non-empty. `locator = f"slide {n}"`. Hidden slides are skipped.

### 5.3 Normalizer

Validates every block: non-empty text after whitespace collapse, known `doc_type` and `block_type`, monotonic `order`. Collapses runs of whitespace, strips control characters, normalizes to NFC. Drops blocks that are only punctuation or digits.

### 5.4 Chunker

```python
def chunk(blocks: list[Block], doc_type: str) -> list[Chunk]: ...
```

| doc_type | Strategy | Budget |
|---|---|---|
| pptx | One chunk per slide. Text order: deck title, slide title, body, tables, then notes under a `Speaker notes:` line. | No split unless > 1200 tokens |
| pdf | Accumulate body blocks under the current heading until budget; prefix heading path. | 600 tokens, 15% overlap |
| docx | Split at heading boundaries, then by budget within a section. | 600 tokens, 15% overlap |

Universal rules: never split a `table` block; drop any chunk under 20 tokens; every chunk carries the `locator` of its first block. Token counting uses the embedding model's tokenizer, not a word-count estimate.

### 5.5 Job queue

In-process `queue.Queue` with one worker thread. Job states: `queued → running → done | failed`. Jobs are held in memory only; an interrupted ingest is re-run by re-adding the folder, which is cheap because of hashing. Progress is reported per file, not per chunk.

---

## 6. Index

### 6.1 Embedder

ONNX Runtime CPU session, batch size 32, mean pooling over the last hidden state, L2-normalized output. Model files download on first run to `<data_dir>/models/` with a progress callback surfaced in the UI. The session loads lazily and is reused for the process lifetime.

Startup check: if `documents.embed_model` differs from the configured model for any row, the API reports `stale_index: true` and the UI offers re-index. Mixed-model vectors are never queried together.

### 6.2 Vector store

```python
class VectorStore(Protocol):
    def add(self, chunk_ids: list[int], vectors: np.ndarray) -> None: ...
    def search(self, vector: np.ndarray, k: int,
               chunk_ids: list[int] | None = None) -> list[tuple[int, float]]: ...
    def delete(self, chunk_ids: list[int]) -> None: ...
```

`SqliteVecStore` is the implementation. The interface exists so Chroma or a NumPy store can be swapped without touching `retrieve/`.

---

## 7. Retrieval

### 7.1 Sequence

1. Resolve candidate chunk IDs by SQL filter: `workspace_id`, optional `document_ids`, optional `doc_type`, excluding documents with status other than `indexed`.
2. Embed the query with the same model and pooling.
3. `store.search(vector, k=20, chunk_ids=candidates)`.
4. Drop results below a configurable cosine cutoff (`config.json` field
   `retrieval_min_score`). Default: 0.70 for the pinned local embedding model.
   This replaces the original fixed 0.25 cutoff with user-approved calibration
   (2026-09-12): relevant and unrelated fixture questions must pass the M4 gate.
5. Assemble context, newest-ordinal-first within a document, capped at 8000 tokens.

### 7.2 Context format

Each chunk is wrapped so the model can cite precisely:

```
[1] INST425_Week3.pptx — slide 12
<chunk text>

[2] Jurafsky_Ch6.pdf — p. 143
<chunk text>
```

### 7.3 System prompt

Instructs the model to: answer only from the provided excerpts; cite with the bracketed index after each claim; state plainly when the excerpts do not contain the answer rather than filling the gap; and never invent a page or slide number.

### 7.4 Citation resolution

After streaming completes, parse bracketed indices from the response, map back to `chunk_id`, and write `citations` rows. Indices with no match are dropped silently — the displayed text keeps the marker but renders it inert rather than linking to the wrong slide.

---

## 8. LLM providers

### 8.1 Interface

```python
class LLMProvider(Protocol):
    name: str
    requires_key: bool
    def list_models(self) -> list[str]: ...
    def validate(self) -> bool: ...
    def stream(self, messages: list[Message], system: str,
               model: str) -> Iterator[str]: ...
```

### 8.2 Implementations

| Provider | Key | Models | Notes |
|---|---|---|---|
| Anthropic | Yes | Fetched from the models endpoint, fallback to a static list | Messages API, streaming |
| OpenAI | Yes | Fetched from `/v1/models`, filtered to chat models | Chat completions, streaming |
| Ollama | No | `GET /api/tags` | Detected by pinging `localhost:11434`; absent means the provider is hidden |

Provider and model persist per workspace in `config.json`. Key validation runs a minimal completion on save and reports failure without storing the key.

### 8.3 Conversation window

Send the last 10 messages plus the retrieved context. Retrieval runs on every user turn against that turn's text only — no query rewriting in v1. This is a known limitation: follow-ups like "what about the second one" will retrieve poorly. Revisit in v1.1.

---

## 9. HTTP API

All routes under `/api`. JSON in, JSON out, except the chat stream.

### 9.1 Workspaces

```
GET    /api/workspaces                    → [{id, name, document_count, created_at}]
POST   /api/workspaces        {name}      → {id, name}            201
DELETE /api/workspaces/{id}               → 204   (cascades)
```

### 9.2 Documents

```
GET    /api/workspaces/{id}/documents     → [{id, filename, doc_type, unit_count,
                                              chunk_count, status, error, ingested_at}]
POST   /api/workspaces/{id}/documents     {paths: [str]}  → {job_id}       202
DELETE /api/documents/{id}                → 204
POST   /api/documents/{id}/reindex        → {job_id}      202
GET    /api/chunks/{id}                   → {text, locator, filename, document_id}
```

Files are selected by path, not uploaded — this is a local app and copying gigabytes of PDFs into a data directory serves no one.

### 9.3 Jobs

```
GET /api/jobs/{job_id}  → {state, total, completed, failed,
                           current_file, errors: [{filename, code, message}]}
```

Polled at 1 Hz while a job is active.

### 9.4 Chat

```
GET  /api/workspaces/{id}/chats        → [{id, title, updated_at}]
POST /api/workspaces/{id}/chats        → {id}
GET  /api/chats/{id}/messages          → [{id, role, content, created_at,
                                           citations: [{chunk_id, rank, filename, locator}]}]
POST /api/chats/{id}/messages          {content, document_ids?}  → SSE stream
DELETE /api/chats/{id}                 → 204
```

The SSE stream emits:

```
event: context   data: {chunks: [{index, filename, locator, chunk_id}]}
event: token     data: {text: "..."}
event: done      data: {message_id, citations: [...]}
event: error     data: {code, message}
```

Context arrives before the first token so the UI can show sources while the answer streams.

### 9.5 Settings

```
GET  /api/settings   → {providers: [{name, available, configured, models}],
                        active: {provider, model}, embed_model, stale_index}
PUT  /api/settings   {provider?, model?}            → 200
PUT  /api/settings/key  {provider, key}             → {valid: bool}
DELETE /api/settings/key/{provider}                 → 204
```

`GET /api/settings` never returns a key, only `configured`.

---

## 10. Frontend

### 10.1 Stack

React 18, TypeScript strict, Vite, Tailwind with the tokens from `CLAUDE.md` as CSS variables, TanStack Query for server state, Zustand for the small amount of UI state. No component library — the surface is small and a library costs more than it saves here.

### 10.2 Screens

**Chat (default).** Sidebar with wordmark, workspace list, chat list for the active workspace, and a document count that opens the document panel. Main column is the message thread at 72ch. Composer pinned to the bottom with the model selector inline. Empty thread shows workspace name and document count in `--text-dim`, nothing more.

**Document panel.** Slide-over from the right. Per document: filename, type icon, unit count, chunk count, status. Failed rows show the error. Actions: add files, add folder, reindex, remove. Active ingest shows a progress bar with the current filename.

**Settings.** Modal. Provider selection, key entry with validate-on-save, model dropdown, embedding model display with a re-index action when `stale_index` is true, and data directory path with a reveal-in-file-manager button.

### 10.3 Message rendering

Markdown with a restricted renderer: headings, lists, code, tables, emphasis. No raw HTML. Citation markers `[n]` render as inline chips in `--accent`; click opens a popover with the chunk text, filename, and locator, plus a button to open the source file at that page where the platform supports it.

Streaming appends to a buffer rendered at most every 50ms. The message container reserves height to avoid reflow on each token.

### 10.4 Keyboard

`⌘K` / `Ctrl+K` workspace switcher · `⌘N` new chat · `Esc` close panel or modal · `Enter` send, `Shift+Enter` newline · focus ring in `--accent` on every interactive element.

---

## 11. Errors

| Code | Surface | Message |
|---|---|---|
| `FILE_NOT_FOUND` | Document row | File moved or deleted. Re-add it. |
| `UNSUPPORTED_TYPE` | Ingest result | Only PDF, DOCX, and PPTX are supported. |
| `PARSE_FAILED` | Document row | Couldn't read this file. It may be corrupt or password-protected. |
| `SCANNED_PDF` | Document row | This PDF has no text layer. OCR isn't included yet. |
| `EMPTY_DOCUMENT` | Document row | No readable text found. |
| `MODEL_DOWNLOAD_FAILED` | Startup banner | Couldn't download the embedding model. Check your connection and restart. |
| `NO_PROVIDER` | Composer | Add a provider key in Settings to ask questions. |
| `PROVIDER_AUTH` | Stream error | Your {provider} key was rejected. Check it in Settings. |
| `PROVIDER_RATE_LIMIT` | Stream error | {provider} is rate limiting. Wait a moment and retry. |
| `PROVIDER_UNREACHABLE` | Stream error | Couldn't reach {provider}. |
| `NO_RESULTS` | Assistant turn | Nothing in this workspace matches that question. |
| `STALE_INDEX` | Settings banner | The embedding model changed. Re-index to use these documents. |

Errors state the cause and the action. No apologies in UI copy. Provider error bodies are never shown raw — they can echo the key.

---

## 12. Performance budgets

Reference machine: 4-core laptop CPU, 16 GB RAM, no GPU.

| Operation | Target |
|---|---|
| Cold start to interactive | < 3 s (excluding first-run model download) |
| Parse 40-slide PPTX | < 2 s |
| Parse 300-page PDF | < 8 s |
| Embed 1000 chunks | < 45 s |
| Retrieval, 25k-chunk workspace | < 150 ms |
| First token after send | < 2 s + provider latency |
| Memory, idle with index loaded | < 600 MB |

A semester of five courses is roughly 20k–30k chunks and under 150 MB of vectors. If a workspace exceeds 200k chunks, revisit the store.

---

## 13. Milestones

Each milestone has a terminal-runnable gate. Do not start the next until the current one passes.

**M1 — Skeleton.** `config.py`, schema, migrations, CLI, FastAPI health route.
*Gate:* `byod init` creates the data directory and database; `byod serve` responds on `/api/health`.

**M2 — Ingest.** Three parsers, normalizer, chunker, job queue, document CRUD.
*Gate:* `byod debug parse` and `byod debug chunk` produce correct output for all three fixtures; PPTX output contains speaker notes; no chunk under 20 tokens; re-adding a folder creates zero duplicates.

**M3 — Index.** Embedder with first-run download, `sqlite-vec` store, wired into ingest.
*Gate:* `byod debug embed` prints dims and norm; ingesting a fixture populates `chunk_vectors` with one row per chunk.

**M4 — Retrieval.** Filters, search, context assembly.
*Gate:* `byod debug search <workspace> "<query>"` returns ranked chunks with locators; adding `--doc` narrows the candidate set; a query with no matches returns empty rather than noise.

**M5 — Providers and chat API.** Three providers, keyring, SSE streaming, citation resolution.
*Gate:* `byod debug llm --provider <p>` streams a completion; posting a message returns a stream whose citations resolve to real chunk IDs; `pytest` covers each route's happy and error path.

**M6 — UI.** Shell and tokens, thread, document panel, settings.
*Gate:* builds with no TypeScript errors, no console errors, full keyboard navigation, citation popovers resolve to correct source text.

**M7 — Use it.** Load the current semester. Four weeks of real use.
*Gate:* honest answer to whether it was opened without being forced.

---

## 14. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Slide chunking produces weak retrieval | Core feature unreliable | Fixture-based gates; tune on real course decks before building UI |
| "Summarize chapter 4" fails — no single chunk holds it | Common query type broken | Known v1 limitation; section summaries in v1.1 |
| Follow-up questions retrieve poorly | Conversational use frustrating | Documented; query rewriting in v1.1 |
| Scanned readings unusable | Some courses blocked | Clear error pointing to the OCR extra |
| Provider API changes | Broken provider | Thin interface, static model fallback |
| Packaging consumes the schedule | Nothing ships | Repo clone first; exe only on request |
| Scope creep into a portfolio piece | Never finishes | Non-goals in `CLAUDE.md` are binding |

---

## 15. Open questions

1. Re-index on every model change, or keep multiple model indexes side by side? Leaning toward re-index — simpler, and it happens rarely.
2. Should a document be addable to more than one workspace? Currently no. A shared textbook across two courses would need re-ingest.
3. Should chats be deletable individually or cleared per workspace? Individually for now.
4. Does the folder watcher belong in v1.1, or does manual re-add stay the model? Manual is honest and has no background process to debug.

---

## Appendix A — CLI

```
byod init                          Create data directory and database
byod serve [--port N] [--no-open]  Start the server
byod add <workspace> <paths...>    Ingest files or folders
byod ls [workspace]                List workspaces or documents
byod debug parse <file>            Print blocks
byod debug chunk <file>            Print chunks with token counts
byod debug embed "<text>"          Print vector dims and norm
byod debug search <ws> "<query>"   Print top-k with scores
byod debug llm --provider <p>      Stream a test completion
byod reindex <workspace>           Re-embed all documents
```

## Appendix B — Test fixtures

Committed in `tests/fixtures/`, small enough for version control, and treated as part of the spec.

- `lecture.pptx` — 5 slides, notes on slides 2 and 4, one table, one multi-column slide, one diagram-only slide
- `reading.pdf` — 3 pages, two heading levels, one table spanning a page break
- `notes.docx` — nested headings three deep, one table, one bulleted list
- `scanned.pdf` — 2 pages, image-only, for the `SCANNED_PDF` path
