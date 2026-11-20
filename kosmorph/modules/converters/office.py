import subprocess
from pathlib import Path
from kosmorph.core.backends import detect_backends
from kosmorph.core.contracts import TaskContext, TaskResult
from kosmorph.core.registry import register_action
from kosmorph.core.safety import resolve_destination

OFFICE_EXTENSIONS = {".doc", ".docx", ".odt", ".ppt", ".pptx", ".odp", ".xls", ".xlsx", ".ods"}


@register_action(
    id="convert.office_to_pdf",
    name="Office Document / Sheet / Slide to PDF",
    category="Converters",
    description="Convert Word, Excel, PowerPoint, and OpenDocument files to PDF via LibreOffice.",
    input_extensions=OFFICE_EXTENSIONS,
    output_formats=["pdf"],
    required_backends=["libreoffice"],
)
def office_to_pdf(ctx: TaskContext, paths: list[str | Path], output_dir: str | Path | None = None) -> TaskResult:
    lo = detect_backends().get("libreoffice")
    if not lo or not lo.available or not lo.path:
        return TaskResult(
            success=False,
            message="LibreOffice was not detected on PATH. Install LibreOffice to enable Office conversions.",
        )

    outputs: list[Path] = []
    errors: list[str] = []
    for idx, raw_path in enumerate(paths, start=1):
        if ctx.is_cancelled():
            break
        src = Path(raw_path).resolve()
        out_folder = Path(output_dir).resolve() if output_dir else src.parent
        out_folder.mkdir(parents=True, exist_ok=True)
        ctx.report(idx, len(paths), f"Converting {src.name} to PDF")
        try:
            subprocess.run(
                [lo.path, "--headless", "--convert-to", "pdf", "--outdir", str(out_folder), str(src)],
                check=True,
                capture_output=True,
                text=True,
                timeout=120,
            )
            expected = out_folder / f"{src.stem}.pdf"
            if not expected.exists():
                raise RuntimeError("LibreOffice finished without producing an output PDF.")
            final_dest = resolve_destination(expected, ctx.conflict_policy)
            outputs.append(final_dest or expected)
        except Exception as exc:
            errors.append(f"{src.name}: {exc}")

    return TaskResult(success=len(errors) == 0, message=f"Converted {len(outputs)} Office file(s) to PDF.", outputs=outputs, errors=errors)
