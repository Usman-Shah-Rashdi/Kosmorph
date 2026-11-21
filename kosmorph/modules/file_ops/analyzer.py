"""Two-pass SHA-256 duplicate detection & cleanup adapted from FOLDR v0.2.1."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from pathlib import Path

from kosmorph.core.contracts import TaskContext, TaskResult
from kosmorph.core.registry import register_action

_CHUNK = 65_536


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            while chunk := f.read(_CHUNK):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return ""


def _pick_keep(files: list[Path], strategy: str) -> Path:
    if strategy == "keep-newest":
        return max(files, key=lambda p: p.stat().st_mtime if p.exists() else 0)
    if strategy == "keep-oldest":
        return min(files, key=lambda p: p.stat().st_mtime if p.exists() else float("inf"))
    if strategy == "keep-largest":
        return max(files, key=lambda p: p.stat().st_size if p.exists() else 0)
    return files[0]


@register_action(
    id="files.find_duplicates",
    name="Find / Clean Duplicate Files",
    category="File Management",
    description="Two-pass duplicate detector grouping by byte size before SHA-256 hashing.",
    supports_dry_run=True,
)
def find_duplicates(
    ctx: TaskContext,
    target_dir: str | Path,
    recursive: bool = True,
    strategy: str = "keep-newest",
    delete_duplicates: bool = False,
) -> TaskResult:
    root = Path(target_dir).resolve()
    iterator = root.rglob("*") if recursive else root.iterdir()
    by_size: dict[int, list[Path]] = defaultdict(list)

    for item in iterator:
        if item.is_file() and not item.is_symlink():
            try:
                by_size[item.stat().st_size].append(item)
            except OSError:
                continue

    candidates = [group for group in by_size.values() if len(group) > 1]
    duplicates: dict[str, list[str]] = {}
    to_remove: list[Path] = []
    total = len(candidates)

    for idx, group in enumerate(candidates, start=1):
        if ctx.is_cancelled():
            break
        ctx.report(idx, total, f"Hashing collision group {idx}/{total}")
        by_hash: dict[str, list[Path]] = defaultdict(list)
        for file in group:
            digest = _sha256(file)
            if digest:
                by_hash[digest].append(file)
        for digest, matching in by_hash.items():
            if len(matching) > 1:
                duplicates[digest] = [str(p) for p in matching]
                keep = _pick_keep(matching, strategy)
                to_remove.extend(p for p in matching if p != keep)

    deleted_count = 0
    errors: list[str] = []
    if delete_duplicates and not ctx.dry_run:
        for p in to_remove:
            try:
                p.unlink()
                deleted_count += 1
            except OSError as exc:
                errors.append(f"{p.name}: {exc}")

    dup_count = len(to_remove)
    msg = (
        f"Deleted {deleted_count} of {dup_count} duplicate file(s)."
        if (delete_duplicates and not ctx.dry_run)
        else f"Found {dup_count} duplicate file(s) across {len(duplicates)} group(s)."
    )
    return TaskResult(
        success=len(errors) == 0,
        message=msg,
        errors=errors,
        metadata={
            "duplicates": duplicates,
            "removable": [str(p) for p in to_remove],
            "deleted_count": deleted_count,
        },
    )
