# BYOD agent memory

## Current status

- Active task (2026-09-13): diagnose whole-workspace query latency. Stage 0
  (measurement) blocked on valid 5k/25k whole-workspace provider timings: the host
  paused during the run. No latency fix has been written. Unloaded retrieval
  measurements and the first successful provider timings are recorded below.
  Bench data lives in `%LOCALAPPDATA%/byod/Cache/bench/{1k,5k,25k}`, built by
  `scripts/bench_scale.py build`.
- Environment note: restored desktop/packaging extras with locked uv sync.
  Full pytest passed (38 tests, 54.36 s), Ruff passed, mypy passed (57 files).
  Benchmark process finished; its Ollama model was unloaded. No test process remains.

- Previous task: user requested a Windows .exe installer and explicitly selected a
  dedicated desktop window. Implementing optional pywebview/WebView2, PyInstaller,
  and Inno Setup packaging while retaining the single local Python process.
- Development browser server was stopped to unlock the Python launcher during
  dependency installation. Desktop/installer verification is now in progress.

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

### 2026-09-14 - Loop 39: final instrumentation regression and report

- Unloaded only the benchmark's qwen3.6 model through Ollama's keep_alive=0 request.
  Full pytest: 38 passed in 54.36 s, two existing upstream deprecation warnings.
  This includes all 15 labeled retrieval/rejection cases, document/doc_type filter
  gates, real ingestion, and the benchmark timeout-reporting regression.
- Ruff check . passed; mypy . passed on 57 files; git diff --check passed (line-ending
  notices only). Reviewed latency changes: instrumentation/debug/script/tests only,
  no format-specific retrieval logic or production retrieval policy change.
- tests/BENCHMARK.md now contains the full baseline phase table, provider samples,
  corpus limitations, interruption evidence, and explicit absence of after-change
  results. Spec follow-up is CLI appendix documentation; section 7.1 is unchanged.
- Remaining blocker: valid uninterrupted 5k/25k whole-workspace provider baseline.
  Stage 0 is not claimed complete, no acceptance target is claimed met, and A-D are
  unapplied as required by the user's measurement-first rule. Resume there.

### 2026-09-14 - Loop 38: interrupted provider matrix; Stage 0 remains incomplete

- All six provider cells attempted, one case / one measured run each. Successful
  TTFT milliseconds: 1k workspace 429394.3, document 39835.6; 5k document 42484.0;
  25k document 48114.7. Context counts for that case: workspace 17/17/19 chunks,
  7777/7948/7982 tokens; document 4 chunks and 415 tokens at every tier.
- 5k/25k whole-workspace requests timed out. Raw elapsed waits were 3176466.1 and
  14163633.9 ms; these are NOT valid prefill/TTFT measurements. A requested 45-second
  clock wait actually lasted 13989.5 seconds, demonstrating a long host interruption.
  System power-event query returned no records, so the precise cause is unverified.
- Saved raw diagnostic output to `.tools/bench-before-ttft.txt`; documented repeatable
  commands, corpus limitations, and the unloaded baseline in tests/BENCHMARK.md.
- Restored missing test import after Ruff had removed the shadowed import. Ruff and
  mypy passed. Full pytest rerun now follows unloading the benchmark's Ollama model.
- Blocker: cannot honestly complete Stage 0's provider comparison using interrupted
  samples. Per the explicit no-fix-before-measurement instruction, A-D remain unapplied.
  Next: complete gates, then rerun missing provider baseline cells during uninterrupted
  host uptime before choosing Fix A (the measured context-volume bottleneck).

### 2026-09-13 - Loop 37: first provider result and timeout regression

- First Stage 0 provider cell completed: 1,189 chunks, whole workspace, 17 included
  chunks / 7,777 tokenizer tokens; warm-up 52,671.4 ms, successful TTFT 429,394.3 ms.
  Retrieval in this memory-contended provider run was 1,677.9 ms (candidates 28.4,
  embedding 116.0 separately, search 42.1, assembly 1,607.4). Use loop 34's unloaded
  20-run measurements for retrieval comparisons, not this single contended sample.
- Added a real-ingestion benchmark regression with only the provider mocked: a
  timeout must produce failed-wait timing and no successful TTFT sample.
- Full Ruff passed. Mypy caught a local command-list variable shadowing the bench
  function; renamed it. Regression execution and recheck remain pending.
- Next: finish the remaining five provider cells and record the full Stage 0 table
  before applying relevance-bounded context. No production fix written yet.

### 2026-09-13 - Loop 36: benchmark validity and environment checks

- Restored the existing desktop/packaging extras with locked uv sync (succeeded).
  Corrected benchmark reporting so provider timeouts are separate failed-wait lower
  bounds, not successful TTFT samples; each phase now reports its sample count.
  This changes measurement only, not retrieval or provider behavior.
- Ruff passed for the CLI. Started full pytest, but stopped that task-owned process
  after observing severe contention with the 23 GB CPU-only Ollama model; the test
  run is incomplete and will be repeated with the provider unloaded. Full Ruff then
  passed; mypy is pending. No latency fix has been written.
