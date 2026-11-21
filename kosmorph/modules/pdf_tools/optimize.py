from pathlib import Path
from kosmorph.core.contracts import TaskContext, TaskResult
from kosmorph.core.registry import register_action
from kosmorph.core.safety import atomic_output, resolve_destination


@register_action(
    id="pdf.compress",
    name="Compress & Optimize PDF",
    category="PDF Tools",
    description="Reduce PDF file size using stream deflation and garbage collection.",
    input_extensions={".pdf"},
    output_formats=["pdf"],
)
def compress_pdf(ctx: TaskContext, paths: list[str | Path]) -> TaskResult:
    import pymupdf

    outputs: list[Path] = []
    for idx, raw_path in enumerate(paths, start=1):
        src = Path(raw_path)
        ctx.report(idx, len(paths), f"Compressing {src.name}")
        dest = resolve_destination(src.with_name(f"{src.stem}_compressed.pdf"), ctx.conflict_policy)
        if dest is None:
            continue
        with pymupdf.open(src) as doc:
            with atomic_output(dest) as tmp:
                doc.save(str(tmp), garbage=4, deflate=True, clean=True)
        outputs.append(dest)

    return TaskResult(success=True, message=f"Compressed {len(outputs)} PDF(s).", outputs=outputs)
