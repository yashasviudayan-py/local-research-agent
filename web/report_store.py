"""Report persistence — JSON metadata + markdown files in reports/ directory."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from .models import ReportDetail, ReportSummary

REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"

_VALID_ID = re.compile(r"^[a-f0-9]{6,16}$")


def _validate_id(report_id: str) -> None:
    """Reject IDs that could cause path traversal."""
    if not _VALID_ID.match(report_id):
        raise ValueError(f"Invalid report ID: {report_id!r}")


def _ensure_dir() -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def save(
    report_id: str,
    topic: str,
    markdown: str,
    urls_found: int = 0,
    pages_scraped: int = 0,
    pages_failed: int = 0,
    elapsed_ms: float = 0.0,
) -> ReportSummary:
    """Save a report (markdown + JSON metadata)."""
    _validate_id(report_id)
    _ensure_dir()

    md_path = REPORTS_DIR / f"{report_id}.md"
    meta_path = REPORTS_DIR / f"{report_id}.json"

    md_path.write_text(markdown, encoding="utf-8")

    meta = {
        "id": report_id,
        "topic": topic,
        "created_at": datetime.now().isoformat(),
        "urls_found": urls_found,
        "pages_scraped": pages_scraped,
        "pages_failed": pages_failed,
        "elapsed_ms": elapsed_ms,
        "file_size": len(markdown.encode("utf-8")),
    }
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    return ReportSummary(**meta)


def list_reports() -> list[ReportSummary]:
    """List all reports, sorted by date (newest first)."""
    _ensure_dir()
    reports = []
    for meta_path in REPORTS_DIR.glob("*.json"):
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
            reports.append(ReportSummary(**data))
        except (json.JSONDecodeError, KeyError):
            continue
    reports.sort(key=lambda r: r.created_at, reverse=True)
    return reports


def get_report(report_id: str) -> Optional[ReportDetail]:
    """Get a single report with full content."""
    try:
        _validate_id(report_id)
    except ValueError:
        return None
    meta_path = REPORTS_DIR / f"{report_id}.json"
    md_path = REPORTS_DIR / f"{report_id}.md"

    if not meta_path.exists() or not md_path.exists():
        return None

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    content = md_path.read_text(encoding="utf-8")
    return ReportDetail(**meta, content=content)


def delete_report(report_id: str) -> bool:
    """Delete a report. Returns True if deleted."""
    try:
        _validate_id(report_id)
    except ValueError:
        return False
    meta_path = REPORTS_DIR / f"{report_id}.json"
    md_path = REPORTS_DIR / f"{report_id}.md"

    deleted = False
    if meta_path.exists():
        meta_path.unlink()
        deleted = True
    if md_path.exists():
        md_path.unlink()
        deleted = True
    return deleted
