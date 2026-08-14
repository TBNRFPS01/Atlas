"""Centralized logging for ATLAS v2."""

from __future__ import annotations

import logging
import logging.handlers
import os
from datetime import datetime
from pathlib import Path
from typing import Any


class AtlasLogger:
    """Centralized logger with file rotation support."""

    _instance: AtlasLogger | None = None
    _initialized = False

    def __new__(cls, name: str = "ATLAS") -> AtlasLogger:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, name: str = "ATLAS") -> None:
        if AtlasLogger._initialized:
            return

        self.name = name
        self.log_dir = Path("logs")
        self.log_dir.mkdir(exist_ok=True)

        self._setup_logger()
        AtlasLogger._initialized = True

    def _setup_logger(self) -> None:
        """Configure the underlying Python logger."""
        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(logging.DEBUG)

        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_format = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        console_handler.setFormatter(console_format)

        file_handler = logging.handlers.RotatingFileHandler(
            self.log_dir / "atlas.log",
            maxBytes=1024 * 1024,
            backupCount=5,
        )
        file_handler.setLevel(logging.DEBUG)
        file_format = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        file_handler.setFormatter(file_format)

        self.logger.addHandler(console_handler)
        self.logger.addHandler(file_handler)

    def info(self, message: str, *args: Any, **kwargs: Any) -> None:
        self.logger.info(message, *args, **kwargs)

    def debug(self, message: str, *args: Any, **kwargs: Any) -> None:
        self.logger.debug(message, *args, **kwargs)

    def warning(self, message: str, *args: Any, **kwargs: Any) -> None:
        self.logger.warning(message, *args, **kwargs)

    def error(self, message: str, *args: Any, **kwargs: Any) -> None:
        self.logger.error(message, *args, **kwargs)

    def critical(self, message: str, *args: Any, **kwargs: Any) -> None:
        self.logger.critical(message, *args, **kwargs)


def get_logger(name: str = "ATLAS") -> AtlasLogger:
    """Return the global ATLAS logger instance."""
    return AtlasLogger(name)