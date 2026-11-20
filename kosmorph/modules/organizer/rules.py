import fnmatch
from pathlib import Path

DEFAULT_CATEGORIES: dict[str, set[str]] = {
    "Images": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".ico", ".bmp", ".tiff", ".tif"},
    "Documents": {".pdf", ".docx", ".doc", ".odt", ".txt", ".rtf", ".md", ".markdown"},
    "Spreadsheets": {".xlsx", ".xls", ".ods", ".csv", ".tsv"},
    "Presentations": {".pptx", ".ppt", ".odp"},
    "Audio": {".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a"},
    "Video": {".mp4", ".mkv", ".mov", ".avi", ".webm", ".wmv"},
    "Archives": {".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar"},
    "Code": {".py", ".js", ".ts", ".html", ".css", ".json", ".yaml", ".yml", ".xml", ".sh", ".cpp", ".c", ".rs", ".go"},
    "Executables": {".exe", ".msi", ".deb", ".rpm", ".appimage", ".dmg"},
}

MAGIC_SIGNATURES: list[tuple[bytes, str]] = [
    (b"\x89PNG\r\n\x1a\n", "Images"),
    (b"\xff\xd8\xff", "Images"),
    (b"GIF87a", "Images"),
    (b"GIF89a", "Images"),
    (b"%PDF-", "Documents"),
    (b"PK\x03\x04", "Archives"),
    (b"\x1f\x8b", "Archives"),
    (b"7z\xbc\xaf'\x1c", "Archives"),
]


def detect_category_by_magic(file_path: Path) -> str | None:
    try:
        with open(file_path, "rb") as f:
            header = f.read(16)
        for sig, category in MAGIC_SIGNATURES:
            if header.startswith(sig):
                return category
    except OSError:
        pass
    return None


def load_ignore_patterns(folder: Path) -> list[str]:
    ignore_file = folder / ".kosmorphignore"
    if not ignore_file.is_file():
        return []
    patterns = []
    for line in ignore_file.read_text(encoding="utf-8", errors="ignore").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            patterns.append(stripped)
    return patterns


def is_ignored(name: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(name, pat) for pat in patterns)
