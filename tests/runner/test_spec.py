import json

import pytest

from runner.spec import SpecError, load_specs, validate_spec

VALID = {"schema_version": 1, "id": "EXP-001", "scenario": "adv003", "policy_mode": "strict", "trials": 3}


def test_valid_spec():
    spec = validate_spec(VALID)
    assert (spec.id, spec.scenario, spec.policy_mode, spec.trials) == ("EXP-001", "adv003", "strict", 3)


@pytest.mark.parametrize("patch", [
    {"schema_version": 2}, {"schema_version": True}, {"trials": True},
    {"trials": 0}, {"trials": 101}, {"trials": 1.2},
    {"scenario": "model001"}, {"scenario": []}, {"policy_mode": "unknown"}, {"policy_mode": []},
    {"id": "bad/path"}, {"id": ""}, {"id": "EXP 001"},
    {"id": "é"},
])
def test_rejects_invalid_values(patch):
    with pytest.raises(SpecError):
        validate_spec({**VALID, **patch})


def test_missing_and_unknown_fields():
    with pytest.raises(SpecError, match="missing fields"):
        validate_spec({k: v for k, v in VALID.items() if k != "id"})
    with pytest.raises(SpecError, match="unknown fields"):
        validate_spec({**VALID, "command": "anything"})


def test_rejects_non_object():
    with pytest.raises(SpecError, match="JSON object"):
        validate_spec([VALID])


def test_loads_batch_with_blank_lines(tmp_path):
    path = tmp_path / "batch.jsonl"
    second = {**VALID, "id": "EXP-002", "policy_mode": "opa"}
    path.write_text(json.dumps(VALID) + "\n\n" + json.dumps(second) + "\n", encoding="utf-8")
    specs = load_specs(path)
    assert [spec.id for spec in specs] == ["EXP-001", "EXP-002"]
    assert sum(spec.trials for spec in specs) == 6


def test_duplicate_ids_report_line(tmp_path):
    path = tmp_path / "batch.jsonl"
    path.write_text(json.dumps(VALID) + "\n" + json.dumps(VALID) + "\n", encoding="utf-8")
    with pytest.raises(SpecError, match=r":2: duplicate experiment id"):
        load_specs(path)


def test_invalid_json_reports_line(tmp_path):
    path = tmp_path / "batch.jsonl"
    path.write_text(json.dumps(VALID) + "\nnot-json\n", encoding="utf-8")
    with pytest.raises(SpecError, match=r":2:"):
        load_specs(path)


def test_empty_batch_rejected(tmp_path):
    path = tmp_path / "batch.jsonl"
    path.write_text("\n", encoding="utf-8")
    with pytest.raises(SpecError, match="no experiments"):
        load_specs(path)
