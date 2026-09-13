# BYOD agent memory

## Current status

- Specification supplied as root `BYOD_SPEC.md`, initially copied to authoritative
  `docs/BYOD_SPEC.md`; both include the approved calibrated relevance cutoff.
- Working v1 (M1 through M6) verified. 35 Python tests, Ruff, strict mypy on 52
  files, TypeScript/build, all 3 real browser tests, and wheel-content audit passed.
- Fifteen labeled natural-language retrieval cases passed; live Ollama answers
  across PDF, DOCX, and PPTX contained expected facts and exact source citations.
- Python 3.12.5 is installed but requires execution outside the restricted sandbox.
  A project-local uv binary is available under ignored `.tools/uv/`.
- Local server: http://127.0.0.1:18765/ using `.byod-dev`. Startup instructions in
  README.md; evidence and limits in docs/V1_VERIFICATION.md. Next product milestone
  is real coursework use (M7), not additional unrequested feature work.
- README presentation refreshed with the app's colors/type style, a local SVG
  banner, screenshots, and step-by-step setup instructions; documentation checks
  and visual inspection passed, as did all 35 tests, Ruff, and mypy (52 files).
- README GitHub rendering repaired after finding an appended UTF-16 fragment in
  the UTF-8 file. GitHub-rendered HTML now has proper headings, tables, and code.

## Logging protocol

Read this file when starting or resuming work. Append an entry after every work
loop, including blocked loops, and refresh Current status. Each entry must include
the date, scope, changes, verification results, blockers, and next step. Distinguish
checks actually run from planned checks. Do not record secrets, document text,
prompts, or retrieved context.

## Progress log

### 2026-09-12 - Loop 1: repository inspection and progress tracking

- Scope: read the repository instructions, locate the specification and existing
  code, and establish the requested persistent progress log.
- Changes: created `AGENT_MEMORY.md` and added a mandatory per-loop memory logging
  rule to `AGENTS.md`.
- Verification: read `AGENTS.md`; used `rg --files` and a directory listing
  including hidden entries. Only `AGENTS.md` existed before these changes.
  Read back both edited files to check the logging rule and initial status.
- Tests: not run; there is no application code, test suite, or dependency manifest.
- Blocker: `docs/BYOD_SPEC.md` is missing. `AGENTS.md` requires reading it before
  architecture, dependency, data-model, ingestion, retrieval, provider, security,
  or UI decisions and requires reporting unavailable required files.
- Next step: user supplies the specification; resume the prescribed build order.

### 2026-09-12 - Loop 2: specification and M1 implementation

- Scope: inspect the supplied specification and toolchain, implement skeleton/database.
- Changes: canonical specification copy, Python package and dependency manifest,
  config paths, transactional migrations, specified tables and vector cleanup trigger,
  workspace queries, CLI, local-only health endpoint, foundation tests, dependency
  justifications, README, and ignore rules.
- Verification: read the complete specification and existing instructions; no nested
  instructions or existing implementation found. Confirmed Python 3.12.5 and uv 0.12.13.
- Environment: sandbox initially denied installed Python access and network download;
  escalated toolchain download succeeded. Dependency setup is pending.
- Blockers: none for M1 implementation. Later specification details conflict on citation
  syntax; AGENTS.md requires filename/locator citations and takes precedence over numeric
  citation markers in the specification. UI tokens are referenced but not defined in
  the supplied files; resolve at the UI layer. Embedding model is not named in the spec.
- Next step: run all M1 checks and fix failures before proceeding.

### 2026-09-12 - Loop 3: M1 verification

- Changes: explicit tool-cache lint exclusions, formatting fixes, real CLI startup test.
- Verification: 5 pytest tests passed; `ruff check .` passed; `mypy .` passed
  (9 source files). `byod --data-dir .byod-dev init` created the database. The CLI
  integration test started `byod serve --no-open` and verified `/api/health` over HTTP.
  Cascade tests include vector cleanup and persisted chat/citation records.
- Failed attempts: sandbox execution cannot reach base Python. Initial Ruff scan
  included the dependency cache before explicit exclusions were added. A shell-inline
  health test had quoting errors; replaced with a checked-in subprocess test.
- Environment: Python checks run through approved escalated commands. Two upstream
  TestClient deprecation warnings remain; they do not fail tests.
- Review: no provider calls, secrets, document logging, or hosted service introduced.
- Next step: M2. Use a 768-dimensional local ONNX model with a context window large
  enough for 600-token sections and 1200-token slides; verify model artifacts first.

### 2026-09-12 - Loop 4: M2 ingestion and first checks

