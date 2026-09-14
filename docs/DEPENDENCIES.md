# Dependencies

Dependencies are introduced by milestone and resolved in `uv.lock`.

| Dependency | Justification |
| --- | --- |
| FastAPI | Required HTTP application framework. |
| Uvicorn | ASGI server needed to serve FastAPI in the single Python process. |
| platformdirs | Specification requires platform-native application data paths. |
| sqlite-vec | Required SQLite vector extension; schema uses a 768-dimensional vec0 table. |
| hatchling | Build backend for the installable Python package and CLI. |
| pytest | Required test runner (development only). |
| Ruff | Required lint gate (development only). |
| mypy | Required strict Python type gate (development only). |
| HTTPX | FastAPI TestClient transport and shared streaming HTTP client for provider adapters; avoids three separate provider SDK dependencies. |
| PyMuPDF | Required native PDF text, font, and table extraction. |
| python-docx | Required native DOCX paragraph, heading, and table extraction. |
| python-pptx | Required native PPTX shapes, tables, and speaker notes. |
| tokenizers | Exact embedding token counts and source offsets; standard library cannot reproduce the model tokenizer. |
| ONNX Runtime | Required local CPU inference engine. |
| NumPy | Efficient tensors, masked mean pooling, normalization, and float32 vector serialization for ONNX. |
| keyring | Required OS keychain storage; BYOD rejects file-backed and plaintext fallback backends. |

NumPy is constrained below 2.4 to retain the project's Python 3.11 compatibility,
including compatibility of the distributed typing stubs.

SQLite, CLI argument parsing, filesystem operations, threading, and configuration
use the Python standard library. No external database or service is required.

The default embedding artifact is the quantized ONNX export of
[jina-embeddings-v2-base-en](https://huggingface.co/Xenova/jina-embeddings-v2-base-en),
revision `459a733e015d7c72b678de3611fc444a7853168a`. Its 768 dimensions match
the schema and its 8192-token window supports the specified chunk budgets. The
[original model card](https://huggingface.co/jinaai/jina-embeddings-v2-base-en)
specifies mean pooling and L2 normalization. BYOD downloads only the pinned
tokenizer/ONNX artifacts, validates their identities, and does not execute remote
model code or call a hosted embedding API.

Frontend dependencies follow the specification: React 18 and React DOM render the
UI; TypeScript provides strict checking; Vite and its React plugin compile the local
bundle; Tailwind and its Vite plugin provide the CSS toolchain; TanStack Query holds
ephemeral server-state caches; Zustand holds ephemeral UI selections. React type
packages are development-only. No browser persistence plugin, remote font, component
library, or Markdown dependency is used. A restricted React renderer escapes source
text and supports the required Markdown subset without raw HTML.

Playwright Test is development-only. The installed browser plugin has no connected
browser in this environment, so Playwright drives the installed Chrome in a fresh
headless test context for console, keyboard, document ingestion, streaming, and
citation acceptance checks. It is not included in the runtime application bundle.

Windows desktop packaging, explicitly requested and approved by the user:

- `pywebview` is an optional `desktop` dependency, supplying the native WebView2
  window. Its Windows dependencies include pythonnet/clr-loader for .NET interop;
  Bottle/proxy-tools are upstream dependencies, but BYOD does not start Bottle's
  server or expose a Python API object. FastAPI remains the single local server.
- `PyInstaller` is isolated in the `packaging` build group. It bundles Python,
  native inference/parser libraries, the OS-keychain backend, and the compiled UI.
- Inno Setup is an external build tool already installed on this machine; it
  creates the per-user Windows installer, shortcuts, and uninstaller.
- Microsoft's signed WebView2 bootstrapper is packaged as an installer prerequisite
  and runs only if the runtime is absent. This setup-time download is separate
  from BYOD's restricted application runtime network use.
