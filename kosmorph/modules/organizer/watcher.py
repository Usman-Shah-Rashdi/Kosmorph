"""Cross-platform background watch-folder daemon & registry adapted from FOLDR v0.2.1."""

from __future__ import annotations

import json
import logging
import os
import platform
import shutil
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from kosmorph.core.contracts import ConflictPolicy, MoveOperation, TaskContext
from kosmorph.core.safety import UndoJournal, resolve_destination
from .config_loader import load_category_template
from .engine import _classify_file, organize_folder
from .ignore import IgnoreRules

_WATCHES_FILE = Path.home() / ".kosmos" / "watches.json"
_LOG_DIR = Path.home() / ".kosmos" / "watch_logs"
_SYSTEM = platform.system()
_IS_WIN = _SYSTEM == "Windows"

_IN_PROGRESS_EXTS: frozenset[str] = frozenset({
    ".crdownload", ".part", ".tmp", ".download",
    ".partial", ".!ut", ".ytdl", ".aria2", ".opdownload",
})


def _load_watches() -> dict:
    if _WATCHES_FILE.exists():
        try:
            return json.loads(_WATCHES_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_watches(data: dict) -> None:
    _WATCHES_FILE.parent.mkdir(parents=True, exist_ok=True)
    _WATCHES_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _is_alive(pid: int) -> bool:
    if not pid:
        return False
    try:
        if _IS_WIN:
            import ctypes
            windll = getattr(ctypes, "windll", None)
            if windll is None:
                return False
            h = windll.kernel32.OpenProcess(0x100000, False, pid)
            if h:
                r = windll.kernel32.WaitForSingleObject(h, 0)
                windll.kernel32.CloseHandle(h)
                return r == 0x102
            return False
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError, OSError, AttributeError):
        return False


def get_watches() -> dict:
    data = _load_watches()
    cleaned = {p: info for p, info in data.items() if _is_alive(info.get("pid", 0))}
    if len(cleaned) != len(data):
        _save_watches(cleaned)
    return cleaned


def add_watch(path: Path, pid: int, dry_run: bool = False, recursive: bool = False) -> None:
    data = _load_watches()
    data[str(path.resolve())] = {
        "pid": pid,
        "started": datetime.now(timezone.utc).isoformat(),
        "dry_run": dry_run,
        "recursive": recursive,
        "total": 0,
    }
    _save_watches(data)


def remove_watch(path: Path) -> bool:
    data = _load_watches()
    key = str(path.resolve())
    if key in data:
        del data[key]
        _save_watches(data)
        return True
    return False


def _increment_count(path: Path, n: int = 1) -> None:
    data = _load_watches()
    key = str(path.resolve())
    if key in data:
        data[key]["total"] = data[key].get("total", 0) + n
        _save_watches(data)


def _get_python() -> str:
    exe = Path(sys.executable).resolve()
    if _IS_WIN:
        for cand in (exe.parent / "pythonw.exe", exe.parent / "Scripts" / "pythonw.exe"):
            if cand.exists():
                return str(cand)
    return str(exe)


def spawn_daemon(target: Path, dry_run: bool = False, recursive: bool = False) -> int:
    python = _get_python()
    root = str(Path(__file__).resolve().parent.parent.parent.parent)
    cmd = [python, "-m", "kosmorph", "_watch-daemon", str(target.resolve())]
    if dry_run:
        cmd.append("--dry-run")
    if recursive:
        cmd.append("--recursive")

    env = os.environ.copy()
    sep = ";" if _IS_WIN else ":"
    old_pp = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = root + (sep + old_pp if old_pp else "")

    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    safe = target.name.replace(" ", "_").replace("/", "_").replace("\\", "_")
    log_file = _LOG_DIR / f"{safe}.log"

    with open(log_file, "a", encoding="utf-8") as lf:
        if _IS_WIN:
            proc = subprocess.Popen(
                cmd,
                creationflags=0x00000008 | 0x08000000 | 0x00000200,
                close_fds=True,
                cwd=root,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=lf,
                stderr=lf,
            )
        else:
            proc = subprocess.Popen(
                cmd,
                start_new_session=True,
                close_fds=True,
                cwd=root,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=lf,
                stderr=lf,
            )
    add_watch(target, proc.pid, dry_run=dry_run, recursive=recursive)
    return proc.pid


