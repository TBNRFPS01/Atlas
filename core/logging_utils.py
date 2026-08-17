from __future__ import annotations

from utils.logger import AtlasLogger, get_logger

__all__ = ["AtlasLogger", "get_logger", "setup_logger"]


def setup_logger(name: str = "atlas", log_dir: str = "logging") -> AtlasLogger:
    """Return the single ATLAS logger, configured once by ``AtlasLogger``.

    Kept for backward compatibility: it delegates to the one real
    implementation in ``utils.logger`` so the project has a single logging
    path instead of two competing ones.
    """
    del log_dir  # directory is managed by AtlasLogger
    return get_logger(name)