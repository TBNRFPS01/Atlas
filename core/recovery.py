"""Safe bounded retry and recovery helpers."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, TypeVar

T = TypeVar("T")


@dataclass
class RecoveryResult:
    succeeded: bool
    value: object | None = None
    attempts: int = 0
    errors: list[str] = field(default_factory=list)


class RecoveryController:
    """Retries a recovery strategy a bounded number of times.

    The caller decides whether a returned value is successful. This prevents
    hidden infinite loops and keeps destructive recovery policy outside this
    generic controller.
    """

    def run(self, action: Callable[[], T], *, success: Callable[[T], bool] | None = None, max_attempts: int = 2) -> RecoveryResult:
        predicate = success or bool
        errors: list[str] = []
        for attempt in range(1, max(1, max_attempts) + 1):
            try:
                value = action()
                if predicate(value):
                    return RecoveryResult(True, value, attempt, errors)
                errors.append("Attempt did not meet success criteria.")
            except Exception as exc:
                errors.append(str(exc))
        return RecoveryResult(False, attempts=max(1, max_attempts), errors=errors)
