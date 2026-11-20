import hashlib
from collections import defaultdict
from pathlib import Path
from kosmorph.core.contracts import TaskContext, TaskResult
from kosmorph.core.registry import register_action


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


@register_action(
    id="files.find_duplicates",
    name="Find Duplicate Files",
    category="File Management",
    description="Two-pass duplicate detector grouping by byte size before computing SHA-256 hashes.",
)
def find_duplicates(ctx: TaskContext, target_dir: str | Path, recursive: bool = True) -> TaskResult:
    root = Path(target_dir).resolve()
    iterator = root.rglob("*") if recursive else root.iterdir()
    by_size: dict[int, list[Path]] = defaultdict(list)

    for item in iterator:
        if item.is_file():
            by_size[item.stat().st_size].append(item)

    candidates = [group for group in by_size.values() if len(group) > 1]
    duplicates: dict[str, list[str]] = {}
    total = len(candidates)

    for idx, group in enumerate(candidates, start=1):
        if ctx.is_cancelled():
            break
        ctx.report(idx, total, f"Hashing size group {idx}/{total}")
        by_hash: dict[str, list[str]] = defaultdict(list)
        for file in group:
            by_hash[_sha256(file)].append(str(file))
        for digest, matching in by_hash.items():
            if len(matching) > 1:
                duplicates[digest] = matching

    dup_count = sum(len(v) - 1 for v in duplicates.values())
    return TaskResult(
        success=True,
        message=f"Found {dup_count} duplicate file(s) across {len(duplicates)} group(s).",
        metadata={"duplicates": duplicates},
    )
