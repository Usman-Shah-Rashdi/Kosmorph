import shutil
import subprocess
import sys
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional


@dataclass(frozen=True, slots=True)
class BackendStatus:
    name: str
    available: bool
    path: Optional[str] = None
    version: Optional[str] = None


@lru_cache(maxsize=1)
def detect_backends() -> dict[str, BackendStatus]:
    return {
        "libreoffice": _probe_cli("libreoffice", ["soffice", "libreoffice"], ["--version"]),
        "tesseract": _probe_cli("tesseract", ["tesseract"], ["--version"]),
        "7zip": _probe_cli("7zip", ["7z", "7za"], []),
        "ms_office": _probe_ms_office(),
    }


def _probe_cli(name: str, binaries: list[str], version_args: list[str]) -> BackendStatus:
    for binary in binaries:
        exe = shutil.which(binary)
        if exe:
            version = None
            if version_args:
                try:
                    proc = subprocess.run([exe, *version_args], capture_output=True, text=True, timeout=5)
                    lines = (proc.stdout or proc.stderr).splitlines()
                    version = lines[0].strip() if lines else None
                except Exception:
                    pass
            return BackendStatus(name=name, available=True, path=exe, version=version)
    return BackendStatus(name=name, available=False)


def _probe_ms_office() -> BackendStatus:
    if sys.platform != "win32":
        return BackendStatus(name="ms_office", available=False)
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"Word.Application\CurVer") as key:
            ver, _ = winreg.QueryValueEx(key, "")
            return BackendStatus(name="ms_office", available=True, version=ver)
    except OSError:
        return BackendStatus(name="ms_office", available=False)
