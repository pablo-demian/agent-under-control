"""M5.1: strict, side-effect-free JSONL experiment specification parser."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
SCENARIOS = frozenset({"baseline", "adv001", "adv003"})
POLICY_MODES = frozenset({"baseline", "strict", "opa"})
MAX_TRIALS = 100
_FIELDS = frozenset({"schema_version", "id", "scenario", "policy_mode", "trials"})


class SpecError(ValueError):
    """Invalid experimental configuration. Includes the source line when known."""


@dataclass(frozen=True)
class ExperimentSpec:
    schema_version: int
    id: str
    scenario: str
    policy_mode: str
    trials: int


def validate_spec(raw: Any) -> ExperimentSpec:
    if not isinstance(raw, dict):
        raise SpecError("record must be a JSON object")

    missing = _FIELDS - raw.keys()
    unknown = raw.keys() - _FIELDS
    if missing:
        raise SpecError(f"missing fields: {', '.join(sorted(missing))}")
    if unknown:
        raise SpecError(f"unknown fields: {', '.join(sorted(unknown))}")

    if type(raw["schema_version"]) is not int or raw["schema_version"] != SCHEMA_VERSION:
        raise SpecError(f"unsupported schema_version: {raw['schema_version']!r}")
    identifier = raw["id"]
    if (not isinstance(identifier, str) or not identifier
            or len(identifier) > 80
            or not all(c.isascii() and (c.isalnum() or c in "_-") for c in identifier)):
        raise SpecError("id must contain 1-80 ASCII letters, digits, underscores or hyphens")
    if not isinstance(raw["scenario"], str) or raw["scenario"] not in SCENARIOS:
        raise SpecError(f"unsupported scenario: {raw['scenario']!r}")
    if not isinstance(raw["policy_mode"], str) or raw["policy_mode"] not in POLICY_MODES:
        raise SpecError(f"unsupported policy_mode: {raw['policy_mode']!r}")
    if type(raw["trials"]) is not int or not 1 <= raw["trials"] <= MAX_TRIALS:
        raise SpecError(f"trials must be an integer between 1 and {MAX_TRIALS}")

    return ExperimentSpec(**raw)


def load_specs(path: str | Path) -> list[ExperimentSpec]:
    """Validate every nonempty line; never launch processes or mutate files."""
    specs: list[ExperimentSpec] = []
    seen: set[str] = set()
    with Path(path).open(encoding="utf-8") as stream:
        for lineno, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                spec = validate_spec(record)
                if spec.id in seen:
                    raise SpecError(f"duplicate experiment id: {spec.id}")
            except (json.JSONDecodeError, SpecError) as exc:
                raise SpecError(f"{path}:{lineno}: {exc}") from exc
            seen.add(spec.id)
            specs.append(spec)
    if not specs:
        raise SpecError(f"{path}: no experiments defined")
    return specs
