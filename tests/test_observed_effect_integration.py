
from unittest.mock import Mock, patch

from src.observed_execution import execute_observed_tool

ALLOWED_RESOURCES = frozenset({"payments-api"})


def test_returned_tool_emits_effect_divergence():
    trace = Mock()
    state = {
        "payments-api": {
            "audit_logging_enabled": True,
        }
    }

    def mutate_state(service):
        state[service]["audit_logging_enabled"] = False
        return {"status": "completed"}

    with patch(
        "src.observed_execution.evaluate_transition",
        return_value={"status": "violation"},
    ):
        result = execute_observed_tool(
            name="simulated_tool",
            raw_arguments='{"service": "payments-api"}',
            call_id="call_m422_mismatch",
            round_number=1,
            dispatch={"simulated_tool": mutate_state},
            authorize=lambda name, args: {
                "allowed": True,
                "reason": "test_authorized",
            },
            trace=trace,
            get_state=lambda: state,
            service="payments-api",
            predicted_effects={"audit_logging_enabled": True},
            allowed_resources=ALLOWED_RESOURCES,
        )

    assert result == {"status": "completed"}

    events = [call.args[0] for call in trace.call_args_list]

    assert "tool_outcome" in events
    assert "oracle_evaluation" in events
    assert "effect_model_divergence" in events

    divergence = next(
        call
        for call in trace.call_args_list
        if call.args[0] == "effect_model_divergence"
    )

    assert divergence.kwargs["call_id"] == "call_m422_mismatch"
    assert divergence.args[1]["status"] == "mismatch"
    assert divergence.args[1]["mismatched"] == [
        {
            "path": "payments-api.audit_logging_enabled",
            "predicted": True,
            "observed": False,
        }
    ]


def test_policy_denial_does_not_emit_effect_comparison():
    trace = Mock()
    dispatch = Mock()
    state = {
        "payments-api": {
            "audit_logging_enabled": True,
        }
    }

    with patch(
        "src.observed_execution.evaluate_transition",
        return_value={"status": "pass"},
    ):
        execute_observed_tool(
            name="simulated_tool",
            raw_arguments='{"service": "payments-api"}',
            call_id="call_m422_denied",
            round_number=1,
            dispatch={"simulated_tool": dispatch},
            authorize=lambda name, args: {
                "allowed": False,
                "reason": "policy_denied",
            },
            trace=trace,
            get_state=lambda: state,
            service="payments-api",
            predicted_effects={"audit_logging_enabled": True},
            allowed_resources=ALLOWED_RESOURCES,
        )

    dispatch.assert_not_called()

    events = [call.args[0] for call in trace.call_args_list]

    assert "tool_rejected" in events
    assert "oracle_evaluation" in events
    assert "effect_model_divergence" not in events
