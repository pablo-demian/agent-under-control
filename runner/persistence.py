"""M5.4.2-B: snapshot, analyze and publish trial evidence without overwrites.

A SHA-256 digest detects changes relative to a captured snapshot; it does not
establish authenticity or prevent a hostile filesystem from racing publication.
"""

import hashlib
import json
import os
import tempfile
from pathlib import Path

from runner.analysis import analyze_trace
from runner.manifest import build_trial_manifest


class PersistenceError(ValueError):
    """The evidence changed or the manifest could not be safely published."""


def persist_trial_manifest(spec, result, destination, *, git_commit=None, git_dirty=None, metadata=None):
    """Analyze a single byte snapshot and publish a new manifest atomically.

    Requires verified attribution. Does not replace existing manifests. The
    trace is checked for changes immediately before publication; later changes
    remain detectable by comparing its bytes to the recorded digest.
    """
    if result.trace_status != "verified" or not result.trace_file or not result.run_id:
        raise PersistenceError("trace_not_attributed")

    trace = Path(result.trace_file)
    target = Path(destination)
    if not target.parent.is_dir():
        raise PersistenceError("missing_manifest_directory")

    try:
        snapshot = trace.read_bytes()
    except OSError as exc:
        raise PersistenceError("trace_unreadable") from exc
    digest = hashlib.sha256(snapshot).hexdigest()

    # analyze_trace currently accepts a path. Use a private temporary file of
    # *captured* bytes rather than reading the live trace a second time.
    with tempfile.TemporaryDirectory(prefix="auc-snapshot-") as directory:
        snapshot_path = Path(directory) / "trace.jsonl"
        snapshot_path.write_bytes(snapshot)
        analysis = analyze_trace(snapshot_path, expected_run_id=result.run_id)

    manifest = build_trial_manifest(
        spec, result, analysis, trace_sha256=digest,
        git_commit=git_commit, git_dirty=git_dirty, metadata=metadata,
    )
    content = (json.dumps(manifest.to_dict(), sort_keys=True, indent=2) + "\n").encode("utf-8")

    # Keep the publication temporary file in the destination filesystem.
    fd, temp_name = tempfile.mkstemp(prefix=".auc-manifest-", suffix=".tmp", dir=target.parent)
    temp = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())

        try:
            current = trace.read_bytes()
        except OSError as exc:
            raise PersistenceError("trace_changed_before_publish") from exc
        if current != snapshot:
            raise PersistenceError("trace_changed_before_publish")

        # os.link is atomic, create-only on the same filesystem: unlike
        # os.replace, it cannot silently overwrite a prior manifest.
        try:
            os.link(temp, target)
        except FileExistsError as exc:
            raise PersistenceError("manifest_already_exists") from exc
        except OSError as exc:
            raise PersistenceError("manifest_publish_failed") from exc
        # fsync directory: best-effort durability on supported POSIX systems.
        try:
            directory_fd = os.open(target.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except OSError:
            pass
    finally:
        temp.unlink(missing_ok=True)
    return manifest


def verify_manifest_trace(manifest_path):
    """Check that the referenced trace still matches the recorded bytes."""
    try:
        document = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
        evidence = document["evidence"]
        expected = evidence["sha256"]
        trace_path = Path(evidence["trace_file"])
        if not isinstance(expected, str) or len(expected) != 64:
            return False
        return hashlib.sha256(trace_path.read_bytes()).hexdigest() == expected
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return False
