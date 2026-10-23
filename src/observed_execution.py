# src/observed_execution.py

from collections.abc import Callable
from copy import deepcopy
from typing import Any

from src.harness import execute_tool
from src.oracle import evaluate_transition


def execute_observed_tool(
    *,
    name: str,
    raw_arguments: str,
    call_id: str,
    round_number: int,
    dispatch: dict,
    authorize: Callable,
    trace: Callable,
    get_state: Callable[[], dict[str, Any]],
) -> dict:
    """
    Execute a tool once through the existing harness.

    Capture independent state snapshots around execution,
    evaluate security invariants, and emit oracle evidence.

    The oracle is observational; it does not authorize
    or prevent execution.
    """

    before = deepcopy(get_state())

    result = execute_tool(
        name=name,
        raw_arguments=raw_arguments,
        call_id=call_id,
        round_number=round_number,
        dispatch=dispatch,
        authorize=authorize,
        trace=trace,
    )

    after = deepcopy(get_state())

    evaluation = evaluate_transition(
        before=before,
        after=after,
    )

    trace(
        "oracle_evaluation",
        {
            "tool": name,
            "status": evaluation["status"],
            "evaluation": evaluation,
        },
        call_id=call_id,
    )

    return result
