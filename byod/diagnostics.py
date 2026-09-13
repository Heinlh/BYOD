"""Fixed lifecycle events only: no request, source, exception, or provider payloads."""

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from logging.handlers import RotatingFileHandler

from byod.config import Config


@contextmanager
def lifecycle_log(config: Config) -> Iterator[None]:
    handler = RotatingFileHandler(
        config.data_dir / "logs" / "byod.log",
        maxBytes=2 * 1024 * 1024,
        backupCount=4,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))

    def emit(message: str) -> None:
        handler.handle(logging.LogRecord("byod.lifecycle", logging.INFO, "", 0, message, (), None))

    try:
        emit("Application started")
        yield
    finally:
        emit("Application stopped")
        handler.close()
