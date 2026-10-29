
"""
Compose resource resolution and observed effect comparison.

M4.2.2 — Observation Adapter.

This module performs no execution, authorization,
state mutation, or automatic rollback.
"""

from typing import Any

from src.effect_comparator import compare_effects
from src.resource_resolution import resolve_effect_paths


def evaluate_observed_effects(
    *,
    service: str,
    predicted_effects: dict[str, Any],
    before_state: dict[str, Any],
    after_state: dict[str, Any],
    allowed_resources: frozenset[str],
) -> dict[str, Any]:
    """
    Compare resource-relative predictions against observed state.

    Resource membership validation is not sufficient to
    establish that execution used that same resource.
    """

    resolved_effects = resolve_effect_paths(
        service=service,
        predicted_effects=predicted_effects,
        allowed_resources=allowed_resources,
    )

    return compare_effects(
        predicted_effects=resolved_effects,
        before_state=before_state,
        after_state=after_state,
    )