"""M5.2: execute exactly one validated trial in a fresh Python process.

No CLI execution switch or batch loop is provided in this increment.
"""

import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from runner.attribution import new_trace_identity, verify_trace
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
    run_id: str | None = None
    trace_file: str | None = None
    trace_status: str = "unverified"


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

    identity = new_trace_identity(root)
    identity.path.parent.mkdir(parents=True, exist_ok=True)
    if identity.path.exists():
        raise FileExistsError("runner trace path already exists")

    env = os.environ.copy()
    env.update({
        "AUC_SCENARIO": spec.scenario,
        "AUC_POLICY_MODE": spec.policy_mode,
        "AUC_RUN_ID": identity.run_id,
        "AUC_TRACE_FILE": str(identity.path),
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
            identity.run_id, str(identity.path), verify_trace(identity),
        )
    except OSError as exc:
        return TrialResult(
            spec.id, trial_number, "spawn_error", None,
            round(time.monotonic() - started, 3), "", "", type(exc).__name__,
            identity.run_id, str(identity.path), verify_trace(identity),
        )

    return TrialResult(
        spec.id, trial_number,
        "completed" if completed.returncode == 0 else "nonzero_exit",
        completed.returncode,
        round(time.monotonic() - started, 3),
        completed.stdout, completed.stderr,
        None, identity.run_id, str(identity.path), verify_trace(identity),
    )


def _text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value
