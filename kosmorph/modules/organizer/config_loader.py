"""TOML category configuration loader adapted from FOLDR v0.2.1."""

from __future__ import annotations

import logging
from copy import deepcopy
from pathlib import Path
from .categories import CATEGORIES_TEMPLATE

logger = logging.getLogger("kosmos.organizer.config")

try:
    import tomllib
except ImportError:  # Python 3.10 fallback if tomli is installed
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ImportError:
        tomllib = None  # type: ignore[assignment]


_DEFAULT_TOML = """# Kosmos Category Configuration (TOML)
# Set merge = true to extend built-in categories, or false to replace them completely.

[kosmos]
merge = true

# Example custom category:
# [RAW Photos]
# folder = "RAW_Photos"
# extensions = [".raw", ".cr2", ".nef", ".arw", ".dng"]
"""


def default_categories_toml() -> Path:
    return Path.home() / ".kosmos" / "categories.toml"


def ensure_categories_toml() -> Path:
    path = default_categories_toml()
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_DEFAULT_TOML, encoding="utf-8")
    return path


def _toml_to_template(data: dict) -> dict[str, dict]:
    template: dict[str, dict] = {}
    for section, value in data.items():
        if section in {"kosmos", "foldr"} or not isinstance(value, dict):
            continue
        exts = value.get("extensions") or value.get("ext") or []
        folder = value.get("folder", section)
        template[section] = {
            "folder": folder,
            "ext": {e.lower().strip() for e in exts if isinstance(e, str) and e.strip()},
        }
    return template


def load_category_template(config_path: Path | None = None) -> tuple[dict[str, dict], str | None]:
    target = config_path or (default_categories_toml() if default_categories_toml().exists() else None)
    if target is None or tomllib is None:
        return deepcopy(CATEGORIES_TEMPLATE), None

    if not target.exists():
        raise FileNotFoundError(f"Category config not found: {target}")

    try:
        with open(target, "rb") as f:
            raw = tomllib.load(f)
    except Exception as exc:
        logger.warning("Invalid TOML in %s (%s); falling back to built-in categories.", target, exc)
        return deepcopy(CATEGORIES_TEMPLATE), None

    user_t = _toml_to_template(raw)
    meta = raw.get("kosmos") or raw.get("foldr") or {}
    should_merge = meta.get("merge", True)

    if should_merge:
        merged = deepcopy(CATEGORIES_TEMPLATE)
        for name, data in user_t.items():
            if name in merged:
                merged[name]["ext"] |= data["ext"]
                if "folder" in data:
                    merged[name]["folder"] = data["folder"]
            else:
                merged[name] = data
        return merged, str(target)

    return user_t, str(target)
