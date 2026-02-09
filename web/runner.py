"""Job runner — bridges the web API to the research pipeline."""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

logger = logging.getLogger("web.runner")

from .models import ResearchRequest
from . import report_store

# Import pipeline components from parent package
import sys
from pathlib import Path

# Ensure the project root is importable
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from main import run_research, generate_report, SearcherConfig, FetcherConfig


@dataclass
class Job:
    """In-memory representation of a research job."""
    id: str
    topic: str
    status: str = "pending"
    task: Optional[asyncio.Task] = None
    events: asyncio.Queue = field(default_factory=asyncio.Queue)
    report_id: Optional[str] = None
    error: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    urls_found: int = 0
    pages_scraped: int = 0
    pages_failed: int = 0
    elapsed_ms: float = 0.0


# Module-level state
_jobs: dict[str, Job] = {}
_research_lock: Optional[asyncio.Lock] = None
_MAX_JOBS = 20


def _get_lock() -> asyncio.Lock:
    """Lazy-init the lock inside the running event loop (Python 3.9 safe)."""
    global _research_lock
    if _research_lock is None:
        _research_lock = asyncio.Lock()
    return _research_lock


def get_job(job_id: str) -> Optional[Job]:
    return _jobs.get(job_id)


def is_busy() -> bool:
    return _get_lock().locked()


async def start_research(request: ResearchRequest) -> Job:
    """Create a job and start the research pipeline in the background.

    Acquires the lock immediately (non-blocking check) so the
    is_busy() check and lock acquisition are atomic within the
    single-threaded event loop — no TOCTOU race.
    """
    lock = _get_lock()
    if lock.locked():
        raise RuntimeError("A research job is already running")

    # Acquire the lock synchronously in this event loop tick
    # (guaranteed not to block since we just checked it's free)
    await lock.acquire()

    # Evict oldest completed jobs if over limit
    if len(_jobs) >= _MAX_JOBS:
        sorted_jobs = sorted(_jobs.values(), key=lambda j: j.created_at)
        for old_job in sorted_jobs[: len(_jobs) - _MAX_JOBS + 1]:
            if old_job.status in ("completed", "failed"):
                _jobs.pop(old_job.id, None)

    job_id = uuid.uuid4().hex[:16]
    job = Job(id=job_id, topic=request.topic)
    _jobs[job_id] = job

    logger.info("Job %s created — topic: %r", job_id, request.topic)
    job.task = asyncio.create_task(_run_job(job, request))
    return job


async def _run_job(job: Job, request: ResearchRequest) -> None:
    """Execute the research pipeline as a background task."""
    try:
        def progress(event_type: str, data: dict) -> None:
            """Callback invoked by the pipeline — pushes events to the queue."""
            job.events.put_nowait({"event": event_type, "data": data})
            # Update job stats
            if event_type == "url_found":
                job.urls_found += 1
            elif event_type == "scrape_progress":
                if data.get("success"):
                    job.pages_scraped += 1
                else:
                    job.pages_failed += 1

        # Emit initial status
        job.status = "searching"
        job.events.put_nowait({
            "event": "status",
            "data": {"status": "searching", "message": "Generating search queries..."},
        })

        searcher_config = SearcherConfig(
            model=request.model,
            num_queries=request.num_queries,
            results_per_query=request.results_per_query,
        )
        fetcher_config = FetcherConfig()

        final_state = await run_research(
            job.topic, searcher_config, fetcher_config,
            progress_callback=progress,
        )

        # Generate report
        job.status = "generating"
        job.events.put_nowait({
            "event": "status",
            "data": {"status": "generating", "message": "Generating report..."},
        })

        report_content = generate_report(final_state)
        elapsed = final_state.get("elapsed_ms", 0)
        urls = final_state.get("urls", [])
        scraped = final_state.get("scraped_content", {})
        errors = final_state.get("errors", {})

        # Persist report
        report_store.save(
            report_id=job.id,
            topic=job.topic,
            markdown=report_content,
            urls_found=len(urls),
            pages_scraped=len(scraped),
            pages_failed=len(errors),
            elapsed_ms=elapsed,
        )

        # Mark complete
        job.status = "completed"
        job.report_id = job.id
        job.elapsed_ms = elapsed
        job.urls_found = len(urls)
        job.pages_scraped = len(scraped)
        job.pages_failed = len(errors)

        logger.info(
            "Job %s completed — %d URLs, %d scraped, %d failed, %.1fs",
            job.id, len(urls), len(scraped), len(errors), elapsed / 1000,
        )

        job.events.put_nowait({
            "event": "complete",
            "data": {
                "report_id": job.id,
                "elapsed_ms": elapsed,
                "urls_found": len(urls),
                "pages_scraped": len(scraped),
                "pages_failed": len(errors),
            },
        })

    except Exception as e:
        logger.exception("Job %s failed: %s", job.id, e)
        job.status = "failed"
        job.error = str(e)
        job.events.put_nowait({
            "event": "error",
            "data": {"message": str(e)},
        })
    finally:
        _get_lock().release()
