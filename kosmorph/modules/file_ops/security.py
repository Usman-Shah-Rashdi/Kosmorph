import hashlib
from pathlib import Path
from kosmorph.core.contracts import TaskContext, TaskResult
from kosmorph.core.registry import register_action


@register_action(
    id="files.checksum",
    name="Generate File Checksums (SHA-256 / MD5)",
    category="File Management",
    description="Compute cryptographic digests for file integrity verification.",
)
def compute_checksums(ctx: TaskContext, paths: list[str | Path], algorithm: str = "sha256") -> TaskResult:
    digests: dict[str, str] = {}
    for idx, raw_path in enumerate(paths, start=1):
        src = Path(raw_path)
        if not src.is_file():
            continue
        ctx.report(idx, len(paths), f"Hashing {src.name}")
        hasher = hashlib.new(algorithm.lower())
        with open(src, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
        digests[str(src)] = hasher.hexdigest()

    return TaskResult(
        success=True,
        message=f"Computed {algorithm.upper()} for {len(digests)} file(s).",
        metadata={"checksums": digests, "algorithm": algorithm.lower()},
    )
