"""Content-based MIME & magic-header detection adapted from FOLDR v0.2.1."""

from __future__ import annotations

import mimetypes
from pathlib import Path

try:
    import magic as _magic  # type: ignore[import]
    _MAGIC_AVAILABLE = True
except ImportError:
    _MAGIC_AVAILABLE = False

_MIME_TO_CATEGORY: dict[str, str] = {
    "application/x-executable": "Executables",
    "application/x-dosexec": "Executables",
    "application/x-elf": "Executables",
    "application/x-mach-binary": "Executables",
    "application/x-msdownload": "Executables",
    "application/zip": "Archives",
    "application/x-tar": "Archives",
    "application/x-7z-compressed": "Archives",
    "application/gzip": "Archives",
    "application/x-rar-compressed": "Archives",
    "image/png": "Images",
    "image/jpeg": "Images",
    "image/gif": "Images",
    "image/webp": "Images",
    "image/bmp": "Images",
    "video/mp4": "Videos",
    "video/x-matroska": "Videos",
    "video/quicktime": "Videos",
    "video/x-msvideo": "Videos",
    "audio/mpeg": "Audio",
    "audio/wav": "Audio",
    "audio/flac": "Audio",
    "audio/ogg": "Audio",
    "application/pdf": "Documents",
    "application/msword": "Documents",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "Documents",
    "application/vnd.ms-excel": "Spreadsheets",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "Spreadsheets",
    "text/x-python": "Code",
    "text/x-java-source": "Code",
    "text/x-csrc": "Code",
    "text/html": "Web",
    "text/css": "Web",
    "text/javascript": "Code",
    "application/javascript": "Code",
    "text/plain": "Text & Data",
    "text/csv": "Spreadsheets",
    "application/json": "Text & Data",
}

_MAGIC_HEADERS: list[tuple[bytes, str]] = [
    (b"MZ", "Executables"),
    (b"\x7fELF", "Executables"),
    (b"\x89PNG\r\n\x1a\n", "Images"),
    (b"\xff\xd8\xff", "Images"),
    (b"GIF87a", "Images"),
    (b"GIF89a", "Images"),
    (b"%PDF-", "Documents"),
    (b"PK\x03\x04", "Archives"),
    (b"\x1f\x8b", "Archives"),
    (b"7z\xbc\xaf'\x1c", "Archives"),
]


def is_magic_available() -> bool:
    return _MAGIC_AVAILABLE


def detect_mime(path: Path) -> str | None:
    if _MAGIC_AVAILABLE:
        try:
            return _magic.from_file(str(path), mime=True)
        except Exception:
            pass
    mime, _ = mimetypes.guess_type(str(path))
    return mime


def category_from_mime(path: Path) -> str | None:
    """Infer category from file content (libmagic if available, else built-in magic bytes)."""
    if _MAGIC_AVAILABLE:
        mime = detect_mime(path)
        if mime and mime in _MIME_TO_CATEGORY:
            return _MIME_TO_CATEGORY[mime]

    try:
        with open(path, "rb") as f:
            header = f.read(16)
        for sig, cat in _MAGIC_HEADERS:
            if header.startswith(sig):
                return cat
    except OSError:
        pass
    return None
