"""M5.2: execute exactly one validated trial in a fresh Python process.

No CLI execution switch or batch loop is provided in this increment.
"""

import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from runner.spec import ExperimentSpec

DEFAULT_TIMEOUT_SECONDS = 180


@dataclass(frozen=True)
class TrialResult:
    experiment_id: str
    trial_number: int
    status: str  # completed | nonzero_exit | timeout | spawn_error
    returncode: int | None
    elapsed_seconds: float
    stdout: str
    stderr: str
    error_type: str | None = None


def execute_trial(
    spec: ExperimentSpec,
    *,
    trial_number: int,
    cwd: str | Path,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> TrialResult:
    """Launch one process. 'completed' means exit code 0, NOT agent safety.

    Does not discover or attribute trace files; this belongs to M5.4.
    """
    if not isinstance(spec, ExperimentSpec):
        raise TypeError("spec must be a validated ExperimentSpec")
    if type(trial_number) is not int or not 1 <= trial_number <= spec.trials:
        raise ValueError("trial_number_out_of_range")
    if type(timeout_seconds) is not int or timeout_seconds <= 0:
        raise ValueError("invalid_timeout")

    root = Path(cwd).resolve()
    if not root.is_dir():
        raise ValueError("invalid_working_directory")

    env = os.environ.copy()
    env.update({
        "AUC_SCENARIO": spec.scenario,
        "AUC_POLICY_MODE": spec.policy_mode,
    })

    started = time.monotonic()
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "src.agent"],
            cwd=root,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return TrialResult(
            spec.id, trial_number, "timeout", None,
            round(time.monotonic() - started, 3),
            _text(exc.stdout), _text(exc.stderr), "TimeoutExpired",
        )
    except OSError as exc:
        return TrialResult(
            spec.id, trial_number, "spawn_error", None,
            round(time.monotonic() - started, 3), "", "", type(exc).__name__,
        )

    return TrialResult(
        spec.id, trial_number,
        "completed" if completed.returncode == 0 else "nonzero_exit",
        completed.returncode,
        round(time.monotonic() - started, 3),
        completed.stdout, completed.stderr,
    )


def _text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value
