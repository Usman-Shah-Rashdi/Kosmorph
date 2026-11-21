from datetime import datetime
from pathlib import Path
from kosmorph.core.contracts import MoveOperation, TaskContext, TaskResult
from kosmorph.core.registry import register_action
from kosmorph.core.safety import UndoJournal, resolve_destination


@register_action(
    id="files.batch_rename",
    name="Batch Rename with Templates",
    category="File Management",
    description="Rename files using {name}, {num}, {date}, and {ext} tokens with full Undo support.",
    supports_dry_run=True,
)
def batch_rename(
    ctx: TaskContext,
    paths: list[str | Path],
    template: str = "{name}_{num:03d}{ext}",
    start_index: int = 1,
) -> TaskResult:
    operations: list[MoveOperation] = []
    for idx, raw_path in enumerate(paths, start=start_index):
        src = Path(raw_path).resolve()
        if not src.is_file():
            continue
        mtime = datetime.fromtimestamp(src.stat().st_mtime).strftime("%Y-%m-%d")
        new_name = template.format(name=src.stem, num=idx, date=mtime, ext=src.suffix)
        dest = resolve_destination(src.with_name(new_name), ctx.conflict_policy)
        if dest and dest != src:
            operations.append(MoveOperation(source=src, destination=dest, reason="batch_rename"))

    if ctx.dry_run:
        return TaskResult(success=True, message=f"Preview: {len(operations)} file(s) will be renamed.", operations=operations)

    completed: list[MoveOperation] = []
    for idx, op in enumerate(operations, start=1):
        if ctx.is_cancelled():
            break
        ctx.report(idx, len(operations), f"Renaming {op.source.name} -> {op.destination.name}")
        op.source.rename(op.destination)
        completed.append(op)

    op_id = None
    if completed:
        op_id = UndoJournal().record("files.batch_rename", completed)

    return TaskResult(
        success=True,
        message=f"Renamed {len(completed)} file(s)." + (f" [Undo ID: {op_id}]" if op_id else ""),
        outputs=[op.destination for op in completed],
        operations=completed,
        metadata={"undo_id": op_id},
    )
