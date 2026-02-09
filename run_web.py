#!/usr/bin/env python3
"""Web frontend for the Local Research Agent.

Start the server:
    python run_web.py

Then open http://localhost:8000 in your browser.
"""

import logging
import os
import sys

import uvicorn


def _configure_logging() -> None:
    """Set up structured logging for the web server."""
    level = logging.DEBUG if os.getenv("VERBOSE", "false").lower() == "true" else logging.INFO
    fmt = "[%(asctime)s] %(name)-16s %(levelname)-7s | %(message)s"
    logging.basicConfig(
        level=level,
        format=fmt,
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )


if __name__ == "__main__":
    _configure_logging()

    host = os.getenv("WEB_HOST", "0.0.0.0")
    try:
        port = int(os.getenv("WEB_PORT", "8000"))
    except ValueError:
        port = 8000

    print()
    print("  ┌────────────────────────────────────────────┐")
    print("  │       Local Research Agent — Web UI         │")
    print(f"  │  Open http://localhost:{port} in your browser  │")
    print("  └────────────────────────────────────────────┘")
    print()

    uvicorn.run(
        "web.server:app",
        host=host,
        port=port,
        reload=False,
        log_level="info",
    )
