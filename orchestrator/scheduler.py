"""
Task scheduler — priority-aware async task queue for the orchestrator.
"""

import asyncio
import heapq
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass(order=True)
class ScheduledTask:
    priority: int
    task_id: str = field(compare=False)
    coro: Coroutine = field(compare=False)
    scheduled_at: str = field(compare=False)
    metadata: Dict[str, Any] = field(compare=False, default_factory=dict)


class TaskScheduler:
    """
    Priority-based async task scheduler.

    Lower priority value = higher urgency (processed first).
    """

    def __init__(self, max_concurrent: int = 10):
        self._queue: List[ScheduledTask] = []
        self._max_concurrent = max_concurrent
        self._running_tasks: Dict[str, asyncio.Task] = {}
        self._semaphore = asyncio.Semaphore(max_concurrent)

    def schedule(
        self,
        coro: Coroutine,
        task_id: str,
        priority: int = 5,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add a coroutine to the scheduler queue."""
        task = ScheduledTask(
            priority=priority,
            task_id=task_id,
            coro=coro,
            scheduled_at=datetime.now(timezone.utc).isoformat(),
            metadata=metadata or {},
        )
        heapq.heappush(self._queue, task)
        logger.debug("Scheduled task %s (priority=%d)", task_id, priority)

    async def run_next(self) -> Optional[Any]:
        """Pop and execute the highest-priority queued task."""
        if not self._queue:
            return None
        task = heapq.heappop(self._queue)
        async with self._semaphore:
            return await task.coro

    async def run_all(self) -> List[Any]:
        """Drain the queue, executing tasks concurrently up to max_concurrent."""
        results = []
        while self._queue:
            batch = []
            while self._queue and len(batch) < self._max_concurrent:
                batch.append(heapq.heappop(self._queue).coro)
            batch_results = await asyncio.gather(*batch, return_exceptions=True)
            results.extend(batch_results)
        return results

    def pending_count(self) -> int:
        return len(self._queue)

    def clear(self) -> None:
        self._queue.clear()
