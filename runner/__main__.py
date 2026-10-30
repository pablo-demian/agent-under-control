"""M5.3.2-A: dry-run CLI with a fail-closed execution gate.

Real subprocess execution remains disconnected until trace attribution is implemented.
"""

import argparse
from collections.abc import Callable, Sequence

from runner.batch import run_batch
from runner.execution import TrialResult
from runner.spec import SpecError, load_specs


def main(
    argv: Sequence[str] | None = None,
    *,
    execute_trial: Callable[..., TrialResult] | None = None,
) -> int:
    parser = argparse.ArgumentParser(description="Validate and preview an AUC JSONL experiment batch")
    parser.add_argument("spec", help="Path to JSONL batch")
    parser.add_argument("--execute", action="store_true", help="Request execution (unavailable until trace attribution is implemented)")
    parser.add_argument("--max-trials", type=int, default=1, help="Maximum permitted trials, not a truncation count (default: 1)")
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

    if total > args.max_trials:
        parser.error(f"batch has {total} trials, exceeds --max-trials={args.max_trials}; no trials started")
    if execute_trial is None:
        parser.error("real execution disabled until trace attribution is implemented; no trials started")

    result = run_batch(specs, execute_trial, max_trials=args.max_trials)
    for trial in result.results:
        print(f"{trial.experiment_id} trial={trial.trial_number} execution_status={trial.status} returncode={trial.returncode}")
    print(f"Attempted {result.attempted} trials; execution status is not a security outcome.")
    return 0 if all(trial.status == "completed" for trial in result.results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
