import sys
from pathlib import Path

import httpx
import pytest

from byod.config import Config
from byod.desktop import InstanceLock, LocalServer
from byod.packaging_check import verify_bundle


def test_desktop_server_lifecycle_and_persistent_workspace(tmp_path: Path) -> None:
    config = Config(tmp_path)
    for iteration in range(2):
        server = LocalServer(config)
        server.start()
        try:
            assert server.url.startswith("http://127.0.0.1:")
            with httpx.Client(base_url=server.url, trust_env=False) as client:
                assert client.get("/api/health").json() == {"status": "ok"}
                assert client.get("/").status_code == 200
                if iteration == 0:
                    assert (
                        client.post("/api/workspaces", json={"name": "Desktop"}).status_code == 201
                    )
                else:
                    assert client.get("/api/workspaces").json()[0]["name"] == "Desktop"
        finally:
            server.close()
        assert not server.thread.is_alive()
        assert server.socket.fileno() == -1
        with pytest.raises((httpx.ConnectError, httpx.ConnectTimeout)):
            httpx.get(server.url + "/api/health", timeout=1, trust_env=False)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows desktop lock")
def test_single_instance_lock_is_released(tmp_path: Path) -> None:
    config = Config(tmp_path)
    lock = InstanceLock(config)
    try:
        with pytest.raises(BlockingIOError):
            InstanceLock(config)
    finally:
        lock.close()
    reopened = InstanceLock(config)
    reopened.close()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows OS-keychain bundle check")
def test_bundle_acceptance_uses_real_document_queries(ingest_config: Config) -> None:
    server = LocalServer(ingest_config)
    server.start()
    try:
        result = verify_bundle(
            ingest_config, server.url, Path(__file__).parent / "fixtures" / "queries"
        )
        assert result["status"] == "passed"
        assert result["document_queries"] == 15
    finally:
        server.close()
