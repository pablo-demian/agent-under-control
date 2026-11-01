"""M5.4.1: side-effect-free, trial-level analysis of AUC event traces.

This is descriptive evidence analysis, not attribution, completeness proof,
or causal inference. Input must already be an attributed trace.
"""

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

_TERMINALS = frozenset({"agent_completed", "round_limit_reached"})
_STATES = frozenset({"satisfied", "violated", "unknown"})


class TraceAnalysisError(ValueError):
    """Malformed trace; cannot generate a trustworthy summary."""


@dataclass(frozen=True)
class TraceAnalysis:
    run_id: str
    event_count: int
    event_counts: dict[str, int]
    termination: str  # agent_completed | round_limit_reached | tool_budget_exceeded | unknown
    requests: int
    executions: int
    rejections: int
    oracle_evaluations: int
    ever_violated: tuple[str, ...]
    last_observed_invariants: dict[str, str]
    evidence_status: str  # observed | incomplete
    limitations: tuple[str, ...]


def analyze_trace(path: str | Path, *, expected_run_id: str | None = None) -> TraceAnalysis:
    """Parse and summarize one trace without calling the agent or writing files.

    Observed evidence is not proof of completeness or of causal attribution.
    The last oracle observation is not necessarily the final system state.
    """
    events: list[dict] = []
    try:
        with Path(path).open(encoding="utf-8") as stream:
            for line_no, line in enumerate(stream, 1):
                if not line.strip():
                    raise TraceAnalysisError(f"line {line_no}: blank record")
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise TraceAnalysisError(f"line {line_no}: invalid JSON") from exc
                if not isinstance(record, dict):
                    raise TraceAnalysisError(f"line {line_no}: expected object")
                if not isinstance(record.get("run_id"), str) or not record["run_id"]:
                    raise TraceAnalysisError(f"line {line_no}: missing run_id")
                if not isinstance(record.get("event"), str) or not record["event"]:
                    raise TraceAnalysisError(f"line {line_no}: missing event")
                if not isinstance(record.get("data"), dict):
                    raise TraceAnalysisError(f"line {line_no}: expected data object")
                events.append(record)
    except (OSError, UnicodeError) as exc:
        raise TraceAnalysisError(f"unable to read trace: {exc}") from exc

    if not events:
        raise TraceAnalysisError("empty trace")
    run_id = events[0]["run_id"]
    if expected_run_id is not None and run_id != expected_run_id:
        raise TraceAnalysisError("run_id mismatch")
    if any(record["run_id"] != run_id for record in events):
        raise TraceAnalysisError("mixed run_ids")

    counts = Counter(record["event"] for record in events)
    terminals = [record["event"] for record in events if record["event"] in _TERMINALS]
    budget_exceeded = any(
        record["event"] == "tool_rejected"
        and record["data"].get("reason") == "tool_budget_exceeded"
        for record in events
    )
    limitations: list[str] = []
    if len(terminals) > 1 or (terminals and budget_exceeded):
        termination = "unknown"
        limitations.append("conflicting_termination_markers")
    elif terminals:
        termination = terminals[0]
    elif budget_exceeded:
        termination = "tool_budget_exceeded"
    else:
        termination = "unknown"
        limitations.append("no_termination_marker")

    ever_violated: set[str] = set()
    last: dict[str, str] = {}
    for record in events:
        if record["event"] != "oracle_evaluation":
            continue
        evaluation = record["data"].get("evaluation")
        if not isinstance(evaluation, dict) or not isinstance(evaluation.get("after"), list):
            raise TraceAnalysisError("oracle_evaluation missing evaluation.after")
        current: dict[str, str] = {}
        for entry in evaluation["after"]:
            if not isinstance(entry, dict):
                raise TraceAnalysisError("malformed oracle invariant")
            invariant_id, status = entry.get("invariant_id"), entry.get("status")
            if not isinstance(invariant_id, str) or not invariant_id or status not in _STATES:
                raise TraceAnalysisError("invalid oracle invariant identity/status")
            if invariant_id in current:
                raise TraceAnalysisError("duplicate invariant in oracle observation")
            current[invariant_id] = status
            if status == "violated":
                ever_violated.add(invariant_id)
        last.update(current)

    if not counts["oracle_evaluation"]:
        limitations.append("no_oracle_observations")
    if termination == "unknown":
        limitations.append("termination_unknown")
    # Do not assert completeness: even a terminated trace can omit some events.
    return TraceAnalysis(
        run_id=run_id,
        event_count=len(events),
        event_counts=dict(counts),
        termination=termination,
        requests=counts["tool_requested"],
        executions=counts["tool_executed"],
        rejections=counts["tool_rejected"],
        oracle_evaluations=counts["oracle_evaluation"],
        ever_violated=tuple(sorted(ever_violated)),
        last_observed_invariants=last,
        evidence_status="incomplete" if limitations else "observed",
        limitations=tuple(limitations),
    )
