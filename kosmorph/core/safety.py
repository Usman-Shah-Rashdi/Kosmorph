import json
import os
import shutil
import tempfile
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
    fd, tmp_name = tempfile.mkstemp(dir=target_path.parent, prefix=".kosmorph_")
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
    """Persists file move/rename batches to disk so Undo works across sessions."""

    def __init__(self, journal_path: Path | None = None):
        if journal_path is None:
            journal_path = Path.home() / ".kosmorph" / "undo_journal.json"
        self.journal_path = journal_path
        self.journal_path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, action_name: str, operations: list[MoveOperation]) -> None:
        if not operations:
            return
        history = self._load()
        history.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action_name,
            "moves": [[str(op.source), str(op.destination)] for op in operations],
        })
        self.journal_path.write_text(json.dumps(history[-25:], indent=2), encoding="utf-8")

    def undo_last(self) -> tuple[int, int, list[str]]:
        history = self._load()
        if not history:
            return 0, 0, ["No operations available to undo."]

        entry = history.pop()
        restored, skipped, logs = 0, 0, []

        for src_str, dst_str in reversed(entry["moves"]):
            src, dst = Path(src_str), Path(dst_str)
            if not dst.exists() or src.exists():
                skipped += 1
                logs.append(f"Skipped {dst.name} (missing or source already occupied)")
                continue
            src.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(dst), str(src))
            restored += 1

        self.journal_path.write_text(json.dumps(history, indent=2), encoding="utf-8")
        return restored, skipped, logs

    def _load(self) -> list[dict]:
        if not self.journal_path.exists():
            return []
        try:
            return json.loads(self.journal_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
