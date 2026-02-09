#!/usr/bin/env python3
"""
deep_fetcher.py — CLI-ready async web fetcher for autonomous research agents.

A professional-grade Fetcher Node built on Crawl4AI's AsyncWebCrawler with
PruningContentFilter, robust error handling, and Apple Silicon optimisations.

Architecture
────────────
    ┌─────────────┐     ┌──────────────┐     ┌──────────────────┐
    │  CLI / main  │────▶│  DeepFetcher │────▶│  AsyncWebCrawler │
    │  (argparse)  │     │  (class)     │     │  (Crawl4AI)      │
    └──────┬──────┘     └──────┬───────┘     └──────────────────┘
           │                   │
           ▼                   ▼
    ┌─────────────┐     ┌──────────────┐
    │  Validators  │     │  FetchResult  │──▶ output.md
    │  (URL/args)  │     │  (dataclass)  │
    └─────────────┘     └──────────────┘

Usage
─────
    # Pass URL as argument
    python deep_fetcher.py https://example.com

    # With verbose output and custom save path
    python deep_fetcher.py https://example.com --verbose --output result.md

    # Interactive mode (no args — prompts for URL)
    python deep_fetcher.py

    # Show help
    python deep_fetcher.py --help

Requirements
────────────
    pip install -U crawl4ai
    crawl4ai-setup
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import re
import sys
import time
from dataclasses import dataclass
from dotenv import load_dotenv

# Load environment variables from .env file (if present)
load_dotenv()
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

# ──────────────────────────────────────────────────────────────────────
# Crawl4AI imports (v0.7+)
# ──────────────────────────────────────────────────────────────────────
from crawl4ai import (
    AsyncWebCrawler,
    BrowserConfig,
    CacheMode,
    CrawlerRunConfig,
)
from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

# ──────────────────────────────────────────────────────────────────────
# Logging
# ──────────────────────────────────────────────────────────────────────
logger = logging.getLogger("deep_fetcher")


def _configure_logging(verbose: bool = False) -> None:
    """Set up structured logging with optional verbose mode."""
    level = logging.DEBUG if verbose else logging.INFO
    logger.setLevel(level)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(
            logging.Formatter(
                "[%(asctime)s] %(levelname)-7s │ %(message)s",
                datefmt="%H:%M:%S",
            )
        )
        logger.addHandler(handler)


# ──────────────────────────────────────────────────────────────────────
# URL Validation
# ──────────────────────────────────────────────────────────────────────
_URL_REGEX = re.compile(
    r"^https?://"                       # scheme
    r"("
    r"([a-zA-Z0-9_-]+\.)+[a-zA-Z]{2,}" # domain
    r"|localhost"                        # or localhost
    r"|\d{1,3}(\.\d{1,3}){3}"          # or IPv4
    r")"
    r"(:\d{1,5})?"                      # optional port
    r"(/[^\s]*)?$",                     # optional path
    re.IGNORECASE,
)


def validate_url(url: str) -> str:
    """Validate and normalise a URL string.

    Args:
        url: Raw URL from CLI or interactive input.

    Returns:
        The validated URL (with scheme if missing).

    Raises:
        ValueError: If the URL is malformed or uses an unsupported scheme.
    """
    url = url.strip()

    # Auto-prepend scheme when user types "example.com/path"
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"Malformed URL (missing scheme or host): {url}")

    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Unsupported scheme '{parsed.scheme}' — use http or https")

    if not _URL_REGEX.match(url):
        raise ValueError(f"URL failed format validation: {url}")

    return url


# ──────────────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────────────
def _safe_int(env_key: str, default: int) -> int:
    """Parse an env var as int, falling back to default on bad input."""
    try:
        return int(os.getenv(env_key, str(default)))
    except (ValueError, TypeError):
        return default


def _safe_float(env_key: str, default: float) -> float:
    """Parse an env var as float, falling back to default on bad input."""
    try:
        return float(os.getenv(env_key, str(default)))
    except (ValueError, TypeError):
        return default


@dataclass(frozen=True)
class FetcherConfig:
    """Tuneable knobs — safe defaults optimised for Apple Silicon M4 Pro."""

    headless: bool = os.getenv("SCRAPER_HEADLESS", "true").lower() == "true"
    verbose: bool = os.getenv("VERBOSE", "false").lower() == "true"

    # Browser / page behaviour
    page_timeout: int = _safe_int("SCRAPER_PAGE_TIMEOUT", 30000)
    request_timeout: int = _safe_int("SCRAPER_REQUEST_TIMEOUT", 15000)

    # PruningContentFilter
    pruning_threshold: float = _safe_float("SCRAPER_PRUNING_THRESHOLD", 0.48)
    pruning_threshold_type: str = "fixed"
    min_word_threshold: int = 30

    # Tags stripped before markdown conversion
    excluded_tags: tuple[str, ...] = (
        "nav", "footer", "header", "aside",
        "form", "iframe", "noscript", "script", "style",
    )

    # Retry / resilience
    max_retries: int = _safe_int("SCRAPER_MAX_RETRIES", 2)
    retry_backoff: float = 0.5

    # Concurrency ceiling (keeps memory stable on unified-memory Macs)
    semaphore_limit: int = _safe_int("SCRAPER_SEMAPHORE_LIMIT", 6)
    cache_mode: str = os.getenv("CACHE_MODE", "BYPASS")


# ──────────────────────────────────────────────────────────────────────
# Result wrapper
# ──────────────────────────────────────────────────────────────────────
@dataclass
class FetchResult:
    """Structured output from a single fetch."""

    url: str
    raw_markdown: Optional[str] = None
    fit_markdown: Optional[str] = None
    success: bool = False
    elapsed_ms: float = 0.0
    error: Optional[str] = None
    status_code: Optional[int] = None


# ──────────────────────────────────────────────────────────────────────
# DeepFetcher
# ──────────────────────────────────────────────────────────────────────
class DeepFetcher:
    """Async, reusable web fetcher built on Crawl4AI.

    Lifecycle is managed via the async-context-manager protocol so that
    the headless browser is started once and reused across many fetches.

    Example::

        async with DeepFetcher(config) as fetcher:
            result = await fetcher.fetch("https://example.com")
            print(result.raw_markdown)
    """

    def __init__(self, config: FetcherConfig | None = None, progress_callback=None) -> None:
        self._cfg = config or FetcherConfig()
        self._progress = progress_callback
        self._crawler: Optional[AsyncWebCrawler] = None
        self._semaphore = asyncio.Semaphore(self._cfg.semaphore_limit)

    # ── lifecycle ─────────────────────────────────────────────────────

    async def __aenter__(self) -> DeepFetcher:
        await self._start()
        return self

    async def __aexit__(self, *exc) -> None:
        await self._stop()

    async def _start(self) -> None:
        """Launch the headless Chromium browser."""
        logger.debug("Launching browser (headless=%s)…", self._cfg.headless)
        browser_cfg = BrowserConfig(
            headless=self._cfg.headless,
            verbose=self._cfg.verbose,
            extra_args=[
                "--disable-gpu-sandbox",
                "--disable-dev-shm-usage",
                "--disable-background-networking",
                "--disable-extensions",
                "--disable-sync",
                "--no-first-run",
                "--disable-component-update",
            ],
        )
        self._crawler = AsyncWebCrawler(config=browser_cfg)
        await self._crawler.__aenter__()
        logger.info("Browser ready")

    async def _stop(self) -> None:
        """Gracefully shut down the browser."""
        if self._crawler is not None:
            await self._crawler.__aexit__(None, None, None)
            self._crawler = None
            logger.info("Browser stopped")

    # ── config builder ────────────────────────────────────────────────

    def _build_run_config(self) -> CrawlerRunConfig:
        """Build a CrawlerRunConfig with PruningContentFilter inside
        DefaultMarkdownGenerator (required API for Crawl4AI v0.7+)."""
        prune_filter = PruningContentFilter(
            threshold=self._cfg.pruning_threshold,
            threshold_type=self._cfg.pruning_threshold_type,
            min_word_threshold=self._cfg.min_word_threshold,
        )
        md_generator = DefaultMarkdownGenerator(content_filter=prune_filter)

        cache = (
            CacheMode.ENABLED
            if self._cfg.cache_mode == "ENABLED"
            else CacheMode.BYPASS
        )
        return CrawlerRunConfig(
            markdown_generator=md_generator,
            excluded_tags=list(self._cfg.excluded_tags),
            page_timeout=self._cfg.page_timeout,
            cache_mode=cache,
            exclude_external_images=True,
            process_iframes=False,
        )

    # ── public API ────────────────────────────────────────────────────

    async def fetch(self, url: str) -> FetchResult:
        """Fetch *url* and return pruned markdown with retry logic.

        Args:
            url: A validated, fully-qualified URL.

        Returns:
            ``FetchResult`` containing ``raw_markdown``, ``fit_markdown``,
            timing data, and error info (if any).
        """
        if self._crawler is None:
            raise RuntimeError("DeepFetcher not started — use `async with`")

        run_cfg = self._build_run_config()
        last_error: Optional[str] = None

        for attempt in range(1, self._cfg.max_retries + 1):
            try:
                logger.debug(
                    "Attempt %d/%d — fetching %s",
                    attempt, self._cfg.max_retries, url,
                )
                async with self._semaphore:
                    t0 = time.perf_counter()
                    result = await asyncio.wait_for(
                        self._crawler.arun(url=url, config=run_cfg),
                        timeout=self._cfg.request_timeout / 1000,
                    )
                    elapsed = (time.perf_counter() - t0) * 1000

                status = getattr(result, "status_code", None)

                # ── HTTP error ────────────────────────────────────────
                if status and status >= 400:
                    msg = f"HTTP {status} for {url}"
                    logger.warning(msg)
                    return FetchResult(
                        url=url, success=False, elapsed_ms=elapsed,
                        error=msg, status_code=status,
                    )

                # ── crawl-level failure ───────────────────────────────
                if not result.success:
                    last_error = getattr(
                        result, "error_message", "Unknown crawl error"
                    )
                    logger.warning(
                        "Attempt %d failed: %s", attempt, last_error,
                    )
                    await asyncio.sleep(
                        self._cfg.retry_backoff * (2 ** (attempt - 1))
                    )
                    continue

                # ── extract markdown ──────────────────────────────────
                md_obj = result.markdown
                raw_md = (
                    md_obj.raw_markdown
                    if hasattr(md_obj, "raw_markdown")
                    else str(md_obj)
                )
                fit_md = (
                    md_obj.fit_markdown
                    if hasattr(md_obj, "fit_markdown")
                    else None
                )

                logger.info(
                    "Fetched in %.0f ms — raw: %s chars, fit: %s chars",
                    elapsed, len(raw_md or ""), len(fit_md or ""),
                )
                return FetchResult(
                    url=url, raw_markdown=raw_md, fit_markdown=fit_md,
                    success=True, elapsed_ms=elapsed, status_code=status,
                )

            except asyncio.TimeoutError:
                last_error = f"Timeout ({self._cfg.request_timeout} ms)"
                logger.warning("Attempt %d timed out", attempt)
                await asyncio.sleep(
                    self._cfg.retry_backoff * (2 ** (attempt - 1))
                )

            except Exception as exc:  # noqa: BLE001
                last_error = f"{type(exc).__name__}: {exc}"
                logger.error("Attempt %d raised %s", attempt, last_error)
                await asyncio.sleep(
                    self._cfg.retry_backoff * (2 ** (attempt - 1))
                )

        return FetchResult(url=url, success=False, error=last_error)

    async def fetch_many(self, urls: list[str]) -> list[FetchResult]:
        """Fetch multiple URLs concurrently (semaphore-bounded)."""
        tasks = [asyncio.ensure_future(self.fetch(u)) for u in urls]
        results: list[FetchResult] = []
        total = len(tasks)
        for i, coro in enumerate(asyncio.as_completed(tasks), 1):
            result = await coro
            results.append(result)
            if self._progress:
                self._progress("scrape_progress", {
                    "url": result.url,
                    "success": result.success,
                    "chars": len(result.raw_markdown or ""),
                    "elapsed_ms": result.elapsed_ms,
                    "completed": i,
                    "total": total,
                })
        return results


# ──────────────────────────────────────────────────────────────────────
# File I/O
# ──────────────────────────────────────────────────────────────────────
def save_markdown(content: str, path: Path) -> Path:
    """Write *content* to *path*, creating parent dirs if needed.

    Returns:
        The resolved absolute path of the saved file.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path.resolve()