- Changes: native parsers, normalized blocks, exact tokenizer chunking, background
  queue, document/workspace APIs, CLI add/parse/chunk, real fixture generator and
  fixtures, tests, and pinned model artifact download with identity verification.
- Verification: 12 tests passed, including all native parsers, notes, table integrity,
  queue deduplication, failure cleanup, and CRUD happy/error paths. Tokenizer downloaded
  and validated successfully. Initial Ruff and mypy checks found issues being corrected.
- Fixes in progress: long lines, explicit callback bindings, narrow PyMuPDF untyped
  API boundary, cross-page table continuation, and overlap for long body blocks.
- Decisions: jina-embeddings-v2-base-en ONNX q8 fits schema and chunk budgets. Oversize
  atomic tables fail with an actionable message rather than violating split/budget rules.
- Next step: pass full M2 checks and terminal parse/chunk gates, then implement M3.

### 2026-09-12 - Loop 5: ingestion boundary fixes and CLI gates

- Changes: preserved actual page/slide counts including diagram-only slides;
  re-indexing changed source content retains the document identity; added regression
  tests and subprocess parse/chunk gates for every supported format.
- Verification: 15 of 16 tests passed; strict mypy passed (27 files). The PDF CLI
  gate caught a PyMuPDF promotional message preceding JSON. Disabled the promotion
  and native diagnostic printing at the PDF boundary; rerun is pending.
- Review: M2 operations remain in the single queue worker; no parser mocks or
  request-handler parsing/embedding. API routes depend on the ingestion queue only.
- Next step: rerun the M2 gate and regression suite; do not start M3 until green.

### 2026-09-12 - Loop 6: M2 gate passed

- Verification: 16 tests passed, including terminal parse/chunk commands for all
  three fixtures; notes and locator/token budgets verified. Folder re-add produces
  no duplicates, scanned failures leave no chunks, and modified-source re-index
  preserves document identity. Ruff passed; strict mypy passed (27 files).
- Changes: no new functionality beyond the PDF output fix in the preceding loop.
- Blockers: none for M3. Upstream TestClient deprecation warnings remain.
- Next step: ONNX CPU embedder, sqlite-vec store, ingestion integration, real gates.

### 2026-09-12 - Loop 7: M3 implementation and first embedding gate

- Changes: lazy shared ONNX CPU session, batches up to 32, masked mean pooling,
  L2 normalization, sqlite-vec store protocol/implementation, index integration,
  model metadata persistence, CLI embed/reindex, and real embedding/index tests.
- Verification: downloaded and SHA-256-validated the pinned 138 MB ONNX artifact;
  `byod --data-dir .byod-dev debug embed` returned dimensions 768 and norm 1.0.
  Ruff passed after import fixes. Full regression/type checks are pending.
- Privacy: inference uses CPUExecutionProvider locally; no remote Python execution
  or provider embeddings. Model downloads use fixed public artifact URLs only.
- Next step: full M3 tests and one-vector-per-chunk gate before retrieval.

### 2026-09-12 - Loop 8: M3 integration verification

- Verification: 19 tests passed, including real semantic embeddings, prefiltered
  sqlite-vec queries, deletion, and one-vector-per-chunk ingestion/re-indexing.
- Failure: NumPy 2.5 typing stubs require Python 3.12 while BYOD supports 3.11.
  Constrained NumPy below 2.4 and resolved 2.3.5; strict mypy then passed (31 files).
- Changes: added model/revision mismatch detection for retrieval/settings; dependency
  compatibility documented. Rechecking inference after the NumPy change is pending.
- Next step: final M3 regression run, then M4 filtered retrieval/context/CLI search.

### 2026-09-12 - Loop 9: M3 passed, M4 implemented

- Verification: M3 final run passed all 19 tests, Ruff, and strict mypy (31 files).
- Changes: M4 workspace-first SQL candidate selection, document/type filters,
  missing-file exclusion, incompatible-model rejection, cosine cutoff 0.25, context
  cap 8000 tokenizer tokens, newest ordinal first within each document, and CLI search.
- Citation decision: use `[filename, locator]` per higher-priority AGENTS.md. Source
  text and metadata remain local until an explicit future chat request.
- Tests added: real retrieval/filter/context checks, stale/missing source cases,
  and terminal search/--doc gates. Execution pending.
- Next step: M4 gates and regression checks before providers/chat.

### 2026-09-12 - Loop 10: M4 cutoff investigation

- Verification: 22 tests initially passed; strict typing found a reused test variable
  and passed after its rename. Adding an explicit unrelated-query gate exposed false
  matches at cosine about 0.63 against the biology fixtures.
