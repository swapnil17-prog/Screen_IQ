"""
In-process background task runner with bounded concurrency.

Long-running AI work (resume ingestion, screening, evaluation) runs outside the
request/response cycle; progress is persisted on the rows so clients poll it.
Task state lives in Postgres, so an interrupted task is detectable on restart
(see `recover_interrupted_work`) and can be retried from the UI.

For horizontal scale, swap `spawn` for a queue (e.g. arq/Celery) — callers only
depend on this function.
"""

import asyncio
import logging
from collections.abc import Coroutine
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

_tasks: set[asyncio.Task] = set()
_semaphore: asyncio.Semaphore | None = None


def _get_semaphore() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(settings.max_concurrent_pipelines)
    return _semaphore


async def _run(coro: Coroutine[Any, Any, Any], name: str) -> None:
    async with _get_semaphore():
        try:
            await coro
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Background task %s failed", name)


def spawn(coro: Coroutine[Any, Any, Any], name: str) -> None:
    task = asyncio.create_task(_run(coro, name), name=name)
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


async def drain(timeout: float = 10.0) -> None:
    """Give running tasks a moment to finish on shutdown, then cancel the rest."""
    if not _tasks:
        return
    done, pending = await asyncio.wait(list(_tasks), timeout=timeout)
    for task in pending:
        task.cancel()
    logger.info("Background tasks drained: %d finished, %d cancelled", len(done), len(pending))


async def wait_all() -> None:
    """Test helper: wait until every spawned task (including ones they spawn) is done."""
    while _tasks:
        await asyncio.gather(*list(_tasks), return_exceptions=True)
