"""Core file organization engine adapted from FOLDR v0.2.1."""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from kosmorph.core.contracts import ConflictPolicy, MoveOperation, TaskContext, TaskResult
from kosmorph.core.registry import register_action
from kosmorph.core.safety import UndoJournal, resolve_destination
from .config_loader import load_category_template
from .ignore import IgnoreRules
from .mime_detect import category_from_mime


def _classify_file(
    file_path: Path,
    strategy: str,
    template: dict[str, dict],
    smart_mime: bool = False,
) -> tuple[str, str]:
    """Return (category_name, destination_subfolder)."""
    if strategy == "date":
        mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
        folder = f"{mtime.year}/{mtime.strftime('%m-%B')}"
        return "By Date", folder

    if strategy == "size":
        size = file_path.stat().st_size
        if size < 100 * 1024:
            return "Small", "Small (<100KB)"
        if size < 10 * 1024 * 1024:
            return "Medium", "Medium (100KB-10MB)"
        if size < 100 * 1024 * 1024:
            return "Large", "Large (10MB-100MB)"
        return "Huge", "Huge (>100MB)"

    # Smart MIME override (catches spoofed extensions like photo.png.exe or extensionless files)
    if smart_mime:
        mime_cat = category_from_mime(file_path)
        if mime_cat and mime_cat in template:
            return mime_cat, template[mime_cat]["folder"]

    ext = file_path.suffix.lower()
    lower_name = file_path.name.lower()
    for cat_name, data in template.items():
        exts = data.get("ext", set())
        if ext in exts or lower_name in exts:
            return cat_name, data["folder"]

    misc = template.get("Misc", {"folder": "Misc"})
    return "Misc", misc["folder"]


def _collect_subdirs(
    base: Path,
    max_depth: int | None,
    follow_symlinks: bool,
    root_dest_folders: set[Path],
    ignore: IgnoreRules,
    root_base: Path,
    _depth: int = 1,
    _seen: set[int] | None = None,
) -> list[Path]:
    if _seen is None:
        _seen = set()

    collected: list[Path] = []
    try:
        children = list(base.iterdir())
    except PermissionError:
        return collected

    for child in children:
        if not child.is_dir() or child in root_dest_folders:
            continue
        try:
            rel = str(child.relative_to(root_base))
        except ValueError:
            rel = child.name
        if ignore.matches_dir(child, rel):
            continue

        if child.is_symlink():
            if not follow_symlinks:
                continue
            try:
                inode = child.resolve().stat().st_ino
            except OSError:
                continue
            if inode in _seen:
                continue
            _seen.add(inode)

        collected.append(child)
        if max_depth is None or _depth < max_depth:
            collected.extend(
                _collect_subdirs(
                    child, max_depth, follow_symlinks,
                    root_dest_folders, ignore, root_base,
                    _depth + 1, _seen,
                )
            )
    return collected


def plan_organization(
    folder: str | Path,
    *,
    recursive: bool = False,
    max_depth: int | None = None,
    follow_symlinks: bool = False,
    strategy: str = "extension",
    smart_mime: bool = False,
    extra_ignore: list[str] | None = None,
    no_ignore: bool = False,
    config_path: Path | None = None,
    conflict_policy: ConflictPolicy = ConflictPolicy.RENAME,
) -> tuple[list[MoveOperation], dict[str, int]]:
    base = Path(folder).resolve()
    if not base.is_dir():
        raise NotADirectoryError(f"Directory not found: {base}")

    template, _ = load_category_template(config_path)
    root_dest_folders = {base / data["folder"] for data in template.values()}
    ignore = IgnoreRules(base, extra_patterns=extra_ignore, disabled=no_ignore)

    dirs_to_scan = [base]
    if recursive:
        dirs_to_scan.extend(
            _collect_subdirs(base, max_depth, follow_symlinks, root_dest_folders, ignore, base)
        )

    operations: list[MoveOperation] = []
    category_counts: dict[str, int] = {}

    for directory in dirs_to_scan:
        try:
            entries = list(directory.iterdir())
        except PermissionError:
            continue

        for entry in entries:
            if entry.is_dir() or entry.name.startswith("."):
                continue
            try:
                rel = str(entry.relative_to(base))
            except ValueError:
                rel = entry.name
            if ignore.matches_file(entry, rel):
                continue

            cat_name, dest_sub = _classify_file(entry, strategy, template, smart_mime=smart_mime)
            dest_dir = base / dest_sub
            raw_dest = dest_dir / entry.name

            try:
                if entry.resolve() == raw_dest.resolve():
                    continue
            except OSError:
                pass

            final_dest = resolve_destination(raw_dest, conflict_policy)
            if final_dest is not None and entry.resolve() != final_dest.resolve():
                category_counts[cat_name] = category_counts.get(cat_name, 0) + 1
                operations.append(
                    MoveOperation(
                        source=entry,
                        destination=final_dest,
                        reason=f"{strategy} -> {dest_sub}",
                        category=cat_name,
                    )
                )

    return operations, category_counts


@register_action(
    id="organizer.sort",
    name="Smart Folder Organizer",
    category="File Management",
    description="Sort files into 31 categories using extension, MIME magic, date, or size with Undo support.",
    supports_dry_run=True,
)
def organize_folder(
    ctx: TaskContext,
    target_dir: str | Path,
    recursive: bool = False,
    max_depth: int | None = None,
    follow_symlinks: bool = False,
    strategy: str = "extension",
    smart_mime: bool = False,
    extra_ignore: list[str] | None = None,
    no_ignore: bool = False,
    config_path: str | Path | None = None,
) -> TaskResult:
    base = Path(target_dir).resolve()
    cfg = Path(config_path) if config_path else None
    plan, counts = plan_organization(
        base,
        recursive=recursive,
        max_depth=max_depth,
        follow_symlinks=follow_symlinks,
        strategy=strategy,
        smart_mime=smart_mime,
        extra_ignore=extra_ignore,
        no_ignore=no_ignore,
        config_path=cfg,
        conflict_policy=ctx.conflict_policy,
    )

    if ctx.dry_run:
        return TaskResult(
            success=True,
            message=f"Preview: {len(plan)} file(s) ready to organize.",
            operations=plan,
            metadata={"categories": counts},
        )

    completed: list[MoveOperation] = []
    created_dirs: set[Path] = set()
    errors: list[str] = []
    total = len(plan)

    for idx, op in enumerate(plan, start=1):
        if ctx.is_cancelled():
            break
        ctx.report(idx, total, f"Moving {op.source.name} -> {op.destination.parent.name}/")
        try:
            if not op.destination.parent.exists():
                op.destination.parent.mkdir(parents=True, exist_ok=True)
                created_dirs.add(op.destination.parent)
            shutil.move(str(op.source), str(op.destination))
            completed.append(op)
        except OSError as exc:
            errors.append(f"{op.source.name}: {exc}")

    # Clean up any newly created folder that remained empty
    for folder in created_dirs:
        try:
            if folder.is_dir() and not any(folder.iterdir()):
                folder.rmdir()
        except OSError:
            pass

    op_id = None
    if completed:
        op_id = UndoJournal().record(
            "organizer.sort",
            completed,
            base_dir=base,
            created_directories=list(created_dirs),
        )

    return TaskResult(
        success=len(errors) == 0,
        message=f"Organized {len(completed)} of {total} file(s)." + (f" [Undo ID: {op_id}]" if op_id else ""),
        outputs=[op.destination for op in completed],
        operations=completed,
        errors=errors,
        metadata={"categories": counts, "undo_id": op_id},
    )