- Investigation: direct NumPy cosine and SQLite L2 agree, ruling out a distance
  conversion bug. The current model has a high similarity baseline. Evaluated a
  second pinned 768-dimensional ONNX model (Nomic v1.5) locally; unrelated similarity
  also exceeds 0.25, so no model change was made.
- Blocker: spec mandates 0.25 yet also requires unrelated queries to return empty.
  Asked the user whether to adopt a calibrated configurable threshold starting at
  0.70, or keep 0.25 and record the failed gate. No response/approval assumed.
- Next step: while awaiting the decision, tighten M4 snapshot consistency and
  candidate memory use; do not start M5 while M4 remains unverified.

### 2026-09-12 - Loop 11: approved retrieval calibration

- User explicitly approved calibrating the cutoff. Updated both spec copies from
  fixed 0.25 to configurable `retrieval_min_score`, default 0.70.
- Changes: validated non-secret config persistence; retrieval applies the configured
  threshold. Candidate IDs, vector scores, and source metadata now share a SQLite
  read snapshot; candidate selection no longer loads all workspace chunk text.
- Verification: added preference validation tests; rerunning M4 relevant/unrelated
  queries and full regression/type checks next.
- Next step: finish M4, then provider implementations and chat API.

### 2026-09-12 - Loop 12: M4 passed and provider inspection

- Verification: 23 tests passed, including the explicit unrelated-query rejection;
  Ruff and strict mypy passed (34 files). M4 CLI search and document narrowing passed.
- Provider inspection: Ollama is reachable at localhost:11434 and advertises the
  existing `qwen3.6:latest` model. No keys were inspected or requested.
- Changes: installed keyring and promoted HTTPX to runtime dependencies. Read the
  OpenAI Docs skill and fetched official provider API references for M5 adapters.
- Next step: provider implementation, secure settings, persisted chat streaming,
  mocked-provider API coverage, and a real Ollama completion gate.

### 2026-09-12 - Loop 13: M5 implementation and live provider gate

- Changes: OpenAI/Anthropic/Ollama streaming adapters, sanitized transport failures,
  explicit OS-backed keychain, validated per-workspace settings, persistent chat
  history, SSE context/token/done/error events, exact filename/locator citations,
  and input-validation responses that never echo keys or submitted text.
- Verification: strict mypy passed (45 files) before test additions. The real
  `byod debug llm --provider ollama --model qwen3.6:latest` gate streamed `OK`.
- Tests added: real isolated OS keychain save/delete and no-secret-response checks,
  mocked-provider chat route coverage, history persistence, citation resolution,
  error paths, and provider wire-format tests. Full execution pending.
- Next step: pass M5 regression gates and inspect security boundaries before M6 UI.

### 2026-09-12 - Loop 14: M5 regression and privacy verification

- Verification: all 31 tests passed, including real temporary OS-keychain storage
  with cleanup, invalid-key replacement protection, response/config/database secret
  checks, provider wire formats, persisted history, context-before-token ordering,
  source citation resolution, and API error paths. Ruff passed after test formatting.
- Failure: mypy needed an explicit LLMProvider annotation for a heterogeneous test
  mapping; fixed it and queued a rerun.
- Extra gate: a full live Ollama fixture chat is running; it checks citation targets
  and removes its own temporary workspace. No cloud credentials are available, so
  OpenAI/Anthropic are verified through mocked provider wire tests only.
- Next step: finish type/live gates, then M6 UI.

### 2026-09-12 - Loop 15: M5 passed and full live citation gate

- Verification: strict mypy passed (47 files); all 6 provider wire tests passed
  after annotation fix; the full suite's 31 tests passed in the prior loop.
  The additional live Ollama fixture chat completed successfully with one citation
  resolving to a persisted source chunk. Its temporary workspace was removed.
- Environment: Ollama reports the existing model uses CPU (no VRAM), so live
  completions take longer than mocked tests. No cloud provider credentials used.
- User steering: continue until a working v1, test different document queries,
  correct context, and natural-language query behavior. This remains the scope.
- Next step: M6 local UI; then broader end-to-end query acceptance checks.

### 2026-09-12 - Loop 16: M6 frontend implementation

- Changes: React/TypeScript/Vite/Tailwind application, TanStack Query server caches,
  ephemeral Zustand selection, dark reading layout, workspace/chat management,
  document progress/path ingestion, settings with uncontrolled key input, restricted
  Markdown and source previews, keyboard shortcuts, 50 ms stream buffering, visible
  focus/reduced-motion styles, and same-process static bundle serving.
- Added user-triggered native source/reveal endpoints, fixed Host parsing rejection,
  and a local-only browser content security policy. No remote assets or browser storage.
