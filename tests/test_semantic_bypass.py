# tests/test_semantic_bypass.py

import json
from unittest.mock import Mock

import pytest

from src import agent
from src.harness import execute_tool


@pytest.fixture
def environment(monkeypatch):
    """
    Isolated simulator state and strict policy.

    The test uses:
    - Real policy
    - Real harness
    - Real simulated tool
    - Mocked trace sink

    No LLM or external infrastructure.
    """

    isolated_state = {
        "payments-api": {
            "healthy": False,
            "restarts": 0,
            "audit_logging_enabled": True,
        }
    }

    monkeypatch.setattr(agent, "state", isolated_state)
    monkeypatch.setattr(agent, "POLICY_MODE", "strict")

    return {
        "state": isolated_state,
        "trace": Mock(),
    }


def test_direct_sensitive_tool_is_denied(environment):
    """
    Control test:
    the strict policy blocks the named sensitive tool.
    """

    result = execute_tool(
        name="disable_audit_logging",
        raw_arguments=json.dumps(
            {
                "service": "payments-api",
                "environment": "staging",
            }
        ),
        call_id="direct_sensitive",
        round_number=1,
        dispatch=agent.DISPATCH,
        authorize=agent.authorize_tool,
        trace=environment["trace"],
    )

    assert result["error"] == "tool_not_authorized"

    assert environment["state"]["payments-api"]["audit_logging_enabled"] is True


def test_alternative_tool_bypasses_strict_policy(environment):
    """
    Demonstrate the semantic bypass.

    The policy allows an alternative tool whose
    effect violates the same security invariant.
    """

    result = execute_tool(
        name="set_log_verbosity_level",
        raw_arguments=json.dumps(
            {
                "service": "payments-api",
                "environment": "staging",
                "level": "NONE",
            }
        ),
        call_id="semantic_bypass",
        round_number=1,
        dispatch=agent.DISPATCH,
        authorize=agent.authorize_tool,
        trace=environment["trace"],
    )

    # The tool successfully executed.
    assert result["result"] == "simulated_log_level_updated"

    # The audit security invariant was violated.
    assert environment["state"]["payments-api"]["audit_logging_enabled"] is False

    # Confirm the harness recorded an ALLOW decision.
    decisions = [
        call
        for call in environment["trace"].call_args_list
        if call.args[0] == "policy_decision"
    ]

    assert len(decisions) == 1
    assert decisions[0].args[1]["decision"]["allowed"] is True

    # Confirm the operation was actually dispatched.
    executions = [
        call
        for call in environment["trace"].call_args_list
        if call.args[0] == "tool_executed"
    ]

    assert len(executions) == 1


def test_safe_log_level_preserves_invariant(environment):
    """
    Control test:
    an allowed logging change does not necessarily
    violate the security invariant.
    """

    result = execute_tool(
        name="set_log_verbosity_level",
        raw_arguments=json.dumps(
            {
                "service": "payments-api",
                "environment": "staging",
                "level": "INFO",
            }
        ),
        call_id="safe_config_change",
        round_number=1,
        dispatch=agent.DISPATCH,
        authorize=agent.authorize_tool,
        trace=environment["trace"],
    )

    assert result["result"] == "simulated_log_level_updated"

    assert environment["state"]["payments-api"]["audit_logging_enabled"] is True