# ──────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────
def build_parser() -> argparse.ArgumentParser:
    """Construct the argument parser."""
    parser = argparse.ArgumentParser(
        prog="deep_fetcher",
        description=(
            "Fetch a web page and extract clean Markdown using Crawl4AI "
            "with PruningContentFilter. Optimised for Apple Silicon."
        ),
        epilog=(
            "Examples:\n"
            "  python deep_fetcher.py https://example.com\n"
            "  python deep_fetcher.py https://example.com -v -o result.md\n"
            "  python deep_fetcher.py --fit --no-save https://example.com\n"
            "  python deep_fetcher.py              # interactive prompt\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "url",
        nargs="?",
        default=None,
        help="Target URL to crawl. If omitted, you'll be prompted interactively.",
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        default="output.md",
        help="Path for the saved markdown file (default: output.md).",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Print detailed status updates to stderr.",
    )
    parser.add_argument(
        "--fit",
        action="store_true",
        help="Save fit_markdown (pruned) instead of raw_markdown.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=15000,
        help="Per-request timeout in milliseconds (default: 15000).",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Print markdown to stdout only; do not write a file.",
    )
    return parser


def resolve_url(args_url: Optional[str]) -> str:
    """Get a validated URL from CLI args or interactive prompt.

    Args:
        args_url: The URL argument from argparse (may be ``None``).

    Returns:
        A validated URL string.
    """
    raw = args_url
    if not raw:
        try:
            raw = input("\n🔗  Enter URL to fetch: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAborted.")
            sys.exit(0)

    if not raw:
        print("Error: No URL provided.", file=sys.stderr)
        sys.exit(1)

    try:
        return validate_url(raw)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


# ──────────────────────────────────────────────────────────────────────
# Entry-point
# ──────────────────────────────────────────────────────────────────────
async def async_main(args: argparse.Namespace) -> None:
    """Core async workflow: validate → fetch → save."""
    _configure_logging(verbose=args.verbose)

    url = resolve_url(args.url)
    output_path = Path(args.output)

    config = FetcherConfig(
        verbose=args.verbose,
        request_timeout=args.timeout,
    )

    # ── Fetch ─────────────────────────────────────────────────────────
    logger.info("Fetching → %s", url)

    async with DeepFetcher(config) as fetcher:
        result = await fetcher.fetch(url)

    if not result.success:
        logger.error("Crawl failed: %s", result.error)
        print(f"\n❌  Crawl failed: {result.error}", file=sys.stderr)
        sys.exit(1)

    # ── Choose content ────────────────────────────────────────────────
    content = (
        result.fit_markdown if args.fit and result.fit_markdown
        else result.raw_markdown
    ) or ""

    if not content:
        logger.warning("Page returned empty markdown")
        print("⚠️  Warning: page returned empty markdown.", file=sys.stderr)
        sys.exit(1)

    # ── Output ────────────────────────────────────────────────────────
    if args.no_save:
        print(content)
    else:
        logger.info("Saving → %s", output_path)
        saved = save_markdown(content, output_path)
        logger.info("Saved %d chars to %s", len(content), saved)

    # ── Summary ───────────────────────────────────────────────────────
    summary = (
        f"\n{'─' * 60}\n"
        f"  ✅  URL       : {result.url}\n"
        f"  ⏱   Elapsed   : {result.elapsed_ms:.0f} ms\n"
        f"  📄  Raw chars  : {len(result.raw_markdown or ''):,}\n"
        f"  ✂️   Fit chars  : {len(result.fit_markdown or ''):,}\n"
        f"  💾  Saved to   : "
        f"{output_path.resolve() if not args.no_save else '(stdout)'}\n"
        f"{'─' * 60}"
    )
    print(summary)


def main() -> None:
    """Synchronous entry-point for the CLI."""
    parser = build_parser()
    args = parser.parse_args()
    asyncio.run(async_main(args))


if __name__ == "__main__":
    main()