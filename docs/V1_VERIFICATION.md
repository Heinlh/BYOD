# BYOD v1 verification — 2026-09-12

M1–M6 are implemented and verified. The application runs as one local Python
process serving its compiled React interface. No hosted backend or embeddings.

| Gate | Result |
|---|---|
| `pytest -q` | 35 passed; two upstream Starlette deprecation warnings |
| `ruff check .` | Passed |
| `mypy .` | Passed, 52 source files |
| Frontend TypeScript and Vite production build | Passed |
| Headless Chrome end-to-end suite | 3 passed in 1.1 minutes |
| Real PDF/DOCX/PPTX parser and chunk CLI gates | Passed; locators, budgets, headings, tables, slide notes checked |
| Local ONNX embedding gate | 768 dimensions, normalized vectors |
| Semantic retrieval acceptance | 11 supported paraphrases plus 4 unrelated queries passed |
| Live Ollama answer acceptance | PDF, DOCX, PPTX: expected facts and exact source citations passed |
| Wheel audit | 62 files; current Python, schema, compiled UI; no node_modules or caches |

The semantic fixtures cover economics PDFs, statistics documents, and networking
slides. Tests verify the expected top page/heading/slide, evidence in assembled
context, document/workspace filters, missing-source exclusion, stale indexes,
duplicate ingestion, and citation persistence. Retrieval uses the user-approved
configurable cosine cutoff, default 0.70. These fixtures establish bounded evidence,
not a guarantee of correctness for every document or natural-language question.

The three browser cases cover focus/restore, workspace selection after creation
and deletion, three-format ingestion, model settings, a live scoped question,
correct source text, persistence after reload, Ctrl+K/Ctrl+N, Enter, visible focus,
an unrelated-question refusal, and absence of console errors/external page requests.

Screenshots: [chat](evidence/chat.png), [source preview](evidence/source-preview.png).
The screenshot documents are synthetic test fixtures.

The existing `qwen3.6:latest` model runs on CPU and uses about 23 GB. Three live
format cases took 24.6, 34.3, and 35.7 seconds. Cold starts and memory pressure
caused intermittent timeouts during development; local requests now allow up to
600 seconds without a response and provide an actionable, sanitized timeout error.
Use a model suitable for the machine's available memory.

OpenAI and Anthropic were verified through provider transport tests, not live
credentials. Native source/file-manager launch error paths passed, but the visible
OS application launch was not interactively exercised. OCR, whole-chapter synthesis,
and conversational query rewriting remain deferred as specified. M7's four weeks
of real coursework use cannot be replaced by automated tests.

Run instructions and repeatable commands are in [README](../README.md). Per-loop
agent records are in [AGENT_MEMORY](../AGENT_MEMORY.md).
