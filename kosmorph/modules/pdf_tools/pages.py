from pathlib import Path
from kosmorph.core.contracts import TaskContext, TaskResult
from kosmorph.core.registry import register_action
from kosmorph.core.safety import atomic_output, resolve_destination


@register_action(
    id="pdf.merge",
    name="Merge PDFs",
    category="PDF Tools",
    description="Combine multiple PDF documents into a single PDF file.",
    input_extensions={".pdf"},
    output_formats=["pdf"],
)
def merge_pdfs(ctx: TaskContext, paths: list[str | Path], output_path: str | Path | None = None) -> TaskResult:
    import pymupdf

    pdf_paths = [Path(p) for p in paths if Path(p).is_file()]
    if len(pdf_paths) < 2:
        return TaskResult(success=False, message="Select at least two PDF files to merge.")

    dest_base = Path(output_path) if output_path else pdf_paths[0].parent / "merged.pdf"
    dest = resolve_destination(dest_base, ctx.conflict_policy)
    if dest is None:
        return TaskResult(success=True, message="Skipped existing merged PDF.")

    merged = pymupdf.open()
    try:
        for idx, p in enumerate(pdf_paths, start=1):
            if ctx.is_cancelled():
                return TaskResult(success=False, message="Merge cancelled.")
            ctx.report(idx, len(pdf_paths), f"Appending {p.name}")
            with pymupdf.open(p) as src_doc:
                merged.insert_pdf(src_doc)
        with atomic_output(dest) as tmp:
            merged.save(str(tmp))
    finally:
        merged.close()

    return TaskResult(success=True, message=f"Merged {len(pdf_paths)} PDFs into {dest.name}.", outputs=[dest])


@register_action(
    id="pdf.split",
    name="Split PDF into Single Pages",
    category="PDF Tools",
    description="Split a PDF document into individual single-page PDF files.",
    input_extensions={".pdf"},
    output_formats=["pdf"],
    supports_batch=False,
)
def split_pdf(ctx: TaskContext, path: str | Path, output_dir: str | Path | None = None) -> TaskResult:
    import pymupdf

    src = Path(path)
    out_dir = Path(output_dir) if output_dir else src.parent / f"{src.stem}_pages"
    out_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []

    with pymupdf.open(src) as doc:
        total = len(doc)
        for idx in range(total):
            if ctx.is_cancelled():
                break
            ctx.report(idx + 1, total, f"Extracting page {idx + 1}/{total}")
            dest = resolve_destination(out_dir / f"{src.stem}_page_{idx + 1:03d}.pdf", ctx.conflict_policy)
            if dest is None:
                continue
            single = pymupdf.open()
            try:
                single.insert_pdf(doc, from_page=idx, to_page=idx)
                with atomic_output(dest) as tmp:
                    single.save(str(tmp))
            finally:
                single.close()
            outputs.append(dest)

    return TaskResult(success=True, message=f"Split into {len(outputs)} page(s).", outputs=outputs)


@register_action(
    id="pdf.rotate",
    name="Rotate PDF Pages",
    category="PDF Tools",
    description="Rotate all pages in a PDF by 90, 180, or 270 degrees.",
    input_extensions={".pdf"},
    output_formats=["pdf"],
)
def rotate_pdf(ctx: TaskContext, paths: list[str | Path], angle: int = 90) -> TaskResult:
    import pymupdf

    outputs: list[Path] = []
    for idx, raw_path in enumerate(paths, start=1):
        src = Path(raw_path)
        ctx.report(idx, len(paths), f"Rotating {src.name} by {angle}°")
        dest = resolve_destination(src.with_name(f"{src.stem}_rotated.pdf"), ctx.conflict_policy)
        if dest is None:
            continue
        with pymupdf.open(src) as doc:
            for page in doc:
                page.set_rotation((page.rotation + angle) % 360)
            with atomic_output(dest) as tmp:
                doc.save(str(tmp))
        outputs.append(dest)

    return TaskResult(success=True, message=f"Rotated {len(outputs)} PDF(s).", outputs=outputs)