- Six-cell TTFT matrix is still running. Its first child loaded the old reporting
  code; any timeout in that first result must be interpreted as a lower bound.
- Next: finish uncontended provider measurement, record the baseline and choose
  only the measured bottleneck; rerun full tests after unloading the test model.

### 2026-09-13 - Loop 35: resume latency measurements

- Read the pasted latency task, current memory, spec, retrieval/store/configuration,
  benchmark CLI/script, and quality tests. Existing Stage 0 scale data and retrieval
  measurements from loops 33-34 are present; no optimization has been applied.
- The previously recorded TTFT process is no longer running and its output was not
  found. Restarted the six-cell provider matrix (one labeled case, one measured run
  per size/scope) with output saved to `.tools/bench-before-ttft.txt`.
- Process inspection initially failed under the sandbox; escalated read succeeded.
  Only Ollama is running, with no competing Python benchmark or development server.
- Final installer rebuild from the previous task succeeded, but installed acceptance
  remains pending while the user's new latency task is active.
- Next: record provider timings before any fix; assembly/context volume is the
  current measured retrieval bottleneck. No test pass claimed for this loop.

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

### 2026-09-13 - Loop 29: desktop distribution implementation

- User authorized a dedicated WebView2 app window and executable installer.
  Added optional desktop/packaging dependency groups, desktop server/window lifecycle,
  OS-released instance lock, fixed startup errors, hidden window/bundle checks,
  PyInstaller spec, branded ICO, Inno installer, repeatable Windows build script,
  and desktop setup/dependency/spec documentation. Added lifecycle/lock tests.
- Provider and data architecture remains unchanged: same FastAPI/SQLite process,
  private WebView2 session, no exposed Python API object or browser chat persistence.
- Tooling failures resolved: running development launcher locked uv installation;
  stopped only identified task-owned processes and synced successfully. A PowerShell
  quote issue prevented the first optional-dependency command; used explicit TOML.
  NSIS downloads returned HTML; found existing Inno Setup 6 and used that compiler.
- Microsoft's prerequisite bootstrapper downloaded with valid Microsoft Authenticode
  signature. No runtime installation executed yet. Icon generated from native shapes.
- Ruff formatting fixed long lines; targeted desktop tests/types and a real hidden
  WebView2 render check are running. Next: pass these gates, then freeze and install-test.

### 2026-09-13 - Loop 30: desktop layer gates passed

- Real WebView2 window loaded the compiled app and composer, then closed cleanly.
  Both desktop tests passed: persistent workspace across server restart and real
  Windows instance locking/release. Ruff passed; strict mypy passed on 56 files.
- Fixed initial test expectation: closed Windows ports may time out instead of
  immediately refusing connections; verified the server thread stops and socket
  closes, accepting either transport failure. Fixed optional window type narrowing
  and callable checks in the bundle diagnostic.
- Started scripts/build_windows.ps1 to build frontend, frozen application, and
  per-user installer with desktop/Start-menu shortcuts. No installer run yet.
- Next: inspect PyInstaller output, run frozen diagnostics, test install/uninstall.

### 2026-09-13 - Loop 31: first executable and installer built

- Full build script succeeded through frontend and PyInstaller; Inno Setup compiled
  BYOD-Setup-0.1.0-x64.exe. Frozen executable passed local API/UI, sqlite-vec, native
  imports, and real isolated OS-keychain save/read/delete. Frozen WebView2 window
  rendered the app and closed successfully without the development interpreter.
- Added optional fixture-directory support to the bundle diagnostic so the final
  installed executable can ingest real PDF/DOCX/PPTX and pass all 15 semantic cases.
  Added a test of that path; full regression/type checks running before final rebuild.
- README now leads with installer/desktop instructions; source setup is optional.
  The executable is currently local, not published to GitHub Releases.
- Next: final bundle rebuild, isolated install, full installed-query/window checks,
  uninstall/data-preservation check, and delivery of the installer artifact.

### 2026-09-13 - Loop 32: full packaging regression passed

- All 38 tests passed, including the new package diagnostic ingesting PDF/DOCX/PPTX
  and validating all 15 supported/unrelated query cases. Two existing upstream
  warnings only. Ruff passed; mypy passed on 56 files. Frontend build passed earlier.
- First installer size was 59.2 MB. Frozen API/native/keychain and WebView2 window
  checks passed. Reviewed PyInstaller warning list: optional/unavailable platform,
  typing, and unsupported feature modules; exercised native runtime paths work.
- Rebuilding final executable/installer with the verified query diagnostic. Both
  spec copies now record the explicitly approved desktop architecture addition.
- Next: run the final installed executable against fixture queries and window;
  test uninstall and preservation, then finalize documentation/artifact checksums.

### 2026-09-13 - Loop 33: latency task, Stage 0 instrumentation and provider probe

- Scope: whole-workspace query latency. Confined to index/, retrieve/, db/migrations.py,
  config.py, debug CLI, tests, scripts. Read AGENTS.md, spec sections 4, 6, 7, 12, and
  the retrieval/store/embed/chat/CLI code and retrieval/semantic tests.
