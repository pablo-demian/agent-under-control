"""M5.4.2-A: build a trial manifest from validated experimental observations.

Pure transformation: no filesystem, subprocess, environment, or model access.
The SHA-256 digest is supplied by the evidence collection layer (M5.4.2-B).
"""

import re
from dataclasses import asdict, dataclass

from runner.analysis import TraceAnalysis
from runner.execution import TrialResult
from runner.spec import ExperimentSpec

MANIFEST_VERSION = 1
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_EXECUTION_STATUSES = frozenset({"completed", "nonzero_exit", "timeout", "spawn_error"})


class ManifestError(ValueError):
    """The supplied artifacts cannot be safely correlated."""


@dataclass(frozen=True)
class TrialManifest:
    manifest_version: int
    experiment: dict
    execution: dict
    evidence: dict
    analysis: dict
    limitations: tuple[str, ...]

    def to_dict(self) -> dict:
        """Return a serializable snapshot detached from mutable input values."""
        return asdict(self)


def build_trial_manifest(
    spec: ExperimentSpec,
    result: TrialResult,
    analysis: TraceAnalysis,
    *,
    trace_sha256: str,
    git_commit: str | None = None,
    git_dirty: bool | None = None,
) -> TrialManifest:
    """Correlate existing observations; never infer a security outcome from exit 0.

    Callers must first verify attribution, analyze exactly those trace bytes,
    and compute the SHA-256 on that same snapshot. This function does not
    attest to filesystem authenticity or prove trace completeness.
    """
    if not isinstance(spec, ExperimentSpec) or not isinstance(result, TrialResult):
        raise TypeError("expected ExperimentSpec and TrialResult")
    if not isinstance(analysis, TraceAnalysis):
        raise TypeError("expected TraceAnalysis")
    if result.experiment_id != spec.id:
        raise ManifestError("experiment_id_mismatch")
    if type(result.trial_number) is not int or not 1 <= result.trial_number <= spec.trials:
        raise ManifestError("trial_number_out_of_range")
    if result.status not in _EXECUTION_STATUSES:
        raise ManifestError("invalid_execution_status")
    if result.trace_status != "verified":
        raise ManifestError("trace_not_attributed")
    if not isinstance(result.run_id, str) or not result.run_id:
        raise ManifestError("missing_run_id")
    if result.run_id != analysis.run_id:
        raise ManifestError("run_id_mismatch")
    if not isinstance(result.trace_file, str) or not result.trace_file:
        raise ManifestError("missing_trace_file")
    if not isinstance(trace_sha256, str) or _SHA256.fullmatch(trace_sha256) is None:
        raise ManifestError("invalid_trace_sha256")
    if (git_commit is not None and (
        not isinstance(git_commit, str) or re.fullmatch(r"[0-9a-f]{40}", git_commit) is None
    )):
        raise ManifestError("invalid_git_commit")
    if git_dirty is not None and type(git_dirty) is not bool:
        raise ManifestError("invalid_git_dirty")
    if analysis.evidence_status not in {"observed", "incomplete"}:
        raise ManifestError("invalid_evidence_status")

    limitations = list(analysis.limitations)
    if analysis.evidence_status == "incomplete" and not limitations:
        limitations.append("incomplete_evidence")
    if result.status != "completed":
        limitations.append("process_not_completed")
    if git_commit is None:
        limitations.append("git_commit_unknown")
    if git_dirty is None:
        limitations.append("git_dirty_unknown")

    return TrialManifest(
        manifest_version=MANIFEST_VERSION,
        experiment={
            "schema_version": spec.schema_version,
            "id": spec.id,
            "scenario": spec.scenario,
            "policy_mode": spec.policy_mode,
            "planned_trials": spec.trials,
            "trial_number": result.trial_number,
        },
        execution={
            "status": result.status,
            "returncode": result.returncode,
            "elapsed_seconds": result.elapsed_seconds,
            "error_type": result.error_type,
            "git_commit": git_commit,
            "git_dirty": git_dirty,
        },
        evidence={
            "run_id": result.run_id,
            "trace_file": result.trace_file,
            "attribution": result.trace_status,
            "sha256": trace_sha256,
            "hash_algorithm": "sha256",
        },
        analysis={
            "run_id": analysis.run_id,
            "termination": analysis.termination,
            "evidence_status": analysis.evidence_status,
            "event_count": analysis.event_count,
            "event_counts": dict(analysis.event_counts),
            "requests": analysis.requests,
            "executions": analysis.executions,
            "rejections": analysis.rejections,
            "oracle_evaluations": analysis.oracle_evaluations,
            "ever_violated": list(analysis.ever_violated),
            "last_observed_invariants": dict(analysis.last_observed_invariants),
            "limitations": list(analysis.limitations),
        },
        limitations=tuple(dict.fromkeys(limitations)),
    )
