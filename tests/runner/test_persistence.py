"""M5.4.2-B tests: synthetic traces and local temporary files only."""
import json
from dataclasses import replace

import pytest

from runner.execution import TrialResult
from runner.persistence import (
    PersistenceError,
    persist_trial_manifest,
    verify_manifest_trace,
)
from runner.spec import ExperimentSpec


def fixture_data(tmp_path):
    spec = ExperimentSpec(1, "EXP-001", "adv003", "strict", 1)
    run_id = "run-one"
    trace = tmp_path / "trace.jsonl"
    entries = [
        {"run_id": run_id, "event": "oracle_evaluation", "data": {"evaluation": {"after": [
            {"invariant_id": "AUDIT-001", "status": "violated"}
        ]}}},
        {"run_id": run_id, "event": "round_limit_reached", "data": {"limit": 6}},
    ]
    trace.write_text("".join(json.dumps(entry) + "\n" for entry in entries))
    result = TrialResult(spec.id, 1, "completed", 0, 1.2, "", "", None, run_id, str(trace), "verified")
    return spec, result, trace, tmp_path / "manifest.json"


def test_persists_manifest_and_verifies_content(tmp_path):
    spec, result, _trace, dest = fixture_data(tmp_path)
    manifest = persist_trial_manifest(spec, result, dest)
    doc = json.loads(dest.read_text())
    assert doc == manifest.to_dict() | {"limitations": list(manifest.limitations)}
    assert doc["analysis"]["ever_violated"] == ["AUDIT-001"]
    assert doc["analysis"]["termination"] == "round_limit_reached"
    assert verify_manifest_trace(dest) is True


def test_post_publish_tampering_is_detected(tmp_path):
    spec, result, trace, dest = fixture_data(tmp_path)
    persist_trial_manifest(spec, result, dest)
    trace.write_text(trace.read_text() + " \n")
    assert verify_manifest_trace(dest) is False


def test_existing_manifest_is_never_overwritten(tmp_path):
    spec, result, _trace, dest = fixture_data(tmp_path)
    dest.write_text("original")
    with pytest.raises(PersistenceError, match="manifest_already_exists"):
        persist_trial_manifest(spec, result, dest)
    assert dest.read_text() == "original"
    assert not list(tmp_path.glob(".auc-manifest-*"))


def test_unverified_trace_rejected_without_manifest(tmp_path):
    spec, result, _trace, dest = fixture_data(tmp_path)
    with pytest.raises(PersistenceError, match="trace_not_attributed"):
        persist_trial_manifest(spec, replace(result, trace_status="invalid"), dest)
    assert not dest.exists()


def test_trace_mutation_during_build_is_rejected(tmp_path, monkeypatch):
    spec, result, trace, dest = fixture_data(tmp_path)
    import runner.persistence as module
    real_build = module.build_trial_manifest

    def mutate(*args, **kwargs):
        manifest = real_build(*args, **kwargs)
        trace.write_text(trace.read_text() + "tampering\n")
        return manifest

    monkeypatch.setattr(module, "build_trial_manifest", mutate)
    with pytest.raises(PersistenceError, match="trace_changed_before_publish"):
        persist_trial_manifest(spec, result, dest)
    assert not dest.exists()
    assert not list(tmp_path.glob(".auc-manifest-*"))


def test_io_write_failure_cleans_temporary_file(tmp_path, monkeypatch):
    spec, result, _trace, dest = fixture_data(tmp_path)
    import runner.persistence as module

    def fail_fsync(_fd):
        raise OSError("simulated disk failure")

    monkeypatch.setattr(module.os, "fsync", fail_fsync)
    with pytest.raises(OSError, match="simulated disk failure"):
        persist_trial_manifest(spec, result, dest)
    assert not dest.exists()
    assert not list(tmp_path.glob(".auc-manifest-*"))


def test_missing_manifest_directory_rejected(tmp_path):
    spec, result, _trace, _dest = fixture_data(tmp_path)
    with pytest.raises(PersistenceError, match="missing_manifest_directory"):
        persist_trial_manifest(spec, result, tmp_path / "missing" / "manifest.json")


def test_missing_trace_is_rejected(tmp_path):
    spec, result, trace, dest = fixture_data(tmp_path)
    trace.unlink()
    with pytest.raises(PersistenceError, match="trace_unreadable"):
        persist_trial_manifest(spec, result, dest)


def test_invalid_trace_does_not_publish(tmp_path):
    spec, result, trace, dest = fixture_data(tmp_path)
    trace.write_text("not json\n")
    with pytest.raises(ValueError):
        persist_trial_manifest(spec, result, dest)
    assert not dest.exists()
