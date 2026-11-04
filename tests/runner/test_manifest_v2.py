"""M5.5-B2: manifest versioning and campaign provenance, no agent calls."""
import json
from dataclasses import replace
from pathlib import Path

import pytest

from runner.analysis import TraceAnalysis
from runner.execution import TrialResult
from runner.manifest import ManifestError, build_trial_manifest
from runner.metadata import ReproducibilityMetadata
from runner.persistence import verify_manifest_trace
from runner.pipeline import run_recorded_batch
from runner.spec import ExperimentSpec


def artifacts(tmp_path):
    spec = ExperimentSpec(1, "ONE", "adv003", "strict", 1)
    trace = tmp_path / "run-1.jsonl"
    trace.write_text(json.dumps({"run_id": "run-1", "event": "oracle_evaluation", "data": {
        "evaluation": {"after": [{"invariant_id": "AUDIT-001", "status": "satisfied"}]}}}) + "\n"
        + json.dumps({"run_id": "run-1", "event": "round_limit_reached", "data": {"limit": 6}}) + "\n")
    result = TrialResult("ONE", 1, "completed", 0, .25, "", "", None, "run-1", str(trace), "verified")
    analysis = TraceAnalysis("run-1", 2, {"oracle_evaluation": 1, "round_limit_reached": 1},
                             "round_limit_reached", 0, 0, 0, 1, (), {"AUDIT-001": "satisfied"}, "observed", ())
    meta = ReproducibilityMetadata("a" * 40, False, {"scenarios/adv003.json": "b" * 64},
                                   {"source": "agent_source_ast_literals", "MODEL": "example"},
                                   ("effective_runtime_not_attested",))
    return spec, result, analysis, meta


def test_v1_backward_compatible(tmp_path):
    spec, result, analysis, _ = artifacts(tmp_path)
    doc = build_trial_manifest(spec, result, analysis, trace_sha256="a" * 64).to_dict()
    assert doc["manifest_version"] == 1
    assert "reproducibility" not in doc


def test_v2_records_provenance_and_limits(tmp_path):
    spec, result, analysis, meta = artifacts(tmp_path)
    doc = build_trial_manifest(spec, result, analysis, trace_sha256="a" * 64, metadata=meta).to_dict()
    assert doc["manifest_version"] == 2
    assert doc["execution"]["git_commit"] == "a" * 40
    assert doc["execution"]["git_dirty"] is False
    assert doc["reproducibility"]["file_sha256"]["scenarios/adv003.json"] == "b" * 64
    assert "effective_runtime_not_attested" in doc["limitations"]
    assert "git_commit_unknown" not in doc["limitations"]
    json.dumps(doc)


def test_v2_does_not_claim_runtime_attestation(tmp_path):
    spec, result, analysis, meta = artifacts(tmp_path)
    doc = build_trial_manifest(spec, result, analysis, trace_sha256="a" * 64, metadata=meta).to_dict()
    assert doc["reproducibility"]["declared_runtime"]["source"] == "agent_source_ast_literals"
    assert "effective_runtime_not_attested" in doc["limitations"]


@pytest.mark.parametrize("mutation,reason", [
    (lambda m: replace(m, file_sha256={"x": None}), "invalid_input_hashes"),
    (lambda m: replace(m, file_sha256={}), "invalid_input_hashes"),
    (lambda m: replace(m, file_sha256={"x": "A" * 64}), "invalid_input_hashes"),
])
def test_invalid_metadata_rejected(tmp_path, mutation, reason):
    spec, result, analysis, meta = artifacts(tmp_path)
    with pytest.raises(ManifestError, match=reason):
        build_trial_manifest(spec, result, analysis, trace_sha256="a" * 64, metadata=mutation(meta))


def test_conflicting_commit_rejected(tmp_path):
    spec, result, analysis, meta = artifacts(tmp_path)
    with pytest.raises(ManifestError, match="git_commit_conflict"):
        build_trial_manifest(spec, result, analysis, trace_sha256="a" * 64,
                             git_commit="c" * 40, metadata=meta)


def test_pipeline_v2_persisted_from_pretrial_snapshot(tmp_path):
    spec, result, _, meta = artifacts(tmp_path)
    captures = []

    def collect(root, s):
        captures.append(s.id)
        return meta

    def execute(s, *, trial_number):
        assert captures == ["ONE", "ONE"]  # reference + immediately before process
        return result

    output = run_recorded_batch([spec], execute, manifest_dir=tmp_path / "manifests",
                                consistency_root=tmp_path, collect=collect)
    assert output.publications[0].status == "persisted"
    path = Path(output.publications[0].manifest_file)
    doc = json.loads(path.read_text())
    assert doc["manifest_version"] == 2
    assert doc["reproducibility"]["git_commit"] == "a" * 40
    assert verify_manifest_trace(path)


def test_pipeline_without_gate_still_v1(tmp_path):
    spec, result, _, _ = artifacts(tmp_path)
    output = run_recorded_batch([spec], lambda *_a, **_kw: result,
                                manifest_dir=tmp_path / "manifests")
    doc = json.loads(Path(output.publications[0].manifest_file).read_text())
    assert doc["manifest_version"] == 1
    assert "reproducibility" not in doc
