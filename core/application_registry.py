from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any


class ApplicationRegistry:
    """Persistent cache of verified desktop application locations.

    Discovery is performed only on a cache miss. Cached paths are always
    re-verified before use, so an application being moved/uninstalled never
    turns into a stale launch target.
    """

    def __init__(self, path: str | Path = "memory/applications.json") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._apps: dict[str, dict[str, Any]] = {}
        self._load()

    @staticmethod
    def normalize(name: str) -> str:
        value = re.sub(r"\s+", " ", name.strip().lower())
        value = re.sub(r"\b(?:app|application|program)\b", "", value)
        return value.strip(" .!?\"'")

    def _load(self) -> None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                self._apps = data
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            self._apps = {}

    def _save(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._apps, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(self.path)

    def get(self, name: str) -> str | None:
        key = self.normalize(name)
        entry = self._apps.get(key)
        if not entry:
            return None
        path = str(entry.get("path", ""))
        if path and os.path.isfile(path):
            return path
        # Forget stale entries instead of trusting them.
        self._apps.pop(key, None)
        self._save()
        return None

    def remember(self, name: str, path: str, *, source: str = "discovery") -> str:
        key = self.normalize(name)
        self._apps[key] = {
            "name": name.strip(),
            "path": str(Path(path)),
            "verified": os.path.isfile(path),
            "source": source,
        }
        self._save()
        return str(Path(path))

    def forget(self, name: str) -> None:
        if self._apps.pop(self.normalize(name), None) is not None:
            self._save()

    def all(self) -> dict[str, dict[str, Any]]:
        return dict(self._apps)
