from pathlib import Path
from kosmorph.core.contracts import TaskContext, TaskResult
from kosmorph.core.registry import register_action
from kosmorph.core.safety import atomic_output, resolve_destination

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".tif", ".gif", ".ico"}


@register_action(
    id="convert.image",
    name="Image Format Converter",
    category="Converters",
    description="Convert images between PNG, JPG, WEBP, BMP, TIFF, GIF, and ICO.",
    input_extensions=IMAGE_EXTENSIONS,
    output_formats=["png", "jpg", "webp", "bmp", "tiff", "gif", "ico"],
)
def convert_images(
    ctx: TaskContext,
    paths: list[str | Path],
    target_format: str = "png",
    output_dir: str | Path | None = None,
) -> TaskResult:
    from PIL import Image

    ext = target_format.lower().lstrip(".")
    outputs: list[Path] = []
    errors: list[str] = []
    total = len(paths)

    for idx, raw_path in enumerate(paths, start=1):
        if ctx.is_cancelled():
            break
        src = Path(raw_path)
        ctx.report(idx, total, f"Converting {src.name} to .{ext}")
        try:
            dest_base = (Path(output_dir) / src.name if output_dir else src).with_suffix(f".{ext}")
            dest = resolve_destination(dest_base, ctx.conflict_policy)
            if dest is None:
                continue
            with Image.open(src) as img:
                if ext in {"jpg", "jpeg"} and img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                with atomic_output(dest) as tmp:
                    pil_format = "JPEG" if ext in {"jpg", "jpeg"} else ext.upper()
                    img.save(tmp, format=pil_format)
            outputs.append(dest)
        except Exception as exc:
            errors.append(f"{src.name}: {exc}")

    return TaskResult(
        success=len(errors) == 0,
        message=f"Converted {len(outputs)} of {total} image(s).",
        outputs=outputs,
        errors=errors,
    )


@register_action(
    id="convert.images_to_pdf",
    name="Images to Single PDF",
    category="Converters",
    description="Compile multiple images into a single multi-page PDF document.",
    input_extensions=IMAGE_EXTENSIONS,
    output_formats=["pdf"],
)
def images_to_pdf(
    ctx: TaskContext,
    paths: list[str | Path],
    output_path: str | Path | None = None,
) -> TaskResult:
    from PIL import Image

    valid_paths = [Path(p) for p in paths if Path(p).is_file()]
    if not valid_paths:
        return TaskResult(success=False, message="No valid image files provided.")

    dest_base = Path(output_path) if output_path else valid_paths[0].parent / "compiled_images.pdf"
    dest = resolve_destination(dest_base, ctx.conflict_policy)
    if dest is None:
        return TaskResult(success=True, message="Skipped existing output PDF.")

    rgb_images = []
    try:
        for idx, p in enumerate(valid_paths, start=1):
            ctx.report(idx, len(valid_paths), f"Loading {p.name}")
            rgb_images.append(Image.open(p).convert("RGB"))
        with atomic_output(dest) as tmp:
            rgb_images[0].save(tmp, format="PDF", save_all=True, append_images=rgb_images[1:])
    finally:
        for im in rgb_images:
            im.close()

    return TaskResult(success=True, message=f"Created {dest.name} from {len(valid_paths)} image(s).", outputs=[dest])
