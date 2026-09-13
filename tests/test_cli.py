import json
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

from byod.tokenize import TokenCounter


def test_cli_init_and_serve(tmp_path: Path) -> None:
    command = [sys.executable, "-m", "byod.cli", "--data-dir", str(tmp_path)]
    result = subprocess.run(command + ["init"], capture_output=True, timeout=20)  # noqa: S603
    assert result.returncode == 0
    assert (tmp_path / "byod.db").is_file()
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    process = subprocess.Popen(  # noqa: S603
        command + ["serve", "--port", str(port), "--no-open"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(100):
            assert process.poll() is None, "CLI server exited before becoming healthy"
            try:
                with urllib.request.urlopen(  # noqa: S310
                    f"http://127.0.0.1:{port}/api/health", timeout=1
                ) as response:
                    assert json.load(response) == {"status": "ok"}
                    break
            except OSError:
                time.sleep(0.1)
        else:
            raise AssertionError("CLI server did not become healthy")
    finally:
        process.terminate()
        process.wait(timeout=10)


@pytest.mark.parametrize("name", ["reading.pdf", "notes.docx", "lecture.pptx"])
def test_parse_and_chunk_cli_gates(name: str, counter: TokenCounter) -> None:
    root = Path(__file__).resolve().parents[1]
    command = [sys.executable, "-m", "byod.cli", "--data-dir", str(root / ".byod-dev"), "debug"]
    fixture = str(root / "tests" / "fixtures" / name)
    for operation in ("parse", "chunk"):
        result = subprocess.run(  # noqa: S603
            command + [operation, fixture],
            capture_output=True,
            timeout=30,
            check=True,
        )
        items = json.loads(result.stdout)
        assert items and all(item["locator"] for item in items)
        if operation == "chunk":
            assert all(
                20 <= item["token_count"] <= (1200 if name.endswith("pptx") else 600)
                for item in items
            )
        if name.endswith("pptx"):
            assert any(
                item.get("block_type") == "notes" or "Speaker notes:" in item["text"]
                for item in items
            )
