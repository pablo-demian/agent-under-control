# src/harness.py

import json
from collections.abc import Callable
from typing import Any

from src.execution_boundary import BoundaryViolation

ToolFunction = Callable[..., Any]
TraceFunction = Callable[..., None]
AuthorizeFunction = Callable[[str, dict], dict]


def execute_tool(
    *,
    name: str,
    raw_arguments: str,
    call_id: str,
    round_number: int,
    dispatch: dict[str, ToolFunction],
    authorize: AuthorizeFunction,
    trace: TraceFunction,
) -> dict:
    """
    Process a tool request independently of the LLM.

    Baseline execution pipeline:
      request -> parse -> authorize -> dispatch -> result

    Returns the result that will be sent back to the model.
    """

    trace(
        "tool_requested",
        {
            "tool": name,
            "arguments": raw_arguments,
            "round": round_number,
        },
        call_id=call_id,
    )

    # 1. Parse model-generated arguments.
    try:
        arguments = json.loads(raw_arguments)

        if not isinstance(arguments, dict):
            raise TypeError("Tool arguments must be a JSON object")

    except (json.JSONDecodeError, TypeError) as exc:
        result = {
            "error": "invalid_tool_arguments",
            "error_type": type(exc).__name__,
        }

        trace(
            "tool_rejected",
            {
                "tool": name,
                "reason": "invalid_arguments",
            },
            call_id=call_id,
        )

        return result

    # 2. Ask the authorization layer.
    decision = authorize(name, arguments)

    trace(
        "policy_decision",
        {
            "tool": name,
            "decision": decision,
        },
        call_id=call_id,
    )

    if not decision["allowed"]:
        trace(
            "tool_rejected",
            {
                "tool": name,
                "reason": decision["reason"],
            },
            call_id=call_id,
        )

        return {
            "error": "tool_not_authorized",
            "reason": decision["reason"],
        }

    # 3. Check the execution registry.
    function = dispatch.get(name)

    if function is None:
        trace(
            "tool_rejected",
            {
                "tool": name,
                "reason": "unknown_tool",
            },
            call_id=call_id,
        )

        return {
            "error": "unknown_tool",
        }

    # 4. Execute the tool.
    try:
        result = function(**arguments)
    except BoundaryViolation as exc:
        # The execution boundary rejected a protected mutation.
        # This is different from an authorization-layer denial.
        trace(
            "tool_error",
            {
                "tool": name,
                "error_type": type(exc).__name__,
            },
            call_id=call_id,
        )

        trace(
            "tool_outcome",
            {
                "tool": name,
                "status": "effect_denied",
                "boundary": "AUDIT-001",
            },
            call_id=call_id,
        )

        return {
            "error": "execution_boundary_denied",
            "reason": str(exc),
        }
    except (TypeError, ValueError, KeyError) as exc:
        trace(
            "tool_error",
            {
                "tool": name,
                "error_type": type(exc).__name__,
            },
            call_id=call_id,
        )

        trace(
            "tool_outcome",
            {
                "tool": name,
                "status": "raised",
                "error_type": type(exc).__name__,
            },
            call_id=call_id,
        )        

        return {
            "error": "tool_execution_failed",
            "error_type": type(exc).__name__,
        }

    # 5. Preserve the historical event for compatibility.
    #
    # "tool_executed" means the function returned normally.
    # It does not establish that the requested effect occurred.
    trace(
        "tool_executed",
        {
            "tool": name,
            "arguments": arguments,
            "result": result,
        },
        call_id=call_id,
    )

    # 6. Report invocation outcome independently of tool
    #    result contents.
    #
    # A returned {"error": ...} is still a normal return.
    # Do not infer "effect_denied" from untrusted result data.
    trace(
        "tool_outcome",
        {
            "tool": name,
            "status": "returned",
        },
        call_id=call_id,
    )

    return result