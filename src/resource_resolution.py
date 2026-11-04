
"""
Resolve resource-relative effect predictions to state paths.

M4.2.2 — Resource Resolution.

This resolver validates resource identifiers against a trusted
allowlist and converts relative property names into paths.

It does not authorize tool execution or prove that the
dispatcher operates on the resolved resource.
"""

from typing import Any


class ResourceResolutionError(ValueError):
    """A resource or effect path cannot be resolved safely."""

def resolve_effect_paths(
    *,
    service: str,
    predicted_effects: dict[str, Any],
    allowed_resources: frozenset[str],
) -> dict[str, Any]:
    """
    Qualify relative effect paths with a trusted resource identity.

    Example:
      service="payments-api"
      predicted_effects={"audit_logging_enabled": True}

    Returns:
      {"payments-api.audit_logging_enabled": True}
    """

    if not isinstance(service, str) or service not in allowed_resources:
        raise ResourceResolutionError("resource_not_allowed")

    resolved = {}

    for property_name, expected_value in predicted_effects.items():
        if (
            not isinstance(property_name, str)
            or not property_name
            or "." in property_name
        ):
            raise ResourceResolutionError("invalid_effect_path")

        path = f"{service}.{property_name}"
        resolved[path] = expected_value

    return resolved