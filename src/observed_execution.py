
from collections.abc import Callable
from copy import deepcopy
from typing import Any

from src.harness import execute_tool
from src.observed_effects import evaluate_observed_effects
from src.oracle import evaluate_transition

authorized_context = None

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

    legacy_context_requested = (
        service is not None
        or predicted_effects is not None
    )

    if legacy_context_requested and (
        service is None
        or predicted_effects is None
        or allowed_resources is None
    ):
        raise ValueError("incomplete_effect_comparison_context")

    outcome_status = None
    authorized_context = None

    def capture_authorization(decision):
        nonlocal authorized_context

        if decision.get("allowed") is True:
            authorized_context = deepcopy(
                decision.get("evaluated_context")
            )

    def observed_trace(event, data, *, call_id):
        nonlocal outcome_status, authorized_context

        if event == "tool_outcome":
            outcome_status = data.get("status")

        if event == "policy_decision":
            decision = data["decision"]

            if decision.get("allowed") is True:
                authorized_context = deepcopy(
                    decision.get("evaluated_context")
                )

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
        on_authorization_decision=capture_authorization,
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


    if outcome_status == "returned":
        comparison_service = service
        comparison_effects = predicted_effects

        if authorized_context is not None:
            authorized_service = authorized_context["resource"]
            authorized_effects = authorized_context["predicted_effects"]

            if service is not None and service != authorized_service:
                raise ValueError("authorization_resource_mismatch")

            if (
                predicted_effects is not None
                and predicted_effects != authorized_effects
            ):
                raise ValueError(
                    "authorization_effect_prediction_mismatch"
                )

            comparison_service = authorized_service
            comparison_effects = authorized_effects

        if (
            comparison_service is not None
            and comparison_effects is not None
            and allowed_resources is not None
        ):
            comparison = evaluate_observed_effects(
                service=comparison_service,
                predicted_effects=comparison_effects,
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