- Verification: TypeScript compilation passed. Dependency installation succeeded on
  retry after automatic approval review timed out before the first attempt started.
  Vite build hit sandbox parent-directory access restrictions; escalated build pending.
- Fix attempt: an initial multi-file style patch failed its final documentation hunk;
  confirmed nothing was applied and reapplied the files with the correct context.
- Next step: compile and browser-test M6, then expanded semantic-query acceptance.

### 2026-09-12 - Loop 17: expanded retrieval and browser regression

- Added economics PDF, statistics DOCX, networking PPTX fixtures and 15 labeled
  natural-language cases. All expected top sources, evidence, filters, and unrelated
  rejections passed using actual ONNX embeddings. Mypy passed on 50 files.
- Frontend production build passed. In-app browser reported no available browser;
  used development-only Playwright with installed headless Chrome in a clean context.
- Browser runs exposed ambiguous selectors and a timeout in Settings before chat
  began. The timeout was initially suspected to be model latency; the failure
  snapshot shows model selection, so that attribution was incorrect.
- Fixed workspace selection cache ordering, adjacent selection after removal, and
  stale document scopes; tightened browser action timeouts and model selector.
- Next: rerun browser gates, inspect screenshots, verify live cross-format answers.

### 2026-09-12 - Loop 18: browser fixes and release preparation

- Workspace creation/removal browser regression passed. Main browser flow now
  reaches chat; Ollama returned a sanitized timeout with the large CPU model and
  only about 1.4 GB free physical RAM. Running subsequent live checks sequentially.
- Full Python suite passed: 32 tests, two upstream deprecation warnings. Ruff passed.
  Added native-source missing/error checks and lifecycle logging checks afterward;
  their targeted rerun is still required.
- Added fixed-message rotating lifecycle log, wheel inclusion for compiled UI,
  repeatable three-format live-answer script, and complete source-run README.
- Browser test now exercises document scoping and explicitly restores its own
  workspace after reload, independent of other workspaces already present.
- A combined README replacement patch was rejected atomically; reapplied safely.
- Next: live answer evidence, final UI gates, package-content verification.

### 2026-09-12 - Loop 19: live cross-format acceptance passed

- Real Ollama answers passed expected-fact and exact persisted citation checks
  for PDF, DOCX, and PPTX. Durations were 24.6, 34.3, and 35.7 seconds.
- Six foundation tests passed, including new local-source error and lifecycle
  privacy checks. Mypy passed on 52 files; frontend typecheck passed.
- Found workspace-specific provider settings survived deletion and could attach
  to a reused SQLite workspace ID. Added a regression, cleanup on delete, and
  locked preference editing to preserve independent concurrent settings updates.
- No Git repository exists, so review uses source inspection and invariant searches;
  no parser imports/format-specific paths found above ingestion, no browser storage.
- Next: verify latest regression, finish browser run, inspect distributable contents.

### 2026-09-12 - Loop 20: UI citation/persistence and keyboard regression

- Browser verified real generation, correct source drawer text, and persisted chat
  after reload. Inspected chat and source screenshots. Workspace switcher autofocus
  failed: React focused before the native modal opened. Added focus after showModal
  and a separate keyboard-focus/restore regression. Production rebuild passed.
- Nine foundation/settings/chat tests passed after preference cleanup; mypy passed
  on 52 files. Ruff passed. Wheel built successfully (~152 KB); final content audit
  and rebuild after latest changes pending.
- Restarted only the task's BYOD server to load updated backend. It is serving the
  compiled UI at 127.0.0.1:18765. Final three-case browser suite running.
- Next: finish final browser and full regression gates; record v1 evidence.

### 2026-09-12 - Loop 21: package audit and local cold-start handling

- Final wheel built and audited: 62 files, compiled UI and schema included, current
  Python sources matched byte-for-byte, no node_modules/cache/test artifacts.
- Keyboard focus/restore and workspace removal browser cases passed. Live browser
  query intermittently hit the 180-second transport timeout during CPU model loading.
  Increased local Ollama read timeout to 600 seconds and added a specific sanitized
  timeout error suggesting a smaller model or freeing memory, with regression tests.
- An automatic approval usage-limit rejection temporarily blocked the package rebuild.
  User explicitly said CONTINUE; retry was approved and the package audit passed.
- Full updated Python suite/type check running. Ruff found one overlong test signature;
  formatted it and reran Ruff. Latest provider changes require another wheel rebuild.
- Next: complete final regression and browser gates using the updated server.

### 2026-09-12 - Loop 22: final backend and packaging gates passed

