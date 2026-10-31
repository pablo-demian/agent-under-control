"""AUC experimental CLI: dry-run default, explicitly gated real execution."""

import argparse
from collections.abc import Callable, Sequence
from functools import partial
from pathlib import Path

from runner.batch import run_batch
from runner.execution import TrialResult
from runner.execution import execute_trial as subprocess_execute_trial
from runner.spec import SpecError, load_specs


def real_trial_executor() -> Callable[..., TrialResult]:
    """Bind subprocess execution to this repository, not the caller's CWD."""
    root = Path(__file__).resolve().parent.parent
    return partial(subprocess_execute_trial, cwd=root)


def main(
    argv: Sequence[str] | None = None,
    *,
    execute_trial: Callable[..., TrialResult] | None = None,
    require_verified_trace: bool = False,
) -> int:
    parser = argparse.ArgumentParser(description="Validate or execute an AUC JSONL batch")
    parser.add_argument("spec", help="Path to JSONL batch")
    parser.add_argument("--execute", action="store_true", help="Explicitly launch agent subprocesses (may use paid API calls)")
    parser.add_argument("--max-trials", type=int, default=1, help="Global trial limit, not a truncation count (default: 1)")
    args = parser.parse_args(argv)

    if args.max_trials < 1:
        parser.error("--max-trials must be a positive integer")
    try:
        specs = load_specs(args.spec)
    except (OSError, UnicodeError, SpecError) as exc:
        parser.error(f"invalid experiment batch: {exc}")

    total = sum(spec.trials for spec in specs)
    if not args.execute:
        for spec in specs:
            print(f"{spec.id}: scenario={spec.scenario} policy={spec.policy_mode} trials={spec.trials}")
        print(f"Validated {len(specs)} experiments / {total} planned trials.")
        print("Dry run only: no agents or subprocesses started.")
        return 0

    # Entire batch is checked *before* the executor is invoked.
    if total > args.max_trials:
        parser.error(f"batch has {total} trials, exceeds --max-trials={args.max_trials}; no trials started")
    if execute_trial is None:
        parser.error("execution requires an explicitly connected executor; no trials started")

    result = run_batch(specs, execute_trial, max_trials=args.max_trials)
    for trial in result.results:
        print(
            f"{trial.experiment_id} trial={trial.trial_number} "
            f"execution_status={trial.status} returncode={trial.returncode} "
            f"trace_status={trial.trace_status} run_id={trial.run_id} "
            f"trace_file={trial.trace_file}"
        )
    print(f"Attempted {result.attempted} trials; execution and trace verification are not security outcomes.")
    return 0 if all(
        trial.status == "completed"
        and (not require_verified_trace or trial.trace_status == "verified")
        for trial in result.results
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main(execute_trial=real_trial_executor(), require_verified_trace=True))
