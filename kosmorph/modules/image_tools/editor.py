from pathlib import Path
from kosmorph.core.contracts import TaskContext, TaskResult
from kosmorph.core.registry import register_action
from kosmorph.core.safety import atomic_output, resolve_destination
from kosmorph.modules.converters.images import IMAGE_EXTENSIONS


@register_action(
    id="image.optimize",
    name="Resize, Compress & Strip EXIF Metadata",
    category="Image Utilities",
    description="Batch resize images, reduce file size, and strip private EXIF metadata.",
    input_extensions=IMAGE_EXTENSIONS,
)
def optimize_images(
    ctx: TaskContext,
    paths: list[str | Path],
    max_width: int | None = None,
    quality: int = 85,
    strip_metadata: bool = True,
) -> TaskResult:
    from PIL import Image

    outputs: list[Path] = []
    for idx, raw_path in enumerate(paths, start=1):
        if ctx.is_cancelled():
            break
        src = Path(raw_path)
        ctx.report(idx, len(paths), f"Optimizing {src.name}")
        dest = resolve_destination(src.with_name(f"{src.stem}_opt{src.suffix}"), ctx.conflict_policy)
        if dest is None:
            continue

        with Image.open(src) as img:
            if max_width and img.width > max_width:
                ratio = max_width / float(img.width)
                new_height = max(1, int(img.height * ratio))
                img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)

            if strip_metadata:
                clean = Image.new(img.mode, img.size)
                clean.putdata(list(img.getdata()))
                img = clean

            with atomic_output(dest) as tmp:
                fmt = img.format or src.suffix.lstrip(".").upper()
                if fmt == "JPG":
                    fmt = "JPEG"
                img.save(tmp, format=fmt, quality=quality, optimize=True)
        outputs.append(dest)

    return TaskResult(success=True, message=f"Optimized {len(outputs)} image(s).", outputs=outputs)