def kill_watch(path: Path) -> tuple[bool, str]:
    watches = _load_watches()
    key = str(path.resolve())
    if key not in watches:
        return False, f"No active watch for: {path}"
    pid = watches[key].get("pid", 0)
    if not pid or not _is_alive(pid):
        remove_watch(path)
        return True, f"Watcher was already stopped (PID {pid})"
    try:
        if _IS_WIN:
            import ctypes
            windll = getattr(ctypes, "windll", None)
            if windll:
                h = windll.kernel32.OpenProcess(1, False, pid)
                if h:
                    windll.kernel32.TerminateProcess(h, 0)
                    windll.kernel32.CloseHandle(h)
        else:
            os.kill(pid, signal.SIGTERM)
        remove_watch(path)
        return True, f"Stopped watcher (PID {pid})"
    except Exception as exc:
        remove_watch(path)
        return False, f"Error stopping PID {pid}: {exc}"


def _file_stable(p: Path) -> bool:
    try:
        before = p.stat().st_size
    except OSError:
        return False
    time.sleep(0.4)
    try:
        return p.stat().st_size == before
    except OSError:
        return False


def run_watch(
    base: Path,
    *,
    dry_run: bool = False,
    recursive: bool = False,
    daemon_mode: bool = False,
    stop_event: threading.Event | None = None,
) -> tuple[bool, str]:
    """Run live directory watcher (requires optional 'watchdog' package)."""
    try:
        from watchdog.events import FileSystemEventHandler  # type: ignore[import]
        from watchdog.observers import Observer  # type: ignore[import]
    except ImportError:
        return False, "Optional dependency 'watchdog' is not installed. Run: pip install watchdog"

    base = base.resolve()
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = _LOG_DIR / f"{base.name.replace(' ', '_')}.log"
    logger = logging.getLogger(f"kosmos.watch.{base.name}")
    if not logger.handlers:
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-8s  %(message)s"))
        logger.addHandler(fh)
        logger.setLevel(logging.INFO)

    template, _ = load_category_template()
    cat_folders = {v["folder"] for v in template.values()}
    ignore = IgnoreRules(base)

    # Initial scan
    init_res = organize_folder(TaskContext(dry_run=dry_run), target_dir=base, recursive=recursive)
    if init_res.operations:
        _increment_count(base, len(init_res.operations))

    if daemon_mode:
        add_watch(base, os.getpid(), dry_run=dry_run, recursive=recursive)

    pending: dict[str, float] = {}
    lock = threading.Lock()
    stop = stop_event or threading.Event()

    def _enqueue(raw_path: object) -> None:
        p = Path(raw_path.decode(errors="replace") if isinstance(raw_path, (bytes, bytearray)) else str(raw_path))
        try:
            parent = p.parent.resolve()
            rel = parent.relative_to(base)
            if rel.parts and rel.parts[0] in cat_folders:
                return
            if not recursive and parent != base:
                return
            if p.suffix.lower() in _IN_PROGRESS_EXTS:
                return
        except (ValueError, OSError):
            return
        with lock:
            pending[str(p)] = time.monotonic()

    class _Handler(FileSystemEventHandler):  # type: ignore[misc]
        def on_created(self, event: object) -> None:
            if not getattr(event, "is_directory", False):
                _enqueue(getattr(event, "src_path", ""))

        def on_modified(self, event: object) -> None:
            if not getattr(event, "is_directory", False):
                _enqueue(getattr(event, "src_path", ""))

        def on_moved(self, event: object) -> None:
            if not getattr(event, "is_directory", False) and getattr(event, "dest_path", None):
                _enqueue(getattr(event, "dest_path", ""))

    def _processor() -> None:
        while not stop.is_set():
            time.sleep(0.5)
            now = time.monotonic()
            with lock:
                due = [ps for ps, t in list(pending.items()) if now - t >= 0.5]
                for ps in due:
                    del pending[ps]

            for ps in due:
                p = Path(ps)
                if not p.is_file() or ignore.matches_file(p) or not _file_stable(p):
                    continue
                cat_name, dest_sub = _classify_file(p, "extension", template, smart_mime=True)
                dest_dir = base / dest_sub
                dest = resolve_destination(dest_dir / p.name, ConflictPolicy.RENAME)
                if dest is None or p.resolve() == dest.resolve() or dry_run:
                    continue
                try:
                    dest_dir.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(p), str(dest))
                    UndoJournal().record(
                        "organizer.watch",
                        [MoveOperation(source=p, destination=dest, category=cat_name)],
                        base_dir=base,
                    )
                    _increment_count(base, 1)
                    logger.info("MOVED %s -> %s/", p.name, dest_sub)
                except OSError as exc:
                    logger.error("Failed to move %s: %s", p.name, exc)

    threading.Thread(target=_processor, daemon=True).start()
    observer = Observer()
    observer.schedule(_Handler(), str(base), recursive=recursive)
    observer.start()

    try:
        while not stop.is_set():
            time.sleep(1.0)
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        stop.set()
        observer.stop()
        observer.join()
    return True, f"Stopped watcher for {base}"
