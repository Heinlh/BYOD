"""Pinned embedding artifacts only. No model-hub client or remote Python code."""

import hashlib
import threading
import urllib.request
from collections.abc import Callable
from pathlib import Path

from byod.config import Config
from byod.errors import ByodError

MODEL_NAME = "Xenova/jina-embeddings-v2-base-en"
MODEL_REVISION = "459a733e015d7c72b678de3611fc444a7853168a"
MODEL_VERSION = MODEL_REVISION + ":q8:mean:l2"
MODEL_DIMS = 768
MODEL_HASH = "5fe2b7a79fb5520fa519af783a5850b050304a447f4ab74947af42213a8abea8"
TOKENIZER_GIT_HASH = "2a1d18a8dd28bdc3e88ce9a09da12756fba024f5"
_lock = threading.Lock()
Progress = Callable[[str, int, int], None]


def artifact(config: Config, *, weights: bool = False, progress: Progress | None = None) -> Path:
    relative = "onnx/model_quantized.onnx" if weights else "tokenizer.json"
    folder = config.data_dir / "models" / "jina-embeddings-v2-base-en" / MODEL_REVISION
    destination = folder / Path(relative).name
    with _lock:
        if destination.exists():
            return destination
        folder.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(".partial")
        try:
            url = f"https://huggingface.co/{MODEL_NAME}/resolve/{MODEL_REVISION}/{relative}"
            with urllib.request.urlopen(url, timeout=60) as response:  # noqa: S310
                size = int(response.headers.get("Content-Length", 0))
                count = 0
                with temporary.open("wb") as output:
                    while data := response.read(1024 * 1024):
                        output.write(data)
                        count += len(data)
                        if progress:
                            progress(relative, count, size)
            if weights:
                with temporary.open("rb") as source:
                    valid = hashlib.file_digest(source, "sha256").hexdigest() == MODEL_HASH
            else:
                content = temporary.read_bytes()
                # Git blob identity pins the tokenizer from the same model revision.
                digest = hashlib.sha1(usedforsecurity=False)
                digest.update(f"blob {len(content)}\0".encode())
                digest.update(content)
                valid = digest.hexdigest() == TOKENIZER_GIT_HASH
            if not valid:
                raise ValueError("Model checksum mismatch")
            temporary.replace(destination)
            return destination
        except Exception:
            temporary.unlink(missing_ok=True)
            raise ByodError("MODEL_DOWNLOAD_FAILED") from None
