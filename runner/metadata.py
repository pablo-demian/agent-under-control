"""M5.5-A: read-only, preflight reproducibility metadata.

Git state and file hashes describe the snapshot at capture time, not proof
of the eventual subprocess runtime state or scientific reproducibility.
"""

import ast
import hashlib
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

from runner.spec import ExperimentSpec


@dataclass(frozen=True)
class ReproducibilityMetadata:
    git_commit: str | None
    git_dirty: bool | None
    file_sha256: dict[str, str | None]
    declared_runtime: dict[str, object | None]
    limitations: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str] | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True, text=True, timeout=5, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result if result.returncode == 0 else None


def _static_literals(path: Path) -> dict[str, object | None]:
    """Extract literal assignments without executing or importing agent code."""
    values: dict[str, object | None] = {"MODEL": None, "MAX_ROUNDS": None, "MAX_TOOL_CALLS": None}
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, SyntaxError):
        return values
    for statement in tree.body:
        if not isinstance(statement, ast.Assign):
            continue
        for target in statement.targets:
            if isinstance(target, ast.Name) and target.id in values:
                try:
                    literal = ast.literal_eval(statement.value)
                except (ValueError, TypeError, MemoryError, RecursionError):
                    continue
                if (target.id == "MODEL" and isinstance(literal, str)) or (
                    target.id != "MODEL" and type(literal) is int and literal > 0
                ):
                    values[target.id] = literal
    return values


def collect_metadata(root: str | Path, spec: ExperimentSpec) -> ReproducibilityMetadata:
    """Capture bounded, pre-execution information without imports or agent calls."""
    if not isinstance(spec, ExperimentSpec):
        raise TypeError("expected validated ExperimentSpec")
    root = Path(root).resolve()
    if not root.is_dir():
        raise ValueError("invalid_project_root")

    limitations: list[str] = []
    head = _git(root, "rev-parse", "--verify", "HEAD")
    commit = head.stdout.strip() if head is not None else None
    if commit is None or len(commit) != 40 or any(c not in "0123456789abcdef" for c in commit):
        commit = None
        limitations.append("git_commit_unknown")

    status = _git(root, "status", "--porcelain", "--untracked-files=normal", "--", ".")
    dirty = bool(status.stdout.strip()) if status is not None else None
    if dirty is None:
        limitations.append("git_dirty_unknown")
    elif dirty:
        limitations.append("working_tree_dirty")

    paths = ["src/agent.py", "src/harness.py", "src/oracle.py", "runner/spec.py", "runner/execution.py", "runner/pipeline.py", "runner/analysis.py", "runner/manifest.py", "runner/persistence.py"]
    if spec.scenario != "baseline":
        paths.append(f"scenarios/{spec.scenario}.json")
    if spec.policy_mode == "opa":
        paths.append("policies/agent.rego")

    hashes: dict[str, str | None] = {}
    for rel in paths:
        try:
            hashes[rel] = hashlib.sha256((root / rel).read_bytes()).hexdigest()
        except OSError:
            hashes[rel] = None
            limitations.append(f"file_unavailable:{rel}")

    declared = _static_literals(root / "src/agent.py")
    if any(v is None for v in declared.values()):
        limitations.append("declared_runtime_incomplete")
    limitations.append("effective_runtime_not_attested")
    limitations.append("preflight_snapshot_not_atomic_with_execution")

    return ReproducibilityMetadata(
        git_commit=commit, git_dirty=dirty, file_sha256=hashes,
        declared_runtime={"source": "agent_source_ast_literals", **declared},
        limitations=tuple(limitations),
    )