- Code inspection findings (not yet measured, no fix written): whole-workspace search
  resolves every chunk ID twice, JSON-binds them into a sqlite-vec `chunk_id IN
  json_each` filter, and stats every indexed source file per query. Context packs all
  results above 0.70 toward 8000 tokens, recounting the whole joined context per result.
- Changes: `Retriever.search(stats=)` records phase seconds/counts only; new
  `byod debug bench <workspace> <query> [--doc] [--runs] [--no-llm]` reports
  candidates/embed/search/assembly/retrieval/TTFT median and nearest-rank p95, cold
  run, provider warm-up (model load), and counts. TTFT uses a per-run marker after the
  fixed system text so Ollama's prefix cache cannot hide prefill; timeouts are recorded.
  `scripts/bench_scale.py` builds real PDF/DOCX/PPTX from installed docstring prose
  (8062 paragraphs), ingests through the real pipeline, snapshots 1k/5k/25k tiers, and
  runs the matrix. CLI search gate test extended to cover bench output and no text leak.
- Provider probe (direct Ollama, qwen3.6:latest 36B Q4_K_M, CPU only, i7-1270P, 31.7 GB
  RAM with ~19 GB free before load): load 46.9 s; 41 prompt tokens 7.4 s; 279 tokens
  32.3 s (8.6 tok/s, partly contended); 1639 tokens 659.1 s (2.5 tok/s, memory-bound).
  The chat provider read timeout is 600 s, so any context above roughly 1.5k model
  tokens times out on this machine. Strong prior that prefill dominates; bench pending.
- Checks run: ruff check . passed; mypy . reported only the environmental `webview`
  missing-import (desktop extra removed by this session's plain uv sync). pytest not
  yet run for this loop. Generator smoke: PDF 237 chunks (mean 429 tok), DOCX 57, PPTX 57.
- Next: finish tier build, run bench matrix (retrieval runs=20 no-llm; TTFT runs=1),
  record the phase table, then choose the fix the numbers indict.

### 2026-09-13 - Loop 34: Stage 0 tier build and retrieval matrix

- Build: first 4-thread attempt measured ~1.2 chunks/s embedding (spec budget ~22/s);
  stopped it. Thread sweep on 32 real chunks: 4/8/12/16 threads gave 0.3 (includes ORT
  arena warm-up)/0.9/1.5/1.6 chunks/s; the full-core build then varied 1-5 chunks/s
  with ~4.6 cores busy (AC power, Balanced plan). Embedding throughput is outside this
  task's fix scope; recorded as a spec-budget miss for the final report.
- Changed bench_scale.py: build embeds with all cores (script-only session) and past
  `--real-chunks` (default 5000) copies indexed documents with their true vectors.
- Tiers built (exit 0): 1k = 12 docs, 1,189 chunks; 5k = 48 docs, 5,061 chunks (all
  embedded); 25k = 228 docs (180 copies), 25,265 chunks. vectors == chunks in each;
  mean 434 tokens/chunk. Data under %LOCALAPPDATA%/byod/Cache/bench.
- Retrieval matrix run: `bench_scale.py run --runs 20` (cases 0,3,7; --no-llm; Ollama
  unloaded). Median of per-query medians / worst per-query p95, ms:

| chunks | scope | cand | ctx chunks | ctx tok | candidates | embed | search | assembly | retrieval |
|---|---|---|---|---|---|---|---|---|---|
| 1,189 | workspace | 1189 | 17 | 6886 | 7.0/16.8 | 9.8/34.7 | 6.8/15.9 | 134.8/439.1 | 148.7/471.9 |
| 1,189 | document | 3 | 2 | 154 | 5.5/7.8 | 9.8/13.0 | 5.5/8.1 | 24.2/36.5 | 36.2/53.1 |
| 5,061 | workspace | 5061 | 17 | 7555 | 25.2/44.8 | 22.9/50.1 | 36.4/67.7 | 301.1/711.9 | 363.5/753.4 |
| 5,061 | document | 3 | 2 | 154 | 8.7/11.4 | 12.9/16.0 | 17.6/23.8 | 30.6/106.5 | 56.7/169.4 |
| 25,265 | workspace | 25265 | 20 | 7415 | 110.5/237.5 | 30.5/71.8 | 205.9/596.2 | 395.7/727.6 | 734.3/1270.5 |
| 25,265 | document | 3 | 2 | 154 | 30.1/215.3 | 28.6/133.2 | 152.5/434.1 | 48.1/261.3 | 230.4/763.3 |

- Reading: assembly dominates retrieval at 1k/5k and scales with context tokens (it
  re-tokenizes the whole joined context per result); search is linear in total vectors
  even with 3 candidates; candidate resolution is linear in chunk IDs. Whole-workspace
  context is 45-50x the single-document context in tokens.
- Running now: TTFT matrix `run --runs 1 --cases 7 --llm qwen3.6:latest`.
- Next: record TTFT, pick the fix the dominant phase indicts.
