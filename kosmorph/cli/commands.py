import argparse
import json
from pathlib import Path
from kosmorph import __version__
from kosmorph.core.backends import detect_backends
from kosmorph.core.contracts import ConflictPolicy
from kosmorph.core.registry import registry
from kosmorph.core.runner import TaskRunner
from kosmorph.core.safety import UndoJournal


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kosmorph", description="Kosmorph File & Document Utility Engine")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("list", help="List all registered backend actions")

    p_search = sub.add_parser("search", help="Search available actions")
    p_search.add_argument("query", help="Keyword to search")

    sub.add_parser("diagnostics", help="Inspect detected external backends")

    p_org = sub.add_parser("organize", help="Organize files in a directory")
    p_org.add_argument("directory", help="Target folder path")
    p_org.add_argument("--strategy", choices=["extension", "date", "size"], default="extension")
    p_org.add_argument("--recursive", action="store_true")
    p_org.add_argument("--dry-run", action="store_true")

    sub.add_parser("undo", help="Undo the last file organization or batch rename")

    p_conv = sub.add_parser("convert", help="Convert one or more files")
    p_conv.add_argument("files", nargs="+", help="Input file path(s)")
    p_conv.add_argument("--to", required=True, help="Target extension (e.g., webp, csv, html, txt, pdf)")
    p_conv.add_argument("--conflict", choices=["rename", "overwrite", "skip"], default="rename")

    sub.add_parser("gui", help="Launch the desktop graphical interface")
    return parser


def run_cli(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    runner = TaskRunner()

    if args.command == "list":
        for spec in registry.all_actions():
            exts = ", ".join(sorted(spec.input_extensions)) or "*"
            print(f"{spec.id:<24} [{spec.category}]  ({exts}) — {spec.name}")
        return 0

    if args.command == "search":
        for spec in registry.search(args.query):
            print(f"{spec.id:<24} [{spec.category}] — {spec.description}")
        return 0

    if args.command == "diagnostics":
        statuses = {
            k: {"available": v.available, "path": v.path, "version": v.version}
            for k, v in detect_backends().items()
        }
        print(json.dumps(statuses, indent=2))
        return 0

    if args.command == "organize":
        res = runner.run_sync(
            "organizer.sort",
            target_dir=Path(args.directory),
            recursive=args.recursive,
            strategy=args.strategy,
            dry_run=args.dry_run,
        )
        print(res.message)
        for op in res.operations[:50]:
            print(f"  {op.source.name} -> {op.destination.parent.name}/{op.destination.name}")
        return 0 if res.success else 1

    if args.command == "undo":
        restored, skipped, logs = UndoJournal().undo_last()
        print(f"Restored {restored} file(s); skipped {skipped}.")
        for line in logs:
            print(f"  {line}")
        return 0

    if args.command == "convert":
        target = args.to.lower().lstrip(".")
        policy = ConflictPolicy(args.conflict)
        paths = [Path(p) for p in args.files]
        first_ext = paths[0].suffix.lower()

        if first_ext in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".gif", ".ico"}:
            action_id = "convert.images_to_pdf" if target == "pdf" else "convert.image"
            kwargs = {"paths": paths} if target == "pdf" else {"paths": paths, "target_format": target}
        elif first_ext == ".pdf" and target == "txt":
            action_id, kwargs = "convert.pdf_to_text", {"paths": paths}
        elif first_ext == ".pdf" and target == "docx":
            action_id, kwargs = "convert.pdf_to_docx", {"paths": paths}
        elif first_ext in {".md", ".markdown"} and target == "html":
            action_id, kwargs = "convert.md_to_html", {"paths": paths}
        elif first_ext in {".json", ".csv", ".yaml", ".yml", ".xml"}:
            action_id, kwargs = "convert.structured", {"paths": paths, "target_format": target}
        else:
            action_id, kwargs = "convert.office_to_pdf", {"paths": paths}

        res = runner.run_sync(action_id, conflict_policy=policy, **kwargs)
        print(res.message)
        for err in res.errors:
            print(f"  [ERROR] {err}")
        return 0 if res.success else 1

    if args.command == "gui" or args.command is None:
        from kosmorph.ui.legacy_bridge import launch_gui
        launch_gui()
        return 0

    return 1
