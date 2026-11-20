from dataclasses import dataclass, field
from typing import Callable, Optional
from .contracts import TaskResult


@dataclass(slots=True)
class ActionSpec:
    id: str
    name: str
    category: str
    description: str
    handler: Callable[..., TaskResult]
    input_extensions: set[str] = field(default_factory=set)
    output_formats: list[str] = field(default_factory=list)
    supports_batch: bool = True
    supports_dry_run: bool = False
    required_backends: list[str] = field(default_factory=list)


class ActionRegistry:
    def __init__(self):
        self._actions: dict[str, ActionSpec] = {}

    def register(
        self,
        *,
        id: str,
        name: str,
        category: str,
        description: str = "",
        input_extensions: Optional[set[str]] = None,
        output_formats: Optional[list[str]] = None,
        supports_batch: bool = True,
        supports_dry_run: bool = False,
        required_backends: Optional[list[str]] = None,
    ):
        def decorator(func: Callable[..., TaskResult]):
            self._actions[id] = ActionSpec(
                id=id,
                name=name,
                category=category,
                description=description,
                handler=func,
                input_extensions={ext.lower() for ext in (input_extensions or set())},
                output_formats=output_formats or [],
                supports_batch=supports_batch,
                supports_dry_run=supports_dry_run,
                required_backends=required_backends or [],
            )
            return func
        return decorator

    def get(self, action_id: str) -> ActionSpec:
        if action_id not in self._actions:
            raise KeyError(f"Unknown Kosmorph action: {action_id}")
        return self._actions[action_id]

    def all_actions(self) -> list[ActionSpec]:
        return list(self._actions.values())

    def matching_actions(self, extensions: set[str]) -> list[ActionSpec]:
        normalized = {ext.lower() for ext in extensions}
        if not normalized:
            return []
        return [
            spec for spec in self._actions.values()
            if spec.input_extensions and normalized.issubset(spec.input_extensions)
        ]

    def search(self, query: str) -> list[ActionSpec]:
        q = query.strip().lower()
        if not q:
            return self.all_actions()
        return [
            spec for spec in self._actions.values()
            if q in spec.id.lower()
            or q in spec.name.lower()
            or q in spec.description.lower()
            or q in spec.category.lower()
        ]


registry = ActionRegistry()
register_action = registry.register
