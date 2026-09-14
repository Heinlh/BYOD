"""Windows desktop lifecycle around the existing single-process local application."""

import argparse
import ctypes
import json
import logging
import multiprocessing
import socket
import threading
import time
from pathlib import Path
from typing import Any

import uvicorn

from byod.app import create_app
from byod.config import Config


class LocalServer:
    def __init__(self, config: Config) -> None:
        self.socket = socket.socket()
        self.socket.bind(("127.0.0.1", 0))
        self.url = f"http://127.0.0.1:{self.socket.getsockname()[1]}"
        self.server = uvicorn.Server(
            uvicorn.Config(
                create_app(config),
                host="127.0.0.1",
                log_config=None,
                access_log=False,
                timeout_graceful_shutdown=3,
            )
        )
        self.thread = threading.Thread(
            target=self.server.run,
            kwargs={"sockets": [self.socket]},
            daemon=True,
        )

    def start(self) -> None:
        self.thread.start()
        deadline = time.monotonic() + 30
        while not self.server.started:
            if not self.thread.is_alive() or time.monotonic() > deadline:
                self.close()
                raise RuntimeError("Local server could not start")
            time.sleep(0.05)

    def close(self) -> None:
        self.server.should_exit = True
        if self.thread.is_alive():
            self.thread.join(timeout=10)
        self.socket.close()


class InstanceLock:
    """OS-released lock, so a crash never leaves a stale running-instance flag."""

    def __init__(self, config: Config) -> None:
        import msvcrt

        config.initialize_directories()
        self.file = (config.data_dir / "desktop.lock").open("a+b")
        self.file.seek(0, 2)
        if self.file.tell() == 0:
            self.file.write(b"0")
            self.file.flush()
        self.file.seek(0)
        try:
            msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            self.file.close()
            raise BlockingIOError("BYOD is already running") from None

    def close(self) -> None:
        self.file.close()


def show_error(message: str) -> None:
    ctypes.windll.user32.MessageBoxW(None, message, "BYOD", 0x10)


def run_window(server: LocalServer, config: Config, report: Path | None = None) -> None:
    import webview

    # The window has no Python API bridge. Existing JSON routes remain the only API.
    logging.getLogger("pywebview").disabled = True
    webview.settings["ALLOW_FILE_URLS"] = False
    webview.settings["ALLOW_DOWNLOADS"] = False
    webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = False
    window = webview.create_window(
        "BYOD",
        server.url,
        width=1280,
        height=860,
        min_size=(860, 600),
        background_color="#111115",
        text_select=True,
        hidden=report is not None,
    )
    if window is None:
        raise RuntimeError("Desktop window could not be created")

    if report:

        def verify_window() -> None:
            try:
                deadline = time.monotonic() + 30
                while time.monotonic() < deadline:
                    result = window.evaluate_js(
                        "Boolean(document.querySelector('.app-shell') && "
                        "document.querySelector('textarea[aria-label=Question]'))"
                    )
                    if result:
                        report.write_text(
                            json.dumps({"window": "passed", "url": server.url}), encoding="utf-8"
                        )
                        return
                    time.sleep(0.1)
                raise RuntimeError("Desktop interface did not render")
            finally:
                window.destroy()

        window.events.loaded += verify_window
    webview.start(
        gui="edgechromium",
        debug=False,
        private_mode=True,
        storage_path=str(config.data_dir / "webview"),
        http_server=False,
    )


def main() -> None:
    multiprocessing.freeze_support()
    parser = argparse.ArgumentParser(description="BYOD desktop")
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--window-check", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--smoke-test", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--fixture-dir", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    config = Config.resolve(args.data_dir)
    report: Path | None = args.window_check or args.smoke_test
    lock = None
    server = None
    try:
        lock = InstanceLock(config)
        server = LocalServer(config)
        server.start()
        if args.smoke_test:
            from byod.packaging_check import verify_bundle

            result: dict[str, Any] = verify_bundle(config, server.url, args.fixture_dir)
            args.smoke_test.write_text(json.dumps(result), encoding="utf-8")
        else:
            run_window(server, config, args.window_check)
            if args.window_check and not args.window_check.exists():
                raise RuntimeError("Desktop window verification failed")
    except BlockingIOError:
        window = ctypes.windll.user32.FindWindowW(None, "BYOD")
        if window:
            ctypes.windll.user32.ShowWindow(window, 9)
            ctypes.windll.user32.SetForegroundWindow(window)
        elif not report:
            show_error("BYOD is already running. Open its window from the taskbar.")
    except Exception:
        if report:
            report.write_text(json.dumps({"status": "failed"}), encoding="utf-8")
            raise SystemExit(1) from None
        show_error(
            "Couldn't start BYOD. Close other BYOD windows and run the installer "
            "again to repair the app and WebView2 runtime. Your library stays in place."
        )
    finally:
        if server:
            server.close()
        if lock:
            lock.close()


if __name__ == "__main__":
    main()
