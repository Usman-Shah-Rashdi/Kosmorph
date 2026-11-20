import zipfile
from pathlib import Path
from kosmorph.core.contracts import TaskContext, TaskResult
from kosmorph.core.registry import register_action
from kosmorph.core.safety import atomic_output, resolve_destination


@register_action(
    id="files.create_zip",
    name="Create ZIP Archive",
    category="File Management",
    description="Compress selected files or folders into a deflated ZIP archive.",
    output_formats=["zip"],
)
def create_zip(ctx: TaskContext, paths: list[str | Path], output_path: str | Path) -> TaskResult:
    dest = resolve_destination(Path(output_path), ctx.conflict_policy)
    if dest is None:
        return TaskResult(success=True, message="Skipped existing archive.")

    items = [Path(p) for p in paths if Path(p).exists()]
    with atomic_output(dest) as tmp:
        with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for idx, item in enumerate(items, start=1):
                if ctx.is_cancelled():
                    break
                ctx.report(idx, len(items), f"Archiving {item.name}")
                if item.is_file():
                    zf.write(item, arcname=item.name)
                elif item.is_dir():
                    for child in item.rglob("*"):
                        if child.is_file():
                            zf.write(child, arcname=str(child.relative_to(item.parent)))

    return TaskResult(success=True, message=f"Created archive {dest.name}.", outputs=[dest])
