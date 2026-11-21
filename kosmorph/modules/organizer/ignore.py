"""Ignore-rule engine adapted from FOLDR v0.2.1 (supports .kosmosignore & .foldrignore)."""

from __future__ import annotations

import fnmatch
from pathlib import Path

IGNORE_FILENAMES = (".kosmosignore", ".foldrignore")

ALWAYS_IGNORE_DIRS = {".git", ".svn", ".hg", "__pycache__", "node_modules", ".venv", "venv", ".kosmos"}
ALWAYS_IGNORE_FILES = {".DS_Store", "Thumbs.db", "desktop.ini"}


class IgnoreRules:
    def __init__(
        self,
        base: Path,
        extra_patterns: list[str] | None = None,
        use_global: bool = False,
        disabled: bool = False,
    ):
        self.disabled = disabled
        self._file_patterns: list[str] = []
        self._dir_patterns: list[str] = []

        if disabled:
            return

        for fname in IGNORE_FILENAMES:
            candidate = base / fname
            if candidate.is_file():
                self._load_file(candidate)

        if use_global:
            for fname in IGNORE_FILENAMES:
                g_file = Path.home() / ".kosmos" / fname
                if g_file.is_file():
                    self._load_file(g_file)

        for pat in (extra_patterns or []):
            if pat.strip():
                self._classify(pat.strip())

    def _load_file(self, path: Path) -> None:
        for line in path.read_text(encoding="utf-8-sig", errors="ignore").splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                self._classify(stripped)

    def _classify(self, pattern: str) -> None:
        if pattern.endswith("/"):
            self._dir_patterns.append(pattern.rstrip("/"))
        else:
            self._file_patterns.append(pattern)

    def matches_file(self, path: Path, rel_path: str = "") -> bool:
        name = path.name
        if name in ALWAYS_IGNORE_FILES or name in IGNORE_FILENAMES:
            return True
        if self.disabled:
            return False
        for pat in self._file_patterns:
            if fnmatch.fnmatch(name, pat) or (rel_path and fnmatch.fnmatch(rel_path, pat)):
                return True
        return False

    def matches_dir(self, path: Path, rel_path: str = "") -> bool:
        name = path.name
        if name in ALWAYS_IGNORE_DIRS:
            return True
        if self.disabled:
            return False
        for pat in (*self._dir_patterns, *self._file_patterns):
            if fnmatch.fnmatch(name, pat) or (rel_path and fnmatch.fnmatch(rel_path, pat)):
                return True
        return False
