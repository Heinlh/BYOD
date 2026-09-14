# BYOD for Windows

Run **BYOD-Setup-0.1.0-x64.exe**, choose **Install**, then open **BYOD** from your
desktop or Start menu. Python, Node.js, and a terminal are not required.

The installer targets Windows 10 (build 19041+) and Windows 11 on x64. It installs
for the current user without requiring administrator rights. If Windows WebView2
is missing, setup installs it using Microsoft's signed bootstrapper; internet is
required for that prerequisite. The app itself downloads its local embedding model
on first ingestion. Choose an API provider or an installed Ollama model in Settings.

BYOD opens in its own desktop window. Closing it stops its local server. Launching
it again restores the same local library. The data directory remains the platform's
`byod` application-data folder, separate from the installation folder. Uninstall
through Windows Settings; your library, source documents, and OS-keychain keys are
preserved. Remove provider keys in BYOD Settings if you no longer want to retain them.

This build is unsigned because no signing certificate was supplied. Windows may
show an unknown-publisher or reputation warning. Distributed releases should be
signed by the publisher; never disable Windows security protections to install.

## Build from source

Install Inno Setup 6, uv, and Node.js, then run from the project root:

```powershell
.\scripts\build_windows.ps1
```

The script installs the optional `desktop` dependencies and the `packaging` tool
group, builds React, freezes one Python application using PyInstaller, and compiles
the installer. It verifies Microsoft's bootstrapper signature before packaging it.
The app folder is `dist/BYOD`; the installer is under `dist/installers`.

The desktop dependency is pywebview (WebView2/Windows Forms via pythonnet). It
provides only the window: the existing FastAPI process and React application remain
the product architecture. There is no exposed Python-to-JavaScript API object, no
extra web server, no browser persistence for chats, and no added telemetry.
WebView2 runs in private mode with developer tools and file-URL access disabled.

Third-party distribution metadata and available license files are included with
the frozen runtime. Python's license is included in `_internal/licenses/Python`.
Build tool references: [PyInstaller](https://pyinstaller.org/en/stable/),
[pywebview freezing](https://pywebview.flowrl.com/guide/freezing.html),
[WebView2 deployment](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/distribution),
[Inno Setup](https://jrsoftware.org/isinfo.php).
