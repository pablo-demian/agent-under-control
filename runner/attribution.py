"""Correlate a runner-owned trial identity with its JSONL trace.

This is evidence attribution, not provenance against a hostile filesystem,
trace completeness, or a security outcome.
"""

import json
import uuid
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TraceIdentity:
    run_id: str
    path: Path


def new_trace_identity(root: Path) -> TraceIdentity:
    """Allocate a fresh name; no filesystem mutation occurs here."""
    run_id = str(uuid.uuid4())
    return TraceIdentity(run_id, root / "results" / "runner" / f"{run_id}.jsonl")


def verify_trace(identity: TraceIdentity) -> str:
    """Return verified | missing | invalid for one trace, never guessing paths."""
    try:
        with identity.path.open(encoding="utf-8") as stream:
            seen = False
            for line in stream:
                if not line.strip():
                    return "invalid"
                record = json.loads(line)
                if not isinstance(record, dict) or record.get("run_id") != identity.run_id:
                    return "invalid"
                if not isinstance(record.get("event"), str) or not record["event"]:
                    return "invalid"
                seen = True
            return "verified" if seen else "invalid"
    except FileNotFoundError:
        return "missing"
    except (OSError, UnicodeError, json.JSONDecodeError):
        return "invalid"
