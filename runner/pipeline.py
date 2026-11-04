"""M5.4.3: persist evidence immediately after each completed trial invocation.

Publication failures are reported separately from subprocess and oracle outcomes.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from runner.analysis import TraceAnalysisError
from runner.batch import BatchResult, run_batch
from runner.consistency import CampaignGate, Collector, collect_metadata
from runner.execution import TrialResult
from runner.manifest import ManifestError
from runner.persistence import PersistenceError, persist_trial_manifest
from runner.spec import ExperimentSpec


@dataclass(frozen=True)
class PublicationResult:
    experiment_id: str
    trial_number: int
    status: str  # persisted | failed | not_attempted
    manifest_file: str | None
    reason: str | None = None


@dataclass(frozen=True)
class RecordedBatch:
    batch: BatchResult
    publications: tuple[PublicationResult, ...]


def run_recorded_batch(
    specifications: Sequence[ExperimentSpec],
    execute: Callable[..., TrialResult],
    *,
    manifest_dir: str | Path,
    max_trials: int = 1,
    persist: Callable[..., object] = persist_trial_manifest,
    consistency_root: str | Path | None = None,
    collect: Collector = collect_metadata,
) -> RecordedBatch:
    """Run sequentially and attempt publication after *each* trial.

    run_batch handles the entire-batch preflight before invoking this wrapper.
    Inability to publish does not silently change process execution status.
    """
    directory = Path(manifest_dir)
    published: list[PublicationResult] = []
    gate = (
        CampaignGate.capture(consistency_root, specifications, collect=collect)
        if consistency_root is not None else None
    )

    def execute_and_record(spec: ExperimentSpec, *, trial_number: int) -> TrialResult:
        metadata = gate.check(spec) if gate is not None else None
        trial = execute(spec, trial_number=trial_number)
        # Let run_batch reject malformed/mismatched executor results. Never
        # publish evidence associated with a different experiment/trial.
        if not isinstance(trial, TrialResult) or (
            trial.experiment_id != spec.id or trial.trial_number != trial_number
        ):
            return trial
        if trial.trace_status != "verified" or not trial.run_id or not trial.trace_file:
            published.append(PublicationResult(spec.id, trial_number, "not_attempted", None, "trace_not_verified"))
            return trial

        destination = directory / f"{trial.run_id}.manifest.json"
        try:
            directory.mkdir(parents=True, exist_ok=True)
            if metadata is None:
                persist(spec, trial, destination)
            else:
                persist(spec, trial, destination, metadata=metadata)
        except (PersistenceError, ManifestError, TraceAnalysisError, OSError, ValueError) as exc:
            # No trace contents, stdout or sensitive exception messages in the result.
            published.append(PublicationResult(spec.id, trial_number, "failed", str(destination), type(exc).__name__))
        else:
            published.append(PublicationResult(spec.id, trial_number, "persisted", str(destination)))
        return trial

    batch = run_batch(specifications, execute_and_record, max_trials=max_trials)
    return RecordedBatch(batch, tuple(published))
