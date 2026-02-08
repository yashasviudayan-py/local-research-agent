"""Pydantic models for the web API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ResearchRequest(BaseModel):
    """Incoming research job request."""

    topic: str = Field(min_length=1, max_length=500)
    model: str = Field(default="llama3.1:8b-instruct-q8_0", min_length=1, max_length=100)
    num_queries: int = Field(default=3, ge=1, le=10)
    results_per_query: int = Field(default=3, ge=1, le=10)


class JobResponse(BaseModel):
    """Returned when a job is created."""
    job_id: str
    status: str
    topic: str
    created_at: str


class JobStatusResponse(JobResponse):
    """Full job status with stats."""
    report_id: str | None = None
    error: str | None = None
    elapsed_ms: float = 0.0
    urls_found: int = 0
    pages_scraped: int = 0
    pages_failed: int = 0


class ReportSummary(BaseModel):
    """Report metadata for listing."""
    id: str
    topic: str
    created_at: str
    urls_found: int = 0
    pages_scraped: int = 0
    pages_failed: int = 0
    elapsed_ms: float = 0.0
    file_size: int = 0


class ReportDetail(ReportSummary):
    """Full report with content."""
    content: str = ""


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    ollama_reachable: bool
    ollama_models: list[str] = []
