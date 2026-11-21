"""Recursively-empty directory scanner & safe cleaner adapted from FOLDR v0.2.1."""

from __future__ import annotations

import os
from pathlib import Path

from kosmorph.core.contracts import TaskContext, TaskResult
from kosmorph.core.registry import register_action


def _is_recursively_empty(path: Path) -> bool:
    try:
        for root, dirs, files in os.walk(path):
            if files:
                return False
            dirs[:] = [d for d in dirs if not (Path(root) / d).is_symlink()]
        return True
    except PermissionError:
        return False


def scan_empty_dirs(base: Path, recursive: bool = True) -> list[Path]:
    found: list[Path] = []
    try:
        children = list(base.iterdir())
    except PermissionError:
        return found

    for child in children:
        if not child.is_dir() or child.is_symlink():
            continue
        if _is_recursively_empty(child):
            found.append(child)
        elif recursive:
            found.extend(scan_empty_dirs(child, recursive=True))

    found.sort(key=lambda p: len(p.parts), reverse=True)
    return found


@register_action(
    id="files.clean_empty_dirs",
    name="Scan & Remove Empty Directories",
    category="File Management",
    description="Find and safely remove recursively-empty folders (deepest-first, symlink-safe).",
    supports_dry_run=True,
)
def clean_empty_dirs(ctx: TaskContext, target_dir: str | Path, recursive: bool = True) -> TaskResult:
    base = Path(target_dir).resolve()
    found = scan_empty_dirs(base, recursive=recursive)

    if ctx.dry_run:
        return TaskResult(
            success=True,
            message=f"Preview: found {len(found)} empty director{'y' if len(found) == 1 else 'ies'}.",
            outputs=found,
        )

    removed: list[Path] = []
    errors: list[str] = []
    for idx, folder in enumerate(found, start=1):
        if ctx.is_cancelled():
            break
        ctx.report(idx, len(found), f"Removing {folder.name}/")
        if not folder.exists() or folder.is_symlink() or not _is_recursively_empty(folder):
            continue
        try:
            for root, _, files in os.walk(folder, topdown=False):
                if not files:
                    try:
                        os.rmdir(root)
                    except OSError:
                        pass
            if not folder.exists():
                removed.append(folder)
        except OSError as exc:
            errors.append(f"{folder}: {exc}")

    return TaskResult(
        success=len(errors) == 0,
        message=f"Removed {len(removed)} empty director{'y' if len(removed) == 1 else 'ies'}.",
        outputs=removed,
        errors=errors,
    )
