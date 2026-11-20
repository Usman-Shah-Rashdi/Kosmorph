import csv
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from kosmorph.core.contracts import TaskContext, TaskResult
from kosmorph.core.registry import register_action
from kosmorph.core.safety import atomic_output, resolve_destination


@register_action(
    id="convert.structured",
    name="Structured Data Converter (JSON / CSV / YAML / XML)",
    category="Converters",
    description="Convert structured datasets between JSON, CSV, YAML, and XML.",
    input_extensions={".json", ".csv", ".yaml", ".yml", ".xml"},
    output_formats=["json", "csv", "yaml", "xml"],
)
def convert_structured(
    ctx: TaskContext,
    paths: list[str | Path],
    target_format: str = "json",
    output_dir: str | Path | None = None,
) -> TaskResult:
    import yaml

    ext = target_format.lower().lstrip(".")
    outputs: list[Path] = []
    errors: list[str] = []

    for idx, raw_path in enumerate(paths, start=1):
        if ctx.is_cancelled():
            break
        src = Path(raw_path)
        ctx.report(idx, len(paths), f"Transforming {src.name} -> .{ext}")
        try:
            records = _load_records(src, yaml)
            dest_base = (Path(output_dir) / src.name if output_dir else src).with_suffix(f".{ext}")
            dest = resolve_destination(dest_base, ctx.conflict_policy)
            if dest is None:
                continue

            with atomic_output(dest) as tmp:
                if ext == "json":
                    tmp.write_text(json.dumps(records, indent=2), encoding="utf-8")
                elif ext in {"yaml", "yml"}:
                    tmp.write_text(yaml.safe_dump(records, sort_keys=False), encoding="utf-8")
                elif ext == "csv":
                    rows = records if isinstance(records, list) else [records]
                    if not rows:
                        raise ValueError("Cannot write empty dataset to CSV.")
                    fieldnames = list(rows[0].keys())
                    with open(tmp, "w", newline="", encoding="utf-8") as f:
                        writer = csv.DictWriter(f, fieldnames=fieldnames)
                        writer.writeheader()
                        writer.writerows(rows)
                elif ext == "xml":
                    root = ET.Element("records")
                    rows = records if isinstance(records, list) else [records]
                    for row in rows:
                        item_el = ET.SubElement(root, "record")
                        for k, v in row.items():
                            child = ET.SubElement(item_el, str(k))
                            child.text = "" if v is None else str(v)
                    ET.ElementTree(root).write(tmp, encoding="utf-8", xml_declaration=True)
                else:
                    raise ValueError(f"Unsupported structured format: {ext}")
            outputs.append(dest)
        except Exception as exc:
            errors.append(f"{src.name}: {exc}")

    return TaskResult(success=len(errors) == 0, message=f"Converted {len(outputs)} data file(s).", outputs=outputs, errors=errors)


def _load_records(src: Path, yaml_mod):
    suffix = src.suffix.lower()
    if suffix == ".json":
        return json.loads(src.read_text(encoding="utf-8"))
    if suffix in {".yaml", ".yml"}:
        return yaml_mod.safe_load(src.read_text(encoding="utf-8"))
    if suffix == ".csv":
        with open(src, "r", encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))
    if suffix == ".xml":
        tree = ET.parse(src)
        return [{child.tag: child.text for child in elem} for elem in tree.getroot()]
    raise ValueError(f"Unsupported source format: {suffix}")
