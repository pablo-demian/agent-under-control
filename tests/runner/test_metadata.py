"""M5.5-A: no agent imports, no model calls, no Git mutations."""

import hashlib
import subprocess
from unittest.mock import Mock

import pytest

from runner.metadata import collect_metadata
from runner.spec import ExperimentSpec


@pytest.fixture
def project(tmp_path):
    files = {
        "src/agent.py": 'MODEL = "example-model"\nMAX_ROUNDS = 6\nMAX_TOOL_CALLS = 10\n',
        "src/harness.py": "# harness\n", "src/oracle.py": "# oracle\n",
        "runner/spec.py": "# spec\n", "runner/execution.py": "# exec\n",
        "runner/pipeline.py": "# pipeline\n", "runner/analysis.py": "# analysis\n",
        "runner/manifest.py": "# manifest\n", "runner/persistence.py": "# persistence\n",
        "scenarios/adv003.json": '{"payload": "test"}',
        "policies/agent.rego": "package agent\n",
    }
    for name, contents in files.items():
        file = tmp_path / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(contents, encoding="utf-8")
    return tmp_path


@pytest.fixture
def spec():
    return ExperimentSpec(1, "EX-1", "adv003", "opa", 1)


def git_stub(monkeypatch, *, dirty=False):
    def fake_run(cmd, **kwargs):
        if "rev-parse" in cmd:
            return subprocess.CompletedProcess(cmd, 0, "a" * 40 + "\n", "")
        if "status" in cmd:
            return subprocess.CompletedProcess(cmd, 0, " M src/agent.py\n" if dirty else "", "")
        raise AssertionError(cmd)
    monkeypatch.setattr(subprocess, "run", fake_run)


def test_captures_commit_and_clean_tree(project, spec, monkeypatch):
    git_stub(monkeypatch)
    result = collect_metadata(project, spec)
    assert result.git_commit == "a" * 40
    assert result.git_dirty is False
    assert result.declared_runtime["MODEL"] == "example-model"
    assert result.declared_runtime["MAX_ROUNDS"] == 6
    assert result.declared_runtime["source"] == "agent_source_ast_literals"
    assert "effective_runtime_not_attested" in result.limitations


def test_opa_and_scenario_file_hashed(project, spec, monkeypatch):
    git_stub(monkeypatch)
    result = collect_metadata(project, spec)
    content = (project / "scenarios/adv003.json").read_bytes()
    assert result.file_sha256["scenarios/adv003.json"] == hashlib.sha256(content).hexdigest()
    assert result.file_sha256["policies/agent.rego"] is not None


def test_strict_does_not_hash_opa(project, monkeypatch):
    git_stub(monkeypatch)
    spec = ExperimentSpec(1, "EX-1", "adv003", "strict", 1)
    assert "policies/agent.rego" not in collect_metadata(project, spec).file_sha256


def test_baseline_no_scenario_payload(project, monkeypatch):
    git_stub(monkeypatch)
    spec = ExperimentSpec(1, "EX-1", "baseline", "baseline", 1)
    assert not any(p.startswith("scenarios/") for p in collect_metadata(project, spec).file_sha256)


def test_dirty_tree_reported(project, spec, monkeypatch):
    git_stub(monkeypatch, dirty=True)
    result = collect_metadata(project, spec)
    assert result.git_dirty is True
    assert "working_tree_dirty" in result.limitations


def test_git_unavailable_is_unknown(project, spec, monkeypatch):
    monkeypatch.setattr(subprocess, "run", Mock(side_effect=FileNotFoundError()))
    result = collect_metadata(project, spec)
    assert result.git_commit is None and result.git_dirty is None
    assert "git_commit_unknown" in result.limitations


def test_git_timeout_is_unknown(project, spec, monkeypatch):
    monkeypatch.setattr(subprocess, "run", Mock(side_effect=subprocess.TimeoutExpired("git", 5)))
    assert collect_metadata(project, spec).git_dirty is None


def test_missing_file_is_unknown(project, spec, monkeypatch):
    git_stub(monkeypatch)
    (project / "policies/agent.rego").unlink()
    result = collect_metadata(project, spec)
    assert result.file_sha256["policies/agent.rego"] is None
    assert "file_unavailable:policies/agent.rego" in result.limitations


def test_static_parser_does_not_execute_code(project, spec, monkeypatch):
    git_stub(monkeypatch)
    (project / "src/agent.py").write_text(
        'MODEL = __import__("os").system("touch /tmp/auc-do-not-run")\n'
        'MAX_ROUNDS = 6\nMAX_TOOL_CALLS = 10\n', encoding="utf-8",
    )
    result = collect_metadata(project, spec)
    assert result.declared_runtime["MODEL"] is None
    assert "declared_runtime_incomplete" in result.limitations


def test_snapshot_dict_is_serializable(project, spec, monkeypatch):
    import json
    git_stub(monkeypatch)
    assert json.loads(json.dumps(collect_metadata(project, spec).to_dict()))["git_dirty"] is False


def test_no_subprocess_agent(project, spec, monkeypatch):
    calls = []
    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 1, "", "")
    monkeypatch.setattr(subprocess, "run", fake_run)
    collect_metadata(project, spec)
    assert all(cmd[0] == "git" for cmd in calls)


@pytest.mark.parametrize("bad", [None, {}, "x", 1])
def test_rejects_unvalidated_spec(project, bad):
    with pytest.raises(TypeError):
        collect_metadata(project, bad)


def test_invalid_root(spec, tmp_path):
    with pytest.raises(ValueError, match="invalid_project_root"):
        collect_metadata(tmp_path / "not-here", spec)
