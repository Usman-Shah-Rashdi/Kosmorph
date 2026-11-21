import json
import os
import shutil
import tempfile
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from .contracts import ConflictPolicy, MoveOperation


def resolve_destination(dest: Path, policy: ConflictPolicy) -> Path | None:
    """Resolve output path collisions according to policy. Returns None if skipped."""
    if not dest.exists():
        return dest
    if policy == ConflictPolicy.OVERWRITE:
        return dest
    if policy == ConflictPolicy.SKIP:
        return None

    counter = 1
    while True:
        candidate = dest.with_name(f"{dest.stem} ({counter}){dest.suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


@contextmanager
def atomic_output(target_path: Path):
    """Write to a temp file in the target directory and atomically replace on success."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=target_path.parent, prefix=".kosmos_")
    os.close(fd)
    tmp_path = Path(tmp_name)
    try:
        yield tmp_path
        if not tmp_path.exists() or tmp_path.stat().st_size == 0:
            raise RuntimeError(f"Validation failed: generated empty output for {target_path.name}")
        os.replace(tmp_path, target_path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


class UndoJournal:
    """
    Non-sequential, ID-based operation history and safe rollback journal.
    Adapted from FOLDR's git-style revert model: any recorded operation can be
    undone independently by ID without forcing strict LIFO order, and empty
    tool-created directories are cleaned up safely.
    """

    def __init__(self, journal_path: Path | None = None):
        if journal_path is None:
            journal_path = Path.home() / ".kosmos" / "history.json"
        self.journal_path = journal_path
        self.journal_path.parent.mkdir(parents=True, exist_ok=True)

    def record(
        self,
        action_name: str,
        operations: list[MoveOperation],
        *,
        base_dir: Path | None = None,
        created_directories: list[Path] | None = None,
    ) -> str | None:
        if not operations:
            return None
        op_id = uuid.uuid4().hex[:8]
        history = self._load()
        history.append({
            "id": op_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action_name,
            "base": str(base_dir) if base_dir else str(operations[0].source.parent),
            "total_files": len(operations),
            "created_directories": [str(d) for d in (created_directories or [])],
            "moves": [
                {
                    "source": str(op.source),
                    "destination": str(op.destination),
                    "category": op.category,
                }
                for op in operations
            ],
        })
        self.journal_path.write_text(json.dumps(history[-50:], indent=2), encoding="utf-8")
        return op_id

    def list_entries(self, limit: int = 25) -> list[dict]:
        return list(reversed(self._load()))[:limit]

    def undo(self, operation_id: str | None = None, dry_run: bool = False) -> tuple[int, int, list[str]]:
        history = self._load()
        if not history:
            return 0, 0, ["No operations available to undo."]

        target_idx: int | None = None
        if operation_id:
            for i in range(len(history) - 1, -1, -1):
                if history[i].get("id") == operation_id or history[i].get("id", "").startswith(operation_id):
                    target_idx = i
                    break
            if target_idx is None:
                return 0, 0, [f"No history entry found matching ID '{operation_id}'."]
        else:
            target_idx = len(history) - 1

        entry = history[target_idx]
        created_dirs = {Path(d) for d in entry.get("created_directories", []) if d}
        restored_dirs: set[Path] = set()
        restored, skipped, logs = 0, 0, []

        for move in reversed(entry.get("moves", [])):
            src = Path(move["source"])
            dst = Path(move["destination"])
            if not dst.exists():
                skipped += 1
                logs.append(f"Skipped {dst.name} (not at expected location)")
                continue
            if dry_run:
                restored += 1
                logs.append(f"Preview restore: {dst.parent.name}/{dst.name} -> {src}")
                continue

            target = src
            if target.exists():
                n = 1
                while target.exists():
                    target = src.with_name(f"{src.stem}_restored({n}){src.suffix}")
                    n += 1

            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(dst), str(target))
                restored += 1
                restored_dirs.add(dst.parent)
            except OSError as exc:
                skipped += 1
                logs.append(f"Error restoring {dst.name}: {exc}")

        if not dry_run:
            # Remove only Kosmos-created directories that became empty after restoration
            cleanup_candidates = {
                folder
                for folder in created_dirs
                if any(folder == r_dir or folder in r_dir.parents for r_dir in restored_dirs)
            }
            for folder in sorted(cleanup_candidates, key=lambda p: len(p.parts), reverse=True):
                try:
                    if not folder.is_symlink() and folder.is_dir() and not any(folder.iterdir()):
                        folder.rmdir()
                except OSError:
                    pass

            history.pop(target_idx)
            self.journal_path.write_text(json.dumps(history, indent=2), encoding="utf-8")

        return restored, skipped, logs

    def _load(self) -> list[dict]:
        if not self.journal_path.exists():
            return []
        try:
            return json.loads(self.journal_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
