import json
import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest

from runner.attribution import TraceIdentity, new_trace_identity, verify_trace
from runner.execution import execute_trial
from runner.spec import ExperimentSpec


@pytest.fixture
def spec():
    return ExperimentSpec(1, "EXP-ADV003-STRICT", "adv003", "strict", 1)


def test_identity_allocated_under_results_runner(tmp_path):
    identity = new_trace_identity(tmp_path)
    assert identity.path.parent == tmp_path / "results" / "runner"
    assert identity.path.name == f"{identity.run_id}.jsonl"
    assert identity.run_id != new_trace_identity(tmp_path).run_id


def test_missing_trace_is_not_attributed(tmp_path):
    identity = TraceIdentity("one", tmp_path / "missing.jsonl")
    assert verify_trace(identity) == "missing"


def test_valid_trace_matches_all_events(tmp_path):
    path = tmp_path / "trace.jsonl"
    path.write_text('\n'.join(json.dumps({"run_id": "one", "event": e}) for e in ("model_response", "agent_completed")) + '\n')
    assert verify_trace(TraceIdentity("one", path)) == "verified"


@pytest.mark.parametrize("contents", [
    "", "\n", "{garbage", '[]\n', '{"run_id":"other","event":"ok"}\n',
    '{"run_id":"one"}\n',
    '{"run_id":"one","event":"a"}\n{"run_id":"wrong","event":"b"}\n',
])
def test_invalid_trace_is_not_attributed(tmp_path, contents):
    path = tmp_path / "trace.jsonl"
    path.write_text(contents)
    assert verify_trace(TraceIdentity("one", path)) == "invalid"


def test_execute_assigns_explicit_identity_and_verifies_trace(monkeypatch, tmp_path, spec):
    def stub_run(*args, **kwargs):
        env = kwargs["env"]
        path = Path(env["AUC_TRACE_FILE"])
        assert path.parent == tmp_path / "results" / "runner"
        assert env["AUC_RUN_ID"] == path.stem
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"run_id": env["AUC_RUN_ID"], "event": "agent_completed"}) + "\n")
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(subprocess, "run", stub_run)
    result = execute_trial(spec, trial_number=1, cwd=tmp_path)
    assert result.status == "completed"
    assert result.trace_status == "verified"
    assert result.trace_file is not None
    assert result.run_id == Path(result.trace_file).stem


def test_successful_process_without_trace_is_not_verified(monkeypatch, tmp_path, spec):
    monkeypatch.setattr(subprocess, "run", Mock(return_value=subprocess.CompletedProcess([], 0, "", "")))
    result = execute_trial(spec, trial_number=1, cwd=tmp_path)
    assert result.status == "completed"
    assert result.trace_status == "missing"


def test_wrong_run_id_does_not_pass(monkeypatch, tmp_path, spec):
    def wrong_run(*args, **kwargs):
        target = Path(kwargs["env"]["AUC_TRACE_FILE"])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('{"run_id":"wrong","event":"agent_completed"}\n')
        return subprocess.CompletedProcess(args, 0, "", "")
    monkeypatch.setattr(subprocess, "run", wrong_run)
    assert execute_trial(spec, trial_number=1, cwd=tmp_path).trace_status == "invalid"


def test_timeout_does_not_claim_attribution(monkeypatch, tmp_path, spec):
    monkeypatch.setattr(subprocess, "run", Mock(side_effect=subprocess.TimeoutExpired("agent", 1)))
    result = execute_trial(spec, trial_number=1, cwd=tmp_path)
    assert result.status == "timeout"
    assert result.trace_status == "missing"
