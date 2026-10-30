"""M5.2 contract tests. All subprocesses are mocked."""

import subprocess
import sys
from unittest.mock import Mock

import pytest

from runner.execution import execute_trial
from runner.spec import ExperimentSpec


@pytest.fixture
def spec():
    return ExperimentSpec(1, "EXP-ADV003-STRICT", "adv003", "strict", 3)


def test_one_trial_uses_explicit_process_arguments(monkeypatch, tmp_path, spec):
    runner = Mock(return_value=subprocess.CompletedProcess([], 0, "ok", ""))
    monkeypatch.setattr(subprocess, "run", runner)
    monkeypatch.setenv("AUC_SCENARIO", "baseline")
    monkeypatch.setenv("AUC_POLICY_MODE", "opa")

    result = execute_trial(spec, trial_number=2, cwd=tmp_path)

    runner.assert_called_once()
    args, kwargs = runner.call_args
    assert args[0] == [sys.executable, "-m", "src.agent"]
    assert kwargs["cwd"] == tmp_path.resolve()
    assert kwargs["env"]["AUC_SCENARIO"] == "adv003"
    assert kwargs["env"]["AUC_POLICY_MODE"] == "strict"
    assert kwargs["capture_output"] is True
    assert kwargs["timeout"] == 180
    assert result.status == "completed"
    assert result.returncode == 0
    assert result.stdout == "ok"
    assert result.experiment_id == spec.id
    assert result.trial_number == 2
    # The parent process environment must remain unchanged.
    assert __import__("os").environ["AUC_SCENARIO"] == "baseline"


def test_nonzero_exit_is_not_a_success(monkeypatch, tmp_path, spec):
    monkeypatch.setattr(subprocess, "run", Mock(return_value=subprocess.CompletedProcess([], 4, "", "failed")))
    result = execute_trial(spec, trial_number=1, cwd=tmp_path)
    assert (result.status, result.returncode, result.stderr) == ("nonzero_exit", 4, "failed")


def test_timeout_captures_partial_output(monkeypatch, tmp_path, spec):
    monkeypatch.setattr(subprocess, "run", Mock(side_effect=subprocess.TimeoutExpired("agent", 2, output=b"partial", stderr=b"timeout")))
    result = execute_trial(spec, trial_number=1, cwd=tmp_path, timeout_seconds=2)
    assert result.status == "timeout"
    assert result.returncode is None
    assert result.stdout == "partial"
    assert result.stderr == "timeout"


def test_spawn_error_is_classified(monkeypatch, tmp_path, spec):
    monkeypatch.setattr(subprocess, "run", Mock(side_effect=FileNotFoundError("python missing")))
    result = execute_trial(spec, trial_number=1, cwd=tmp_path)
    assert result.status == "spawn_error"
    assert result.error_type == "FileNotFoundError"


@pytest.mark.parametrize("trial_number", [0, 4, True, 1.5])
def test_invalid_trial_number_cannot_launch(monkeypatch, tmp_path, spec, trial_number):
    runner = Mock()
    monkeypatch.setattr(subprocess, "run", runner)
    with pytest.raises(ValueError, match="trial_number_out_of_range"):
        execute_trial(spec, trial_number=trial_number, cwd=tmp_path)
    runner.assert_not_called()


@pytest.mark.parametrize("timeout", [0, -1, True, 1.5])
def test_invalid_timeout_cannot_launch(monkeypatch, tmp_path, spec, timeout):
    runner = Mock()
    monkeypatch.setattr(subprocess, "run", runner)
    with pytest.raises(ValueError, match="invalid_timeout"):
        execute_trial(spec, trial_number=1, cwd=tmp_path, timeout_seconds=timeout)
    runner.assert_not_called()


def test_invalid_working_directory_cannot_launch(monkeypatch, tmp_path, spec):
    runner = Mock()
    monkeypatch.setattr(subprocess, "run", runner)
    with pytest.raises(ValueError, match="invalid_working_directory"):
        execute_trial(spec, trial_number=1, cwd=tmp_path / "missing")
    runner.assert_not_called()


def test_unvalidated_spec_cannot_launch(monkeypatch, tmp_path):
    runner = Mock()
    monkeypatch.setattr(subprocess, "run", runner)
    with pytest.raises(TypeError, match="validated ExperimentSpec"):
        execute_trial({"id": "something"}, trial_number=1, cwd=tmp_path)
    runner.assert_not_called()
