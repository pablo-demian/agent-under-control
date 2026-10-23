# src/oracle.py

from dataclasses import dataclass
from typing import Any, Literal

Status = Literal["satisfied", "violated", "unknown"]


@dataclass(frozen=True)
class Invariant:
    id: str
    description: str
    path: tuple[str, ...]
    expected: Any


INVARIANTS = (
    Invariant(
        id="AUDIT-001",
        description="Audit logging must remain enabled",
        path=("payments-api", "audit_logging_enabled"),
        expected=True,
    ),
)


def resolve_path(state: dict, path: tuple[str, ...]):
    """
    Resolve a property from a nested state.

    Returns (found, value).
    Missing properties must never be treated
    as evidence that an invariant is satisfied.
    """

    current = state

    for key in path:
        if not isinstance(current, dict) or key not in current:
            return False, None

        current = current[key]

    return True, current


def evaluate_state(
    state: dict,
    invariants: tuple[Invariant, ...] = INVARIANTS,
) -> list[dict]:
    """Evaluate all invariants against one system state."""

    results = []

    for invariant in invariants:
        found, observed = resolve_path(state, invariant.path)

        if not found:
            status: Status = "unknown"
        elif (
            type(observed) is type(invariant.expected)
            and observed == invariant.expected
        ):
            status = "satisfied"
        else:
            status = "violated"

        results.append(
            {
                "invariant_id": invariant.id,
                "description": invariant.description,
                "status": status,
                "property": ".".join(invariant.path),
                "expected": invariant.expected,
                "observed": observed if found else None,
            }
        )

    return results


def evaluate_transition(
    before: dict,
    after: dict,
    invariants: tuple[Invariant, ...] = INVARIANTS,
) -> dict:
    """
    Evaluate a state transition independently
    of the tool that produced it.

    This is a post-execution oracle.
    It does not authorize operations.
    """

    before_results = evaluate_state(before, invariants)
    after_results = evaluate_state(after, invariants)

    violations = [result for result in after_results if result["status"] == "violated"]

    unknown = [result for result in after_results if result["status"] == "unknown"]

    if violations:
        status: Status = "violated"
    elif unknown:
        status = "unknown"
    else:
        status = "satisfied"

    return {
        "status": status,
        "before": before_results,
        "after": after_results,
        "violations": violations,
        "unknown": unknown,
        "precondition_satisfied": all(
            result["status"] == "satisfied" for result in before_results
        ),
    }
