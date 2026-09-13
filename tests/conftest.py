import os
import shutil
from pathlib import Path

import pytest

from byod.config import Config
from byod.model_files import MODEL_REVISION, artifact
from byod.tokenize import TokenCounter

FIXTURES = Path(__file__).parent / "fixtures"
MODEL_CACHE = Path(__file__).resolve().parents[1] / ".byod-dev"


@pytest.fixture(scope="session")
def counter() -> TokenCounter:
    return TokenCounter(Config(MODEL_CACHE))


@pytest.fixture
def ingest_config(tmp_path: Path, counter: TokenCounter) -> Config:
    config = Config(tmp_path / "data")
    folder = config.data_dir / "models" / "jina-embeddings-v2-base-en" / MODEL_REVISION
    folder.mkdir(parents=True)
    shutil.copyfile(artifact(Config(MODEL_CACHE)), folder / "tokenizer.json")
    weights = artifact(Config(MODEL_CACHE), weights=True)
    os.link(weights, folder / weights.name)
    return config
