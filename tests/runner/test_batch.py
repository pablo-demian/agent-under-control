"""M5.3.1: orchestration tests never start subprocesses or call models."""

from unittest.mock import Mock

import pytest

from runner.batch import BatchResult, run_batch
from runner.execution import TrialResult
from runner.spec import ExperimentSpec


def spec(identifier="EXP-1", *, trials=1, policy="strict"):
    return ExperimentSpec(1, identifier, "adv003", policy, trials)


def result(s, *, trial_number, status="completed"):
    return TrialResult(
        s.id, trial_number, status,
        0 if status == "completed" else None, 0.01, "", "",
    )


def fake_executor(s, *, trial_number):
    return result(s, trial_number=trial_number)


def test_single_trial_returns_structured_batch():
    batch = run_batch([spec()], fake_executor)
    assert isinstance(batch, BatchResult)
    assert batch.attempted == 1
    assert batch.results[0].experiment_id == "EXP-1"
    assert batch.results[0].trial_number == 1


def test_multiple_specs_execute_in_file_order():
    calls = []

    def execute(s, *, trial_number):
        calls.append((s.id, trial_number))
        return result(s, trial_number=trial_number)

    batch = run_batch([spec("A", trials=2), spec("B", trials=2)], execute, max_trials=4)
    assert calls == [("A", 1), ("A", 2), ("B", 1), ("B", 2)]
    assert [r.trial_number for r in batch.results] == [1, 2, 1, 2]


def test_trial_cap_rejects_whole_batch_before_execution():
    execute = Mock()
    with pytest.raises(ValueError, match="batch_trial_limit_exceeded"):
        run_batch([spec("A", trials=2)], execute, max_trials=1)
    execute.assert_not_called()


@pytest.mark.parametrize("limit", [0, -1, True, 1.2, "3"])
def test_invalid_limit_rejected(limit):
    execute = Mock()
    with pytest.raises(ValueError, match="invalid_max_trials"):
        run_batch([spec()], execute, max_trials=limit)
    execute.assert_not_called()


@pytest.mark.parametrize("specs", [[], (), None, "not a sequence"])
def test_missing_or_invalid_spec_collection_rejected(specs):
    execute = Mock()
    with pytest.raises(ValueError, match="invalid_specifications"):
        run_batch(specs, execute)
    execute.assert_not_called()


def test_unvalidated_spec_rejected_before_execution():
    execute = Mock()
    with pytest.raises(TypeError, match="specifications_must_be_validated"):
        run_batch([spec(), {"id": "bad"}], execute, max_trials=2)
    execute.assert_not_called()


def test_duplicate_experiment_id_rejected():
    execute = Mock()
    with pytest.raises(ValueError, match="duplicate_experiment_id"):
        run_batch([spec("A"), spec("A")], execute, max_trials=2)
    execute.assert_not_called()


def test_timeout_result_does_not_stop_next_trial():
    def execute(s, *, trial_number):
        status = "timeout" if trial_number == 1 else "completed"
        return result(s, trial_number=trial_number, status=status)

    batch = run_batch([spec(trials=2)], execute, max_trials=2)
    assert [r.status for r in batch.results] == ["timeout", "completed"]


def test_executor_wrong_type_is_rejected():
    with pytest.raises(TypeError, match="executor_must_return_trial_result"):
        run_batch([spec()], lambda s, *, trial_number: {"status": "completed"})


def test_executor_identity_mismatch_is_rejected():
    def execute(s, *, trial_number):
        return TrialResult("OTHER", trial_number, "completed", 0, 0, "", "")

    with pytest.raises(ValueError, match="executor_result_identity_mismatch"):
        run_batch([spec()], execute)


def test_unexpected_executor_exception_propagates():
    def execute(s, *, trial_number):
        raise RuntimeError("unexpected failure")

    with pytest.raises(RuntimeError, match="unexpected failure"):
        run_batch([spec()], execute)
