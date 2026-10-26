# tests/test_opa_adapter.py

import shutil
import subprocess
from unittest.mock import Mock

import pytest

from src.opa_adapter import authorize_with_opa

SAFE = {
    "service": "payments-api",
    "environment": "staging",
    "level": "INFO",
}

UNSAFE = {
    "service": "payments-api",
    "environment": "staging",
    "level": "NONE",
}

@pytest.mark.parametrize(
    ("stdout", "expected"),
    [
        ("true\n", True),
        ("false\n", False),
    ],
)
def test_boolean_policy_decision(monkeypatch, stdout, expected):
    runner = Mock(
        return_value=subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=stdout,
            stderr="",
        )
    )

    monkeypatch.setattr(subprocess, "run", runner)

    decision = authorize_with_opa(
        "set_log_verbosity_level",
        SAFE,
    )

    assert decision["allowed"] is expected
    assert runner.call_count == 1

@pytest.mark.parametrize(
    "error",
    [
        FileNotFoundError("opa"),
        subprocess.TimeoutExpired(cmd="opa", timeout=3),
    ],
)
def test_pdp_failure_is_fail_closed(monkeypatch, error):
    runner = Mock(side_effect=error)
    monkeypatch.setattr(subprocess, "run", runner)

    decision = authorize_with_opa(
        "set_log_verbosity_level",
        UNSAFE,
    )

    assert decision["allowed"] is False
    assert decision["reason"] == "policy_engine_unavailable"

@pytest.mark.parametrize(
    "stdout",
    [
        "",
        "undefined",
        "ALLOW",
        "{}",
    ],
)
def test_invalid_response_is_denied(monkeypatch, stdout):
    runner = Mock(
        return_value=subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=stdout,
            stderr="",
        )
    )

    monkeypatch.setattr(subprocess, "run", runner)

    decision = authorize_with_opa(
        "set_log_verbosity_level",
        SAFE,
    )

    assert decision["allowed"] is False
    assert decision["reason"] == "invalid_policy_response"

def test_nonzero_exit_is_denied(monkeypatch):
    runner = Mock(
        return_value=subprocess.CompletedProcess(
            args=[],
            returncode=1,
            stdout="",
            stderr="policy compilation error",
        )
    )

    monkeypatch.setattr(subprocess, "run", runner)

    decision = authorize_with_opa(
        "set_log_verbosity_level",
        SAFE,
    )

    assert decision["allowed"] is False
    assert decision["reason"] == "policy_engine_error"

def test_unknown_tool_never_reaches_opa(monkeypatch):
    runner = Mock()
    monkeypatch.setattr(subprocess, "run", runner)

    decision = authorize_with_opa(
        "arbitrary_code_execution",
        {"service": "payments-api"},
    )

    assert decision["allowed"] is False
    assert decision["reason"] == "unknown_tool"
    runner.assert_not_called()

def test_invalid_resource_never_reaches_opa(monkeypatch):
    runner = Mock()
    monkeypatch.setattr(subprocess, "run", runner)

    decision = authorize_with_opa(
        "restart_service",
        {
            "service": "other-service",
            "environment": "staging",
        },
    )

    assert decision["allowed"] is False
    runner.assert_not_called()


@pytest.mark.parametrize(
    ("tool", "arguments", "expected"),
    [
        (
            "disable_audit_logging",
            {
                "service": "payments-api",
                "environment": "staging",
            },
            False,
        ),
        (
            "set_log_verbosity_level",
            UNSAFE,
            False,
        ),
        (
            "set_log_verbosity_level",
            SAFE,
            True,
        ),
        (
            "set_log_verbosity_level",
            {
                "service": "payments-api",
                "environment": "staging",
                "level": "UNRECOGNIZED",
            },
            False,
        ),
    ],
)
def test_real_opa_decisions(tool, arguments, expected):
    if shutil.which("opa") is None:
        pytest.skip("OPA binary not available")

    decision = authorize_with_opa(tool, arguments)

    assert decision["allowed"] is expected