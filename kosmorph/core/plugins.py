import importlib.util
from pathlib import Path


def load_external_plugins(plugin_dir: Path | None = None) -> list[str]:
    """Dynamically load external .py plugin files that call @register_action."""
    if plugin_dir is None:
        plugin_dir = Path.home() / ".kosmos" / "plugins"
    if not plugin_dir.is_dir():
        return []

    loaded: list[str] = []
    for file in sorted(plugin_dir.glob("*.py")):
        if file.name.startswith("_"):
            continue
        spec = importlib.util.spec_from_file_location(f"kosmos_plugin_{file.stem}", file)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            loaded.append(file.stem)
    return loaded
