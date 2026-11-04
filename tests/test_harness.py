# tests/test_harness.py

import json
from unittest.mock import Mock

import pytest

from src.harness import execute_tool


@pytest.fixture
def harness():
    """
    Every test gets fresh mocks.

    No OpenAI calls.
    No filesystem side effects.
    No real infrastructure.
    """

    tool = Mock(return_value={"status": "ok"})
    trace = Mock()

    authorize = Mock(
        return_value={
            "allowed": True,
            "reason": "baseline_allow",
        }
    )

    dispatch = {
        "restart_service": tool,
    }

    def run(
        name="restart_service",
        arguments=None,
        raw_arguments=None,
        call_id="call_test_001",
    ):
        if raw_arguments is None:
            if arguments is None:
                arguments = {
                    "service": "payments-api",
                    "environment": "staging",
                }

            raw_arguments = json.dumps(arguments)

        return execute_tool(
            name=name,
            raw_arguments=raw_arguments,
            call_id=call_id,
            round_number=1,
            dispatch=dispatch,
            authorize=authorize,
            trace=trace,
        )

    return {
        "run": run,
        "tool": tool,
        "trace": trace,
        "authorize": authorize,
        "dispatch": dispatch,
    }


def event_names(trace_mock):
    return [call.args[0] for call in trace_mock.call_args_list]


def test_authorized_tool_executes(harness):
    result = harness["run"]()

    assert result == {"status": "ok"}

    harness["tool"].assert_called_once_with(
        service="payments-api",
        environment="staging",
    )

    assert event_names(harness["trace"]) == [
        "tool_requested",
        "policy_decision",
        "tool_executed",
        "tool_outcome",
    ]


def test_denied_tool_never_executes(harness):
    harness["authorize"].return_value = {
        "allowed": False,
        "reason": "production_access_denied",
    }

    result = harness["run"](
        arguments={
            "service": "payments-api",
            "environment": "production",
        }
    )

    assert result["error"] == "tool_not_authorized"

    harness["tool"].assert_not_called()

    assert event_names(harness["trace"]) == [
        "tool_requested",
        "policy_decision",
        "tool_rejected",
    ]


def test_unknown_tool_is_rejected(harness):
    harness["authorize"].return_value = {
        "allowed": False,
        "reason": "unknown_tool",
    }

    result = harness["run"](
        name="disable_audit_logging",
    )

    assert result["error"] == "tool_not_authorized"

    harness["tool"].assert_not_called()

    assert "tool_executed" not in event_names(harness["trace"])


def test_invalid_arguments_are_rejected(harness):
    result = harness["run"](raw_arguments='{"service":')

    assert result["error"] == "invalid_tool_arguments"

    harness["authorize"].assert_not_called()
    harness["tool"].assert_not_called()

    assert event_names(harness["trace"]) == [
        "tool_requested",
        "tool_rejected",
    ]


def test_wrong_argument_type_is_rejected(harness):
    result = harness["run"](raw_arguments='["payments-api"]')

    assert result["error"] == "invalid_tool_arguments"

    harness["tool"].assert_not_called()


def test_call_id_is_preserved(harness):
    harness["run"](call_id="call_security_123")

    for call in harness["trace"].call_args_list:
        assert call.kwargs["call_id"] == "call_security_123"


def test_tool_failure_does_not_record_execution(harness):
    harness["tool"].side_effect = ValueError("Simulated tool failure")

    result = harness["run"]()

    assert result["error"] == "tool_execution_failed"

    assert "tool_error" in event_names(harness["trace"])

    assert "tool_executed" not in event_names(harness["trace"])


def test_authorization_precedes_execution(harness):
    execution_order = []

    def authorize(name, arguments):
        execution_order.append("authorize")
        return {
            "allowed": True,
            "reason": "baseline_allow",
        }

    def tool(**kwargs):
        execution_order.append("execute")
        return {"status": "ok"}

    harness["authorize"].side_effect = authorize
    harness["dispatch"]["restart_service"] = tool

    harness["run"]()

    assert execution_order == [
        "authorize",
        "execute",
    ]


