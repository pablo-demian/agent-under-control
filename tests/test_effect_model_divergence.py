# tests/test_effect_model_divergence.py

import json
import shutil
from unittest.mock import Mock

import pytest

from src import agent
from src.observed_execution import execute_observed_tool
from src.tool_registry import (
    TOOL_REGISTRY,
    ToolDescriptor,
)


@pytest.fixture
def environment(monkeypatch):
    if shutil.which("opa") is None:
        pytest.skip("OPA binary not available")

    isolated_state = {
        "payments-api": {
            "healthy": False,
            "restarts": 0,
            "audit_logging_enabled": True,
        }
    }

    monkeypatch.setattr(agent, "state", isolated_state)
    monkeypatch.setattr(agent, "POLICY_MODE", "opa")

    return {
        "state": isolated_state,
        "trace": Mock(),
    }

def run_logging_change(environment, call_id):
    return execute_observed_tool(
        name="set_log_verbosity_level",
        raw_arguments=json.dumps({
            "service": "payments-api",
            "environment": "staging",
            "level": "NONE",
        }),
        call_id=call_id,
        round_number=1,
        dispatch=agent.DISPATCH,
        authorize=agent.authorize_tool,
        trace=environment["trace"],
        get_state=lambda: environment["state"],
    )

def get_events(trace, event_type):
    return [
        call
        for call in trace.call_args_list
        if call.args[0] == event_type
    ]

def test_correct_model_blocks_unsafe_effect(environment):
    """
    Control experiment.

    The real descriptor correctly predicts that
    NONE disables auditing. OPA must deny.
    """

    result = run_logging_change(
        environment,
        call_id="model001-control",
    )

    assert result["error"] == "tool_not_authorized"

    assert (
        environment["state"]["payments-api"][
            "audit_logging_enabled"
        ]
        is True
    )

    assert len(get_events(environment["trace"], "tool_rejected")) == 1
    assert len(get_events(environment["trace"], "tool_executed")) == 0

    oracle_events = get_events(
        environment["trace"],
        "oracle_evaluation",
    )

    assert len(oracle_events) == 1
    assert oracle_events[0].args[1]["evaluation"]["status"] == "satisfied"

def test_incorrect_effect_model_causes_unsafe_authorization(
    environment,
    monkeypatch,
):
    """
    MODEL-001.

    The descriptor reports a safe effect, but the
    actual simulated tool disables audit logging.

    OPA, harness and oracle remain unchanged.
    """

    incorrect_descriptor = ToolDescriptor(
        name="set_log_verbosity_level",
        capability="logging.configure",
        effect_model=lambda arguments: {
            "audit_logging_enabled": True,
        },
    )

    monkeypatch.setitem(
        TOOL_REGISTRY,
        "set_log_verbosity_level",
        incorrect_descriptor,
    )

    result = run_logging_change(
        environment,
        call_id="model001-divergence",
    )

    # The simulated tool really executed.
    assert result["result"] == "simulated_log_level_updated"

    # The actual state violates AUDIT-001.
    assert (
        environment["state"]["payments-api"][
            "audit_logging_enabled"
        ]
        is False
    )

    decisions = get_events(
        environment["trace"],
        "policy_decision",
    )

    assert len(decisions) == 1
    assert decisions[0].args[1]["decision"]["allowed"] is True
    assert decisions[0].args[1]["decision"]["reason"] == "opa_allow"

    executions = get_events(
        environment["trace"],
        "tool_executed",
    )

    assert len(executions) == 1

    oracle_events = get_events(
        environment["trace"],
        "oracle_evaluation",
    )

    assert len(oracle_events) == 1

    evaluation = oracle_events[0].args[1]["evaluation"]

    assert evaluation["status"] == "violated"
    assert evaluation["precondition_satisfied"] is True

    assert evaluation["before"][0]["observed"] is True
    assert evaluation["after"][0]["observed"] is False

    assert evaluation["violations"][0]["invariant_id"] == "AUDIT-001"