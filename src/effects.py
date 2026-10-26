# src/effects.py

from typing import Any

from src.tool_registry import get_tool_descriptor


def resolve_effects(
    name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    """
    Resolve a tool's declared capability and modeled effects.

    Unknown tools and incomplete effect models
    must not be interpreted as safe.
    """

    descriptor = get_tool_descriptor(name)

    if descriptor is None:
        return {
            "capability": "unknown",
            "predicted_effects": {},
        }

    if descriptor.effect_model is None:
        predicted_effects = {}
    else:
        predicted_effects = descriptor.effect_model(arguments)

    return {
        "capability": descriptor.capability,
        "predicted_effects": predicted_effects,
    }