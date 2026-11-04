
from unittest.mock import Mock

from src.execution_boundary import BoundaryViolation
from src.harness import execute_tool


def test_returned_error_is_not_classified_as_effect_denied():
    """
    A normal function return does not prove that the
    requested operational effect succeeded or failed.

    In particular, an error-shaped result is not
    sufficient evidence of execution-boundary denial.
    """
    trace = Mock()
    dispatch = Mock(
        return_value={"error": "simulated_operation_failed"}
    )
    authorize = Mock(
        return_value={
            "allowed": True,
            "reason": "test_authorized",
        }
    )

    result = execute_tool(
        name="simulated_tool",
        raw_arguments='{"service": "payments-api"}',
        call_id="call_m41_returned_001",
        round_number=1,
        dispatch={"simulated_tool": dispatch},
        authorize=authorize,
        trace=trace,
    )

    assert result == {"error": "simulated_operation_failed"}

    authorize.assert_called_once_with(
        "simulated_tool",
        {"service": "payments-api"},
    )
    dispatch.assert_called_once_with(service="payments-api")

    outcome_events = [
        call
        for call in trace.call_args_list
        if call.args[0] == "tool_outcome"
    ]

    assert len(outcome_events) == 1

    event = outcome_events[0]
    assert event.args[1] == {
        "tool": "simulated_tool",
        "status": "returned",
    }
    assert event.kwargs["call_id"] == "call_m41_returned_001"

    event_names = [
        call.args[0]
        for call in trace.call_args_list
    ]

    assert event_names == [
        "tool_requested",
        "policy_decision",
        "tool_executed",
        "tool_outcome",
    ]

    assert "effect_denied" not in str(event.args[1])

def test_dispatch_exception_emits_raised_outcome():
    trace = Mock()

    def failing_tool(service):
        raise ValueError("simulated dispatch failure")

    result = execute_tool(
        name="simulated_tool",
        raw_arguments='{"service": "payments-api"}',
        call_id="call_m41_raised_001",
        round_number=1,
        dispatch={"simulated_tool": failing_tool},
        authorize=lambda name, args: {
            "allowed": True,
            "reason": "test_authorized",
        },
        trace=trace,
    )

    assert result == {
        "error": "tool_execution_failed",
        "error_type": "ValueError",
    }

    outcome_events = [
        call
        for call in trace.call_args_list
        if call.args[0] == "tool_outcome"
    ]

    assert len(outcome_events) == 1
    assert outcome_events[0].args[1] == {
        "tool": "simulated_tool",
        "status": "raised",
        "error_type": "ValueError",
    }

    assert outcome_events[0].kwargs["call_id"] == (
        "call_m41_raised_001"
    )

def test_boundary_violation_emits_effect_denied():
    trace = Mock()

    def forbidden_tool(service):
        raise BoundaryViolation(
            "AUDIT-001: audit logging cannot be disabled"
        )

    result = execute_tool(
        name="simulated_tool",
        raw_arguments='{"service": "payments-api"}',
        call_id="call_m41_boundary_001",
        round_number=1,
        dispatch={"simulated_tool": forbidden_tool},
        authorize=lambda name, args: {
            "allowed": True,
            "reason": "test_authorized",
        },
        trace=trace,
    )

    assert result["error"] == "execution_boundary_denied"

    events = [
        call.args[0]
        for call in trace.call_args_list
    ]

    assert events == [
        "tool_requested",
        "policy_decision",
        "tool_error",
        "tool_outcome",
    ]

    outcomes = [
        call for call in trace.call_args_list
        if call.args[0] == "tool_outcome"
    ]

    assert len(outcomes) == 1
    assert outcomes[0].args[1] == {
        "tool": "simulated_tool",
        "status": "effect_denied",
        "boundary": "AUDIT-001",
    }
    assert outcomes[0].kwargs["call_id"] == (
        "call_m41_boundary_001"
    )    

def test_policy_denial_does_not_emit_execution_outcome():
    trace = Mock()
    dispatch = Mock()

    result = execute_tool(
        name="disable_audit_logging",
        raw_arguments='{"service": "payments-api"}',
        call_id="call_m41_policy_deny_001",
        round_number=1,
        dispatch={"disable_audit_logging": dispatch},
        authorize=lambda name, args: {
            "allowed": False,
            "reason": "sensitive_operation_denied",
        },
        trace=trace,
    )

    assert result == {
        "error": "tool_not_authorized",
        "reason": "sensitive_operation_denied",
    }

    dispatch.assert_not_called()

    event_names = [
        call.args[0]
        for call in trace.call_args_list
    ]

    assert event_names == [
        "tool_requested",
        "policy_decision",
        "tool_rejected",
    ]

    assert "tool_outcome" not in event_names    