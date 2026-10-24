# src/execution_boundary.py

from collections.abc import Iterator, MutableMapping
from typing import Any


class BoundaryViolation(PermissionError):
    """A protected state transition was rejected."""


class ProtectedServiceState(MutableMapping[str, Any]):
    """
    Protected state interface for the simulated service.

    Prevents writes that disable audit logging.

    This is an in-process simulation boundary,
    not a security sandbox for arbitrary Python code.
    """

    def __init__(self, initial: dict[str, Any]) -> None:
        if initial.get("audit_logging_enabled") is not True:
            raise ValueError(
                "Protected state requires audit logging enabled"
            )

        self.__values = dict(initial)

    def __getitem__(self, key: str) -> Any:
        return self.__values[key]

    def __setitem__(self, key: str, value: Any) -> None:
        if key == "audit_logging_enabled" and value is not True:
            raise BoundaryViolation(
                "AUDIT-001: audit logging cannot be disabled"
            )

        self.__values[key] = value

    def __delitem__(self, key: str) -> None:
        if key == "audit_logging_enabled":
            raise BoundaryViolation(
                "AUDIT-001: audit logging cannot be removed"
            )

        del self.__values[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self.__values)

    def __len__(self) -> int:
        return len(self.__values)