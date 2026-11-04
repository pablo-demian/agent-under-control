
"""
Compare predicted tool effects with observed state.

M4.2.1 — Pure Effect Comparator.

This module does not authorize operations, invoke tools,
or establish that all side effects have been observed.

Predictions use dotted paths relative to a complete
state snapshot, e.g. "payments-api.audit_logging_enabled".
"""

from typing import Any

_MISSING = object()


def _resolve_path(state: dict[str, Any], path: str) -> Any:
    """Return the value at a dotted path, or _MISSING."""
    current: Any = state

    for component in path.split("."):
        if not isinstance(current, dict):
            return _MISSING

        if component not in current:
            return _MISSING

        current = current[component]

    return current


def _same_value(predicted: Any, observed: Any) -> bool:
    """Avoid Python equality conflating bool and int."""
    return (
        type(predicted) is type(observed)
        and predicted == observed
    )


def compare_effects(
    predicted_effects: dict[str, Any],
    before_state: dict[str, Any],
    after_state: dict[str, Any],
) -> dict[str, Any]:
    """
    Compare declared post-state predictions to observations.

    Status precedence:
      mismatch > unknown > match

    The comparison is limited to predicted properties.

    `before_state` is retained in the interface for
    transition-aware analysis in later milestones.
    """
    matched: list[str] = []
    mismatched: list[dict[str, Any]] = []
    unknown: list[str] = []

    for path, predicted in predicted_effects.items():
        observed = _resolve_path(after_state, path)

        if observed is _MISSING:
            unknown.append(path)
            continue

        if _same_value(predicted, observed):
            matched.append(path)
            continue

        mismatched.append(
            {
                "path": path,
                "predicted": predicted,
                "observed": observed,
            }
        )

    if mismatched:
        status = "mismatch"
    elif unknown or not predicted_effects:
        status = "unknown"
    else:
        status = "match"

    return {
        "status": status,
        "matched": matched,
        "mismatched": mismatched,
        "unknown": unknown,
    }
