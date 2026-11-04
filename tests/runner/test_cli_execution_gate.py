"""M5.3.2-A CLI gate tests: no real agent or subprocess launches."""

import json

import pytest

from runner.__main__ import main
from runner.execution import TrialResult


def spec_file(tmp_path, trials=1, entries=1):
    path = tmp_path / "batch.jsonl"
    path.write_text("\n".join(json.dumps({
        "schema_version": 1,
        "id": f"EXP-{i}",
        "scenario": "adv003",
        "policy_mode": "strict",
        "trials": trials,
    }) for i in range(entries)) + "\n", encoding="utf-8")
    return str(path)


def fake_result(spec, *, trial_number, status="completed"):
    return TrialResult(spec.id, trial_number, status, 0 if status == "completed" else 1, 0.01, "", "")


def test_default_dry_run(tmp_path, capsys):
    calls = []
    path = spec_file(tmp_path, trials=3)
    assert main([path], execute_trial=lambda *a, **kw: calls.append((a, kw))) == 0
    assert calls == []
    assert "3 planned trials" in capsys.readouterr().out


def test_dry_run_does_not_apply_execution_cap(tmp_path):
    assert main([spec_file(tmp_path, trials=3)]) == 0


def test_execute_is_fail_closed_without_executor(tmp_path):
    with pytest.raises(SystemExit) as exc:
        main([spec_file(tmp_path), "--execute"])
    assert exc.value.code == 2


def test_execute_preflight_limit_before_executor(tmp_path):
    calls = []
    with pytest.raises(SystemExit) as exc:
        main([spec_file(tmp_path, trials=2), "--execute"], execute_trial=lambda *a, **kw: calls.append(1))
    assert exc.value.code == 2
    assert calls == []


def test_global_limit_counts_all_records(tmp_path):
    calls = []
    with pytest.raises(SystemExit) as exc:
        main([spec_file(tmp_path, entries=2), "--execute"], execute_trial=lambda *a, **kw: calls.append(1))
    assert exc.value.code == 2
    assert calls == []


def test_explicit_single_trial_with_fake_executor(tmp_path, capsys):
    calls = []
    def fake(spec, *, trial_number):
        calls.append((spec.id, trial_number))
        return fake_result(spec, trial_number=trial_number)
    assert main([spec_file(tmp_path), "--execute"], execute_trial=fake) == 0
    assert calls == [("EXP-0", 1)]
    assert "execution_status=completed" in capsys.readouterr().out


def test_explicit_multi_trial_with_fake_executor(tmp_path):
    calls = []
    def fake(spec, *, trial_number):
        calls.append((spec.id, trial_number))
        return fake_result(spec, trial_number=trial_number)
    assert main([spec_file(tmp_path, trials=2), "--execute", "--max-trials", "2"], execute_trial=fake) == 0
    assert calls == [("EXP-0", 1), ("EXP-0", 2)]


def test_nonzero_execution_status_returns_one(tmp_path):
    assert main([spec_file(tmp_path), "--execute"], execute_trial=lambda spec, *, trial_number: fake_result(spec, trial_number=trial_number, status="nonzero_exit")) == 1


@pytest.mark.parametrize("arg", ["0", "-1", "wrong"])
def test_invalid_max_trials(tmp_path, arg):
    with pytest.raises(SystemExit) as exc:
        main([spec_file(tmp_path), "--max-trials", arg])
    assert exc.value.code == 2


def test_invalid_spec_never_calls_executor(tmp_path):
    path = tmp_path / "bad.jsonl"
    path.write_text("not json\n", encoding="utf-8")
    calls = []
    with pytest.raises(SystemExit) as exc:
        main([str(path), "--execute"], execute_trial=lambda *a, **kw: calls.append(1))
    assert exc.value.code == 2
    assert calls == []