- Full suite passed: 35 tests, including real document/embedding retrieval and the
  new provider timeout/workspace settings regressions. Only two upstream Starlette
  deprecation warnings remain. Strict mypy passed on all 52 source files. Ruff passed.
- Rebuilt/audited final wheel: 62 files, 152781 bytes, bundled UI/schema and exact
  current Python sources, no development dependency or cache directories.
- Updated local server health passed and lifecycle log contained fixed start events
  only. Browser suite rerun started after heavy Python checks completed.
- Next: finish browser gate, clean owned acceptance workspaces, record final evidence.

### 2026-09-12 - Loop 23: live browser completion and final test selector

- Live browser generation completed successfully with the updated provider handling;
  citations/source preview, persistence, Ctrl+K focus, and workspace switching passed.
- Remaining browser failure was a test selector: the partial label Question also
  matched Send question. Made all three remaining Question selectors exact.
- Both standalone focus/restore and workspace create/remove cases passed again.
- No production code changed in this loop; rerunning browser acceptance only.

### 2026-09-12 - Loop 24: v1 complete and final evidence

- All three browser cases passed in 1.1 minutes: live scoped document chat,
  citation source text, persisted history, unrelated-query refusal, keyboard focus,
  shortcuts, workspace creation/removal, no console errors, no external page requests.
- Final production checks: 35 Python tests, Ruff, mypy (52 files), TypeScript,
  Vite build, live three-format answers, and exact wheel-source/UI audit passed.
- Removed the one owned workspace left by the initial browser timeout; verified
  server health and empty workspace list. Source fixtures remain in tests/fixtures.
- Recorded docs/V1_VERIFICATION.md and screenshots under docs/evidence. User can
  open the running local app or launch from source using README instructions.
- Remaining limits: cloud providers not live-tested without credentials; native
  file-manager launch not interactively exercised; scanned OCR, vague follow-up
  rewriting, and chapter synthesis are deferred. M7 requires four weeks of user use.

### 2026-09-12 - Loop 25: branded README and setup instructions

- User requested a welcoming README matching BYOD and explicit setup instructions.
  Read existing README, agent instructions, specification, design tokens, CLI, and
  provider-control labels. Checked official prerequisite/Ollama installation sources.
- Rewrote README with a local charcoal/lavender SVG banner, brief introduction,
  expandable real screenshots, five setup steps, provider choices, first ingestion,
  restart instructions, keyboard shortcuts, data ownership, troubleshooting, and
  collapsible contributor commands. Added docs/assets/readme-banner.svg.
- Verified eight local link/image targets, SVG XML, balanced code fences/details;
  rendered banner using fresh headless Chrome for visual inspection. No application
  code or dependencies changed. Required pytest/Ruff/mypy checks are running.
- Next: finish regression checks and record final documentation verification.

### 2026-09-12 - Loop 26: README verification complete

- Visually inspected the rendered 1200x320 banner: typography, document icon,
  format labels, neutral body copy, and restrained lavender accents render cleanly.
- All 35 Python tests passed in 30.62 seconds with the same two upstream warnings;
  Ruff passed and strict mypy passed on 52 files. Local links and Markdown structural
  checks passed in the prior loop. Setup commands match the existing CLI/npm scripts.
- Scope review: README, local SVG documentation asset, and this memory file only;
  no runtime changes, new dependencies, or unresolved task blockers.
- Next: user can read the refreshed README and follow its setup instructions.

### 2026-09-12 - Loop 27: repair README encoding and verify GitHub rendering

- User screenshot showed Markdown displayed as raw text. Reproduced a file-encoding
  regression: eight null bytes in an appended UTF-16 duplicate heading after the
  UTF-8 document. Removed that corrupted trailer and the leading BOM; saved UTF-8.
- Kept existing branding, content, and setup instructions. Git diff confirms only
  encoding/trailer cleanup in README; no application changes.
- GitHub's non-publishing Markdown API returned HTTP 200. Rendered its HTML locally
  in isolated headless Chrome: 11 headings, 4 tables, 8 code blocks, all images loaded.
  Visual inspection confirmed real headings/table layout instead of raw syntax.
- Repository-required regression checks running. No commit or push performed.
- Next: finish checks and report the local correction.

### 2026-09-12 - Loop 28: README repair checks passed

- All 35 tests passed in 30.33 seconds (two unchanged upstream warnings), Ruff
  passed, and strict mypy passed on 52 files. GitHub render/visual checks passed
  in the prior loop. README has no null bytes and preserves its intended layout.
- Changed files: README.md and this progress log. Fix is local and ready for the
  user's normal Git commit/push workflow; remote repository was not modified.
