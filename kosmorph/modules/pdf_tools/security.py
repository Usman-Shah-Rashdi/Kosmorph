from pathlib import Path
from kosmorph.core.contracts import TaskContext, TaskResult
from kosmorph.core.registry import register_action
from kosmorph.core.safety import atomic_output, resolve_destination


@register_action(
    id="pdf.encrypt",
    name="Password-Protect PDF",
    category="PDF Tools",
    description="Encrypt a PDF with AES-256 user/owner passwords.",
    input_extensions={".pdf"},
    output_formats=["pdf"],
)
def encrypt_pdf(ctx: TaskContext, paths: list[str | Path], user_password: str, owner_password: str | None = None) -> TaskResult:
    import pymupdf

    outputs: list[Path] = []
    for idx, raw_path in enumerate(paths, start=1):
        src = Path(raw_path)
        ctx.report(idx, len(paths), f"Encrypting {src.name}")
        dest = resolve_destination(src.with_name(f"{src.stem}_protected.pdf"), ctx.conflict_policy)
        if dest is None:
            continue
        with pymupdf.open(src) as doc:
            with atomic_output(dest) as tmp:
                doc.save(
                    str(tmp),
                    encryption=pymupdf.PDF_ENCRYPT_AES_256,
                    user_pw=user_password,
                    owner_pw=owner_password or user_password,
                )
        outputs.append(dest)

    return TaskResult(success=True, message=f"Encrypted {len(outputs)} PDF(s).", outputs=outputs)
