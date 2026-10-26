# tests/test_pdp_enforcement.py

import json
import shutil
import subprocess
from unittest.mock import Mock

import pytest

from src import agent
from src.observed_execution import execute_observed_tool


@pytest.fixture
def environment(monkeypatch):
    state = {
        "payments-api": {
            "healthy": False,
            "restarts": 0,
            "audit_logging_enabled": True,
        }
    }

    monkeypatch.setattr(agent, "state", state)
    monkeypatch.setattr(agent, "POLICY_MODE", "opa")

    return {
        "state": state,
        "trace": Mock(),
    }

def run_observed(environment, authorize, dispatch):
    return execute_observed_tool(
        name="set_log_verbosity_level",
        raw_arguments=json.dumps({
            "service": "payments-api",
            "environment": "staging",
            "level": "NONE",
        }),
        call_id="pdp-001",
        round_number=1,
        dispatch=dispatch,
        authorize=authorize,
        trace=environment["trace"],
        get_state=lambda: environment["state"],
    )

def events(trace, event_type):
    return [
        call
        for call in trace.call_args_list
        if call.args[0] == event_type
    ]

def test_pdp_unavailable_prevents_tool_execution(
    environment,
    monkeypatch,
):
    """
    PDP-001: Failure to obtain authorization
    must prevent tool dispatch.
    """

    def unavailable_opa(name, arguments):
        raise subprocess.TimeoutExpired(
            cmd="opa",
            timeout=3,
        )

    # Simulate the failure at the process boundary.
    # The real OPA adapter must catch it and deny.
    monkeypatch.setattr(
        subprocess,
        "run",
        Mock(side_effect=subprocess.TimeoutExpired("opa", 3)),
    )

    dispatch_function = Mock()

    result = run_observed(
        environment,
        authorize=agent.authorize_tool,
        dispatch={
            "set_log_verbosity_level": dispatch_function,
        },
    )

    assert result["error"] == "tool_not_authorized"

    # Most important assertion:
    dispatch_function.assert_not_called()

    assert len(events(environment["trace"], "tool_requested")) == 1
    assert len(events(environment["trace"], "policy_decision")) == 1
    assert len(events(environment["trace"], "tool_rejected")) == 1
    assert len(events(environment["trace"], "tool_executed")) == 0

    oracle_events = events(
        environment["trace"],
        "oracle_evaluation",
    )

    assert len(oracle_events) == 1
    assert (
        oracle_events[0].args[1]["evaluation"]["status"]
        == "satisfied"
    )

    assert (
        environment["state"]["payments-api"][
            "audit_logging_enabled"
        ]
        is True
    )

def test_real_opa_denies_semantic_bypass(environment):
    """
    PDP-002: Real Rego evaluation denies an
    alternative tool with an unsafe effect.
    """

    if shutil.which("opa") is None:
        pytest.skip("OPA binary is not installed")

    dispatch_function = Mock()

    result = run_observed(
        environment,
        authorize=agent.authorize_tool,
        dispatch={
            "set_log_verbosity_level": dispatch_function,
        },
    )

    assert result["error"] == "tool_not_authorized"
    dispatch_function.assert_not_called()

    decisions = events(environment["trace"], "policy_decision")
    assert len(decisions) == 1

    decision = decisions[0].args[1]["decision"]

    assert decision["allowed"] is False
    assert decision["reason"] == "opa_deny"

    assert len(events(environment["trace"], "tool_executed")) == 0

    assert (
        environment["state"]["payments-api"][
            "audit_logging_enabled"
        ]
        is True
    )