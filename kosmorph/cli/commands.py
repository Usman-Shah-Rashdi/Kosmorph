import argparse
import json
import os
import sys
from pathlib import Path
from kosmorph import __version__
from kosmorph.core.backends import detect_backends
from kosmorph.core.contracts import ConflictPolicy
from kosmorph.core.registry import registry
from kosmorph.core.runner import TaskRunner
from kosmorph.core.safety import UndoJournal

BANNER = r"""
█▄▀ █▀█ █▀ █▀▄▀█ █▀█ █▀█ █▀█ █ █
█ █ █▄█ ▄█ █ ▀ █ █▄█ █▀▄ █▀▀ █▀█
"""


def print_banner(start_rgb: tuple[int, int, int] = (0, 245, 212), end_rgb: tuple[int, int, int] = (155, 93, 229)) -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    lines = BANNER.strip("\n").splitlines()
    use_color = sys.stdout.isatty() and not os.environ.get("NO_COLOR")

    if not use_color:
        print("\n".join(lines) + "\n")
        return

    max_len = max(len(line) for line in lines)
    for line in lines:
        colored_line = []
        for i, char in enumerate(line):
            ratio = i / max(max_len - 1, 1)
            r = int(start_rgb[0] + (end_rgb[0] - start_rgb[0]) * ratio)
            g = int(start_rgb[1] + (end_rgb[1] - start_rgb[1]) * ratio)
            b = int(start_rgb[2] + (end_rgb[2] - start_rgb[2]) * ratio)
            colored_line.append(f"\033[38;2;{r};{g};{b}m{char}")
        print("".join(colored_line) + "\033[0m")
    print()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kosmos", description="Kosmos File & Document Utility Suite")
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
    p_org.add_argument("--depth", type=int, default=None, help="Max recursion depth")
    p_org.add_argument("--smart", action="store_true", help="Use MIME/magic-header detection")
    p_org.add_argument("--ignore", nargs="+", default=None, help="Extra ignore glob patterns")
    p_org.add_argument("--no-ignore", action="store_true", help="Disable ignore rules")
    p_org.add_argument("--dry-run", action="store_true")

    p_watch = sub.add_parser("watch", help="Start background auto-organizer watcher")
    p_watch.add_argument("directory", help="Directory to watch")
    p_watch.add_argument("--recursive", action="store_true")
    p_watch.add_argument("--dry-run", action="store_true")

    p_unwatch = sub.add_parser("unwatch", help="Stop background watcher for a directory")
    p_unwatch.add_argument("directory", help="Watched directory path")

    sub.add_parser("watches", help="List active background watchers")

    p_wd = sub.add_parser("_watch-daemon", help=argparse.SUPPRESS)
    p_wd.add_argument("directory")
    p_wd.add_argument("--recursive", action="store_true")
    p_wd.add_argument("--dry-run", action="store_true")

    sub.add_parser("history", help="Show past file operations")

    p_undo = sub.add_parser("undo", help="Undo an operation (latest or by --id)")
    p_undo.add_argument("--id", default=None, help="Specific operation ID to revert")
    p_undo.add_argument("--dry-run", action="store_true")

    p_conv = sub.add_parser("convert", help="Convert one or more files")
    p_conv.add_argument("files", nargs="+", help="Input file path(s)")
    p_conv.add_argument("--to", required=True, help="Target extension (e.g., webp, csv, html, txt, pdf)")
    p_conv.add_argument("--conflict", choices=["rename", "overwrite", "skip"], default="rename")

    sub.add_parser("gui", help="Launch the desktop graphical interface")
    return parser


def run_cli(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "gui" or args.command is None:
        from kosmorph.ui.app import launch_gui
        launch_gui()
        return 0

    if args.command != "_watch-daemon":
        print_banner()

    runner = TaskRunner()

    if args.command == "list":
        for spec in registry.all_actions():
            exts = ", ".join(sorted(spec.input_extensions)) or "*"
            print(f"{spec.id:<26} [{spec.category}]  ({exts}) — {spec.name}")
        return 0

    if args.command == "search":
        for spec in registry.search(args.query):
            print(f"{spec.id:<26} [{spec.category}] — {spec.description}")
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
            max_depth=args.depth,
            strategy=args.strategy,
            smart_mime=args.smart,
            extra_ignore=args.ignore,
            no_ignore=args.no_ignore,
            dry_run=args.dry_run,
        )
        print(res.message)
        for op in res.operations[:50]:
            print(f"  {op.source.name} -> {op.destination.parent.name}/{op.destination.name}")
        return 0 if res.success else 1

    if args.command == "watch":
        from kosmorph.modules.organizer.watcher import spawn_daemon
        pid = spawn_daemon(Path(args.directory), dry_run=args.dry_run, recursive=args.recursive)
        print(f"Started watcher for {Path(args.directory).resolve()} (PID {pid})")
        return 0

    if args.command == "unwatch":
        from kosmorph.modules.organizer.watcher import kill_watch
        ok, msg = kill_watch(Path(args.directory))
        print(msg)
        return 0 if ok else 1

    if args.command == "watches":
        from kosmorph.modules.organizer.watcher import get_watches
        watches = get_watches()
        if not watches:
            print("No active watchers.")
        else:
            for path_str, info in watches.items():
                print(f"{path_str}  [PID {info.get('pid')}]  organized={info.get('total', 0)}")
        return 0

    if args.command == "_watch-daemon":
        from kosmorph.modules.organizer.watcher import run_watch
        ok, msg = run_watch(
            Path(args.directory),
            dry_run=args.dry_run,
            recursive=args.recursive,
            daemon_mode=True,
        )
        if not ok:
            print(msg)
        return 0 if ok else 1

    if args.command == "history":
        entries = UndoJournal().list_entries()
        if not entries:
            print("No recorded history.")
        else:
            for e in entries:
                print(f"{e['id']}  {e['timestamp'][:19]}  {e['action']:<22}  {e['total_files']} file(s)  {e['base']}")
        return 0

    if args.command == "undo":
        restored, skipped, logs = UndoJournal().undo(operation_id=args.id, dry_run=args.dry_run)
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

    return 1
