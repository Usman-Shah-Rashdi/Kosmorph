from pathlib import Path
from kosmorph.core.contracts import TaskContext, TaskResult
from kosmorph.core.registry import register_action
from kosmorph.core.safety import atomic_output, resolve_destination


@register_action(
    id="convert.pdf_to_text",
    name="PDF to Extracted Text (.txt)",
    category="Converters",
    description="Extract plain text from PDF files using PyMuPDF.",
    input_extensions={".pdf"},
    output_formats=["txt"],
)
def pdf_to_text(ctx: TaskContext, paths: list[str | Path], output_dir: str | Path | None = None) -> TaskResult:
    import pymupdf

    outputs: list[Path] = []
    errors: list[str] = []
    for idx, raw_path in enumerate(paths, start=1):
        if ctx.is_cancelled():
            break
        src = Path(raw_path)
        ctx.report(idx, len(paths), f"Extracting text from {src.name}")
        try:
            dest_base = (Path(output_dir) / src.name if output_dir else src).with_suffix(".txt")
            dest = resolve_destination(dest_base, ctx.conflict_policy)
            if dest is None:
                continue
            with pymupdf.open(src) as doc:
                chunks = [page.get_text() for page in doc]
            with atomic_output(dest) as tmp:
                tmp.write_text("\n--- Page Break ---\n".join(chunks), encoding="utf-8")
            outputs.append(dest)
        except Exception as exc:
            errors.append(f"{src.name}: {exc}")

    return TaskResult(success=len(errors) == 0, message=f"Extracted {len(outputs)} text file(s).", outputs=outputs, errors=errors)


@register_action(
    id="convert.pdf_to_docx",
    name="PDF to Editable Word (.docx)",
    category="Converters",
    description="Convert PDF layout and text into an editable DOCX document.",
    input_extensions={".pdf"},
    output_formats=["docx"],
)
def pdf_to_docx(ctx: TaskContext, paths: list[str | Path], output_dir: str | Path | None = None) -> TaskResult:
    try:
        from pdf2docx import Converter
    except ImportError as exc:
        return TaskResult(
            success=False,
            message="Optional dependency 'pdf2docx' is not installed. Run: pip install kosmorph[docx]",
            errors=[str(exc)],
        )

    outputs: list[Path] = []
    errors: list[str] = []
    for idx, raw_path in enumerate(paths, start=1):
        if ctx.is_cancelled():
            break
        src = Path(raw_path)
        ctx.report(idx, len(paths), f"Converting {src.name} to DOCX")
        try:
            dest_base = (Path(output_dir) / src.name if output_dir else src).with_suffix(".docx")
            dest = resolve_destination(dest_base, ctx.conflict_policy)
            if dest is None:
                continue
            with atomic_output(dest) as tmp:
                converter = Converter(str(src))
                try:
                    converter.convert(str(tmp))
                finally:
                    converter.close()
            outputs.append(dest)
        except Exception as exc:
            errors.append(f"{src.name}: {exc}")

    return TaskResult(success=len(errors) == 0, message=f"Converted {len(outputs)} PDF(s) to DOCX.", outputs=outputs, errors=errors)


@register_action(
    id="convert.md_to_html",
    name="Markdown to HTML (.html)",
    category="Converters",
    description="Render Markdown documents into standalone HTML5 files.",
    input_extensions={".md", ".markdown"},
    output_formats=["html"],
)
def markdown_to_html(ctx: TaskContext, paths: list[str | Path], output_dir: str | Path | None = None) -> TaskResult:
    import markdown

    outputs: list[Path] = []
    errors: list[str] = []
    for idx, raw_path in enumerate(paths, start=1):
        if ctx.is_cancelled():
            break
        src = Path(raw_path)
        ctx.report(idx, len(paths), f"Rendering {src.name} to HTML")
        try:
            dest_base = (Path(output_dir) / src.name if output_dir else src).with_suffix(".html")
            dest = resolve_destination(dest_base, ctx.conflict_policy)
            if dest is None:
                continue
            md_text = src.read_text(encoding="utf-8")
            body = markdown.markdown(md_text, extensions=["tables", "fenced_code"])
            html = (
                f"<!DOCTYPE html>\n<html>\n<head><meta charset='utf-8'>"
                f"<title>{src.stem}</title></head>\n<body>\n{body}\n</body>\n</html>"
            )
            with atomic_output(dest) as tmp:
                tmp.write_text(html, encoding="utf-8")
            outputs.append(dest)
        except Exception as exc:
            errors.append(f"{src.name}: {exc}")

    return TaskResult(success=len(errors) == 0, message=f"Rendered {len(outputs)} HTML file(s).", outputs=outputs, errors=errors)
