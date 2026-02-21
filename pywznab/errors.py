from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class ErrorCode(IntEnum):
    UNSUPPORTED_FUNCTION = 100
    INVALID_PARAMETER = 200
    MISSING_PARAMETER = 201


@dataclass(frozen=True)
class NewznabError(Exception):
    code: ErrorCode
    description: str

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.code}: {self.description}"
