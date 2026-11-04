"""End-to-end orchestration with synthetic processes and traces only."""
import json
from pathlib import Path

import pytest

from runner.execution import TrialResult
from runner.persistence import verify_manifest_trace
from runner.pipeline import run_recorded_batch
from runner.spec import ExperimentSpec


def spec(trials=1):
    return ExperimentSpec(1, "EXP-TEST", "adv003", "strict", trials)


def executor(tmp_path, *, status="completed", trace_status="verified"):
    def run(experiment, *, trial_number):
        run_id = f"trial-{trial_number}"
        trace = tmp_path / f"{run_id}.jsonl"
        trace.write_text("\n".join(json.dumps({"run_id": run_id, "event": event, "data": data}) for event, data in [
            ("oracle_evaluation", {"evaluation": {"after": [{"invariant_id": "AUDIT-001", "status": "violated"}]}}),
            ("round_limit_reached", {"limit": 6}),
        ]) + "\n", encoding="utf-8")
        return TrialResult(experiment.id, trial_number, status, 0 if status == "completed" else 2, 0.1, "", "", None, run_id, str(trace), trace_status)
    return run


def test_publishes_manifest_and_hash_matches(tmp_path):
    out = run_recorded_batch([spec()], executor(tmp_path), manifest_dir=tmp_path / "manifests")
    assert out.batch.attempted == 1
    pub = out.publications[0]
    assert pub.status == "persisted"
    assert verify_manifest_trace(pub.manifest_file)
    doc = json.loads(Path(pub.manifest_file).read_text())
    assert doc["analysis"]["ever_violated"] == ["AUDIT-001"]
    assert doc["execution"]["status"] == "completed"


def test_publishes_each_trial_before_next_execution(tmp_path):
    seen = []
    base = executor(tmp_path)
    directory = tmp_path / "manifests"
    def run(exp, *, trial_number):
        if trial_number == 2:
            assert (directory / "trial-1.manifest.json").exists()
        seen.append(trial_number)
        return base(exp, trial_number=trial_number)
    out = run_recorded_batch([spec(2)], run, manifest_dir=directory, max_trials=2)
    assert seen == [1, 2]
    assert [p.status for p in out.publications] == ["persisted", "persisted"]


def test_unverified_trace_is_not_published(tmp_path):
    directory = tmp_path / "manifests"
    out = run_recorded_batch([spec()], executor(tmp_path, trace_status="missing"), manifest_dir=directory)
    assert out.publications[0].status == "not_attempted"
    assert not directory.exists()


def test_nonzero_exit_can_have_valid_evidence(tmp_path):
    out = run_recorded_batch([spec()], executor(tmp_path, status="nonzero_exit"), manifest_dir=tmp_path / "manifests")
    assert out.batch.results[0].status == "nonzero_exit"
    assert out.publications[0].status == "persisted"


def test_duplicate_manifest_is_failure_not_overwrite(tmp_path):
    directory = tmp_path / "manifests"
    first = run_recorded_batch([spec()], executor(tmp_path), manifest_dir=directory)
    original = Path(first.publications[0].manifest_file).read_bytes()
    second = run_recorded_batch([spec()], executor(tmp_path), manifest_dir=directory)
    assert second.publications[0].status == "failed"
    assert Path(first.publications[0].manifest_file).read_bytes() == original


def test_preflight_aborts_before_executor_or_directory(tmp_path):
    calls = []
    with pytest.raises(ValueError, match="batch_trial_limit_exceeded"):
        run_recorded_batch([spec(2)], lambda *a, **k: calls.append(1), manifest_dir=tmp_path / "manifests")
    assert calls == []
    assert not (tmp_path / "manifests").exists()


def test_persistence_exception_is_reported(tmp_path):
    def broken(*args):
        raise OSError("do not show path or secrets")
    out = run_recorded_batch([spec()], executor(tmp_path), manifest_dir=tmp_path / "manifests", persist=broken)
    assert out.publications[0].status == "failed"
    assert out.publications[0].reason == "OSError"


def test_mismatched_executor_result_is_rejected_before_publishing(tmp_path):
    def wrong(s, *, trial_number):
        return TrialResult("WRONG", trial_number, "completed", 0, 0, "", "")
    with pytest.raises(ValueError, match="executor_result_identity_mismatch"):
        run_recorded_batch([spec()], wrong, manifest_dir=tmp_path / "manifests")
    assert not (tmp_path / "manifests").exists()
