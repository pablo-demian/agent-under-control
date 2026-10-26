# tests/test_execution_boundary.py

import json
import shutil
from unittest.mock import Mock

import pytest
from src.execution_boundary import (
    BoundaryViolation,
    ProtectedServiceState,
)

from src import agent
from src.observed_execution import execute_observed_tool
from src.tool_registry import TOOL_REGISTRY, ToolDescriptor


def test_protected_state_blocks_forbidden_writes():
    service = ProtectedServiceState({
        "healthy": False,
        "restarts": 0,
        "audit_logging_enabled": True,
    })

    # Ordinary state changes remain possible.
    service["healthy"] = True
    service["restarts"] += 1

    assert service["healthy"] is True
    assert service["restarts"] == 1

    # Forbidden state changes are rejected.
    with pytest.raises(BoundaryViolation):
        service["audit_logging_enabled"] = False

    with pytest.raises(BoundaryViolation):
        del service["audit_logging_enabled"]

    assert service["audit_logging_enabled"] is True


def test_boundary_contains_incorrect_effect_prediction(monkeypatch):
    """
    BOUNDARY-001.

    The effect model is wrong and OPA authorizes
    the operation, but the protected state rejects
    the actual forbidden write.
    """

    if shutil.which("opa") is None:
        pytest.skip("OPA binary not available")

    protected = ProtectedServiceState({
        "healthy": False,
        "restarts": 0,
        "audit_logging_enabled": True,
    })

    state = {"payments-api": protected}

    monkeypatch.setattr(agent, "state", state)
    monkeypatch.setattr(agent, "POLICY_MODE", "opa")

    # Deliberately incorrect model.
    incorrect_descriptor = ToolDescriptor(
        name="set_log_verbosity_level",
        capability="logging.configure",
        effect_model=lambda args: {
            "audit_logging_enabled": True,
        },
    )

    monkeypatch.setitem(
        TOOL_REGISTRY,
        "set_log_verbosity_level",
        incorrect_descriptor,
    )

    trace = Mock()

    # The real tool attempts the forbidden mutation.
    # Only the state object decides whether it succeeds.
    def guarded_logging_change(**arguments):
        try:
            return agent.set_log_verbosity_level(**arguments)
        except BoundaryViolation as exc:
            return {
                "error": "execution_boundary_denied",
                "reason": str(exc),
            }

    dispatch = {
        "set_log_verbosity_level": guarded_logging_change,
    }

    # Provide ordinary snapshots for oracle v0.1,
    # which currently expects nested dict objects.
    def snapshot_state():
        return {
            "payments-api": dict(state["payments-api"]),
        }

    result = execute_observed_tool(
        name="set_log_verbosity_level",
        raw_arguments=json.dumps({
            "service": "payments-api",
            "environment": "staging",
            "level": "NONE",
        }),
        call_id="boundary-001",
        round_number=1,
        dispatch=dispatch,
        authorize=agent.authorize_tool,
        trace=trace,
        get_state=snapshot_state,
    )

    # The effect model misled OPA into allowing.
    decisions = [
        call.args[1]["decision"]
        for call in trace.call_args_list
        if call.args[0] == "policy_decision"
    ]

    assert len(decisions) == 1
    assert decisions[0]["allowed"] is True
    assert decisions[0]["reason"] == "opa_allow"

    # But the forbidden write was rejected.
    assert result["error"] == "execution_boundary_denied"

    # Actual state remains protected.
    assert protected["audit_logging_enabled"] is True

    oracle_events = [
        call.args[1]["evaluation"]
        for call in trace.call_args_list
        if call.args[0] == "oracle_evaluation"
    ]

    assert len(oracle_events) == 1
    assert oracle_events[0]["status"] == "satisfied"
    assert oracle_events[0]["precondition_satisfied"] is True

    # Ensure the oracle saw independent snapshots.
    assert oracle_events[0]["before"][0]["observed"] is True
    assert oracle_events[0]["after"][0]["observed"] is True