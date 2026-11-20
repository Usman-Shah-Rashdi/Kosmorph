import shutil
from datetime import datetime
from pathlib import Path
from kosmorph.core.contracts import ConflictPolicy, MoveOperation, TaskContext, TaskResult
from kosmorph.core.registry import register_action
from kosmorph.core.safety import UndoJournal, resolve_destination
from .rules import DEFAULT_CATEGORIES, detect_category_by_magic, is_ignored, load_ignore_patterns


def _classify_file(
    file_path: Path,
    strategy: str,
    categories: dict[str, set[str]],
    use_magic_fallback: bool = True,
) -> str:
    if strategy == "date":
        mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
        return f"{mtime.year}/{mtime.strftime('%m-%B')}"

    if strategy == "size":
        size = file_path.stat().st_size
        if size < 100 * 1024:
            return "Small (<100KB)"
        if size < 10 * 1024 * 1024:
            return "Medium (100KB-10MB)"
        if size < 100 * 1024 * 1024:
            return "Large (10MB-100MB)"
        return "Huge (>100MB)"

    # Default: extension (with optional magic-byte inspection for unknown/extensionless files)
    ext = file_path.suffix.lower()
    for category, exts in categories.items():
        if ext in exts:
            return category

    if use_magic_fallback:
        magic_cat = detect_category_by_magic(file_path)
        if magic_cat:
            return magic_cat

    return "Misc"


def plan_organization(
    folder: Path,
    *,
    recursive: bool = False,
    strategy: str = "extension",
    categories: dict[str, set[str]] | None = None,
    conflict_policy: ConflictPolicy = ConflictPolicy.RENAME,
    use_magic_fallback: bool = True,
) -> list[MoveOperation]:
    folder = Path(folder).resolve()
    if not folder.is_dir():
        raise FileNotFoundError(f"Directory not found: {folder}")

    active_categories = categories or DEFAULT_CATEGORIES
    ignore_patterns = load_ignore_patterns(folder)
    iterator = folder.rglob("*") if recursive else folder.iterdir()
    operations: list[MoveOperation] = []

    for item in iterator:
        if not item.is_file() or item.name.startswith("."):
            continue
        if is_ignored(item.name, ignore_patterns):
            continue

        rel_parts = item.relative_to(folder).parts
        if recursive and any(part in active_categories for part in rel_parts[:-1]):
            continue

        bucket = _classify_file(item, strategy, active_categories, use_magic_fallback)
        target_dir = folder / bucket
        raw_dest = target_dir / item.name
        if item.resolve() == raw_dest.resolve():
            continue

        final_dest = resolve_destination(raw_dest, conflict_policy)
        if final_dest is not None and item.resolve() != final_dest.resolve():
            operations.append(MoveOperation(source=item, destination=final_dest, reason=f"strategy={strategy} -> {bucket}"))

    return operations


@register_action(
    id="organizer.sort",
    name="Folder Organizer",
    category="File Management",
    description="Sort files into structured folders by extension, MIME header, date, or size.",
    supports_dry_run=True,
)
def organize_folder(
    ctx: TaskContext,
    target_dir: str | Path,
    recursive: bool = False,
    strategy: str = "extension",
    use_magic_fallback: bool = True,
) -> TaskResult:
    folder = Path(target_dir).resolve()
    plan = plan_organization(
        folder,
        recursive=recursive,
        strategy=strategy,
        conflict_policy=ctx.conflict_policy,
        use_magic_fallback=use_magic_fallback,
    )

    if ctx.dry_run:
        return TaskResult(
            success=True,
            message=f"Preview: {len(plan)} file(s) ready to organize.",
            operations=plan,
        )

    completed: list[MoveOperation] = []
    errors: list[str] = []
    total = len(plan)

    for idx, op in enumerate(plan, start=1):
        if ctx.is_cancelled():
            break
        ctx.report(idx, total, f"Moving {op.source.name} -> {op.destination.parent.name}/")
        try:
            op.destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(op.source), str(op.destination))
            completed.append(op)
        except OSError as exc:
            errors.append(f"{op.source.name}: {exc}")

    if completed:
        UndoJournal().record("organizer.sort", completed)

    return TaskResult(
        success=len(errors) == 0,
        message=f"Organized {len(completed)} of {total} file(s).",
        outputs=[op.destination for op in completed],
        operations=completed,
        errors=errors,
    )
