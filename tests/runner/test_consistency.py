"""M5.5-B1: all synthetic; no agent subprocess or paid API usage."""
from dataclasses import replace

import pytest

from runner.consistency import CampaignConsistencyError, CampaignGate
from runner.execution import TrialResult
from runner.metadata import ReproducibilityMetadata
from runner.pipeline import run_recorded_batch
from runner.spec import ExperimentSpec


def spec(identifier="ONE", trials=2):
    return ExperimentSpec(1, identifier, "adv003", "strict", trials)


def snapshot(**changes):
    baseline = ReproducibilityMetadata("a" * 40, False,
        {"src/agent.py": "a" * 64, "scenarios/adv003.json": "b" * 64},
        {"MODEL": "test-model"}, ())
    return replace(baseline, **changes)


def test_stable_inputs_allow_two_trials(tmp_path):
    invocations = []
    def execute(s, *, trial_number):
        invocations.append(trial_number)
        return TrialResult(s.id, trial_number, "completed", 0, .01, "", "")
    record = run_recorded_batch([spec()], execute, manifest_dir=tmp_path,
        max_trials=2, consistency_root=tmp_path, collect=lambda _root, _spec: snapshot())
    assert invocations == [1, 2]
    assert [p.status for p in record.publications] == ["not_attempted", "not_attempted"]


def test_modified_policy_or_scenario_blocks_second_trial(tmp_path):
    invoked = []
    calls = 0
    def collect(_root, _spec):
        nonlocal calls
        calls += 1
        if calls == 3:
            return snapshot(file_sha256={"src/agent.py": "a" * 64, "scenarios/adv003.json": "c" * 64})
        return snapshot()
    def execute(s, *, trial_number):
        invoked.append(trial_number)
        return TrialResult(s.id, trial_number, "completed", 0, .01, "", "")
    with pytest.raises(CampaignConsistencyError, match="experimental_inputs_changed"):
        run_recorded_batch([spec()], execute, manifest_dir=tmp_path,
            max_trials=2, consistency_root=tmp_path, collect=collect)
    assert invoked == [1]


def test_changed_git_commit_blocks_before_first_trial(tmp_path):
    calls = 0
    def collect(_root, _spec):
        nonlocal calls
        calls += 1
        return snapshot(git_commit=("a" if calls == 1 else "b") * 40)
    invoked = []
    with pytest.raises(CampaignConsistencyError, match="git_commit_changed"):
        run_recorded_batch([spec(trials=1)], lambda *_a, **_kw: invoked.append(1),
            manifest_dir=tmp_path, max_trials=1, consistency_root=tmp_path, collect=collect)
    assert not invoked


def test_dirty_flag_alone_does_not_stop_trial(tmp_path):
    baseline, current = snapshot(git_dirty=False), snapshot(git_dirty=True)
    calls = iter([baseline, current])
    gate = CampaignGate.capture(tmp_path, [spec()], collect=lambda *_: next(calls))
    assert gate.check(spec()) == current


@pytest.mark.parametrize("hashes", [{}, {"src/agent.py": None}])
def test_missing_relevant_input_is_fail_closed(tmp_path, hashes):
    with pytest.raises(CampaignConsistencyError, match="experimental_inputs_unavailable"):
        CampaignGate.capture(tmp_path, [spec()], collect=lambda *_: snapshot(file_sha256=hashes))


def test_missing_git_commit_is_fail_closed(tmp_path):
    with pytest.raises(CampaignConsistencyError, match="git_commit_unavailable"):
        CampaignGate.capture(tmp_path, [spec()], collect=lambda *_: snapshot(git_commit=None))


def test_declared_runtime_change_blocks(tmp_path):
    snaps = iter([snapshot(), snapshot(declared_runtime={"MODEL": "new-model"})])
    gate = CampaignGate.capture(tmp_path, [spec()], collect=lambda *_: next(snaps))
    with pytest.raises(CampaignConsistencyError, match="declared_runtime_changed"):
        gate.check(spec())


def test_multiple_conditions_get_independent_baselines(tmp_path):
    specs = [spec("BASE", 1), spec("OPA", 1)]
    seen = []
    def collect(_root, item):
        seen.append(item.id)
        return snapshot(file_sha256={"scenario": ("a" if item.id == "BASE" else "b") * 64})
    gate = CampaignGate.capture(tmp_path, specs, collect=collect)
    for item in specs:
        gate.check(item)
    assert seen == ["BASE", "OPA", "BASE", "OPA"]


def test_unknown_experiment_rejected(tmp_path):
    gate = CampaignGate.capture(tmp_path, [spec()], collect=lambda *_: snapshot())
    with pytest.raises(CampaignConsistencyError, match="unknown_experiment"):
        gate.check(spec("OTHER"))


def test_duplicate_id_rejected_before_collection(tmp_path):
    with pytest.raises(CampaignConsistencyError, match="duplicate_experiment_id"):
        CampaignGate.capture(tmp_path, [spec(), spec()], collect=lambda *_: snapshot())
