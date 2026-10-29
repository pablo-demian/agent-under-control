
from collections.abc import Callable
from copy import deepcopy
from typing import Any

from src.harness import execute_tool
from src.observed_effects import evaluate_observed_effects
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
    service: str | None = None,
    predicted_effects: dict[str, Any] | None = None,
    allowed_resources: frozenset[str] | None = None,
) -> dict:
    """
    Execute through the harness and observe state transitions.

    Oracle evaluation remains independent from effect
    prediction comparison.

    Effect comparison runs only when:
      - comparison context is explicitly provided;
      - the tool returns normally.

    The caller is responsible for ensuring that the
    resource identity is bound to the authorized execution.
    """

    comparison_requested = any(
        value is not None
        for value in (
            service,
            predicted_effects,
            allowed_resources,
        )
    )

    if comparison_requested and (
        service is None
        or predicted_effects is None
        or allowed_resources is None
    ):
        raise ValueError("incomplete_effect_comparison_context")

    outcome_status = None

    def observed_trace(event, data, *, call_id):
        nonlocal outcome_status

        if event == "tool_outcome":
            outcome_status = data.get("status")

        trace(event, data, call_id=call_id)

    before = deepcopy(get_state())

    result = execute_tool(
        name=name,
        raw_arguments=raw_arguments,
        call_id=call_id,
        round_number=round_number,
        dispatch=dispatch,
        authorize=authorize,
        trace=observed_trace,
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

    if comparison_requested and outcome_status == "returned":
        comparison = evaluate_observed_effects(
            service=service,
            predicted_effects=predicted_effects,
            before_state=before,
            after_state=after,
            allowed_resources=allowed_resources,
        )

        trace(
            "effect_model_divergence",
            {
                "tool": name,
                **comparison,
            },
            call_id=call_id,
        )

    return result
