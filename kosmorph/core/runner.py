import threading
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Callable, Optional
from .contracts import ConflictPolicy, TaskContext, TaskResult
from .registry import registry


@dataclass
class JobHandle:
    job_id: str
    action_id: str
    kwargs: dict[str, Any]
    cancel_event: threading.Event
    future: Optional[Future] = None

    def cancel(self) -> None:
        self.cancel_event.set()


class TaskRunner:
    def __init__(self, max_workers: int = 2):
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="kosmorph")
        self._history: list[JobHandle] = []
        self._counter = 0

    def submit(
        self,
        action_id: str,
        *,
        on_progress: Optional[Callable[[int, int, str], None]] = None,
        on_complete: Optional[Callable[[TaskResult], None]] = None,
        conflict_policy: ConflictPolicy = ConflictPolicy.RENAME,
        dry_run: bool = False,
        **kwargs: Any,
    ) -> JobHandle:
        spec = registry.get(action_id)
        cancel_event = threading.Event()
        self._counter += 1
        job = JobHandle(
            job_id=f"job-{self._counter}",
            action_id=action_id,
            kwargs=kwargs,
            cancel_event=cancel_event,
        )

        ctx = TaskContext(
            on_progress=on_progress,
            is_cancelled=cancel_event.is_set,
            conflict_policy=conflict_policy,
            dry_run=dry_run,
        )

        def _worker() -> TaskResult:
            try:
                result = spec.handler(ctx=ctx, **kwargs)
            except Exception as exc:
                result = TaskResult(success=False, message=str(exc), errors=[str(exc)])
            if on_complete:
                on_complete(result)
            return result

        job.future = self._executor.submit(_worker)
        self._history.append(job)
        return job

    def run_sync(
        self,
        action_id: str,
        *,
        conflict_policy: ConflictPolicy = ConflictPolicy.RENAME,
        dry_run: bool = False,
        on_progress: Optional[Callable[[int, int, str], None]] = None,
        **kwargs: Any,
    ) -> TaskResult:
        spec = registry.get(action_id)
        ctx = TaskContext(
            on_progress=on_progress,
            conflict_policy=conflict_policy,
            dry_run=dry_run,
        )
        return spec.handler(ctx=ctx, **kwargs)

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)
