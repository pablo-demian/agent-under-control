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
