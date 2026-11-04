"""M5.5-B1: bounded pre-trial consistency checks, not a filesystem sandbox."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from runner.metadata import ReproducibilityMetadata, collect_metadata
from runner.spec import ExperimentSpec


class CampaignConsistencyError(ValueError):
    """Relevant campaign inputs changed or could not be observed reliably."""


Collector = Callable[[str | Path, ExperimentSpec], ReproducibilityMetadata]


@dataclass
class CampaignGate:
    root: Path
    baselines: dict[str, ReproducibilityMetadata]
    collect: Collector

    @classmethod
    def capture(
        cls,
        root: str | Path,
        specs: Sequence[ExperimentSpec],
        *,
        collect: Collector = collect_metadata,
    ) -> "CampaignGate":
        if not specs or any(not isinstance(s, ExperimentSpec) for s in specs):
            raise CampaignConsistencyError("invalid_campaign_specifications")
        if len({s.id for s in specs}) != len(specs):
            raise CampaignConsistencyError("duplicate_experiment_id")
        root = Path(root).resolve()
        snapshots = {spec.id: collect(root, spec) for spec in specs}
        if any(not isinstance(v, ReproducibilityMetadata) for v in snapshots.values()):
            raise CampaignConsistencyError("invalid_metadata_snapshot")
        for snapshot in snapshots.values():
            _require_known_inputs(snapshot)
        return cls(root, snapshots, collect)

    def check(self, spec: ExperimentSpec) -> ReproducibilityMetadata:
        if spec.id not in self.baselines:
            raise CampaignConsistencyError("unknown_experiment")
        current = self.collect(self.root, spec)
        if not isinstance(current, ReproducibilityMetadata):
            raise CampaignConsistencyError("invalid_metadata_snapshot")
        _require_known_inputs(current)
        baseline = self.baselines[spec.id]
        if baseline.file_sha256 != current.file_sha256:
            raise CampaignConsistencyError("experimental_inputs_changed")
        if baseline.declared_runtime != current.declared_runtime:
            raise CampaignConsistencyError("declared_runtime_changed")
        if baseline.git_commit != current.git_commit:
            raise CampaignConsistencyError("git_commit_changed")
        # Deliberately don't gate on git_dirty: unrelated untracked files,
        # including output artifacts, can change it without changing inputs.
        return current


def _require_known_inputs(snapshot: ReproducibilityMetadata) -> None:
    if not snapshot.file_sha256 or any(v is None for v in snapshot.file_sha256.values()):
        raise CampaignConsistencyError("experimental_inputs_unavailable")
    if snapshot.git_commit is None:
        raise CampaignConsistencyError("git_commit_unavailable")
