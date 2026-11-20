import subprocess
import sys
from pathlib import Path
from kosmorph.core.backends import detect_backends
from kosmorph.core.contracts import TaskContext, TaskResult
from kosmorph.core.registry import register_action
from kosmorph.core.safety import resolve_destination

OFFICE_EXTENSIONS = {".doc", ".docx", ".odt", ".ppt", ".pptx", ".odp", ".xls", ".xlsx", ".ods"}


def _try_windows_com(src: Path, out_pdf: Path) -> bool:
    if sys.platform != "win32":
        return False
    ext = src.suffix.lower()
    try:
        import win32com.client  # type: ignore[import]
    except ImportError:
        return False

    if ext in {".doc", ".docx", ".odt"}:
        word = win32com.client.DispatchEx("Word.Application")
        try:
            doc = word.Documents.Open(str(src.resolve()))
            doc.SaveAs(str(out_pdf.resolve()), FileFormat=17)
            doc.Close(False)
            return out_pdf.exists()
        finally:
            word.Quit()
    elif ext in {".ppt", ".pptx", ".odp"}:
        ppt = win32com.client.DispatchEx("PowerPoint.Application")
        pres = None
        try:
            pres = ppt.Presentations.Open(str(src.resolve()), WithWindow=False)
            pres.SaveAs(str(out_pdf.resolve()), 32)
            return out_pdf.exists()
        finally:
            if pres is not None:
                pres.Close()
            ppt.Quit()
    elif ext in {".xls", ".xlsx", ".ods"}:
        excel = win32com.client.DispatchEx("Excel.Application")
        wb = None
        try:
            wb = excel.Workbooks.Open(str(src.resolve()))
            wb.ExportAsFixedFormat(0, str(out_pdf.resolve()))
            return out_pdf.exists()
        finally:
            if wb is not None:
                wb.Close(False)
            excel.Quit()
    return False


@register_action(
    id="convert.office_to_pdf",
    name="Office Document / Sheet / Slide to PDF",
    category="Converters",
    description="Convert Word, Excel, PowerPoint, and OpenDocument files to PDF via MS Office or LibreOffice.",
    input_extensions=OFFICE_EXTENSIONS,
    output_formats=["pdf"],
    required_backends=["libreoffice"],
)
def office_to_pdf(ctx: TaskContext, paths: list[str | Path], output_dir: str | Path | None = None) -> TaskResult:
    backends = detect_backends()
    lo = backends.get("libreoffice")
    ms = backends.get("ms_office")

    if (not lo or not lo.available) and (not ms or not ms.available):
        return TaskResult(
            success=False,
            message="Neither LibreOffice nor Microsoft Office was detected. Install LibreOffice to enable Office -> PDF.",
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

        dest = resolve_destination(out_folder / f"{src.stem}.pdf", ctx.conflict_policy)
        if dest is None:
            continue

        try:
            if ms and ms.available and _try_windows_com(src, dest):
                outputs.append(dest)
                continue

            if not lo or not lo.available or not lo.path:
                raise RuntimeError("LibreOffice is required on this platform.")

            subprocess.run(
                [lo.path, "--headless", "--convert-to", "pdf", "--outdir", str(out_folder), str(src)],
                check=True,
                capture_output=True,
                text=True,
                timeout=120,
            )
            generated = out_folder / f"{src.stem}.pdf"
            if not generated.exists():
                raise RuntimeError("LibreOffice finished without producing an output PDF.")
            if generated != dest:
                generated.replace(dest)
            outputs.append(dest)
        except Exception as exc:
            errors.append(f"{src.name}: {exc}")

    return TaskResult(success=len(errors) == 0, message=f"Converted {len(outputs)} Office file(s) to PDF.", outputs=outputs, errors=errors)
