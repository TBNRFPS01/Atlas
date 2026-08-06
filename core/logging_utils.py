from __future__ import annotations

import logging
from pathlib import Path


def setup_logger(name: str = "atlas", log_dir: str = "logging") -> logging.Logger:
    """Create a basic logger for ATLAS events and diagnostics."""
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        file_handler = logging.FileHandler(log_path / f"{name}.log", encoding="utf-8")
        file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(file_handler)

    return logger
