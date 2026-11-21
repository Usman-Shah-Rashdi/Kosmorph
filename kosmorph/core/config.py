import json
from pathlib import Path
from typing import Any


class ConfigManager:
    """Manages persistent user settings and presets in ~/.kosmos/config.json."""

    DEFAULTS: dict[str, Any] = {
        "theme": "system",
        "conflict_policy": "rename",
        "preferred_office_backend": "auto",
        "recent_directories": [],
    }

    def __init__(self, config_path: Path | None = None):
        if config_path is None:
            config_path = Path.home() / ".kosmos" / "config.json"
        self.config_path = config_path
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self._data = dict(self.DEFAULTS)
        self.load()

    def load(self) -> dict[str, Any]:
        if self.config_path.exists():
            try:
                loaded = json.loads(self.config_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    self._data.update(loaded)
            except (json.JSONDecodeError, OSError):
                pass
        return self._data

    def save(self) -> None:
        self.config_path.write_text(json.dumps(self._data, indent=2), encoding="utf-8")

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self.save()
