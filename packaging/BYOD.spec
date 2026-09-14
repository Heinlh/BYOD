from pathlib import Path
import sys

from PyInstaller.utils.hooks import collect_dynamic_libs, copy_metadata

root = Path(SPECPATH).parent
datas = [
    (str(root / 'byod' / 'ui' / 'dist'), 'byod/ui/dist'),
    (str(root / 'byod' / 'db' / 'schema.sql'), 'byod/db'),
    (str(root / 'packaging' / 'byod.ico'), 'byod'),
    (str(root / 'docs' / 'DESKTOP.md'), '.'),
]
for package in ['fastapi', 'uvicorn', 'platformdirs', 'sqlite-vec', 'pymupdf',
                'python-docx', 'python-pptx', 'tokenizers', 'onnxruntime',
                'numpy', 'keyring', 'httpx', 'pywebview']:
    datas += copy_metadata(package, recursive=True)
python_license = Path(sys.base_prefix) / 'LICENSE.txt'
if python_license.exists():
    datas.append((str(python_license), 'licenses/Python'))

a = Analysis(
    [str(root / 'packaging' / 'desktop_entry.py')], pathex=[str(root)],
    binaries=collect_dynamic_libs('sqlite_vec'), datas=datas,
    hiddenimports=['keyring.backends.Windows', 'webview.platforms.winforms',
                   'webview.platforms.edgechromium', 'uvicorn.logging',
                   'uvicorn.loops.auto', 'uvicorn.protocols.http.auto',
                   'uvicorn.protocols.websockets.auto', 'uvicorn.lifespan.on'],
    excludes=['pytest', 'mypy', 'PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'tkinter'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='BYOD',
          console=False, icon=str(root / 'packaging' / 'byod.ico'), upx=False)
coll = COLLECT(exe, a.binaries, a.datas, name='BYOD', upx=False)
