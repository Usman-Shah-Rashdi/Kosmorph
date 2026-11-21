import csv
from pathlib import Path
from kosmorph.core.contracts import TaskContext, TaskResult
from kosmorph.core.registry import register_action
from kosmorph.core.safety import atomic_output, resolve_destination


@register_action(
    id="tables.deduplicate_csv",
    name="Deduplicate CSV Rows",
    category="Spreadsheets",
    description="Remove duplicate rows from CSV datasets while preserving column order.",
    input_extensions={".csv"},
    output_formats=["csv"],
)
def deduplicate_csv(ctx: TaskContext, path: str | Path, delimiter: str = ",") -> TaskResult:
    src = Path(path)
    dest = resolve_destination(src.with_name(f"{src.stem}_dedup.csv"), ctx.conflict_policy)
    if dest is None:
        return TaskResult(success=True, message="Skipped existing deduplicated CSV.")

    seen: set[tuple[str, ...]] = set()
    unique_rows: list[list[str]] = []
    removed = 0

    with open(src, "r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f, delimiter=delimiter)
        header = next(reader, None)
        if header is not None:
            unique_rows.append(header)
        for row in reader:
            key = tuple(row)
            if key in seen:
                removed += 1
            else:
                seen.add(key)
                unique_rows.append(row)

    with atomic_output(dest) as tmp:
        with open(tmp, "w", encoding="utf-8", newline="") as out_f:
            writer = csv.writer(out_f, delimiter=delimiter)
            writer.writerows(unique_rows)

    return TaskResult(
        success=True,
        message=f"Removed {removed} duplicate row(s) -> {dest.name}.",
        outputs=[dest],
        metadata={"removed_rows": removed},
    )
