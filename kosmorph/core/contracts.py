from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional


class ConflictPolicy(str, Enum):
    RENAME = "rename"
    OVERWRITE = "overwrite"
    SKIP = "skip"


@dataclass(slots=True)
class MoveOperation:
    source: Path
    destination: Path
    reason: str = ""


@dataclass(slots=True)
class TaskContext:
    """Execution context passed to every backend action."""
    on_progress: Optional[Callable[[int, int, str], None]] = None
    is_cancelled: Callable[[], bool] = lambda: False
    conflict_policy: ConflictPolicy = ConflictPolicy.RENAME
    dry_run: bool = False

    def report(self, current: int, total: int, message: str = "") -> None:
        if self.on_progress:
            self.on_progress(current, total, message)


@dataclass(slots=True)
class TaskResult:
    """Standardized response returned by every backend action."""
    success: bool
    message: str
    outputs: list[Path] = field(default_factory=list)
    operations: list[MoveOperation] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
