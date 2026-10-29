
"""
M4.2.3 — Registry-backed observed execution.

Resolve effect predictions from the trusted Tool Registry
instead of accepting caller-supplied predictions.
"""

import json
from collections.abc import Callable
from typing import Any

from src.effects import resolve_effects
from src.observed_execution import execute_observed_tool
from src.resource_resolution import ResourceResolutionError
from src.tool_registry import get_tool_descriptor


def execute_registered_observed_tool(
    *,
    name: str,
    raw_arguments: str,
    call_id: str,
    round_number: int,
    dispatch: dict,
    authorize: Callable,
    trace: Callable,
    get_state: Callable[[], dict[str, Any]],
    allowed_resources: frozenset[str],
) -> dict:
    descriptor = get_tool_descriptor(name)

    if descriptor is None:
        raise ValueError("unknown_registered_tool")

    try:
        arguments = json.loads(raw_arguments)
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid_tool_arguments") from exc

    if not isinstance(arguments, dict):
        raise TypeError("invalid_tool_arguments")

    service = arguments.get("service")

    if (
        not isinstance(service, str)
        or service not in allowed_resources
    ):
        raise ResourceResolutionError("resource_not_allowed")

    effects = resolve_effects(name, arguments)

    return execute_observed_tool(
        name=name,
        raw_arguments=raw_arguments,
        call_id=call_id,
        round_number=round_number,
        dispatch=dispatch,
        authorize=authorize,
        trace=trace,
        get_state=get_state,
        service=service,
        predicted_effects=effects["predicted_effects"],
        allowed_resources=allowed_resources,
    )