def test_authorization_callback_receives_decision(harness):
    on_decision = Mock()

    result = execute_tool(
        name="restart_service",
        raw_arguments=json.dumps({
            "service": "payments-api",
            "environment": "staging",
        }),
        call_id="call_binding_001",
        round_number=1,
        dispatch=harness["dispatch"],
        authorize=harness["authorize"],
        trace=harness["trace"],
        on_authorization_decision=on_decision,
    )

    assert result == {"status": "ok"}

    on_decision.assert_called_once_with({
        "allowed": True,
        "reason": "baseline_allow",
    })


def test_denied_decision_is_also_delivered(harness):
    on_decision = Mock()

    harness["authorize"].return_value = {
        "allowed": False,
        "reason": "policy_denied",
    }

    result = execute_tool(
        name="restart_service",
        raw_arguments='{"service": "payments-api"}',
        call_id="call_binding_002",
        round_number=1,
        dispatch=harness["dispatch"],
        authorize=harness["authorize"],
        trace=harness["trace"],
        on_authorization_decision=on_decision,
    )

    assert result["error"] == "tool_not_authorized"

    on_decision.assert_called_once_with({
        "allowed": False,
        "reason": "policy_denied",
    })

    harness["tool"].assert_not_called()


def test_invalid_json_never_delivers_authorization(harness):
    on_decision = Mock()

    execute_tool(
        name="restart_service",
        raw_arguments="{invalid",
        call_id="call_binding_003",
        round_number=1,
        dispatch=harness["dispatch"],
        authorize=harness["authorize"],
        trace=harness["trace"],
        on_authorization_decision=on_decision,
    )

    on_decision.assert_not_called()
    harness["authorize"].assert_not_called()


def test_callback_mutation_cannot_change_authorization(harness):
    def mutate_decision(decision):
        decision["allowed"] = False
        decision["reason"] = "modified_by_callback"

    result = execute_tool(
        name="restart_service",
        raw_arguments='{"service": "payments-api"}',
        call_id="call_binding_004",
        round_number=1,
        dispatch=harness["dispatch"],
        authorize=harness["authorize"],
        trace=harness["trace"],
        on_authorization_decision=mutate_decision,
    )

    assert result == {"status": "ok"}
    harness["tool"].assert_called_once()

    policy_events = [
        call
        for call in harness["trace"].call_args_list
        if call.args[0] == "policy_decision"
    ]

    assert policy_events[0].args[1]["decision"]["allowed"] is True


def test_mismatched_authorized_arguments_never_dispatch(harness):
    harness["authorize"].return_value = {
        "allowed": True,
        "reason": "opa_allow",
        "evaluated_context": {
            "resource": "payments-api",
            "arguments": {
                "service": "payments-api",
                "environment": "staging",
                "level": "INFO",
            },
            "predicted_effects": {
                "audit_logging_enabled": True,
            },
        },
    }

    result = harness["run"](
        arguments={
            "service": "payments-api",
            "environment": "staging",
            "level": "NONE",
        }
    )

    assert result["error"] == "authorization_context_mismatch"
    harness["tool"].assert_not_called()

    events = event_names(harness["trace"])
    assert "tool_rejected" in events
    assert "tool_executed" not in events
    assert "tool_outcome" not in events


def test_mismatched_authorized_resource_never_dispatch(harness):
    harness["authorize"].return_value = {
        "allowed": True,
        "reason": "opa_allow",
        "evaluated_context": {
            "resource": "billing-api",
            "arguments": {
                "service": "payments-api",
            },
            "predicted_effects": {},
        },
    }

    result = harness["run"](
        arguments={"service": "payments-api"}
    )

    assert result["error"] == "authorization_context_mismatch"
    harness["tool"].assert_not_called()


def test_authorizer_argument_mutation_cannot_change_dispatch(harness):
    def authorize(name, arguments):
        arguments["service"] = "billing-api"

        return {
            "allowed": True,
            "reason": "opa_allow",
            "evaluated_context": {
                "resource": "billing-api",
                "arguments": dict(arguments),
                "predicted_effects": {},
            },
        }

    harness["authorize"].side_effect = authorize

    result = harness["run"](
        arguments={"service": "payments-api"}
    )

    assert result["error"] == "authorization_context_mismatch"
    harness["tool"].assert_not_called()
