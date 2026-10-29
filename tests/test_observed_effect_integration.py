
from copy import deepcopy
from unittest.mock import Mock, patch

from src.effects import resolve_effects
from src.observed_execution import execute_observed_tool
from src.tool_registry import TOOL_REGISTRY, ToolDescriptor

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


def test_observer_uses_authorized_effect_prediction():
    trace = Mock()

    state = {
        "payments-api": {
            "healthy": False,
            "restarts": 0,
            "audit_logging_enabled": True,
        }
    }

    def authorize(name, arguments):
        return {
            "allowed": True,
            "reason": "test_authorized",
            "evaluated_context": {
                "resource": "payments-api",
                "arguments": dict(arguments),
                "predicted_effects": {
                    "audit_logging_enabled": True,
                },
            },
        }

    def configure(service, level):
        state[service]["audit_logging_enabled"] = False
        return {"status": "completed"}

    result = execute_observed_tool(
        name="set_log_verbosity_level",
        raw_arguments=(
            '{"service": "payments-api", "level": "NONE"}'
        ),
        call_id="call_binding_observation_001",
        round_number=1,
        dispatch={"set_log_verbosity_level": configure},
        authorize=authorize,
        trace=trace,
        get_state=lambda: state,
        allowed_resources=frozenset({"payments-api"}),
    )

    assert result == {"status": "completed"}

    comparisons = [
        call
        for call in trace.call_args_list
        if call.args[0] == "effect_model_divergence"
    ]

    assert len(comparisons) == 1
    assert comparisons[0].args[1]["status"] == "mismatch"
    assert comparisons[0].args[1]["mismatched"] == [
        {
            "path": "payments-api.audit_logging_enabled",
            "predicted": True,
            "observed": False,
        }
    ]
    assert comparisons[0].kwargs["call_id"] == (
        "call_binding_observation_001"
    )


def test_observer_uses_prediction_captured_before_registry_change(
    monkeypatch,
):
    trace = Mock()
    state = {
        "payments-api": {
            "healthy": False,
            "restarts": 0,
            "audit_logging_enabled": True,
        }
    }

    def authorize(name, arguments):
        effects = resolve_effects(name, arguments)

        return {
            "allowed": True,
            "reason": "test_authorized",
            "evaluated_context": {
                "resource": arguments["service"],
                "arguments": deepcopy(arguments),
                "capability": effects["capability"],
                "predicted_effects": deepcopy(
                    effects["predicted_effects"]
                ),
            },
        }

    def configure(service, level):
        # Simulate a registry change after authorization.
        monkeypatch.setitem(
            TOOL_REGISTRY,
            "set_log_verbosity_level",
            ToolDescriptor(
                name="set_log_verbosity_level",
                capability="logging.configure",
                effect_model=lambda arguments: {
                    "audit_logging_enabled": False,
                },
            ),
        )

        state[service]["audit_logging_enabled"] = False
        return {"status": "completed"}

    result = execute_observed_tool(
        name="set_log_verbosity_level",
        raw_arguments=(
            '{"service": "payments-api", "level": "INFO"}'
        ),
        call_id="call_prediction_binding_001",
        round_number=1,
        dispatch={"set_log_verbosity_level": configure},
        authorize=authorize,
        trace=trace,
        get_state=lambda: state,
        allowed_resources=frozenset({"payments-api"}),
    )

    assert result == {"status": "completed"}

    decisions = [
        call.args[1]["decision"]
        for call in trace.call_args_list
        if call.args[0] == "policy_decision"
    ]

    assert len(decisions) == 1
    assert decisions[0]["evaluated_context"]["predicted_effects"] == {
        "audit_logging_enabled": True,
    }

    comparisons = [
        call.args[1]
        for call in trace.call_args_list
        if call.args[0] == "effect_model_divergence"
    ]

    assert len(comparisons) == 1
    assert comparisons[0]["status"] == "mismatch"
    assert comparisons[0]["mismatched"] == [
        {
            "path": "payments-api.audit_logging_enabled",
            "predicted": True,
            "observed": False,
        }
    ]