"""Explicit @ references for selecting ATLAS context without dumping whole sessions."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

TOKEN = re.compile(r"@(?P<kind>file|folder|skill|memory|mission|session):(?P<value>[A-Za-z0-9_./-]+)")


@dataclass(frozen=True)
class ContextRef:
    kind: str
    value: str


def parse(text: str) -> list[ContextRef]:
    return [ContextRef(m.group("kind"), m.group("value")) for m in TOKEN.finditer(text)]


class ContextResolver:
    def __init__(self) -> None:
        self._resolvers: dict[str, Callable[[str], str | None]] = {}

    def register(self, kind: str, resolver: Callable[[str], str | None]) -> None:
        self._resolvers[kind] = resolver

    def resolve(self, text: str) -> dict[str, str]:
        resolved: dict[str, str] = {}
        for ref in parse(text):
            resolver = self._resolvers.get(ref.kind)
            if resolver is not None:
                value = resolver(ref.value)
                if value is not None:
                    resolved[f"{ref.kind}:{ref.value}"] = value
        return resolved
