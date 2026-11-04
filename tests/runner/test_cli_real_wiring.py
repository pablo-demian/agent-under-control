"""M5.3.2-C: subprocess CLI wiring, never launches a real agent."""

import json
from pathlib import Path
from unittest.mock import Mock

import pytest

import runner.__main__ as cli
from runner.execution import TrialResult


def make_spec(tmp_path, trials=1):
    path = tmp_path / "one.jsonl"
    path.write_text(json.dumps({"schema_version": 1, "id": "ONE", "scenario": "adv003", "policy_mode": "strict", "trials": trials}) + "\n", encoding="utf-8")
    return str(path)


def result(spec, *, trial_number, status="completed", trace_status="verified"):
    return TrialResult(spec.id, trial_number, status, 0 if status == "completed" else 2, 0.01, "", "", None, "uuid", "results/runner/uuid.jsonl", trace_status)


def test_binding_uses_repo_root_and_production_executor(monkeypatch):
    mocked = Mock(return_value="not-used")
    monkeypatch.setattr(cli, "subprocess_execute_trial", mocked)
    bound = cli.real_trial_executor()
    bound("spec", trial_number=1)
    mocked.assert_called_once_with("spec", trial_number=1, cwd=Path(cli.__file__).resolve().parent.parent)


def test_no_execute_does_not_call_injected_runner(tmp_path):
    mocked = Mock()
    assert cli.main([make_spec(tmp_path)], execute_trial=mocked, require_verified_trace=True) == 0
    mocked.assert_not_called()


def test_real_gate_requires_verified_trace(tmp_path):
    assert cli.main([make_spec(tmp_path), "--execute"], execute_trial=lambda spec, *, trial_number: result(spec, trial_number=trial_number, trace_status="missing"), require_verified_trace=True) == 1


@pytest.mark.parametrize("trace_status", ["missing", "invalid", "unverified"])
def test_unverified_trace_never_success_in_real_mode(tmp_path, trace_status):
    assert cli.main([make_spec(tmp_path), "--execute"], execute_trial=lambda spec, *, trial_number: result(spec, trial_number=trial_number, trace_status=trace_status), require_verified_trace=True) == 1


def test_verified_and_completed_is_process_success_not_security_success(tmp_path, capsys):
    assert cli.main([make_spec(tmp_path), "--execute"], execute_trial=lambda spec, *, trial_number: result(spec, trial_number=trial_number), require_verified_trace=True) == 0
    captured = capsys.readouterr().out
    assert "trace_status=verified" in captured
    assert "not security outcomes" in captured


def test_nonzero_process_with_verified_trace_returns_error(tmp_path):
    assert cli.main([make_spec(tmp_path), "--execute"], execute_trial=lambda spec, *, trial_number: result(spec, trial_number=trial_number, status="nonzero_exit"), require_verified_trace=True) == 1


def test_limit_rejection_precedes_any_executor_call(tmp_path):
    mocked = Mock()
    with pytest.raises(SystemExit) as exc:
        cli.main([make_spec(tmp_path, trials=2), "--execute"], execute_trial=mocked, require_verified_trace=True)
    assert exc.value.code == 2
    mocked.assert_not_called()


def test_missing_executor_remains_fail_closed_when_imported(tmp_path):
    with pytest.raises(SystemExit) as exc:
        cli.main([make_spec(tmp_path), "--execute"], require_verified_trace=True)
    assert exc.value.code == 2
