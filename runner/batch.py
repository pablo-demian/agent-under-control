"""M5.3.1: sequential orchestration with an injected trial executor.

No subprocesses, model calls, trace attribution, or filesystem writes occur here.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from runner.execution import TrialResult
from runner.spec import ExperimentSpec

TrialExecutor = Callable[..., TrialResult]


@dataclass(frozen=True)
class BatchResult:
    results: tuple[TrialResult, ...]

    @property
    def attempted(self) -> int:
        return len(self.results)


def run_batch(
    specifications: Sequence[ExperimentSpec],
    execute: TrialExecutor,
    *,
    max_trials: int = 1,
) -> BatchResult:
    """Execute validated specifications in order, with a global trial cap.

    This cap is a preflight constraint, NOT a truncation instruction.
    Execution results never imply success or safety of agent actions.
    Unexpected executor exceptions propagate; no hidden retry is performed.
    """
    if type(max_trials) is not int or max_trials < 1:
        raise ValueError("invalid_max_trials")
    if not isinstance(specifications, (list, tuple)) or not specifications:
        raise ValueError("invalid_specifications")
    if any(not isinstance(spec, ExperimentSpec) for spec in specifications):
        raise TypeError("specifications_must_be_validated")
    ids = [spec.id for spec in specifications]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate_experiment_id")
    total = sum(spec.trials for spec in specifications)
    if total > max_trials:
        raise ValueError("batch_trial_limit_exceeded")

    results: list[TrialResult] = []
    for spec in specifications:
        for trial_number in range(1, spec.trials + 1):
            result = execute(spec, trial_number=trial_number)
            if not isinstance(result, TrialResult):
                raise TypeError("executor_must_return_trial_result")
            if result.experiment_id != spec.id or result.trial_number != trial_number:
                raise ValueError("executor_result_identity_mismatch")
            results.append(result)
    return BatchResult(results=tuple(results))
