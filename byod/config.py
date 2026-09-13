"""Filesystem configuration. Secrets never belong in configuration files."""

import os
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from platformdirs import user_data_path
from pydantic import BaseModel, ConfigDict, Field

_preferences_lock = threading.RLock()


class Selection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: Literal["openai", "anthropic", "ollama"] | None = None
    model: str = Field(default="", max_length=200)


class Preferences(BaseModel):
    model_config = ConfigDict(extra="forbid")
    retrieval_min_score: float = Field(default=0.70, ge=0, le=1)
    active: Selection = Field(default_factory=Selection)
    workspaces: dict[str, Selection] = Field(default_factory=dict)

    def selection(self, workspace_id: int | None = None) -> Selection:
        return self.workspaces.get(str(workspace_id), self.active)


@dataclass(frozen=True)
class Config:
    data_dir: Path

    @classmethod
    def resolve(cls, data_dir: Path | None = None) -> "Config":
        override = os.environ.get("BYOD_DATA_DIR")
        root = data_dir or (Path(override) if override else user_data_path("byod", appauthor=False))
        return cls(root.expanduser().resolve())

    @property
    def database(self) -> Path:
        return self.data_dir / "byod.db"

    def initialize_directories(self) -> None:
        for directory in (self.data_dir, self.data_dir / "models", self.data_dir / "logs"):
            directory.mkdir(parents=True, exist_ok=True)

    def preferences(self) -> Preferences:
        with _preferences_lock:
            path = self.data_dir / "config.json"
            if not path.exists():
                return Preferences()
            try:
                return Preferences.model_validate_json(path.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                raise ValueError("Couldn't read settings. Repair or remove config.json.") from None

    def save_preferences(self, preferences: Preferences) -> None:
        # Only allowlisted non-secret fields can be persisted.
        with _preferences_lock:
            self.initialize_directories()
            temporary = self.data_dir / "config.json.partial"
            temporary.write_text(preferences.model_dump_json(indent=2), encoding="utf-8")
            temporary.replace(self.data_dir / "config.json")

    @contextmanager
    def edit_preferences(self) -> Iterator[Preferences]:
        with _preferences_lock:
            preferences = self.preferences()
            yield preferences
            self.save_preferences(preferences)
