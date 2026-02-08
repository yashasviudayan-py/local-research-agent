"""FastAPI web server for the Local Research Agent."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader

from .models import (
    HealthResponse,
    JobResponse,
    JobStatusResponse,
    ResearchRequest,
)
from . import report_store, runner

logger = logging.getLogger("web.server")

# ── Paths ──────────────────────────────────────────────────────────────
_WEB_DIR = Path(__file__).resolve().parent
_STATIC_DIR = _WEB_DIR / "static"
_TEMPLATE_DIR = _WEB_DIR / "templates"


# ── Lifespan ───────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(application: FastAPI):
    """Startup / shutdown lifecycle."""
    logger.info("Local Research Agent — web server starting")
    yield
    logger.info("Web server shutting down")


# ── App ────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Local Research Agent",
    version="1.0.0",
    lifespan=lifespan,
)

# Serve static files (CSS, JS)
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

# Jinja2 templates
_jinja = Environment(loader=FileSystemLoader(str(_TEMPLATE_DIR)), autoescape=True)


# ── Global exception handler ──────────────────────────────────────────
@app.exception_handler(Exception)
async def _unhandled_exception(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


# ══════════════════════════════════════════════════════════════════════
# Pages
# ══════════════════════════════════════════════════════════════════════
@app.get("/", response_class=HTMLResponse)
async def index():
    template = _jinja.get_template("index.html")
    return template.render()


# ══════════════════════════════════════════════════════════════════════
# Research API
# ══════════════════════════════════════════════════════════════════════
@app.post("/api/research", response_model=JobResponse)
async def start_research(request: ResearchRequest):
    """Start a new research job."""
    if not request.topic.strip():
        raise HTTPException(400, "Topic cannot be empty")

    if runner.is_busy():
        raise HTTPException(409, "A research job is already running. Please wait.")

    logger.info("Starting research: %r", request.topic)
    job = await runner.start_research(request)
    return JobResponse(
        job_id=job.id,
        status=job.status,
        topic=job.topic,
        created_at=job.created_at,
    )


@app.get("/api/research/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """Get current status of a research job."""
    job = runner.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    return JobStatusResponse(
        job_id=job.id,
        status=job.status,
        topic=job.topic,
        created_at=job.created_at,
        report_id=job.report_id,
        error=job.error,
        elapsed_ms=job.elapsed_ms,
        urls_found=job.urls_found,
        pages_scraped=job.pages_scraped,
        pages_failed=job.pages_failed,
    )


@app.get("/api/research/{job_id}/stream")
async def stream_progress(job_id: str):
    """SSE endpoint for real-time progress updates."""
    job = runner.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    async def event_generator():
        while True:
            try:
                event = await asyncio.wait_for(job.events.get(), timeout=30.0)
                event_type = event["event"]
                data = json.dumps(event["data"])
                yield f"event: {event_type}\ndata: {data}\n\n"

                if event_type in ("complete", "error"):
                    break
            except asyncio.TimeoutError:
                # Send keepalive to prevent connection dropping
                yield ": keepalive\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ══════════════════════════════════════════════════════════════════════
# Reports API
# ══════════════════════════════════════════════════════════════════════
@app.get("/api/reports")
async def list_reports():
    """List all saved reports."""
    return report_store.list_reports()


@app.get("/api/reports/{report_id}")
async def get_report(report_id: str):
    """Get a specific report with content."""
    report = report_store.get_report(report_id)
    if not report:
        raise HTTPException(404, "Report not found")
    return report


@app.delete("/api/reports/{report_id}")
async def delete_report(report_id: str):
    """Delete a report."""
    if not report_store.delete_report(report_id):
        raise HTTPException(404, "Report not found")
    logger.info("Deleted report %s", report_id)
    return {"deleted": True}


# ══════════════════════════════════════════════════════════════════════
# Health
# ══════════════════════════════════════════════════════════════════════
@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    """Check if Ollama is reachable."""
    import ollama as ollama_client

    host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    try:
        client = ollama_client.AsyncClient(host=host, timeout=5.0)
        model_list = await client.list()
        models = [m.model for m in model_list.models]
        return HealthResponse(status="ok", ollama_reachable=True, ollama_models=models)
    except Exception:
        return HealthResponse(status="degraded", ollama_reachable=False)
