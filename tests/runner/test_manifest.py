"""M5.4.2-A pure builder tests: no trace reads, subprocesses, or model calls."""
import json
from dataclasses import replace

import pytest

from runner.analysis import TraceAnalysis
from runner.execution import TrialResult
from runner.manifest import ManifestError, build_trial_manifest
from runner.spec import ExperimentSpec

HASH = "a" * 64
COMMIT = "b" * 40


@pytest.fixture
def artifacts():
    spec = ExperimentSpec(1, "EXP-ADV003-STRICT", "adv003", "strict", 3)
    result = TrialResult("EXP-ADV003-STRICT", 2, "completed", 0, 1.25,
                         "SECRET STDOUT", "SECRET STDERR", run_id="run-1",
                         trace_file="results/runner/run-1.jsonl", trace_status="verified")
    analysis = TraceAnalysis("run-1", 6, {"model_response": 2, "oracle_evaluation": 1},
                             "round_limit_reached", 2, 1, 1, 1, ("AUDIT-001",),
                             {"AUDIT-001": "violated"}, "observed", ())
    return spec, result, analysis


def build(items, **kwargs):
    return build_trial_manifest(*items, trace_sha256=HASH, **kwargs)


def test_builds_correlated_manifest(artifacts):
    doc = build(artifacts, git_commit=COMMIT, git_dirty=False).to_dict()
    assert doc["manifest_version"] == 1
    assert doc["experiment"]["trial_number"] == 2
    assert doc["execution"]["git_commit"] == COMMIT
    assert doc["evidence"]["run_id"] == "run-1"
    assert doc["evidence"]["sha256"] == HASH
    assert doc["analysis"]["ever_violated"] == ["AUDIT-001"]
    assert doc["analysis"]["last_observed_invariants"]["AUDIT-001"] == "violated"
    assert doc["analysis"]["termination"] == "round_limit_reached"
    assert doc["limitations"] == ()
    json.dumps(doc)


def test_does_not_copy_raw_stdout_stderr(artifacts):
    doc = json.dumps(build(artifacts).to_dict())
    assert "SECRET" not in doc


def test_unknown_source_version_is_explicit(artifacts):
    doc = build(artifacts)
    assert "git_commit_unknown" in doc.limitations
    assert "git_dirty_unknown" in doc.limitations


def test_nonzero_process_can_have_attributed_evidence(artifacts):
    s, r, a = artifacts
    doc = build((s, replace(r, status="nonzero_exit", returncode=1), a))
    assert doc.execution["status"] == "nonzero_exit"
    assert "process_not_completed" in doc.limitations
    assert doc.analysis["ever_violated"] == ["AUDIT-001"]


def test_incomplete_analysis_preserves_uncertainty(artifacts):
    s, r, a = artifacts
    doc = build((s, r, replace(a, evidence_status="incomplete", limitations=("no_termination_marker",))))
    assert "no_termination_marker" in doc.limitations
    assert doc.analysis["evidence_status"] == "incomplete"


def test_malformed_incomplete_analysis_is_marked(artifacts):
    s, r, a = artifacts
    doc = build((s, r, replace(a, evidence_status="incomplete")))
    assert "incomplete_evidence" in doc.limitations


def test_snapshot_detaches_mutable_observations(artifacts):
    s, r, a = artifacts
    manifest = build((s, r, a))
    a.event_counts["model_response"] = 999
    a.last_observed_invariants["AUDIT-001"] = "satisfied"
    assert manifest.analysis["event_counts"]["model_response"] == 2
    assert manifest.analysis["last_observed_invariants"]["AUDIT-001"] == "violated"
    snapshot = manifest.to_dict()
    snapshot["analysis"]["last_observed_invariants"]["AUDIT-001"] = "unknown"
    assert manifest.analysis["last_observed_invariants"]["AUDIT-001"] == "violated"


@pytest.mark.parametrize(("mutation", "error"), [
    (lambda s, r, a: (s, replace(r, experiment_id="OTHER"), a), "experiment_id_mismatch"),
    (lambda s, r, a: (s, replace(r, trial_number=4), a), "trial_number_out_of_range"),
    (lambda s, r, a: (s, replace(r, trial_number=True), a), "trial_number_out_of_range"),
    (lambda s, r, a: (s, replace(r, trace_status="missing"), a), "trace_not_attributed"),
    (lambda s, r, a: (s, replace(r, run_id=None), a), "missing_run_id"),
    (lambda s, r, a: (s, r, replace(a, run_id="OTHER")), "run_id_mismatch"),
    (lambda s, r, a: (s, replace(r, trace_file=None), a), "missing_trace_file"),
    (lambda s, r, a: (s, replace(r, status="invented"), a), "invalid_execution_status"),
])
def test_rejects_incompatible_artifacts(artifacts, mutation, error):
    with pytest.raises(ManifestError, match=error):
        build(mutation(*artifacts))


@pytest.mark.parametrize("digest", ["", "A" * 64, "f" * 63, "x" * 64, None])
def test_rejects_invalid_hash(artifacts, digest):
    with pytest.raises(ManifestError, match="invalid_trace_sha256"):
        build_trial_manifest(*artifacts, trace_sha256=digest)


@pytest.mark.parametrize("extra", [
    {"git_commit": "not-a-sha"},
    {"git_commit": "A" * 40},
    {"git_dirty": 0},
])
def test_rejects_invalid_git_metadata(artifacts, extra):
    with pytest.raises(ManifestError):
        build(artifacts, **extra)
