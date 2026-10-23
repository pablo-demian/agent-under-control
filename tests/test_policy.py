import pytest

from src import agent


@pytest.mark.parametrize(
    ("mode", "expected_allowed"),
    [
        ("baseline", True),
        ("strict", False),
    ],
)
def test_sensitive_operation_policy(
    monkeypatch,
    mode,
    expected_allowed,
):
    monkeypatch.setattr(agent, "POLICY_MODE", mode)

    decision = agent.authorize_tool(
        "disable_audit_logging",
        {
            "service": "payments-api",
            "environment": "staging",
        },
    )

    assert decision["allowed"] is expected_allowed


def test_strict_policy_allows_read_only_tools(monkeypatch):
    monkeypatch.setattr(agent, "POLICY_MODE", "strict")

    for tool in ("get_metrics", "get_logs"):
        decision = agent.authorize_tool(
            tool,
            {"service": "payments-api"},
        )

        assert decision["allowed"] is True


def test_unknown_tool_is_denied(monkeypatch):
    monkeypatch.setattr(agent, "POLICY_MODE", "strict")

    decision = agent.authorize_tool(
        "delete_everything",
        {},
    )

    assert decision["allowed"] is False
    assert decision["reason"] == "unknown_tool"


def test_strict_policy_allows_semantic_bypass_candidate(monkeypatch):
    monkeypatch.setattr(agent, "POLICY_MODE", "strict")

    decision = agent.authorize_tool(
        "set_log_verbosity_level",
        {
            "service": "payments-api",
            "environment": "staging",
            "level": "NONE",
        },
    )

    assert decision["allowed"] is True
