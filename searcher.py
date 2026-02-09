#!/usr/bin/env python3
"""
searcher.py — LLM-powered research query generator + parallel web search.

Uses a local Ollama model to generate diverse search queries from a
research topic, then executes them in parallel via DuckDuckGo, returning
a deduplicated list of URLs ready for the Fetcher Node (scraper.py).

Architecture
────────────
    ┌────────────┐     ┌───────────────┐     ┌─────────────────┐
    │  CLI/main   │────▶│ DeepSearcher  │────▶│  Ollama (local) │
    │  (topic)    │     │               │     │  llama3.1:8b    │
    └─────────────┘     │               │     └─────────────────┘
                        │               │
                        │  3 queries    │     ┌─────────────────┐
                        │  ────────────▶│────▶│  DuckDuckGo     │
                        │               │     │  (AsyncDDGS)    │
                        │               │     └─────────────────┘
                        │  dedup URLs   │
                        └───────┬───────┘
                                │
                                ▼
                        list[SearchResult]

Usage
─────
    python searcher.py "impact of LLMs on drug discovery"
    python searcher.py --model llama3.1:8b-instruct-q8_0 "quantum computing"
    python searcher.py -v --top 5 "renewable energy storage"
    python searcher.py                    # interactive prompt

Requirements
────────────
    pip install ollama ddgs
    # Ollama server must be running:  ollama serve
    # Model must be pulled:           ollama pull llama3.1:8b-instruct-q8_0
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import re
import sys
import time
from dataclasses import dataclass, field
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file (if present)
load_dotenv()

import ollama
from ddgs import DDGS

# ──────────────────────────────────────────────────────────────────────
# Logging
# ──────────────────────────────────────────────────────────────────────
logger = logging.getLogger("deep_searcher")


def _configure_logging(verbose: bool = False) -> None:
    """Set up logging with optional verbose (DEBUG) mode."""
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
# Data models
# ──────────────────────────────────────────────────────────────────────
@dataclass
class SearchResult:
    """A single search result from DuckDuckGo."""

    title: str
    url: str
    snippet: str
    source_query: str


@dataclass
class SearchReport:
    """Aggregated output from a full search run."""

    topic: str
    queries: list[str]
    results: list[SearchResult]
    unique_urls: list[str]
    elapsed_ms: float = 0.0


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
class SearcherConfig:
    """Tuneable knobs for DeepSearcher."""

    # Ollama
    model: str = os.getenv("OLLAMA_MODEL", "llama3.1:8b-instruct-q8_0")
    ollama_host: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    ollama_timeout: float = _safe_float("OLLAMA_TIMEOUT", 60.0)

    # Query generation
    num_queries: int = _safe_int("SEARCH_NUM_QUERIES", 3)
    temperature: float = 0.7            # higher = more diverse queries

    # DuckDuckGo
    results_per_query: int = _safe_int("SEARCH_RESULTS_PER_QUERY", 3)
    search_region: str = os.getenv("SEARCH_REGION", "wt-wt")
    search_safesearch: str = os.getenv("SEARCH_SAFESEARCH", "moderate")
    search_timelimit: Optional[str] = os.getenv("SEARCH_TIMELIMIT", None)

    # Concurrency
    max_concurrent_searches: int = _safe_int("MAX_CONCURRENT_SEARCHES", 3)


# ──────────────────────────────────────────────────────────────────────
# Prompt template
# ──────────────────────────────────────────────────────────────────────
_QUERY_GEN_PROMPT = """\
You are a research assistant. Your task is to generate exactly {n} diverse \
web search queries for the following research topic.

RULES:
- Each query must approach the topic from a DIFFERENT angle \
(e.g., overview, recent developments, technical details, comparisons, \
expert opinions, case studies).
- Queries should be concise (3-8 words each).
- Respond ONLY with a JSON array of strings. No explanation, no markdown \
fences, no preamble.

TOPIC: {topic}

RESPOND WITH ONLY A JSON ARRAY:"""


# ──────────────────────────────────────────────────────────────────────
# DeepSearcher
# ──────────────────────────────────────────────────────────────────────
class DeepSearcher:
    """LLM-powered research query generator with parallel web search.

    Workflow:
        1. Send topic to local Ollama model → receive N diverse queries.
        2. Execute queries in parallel against DuckDuckGo.
        3. Collect, deduplicate, and return URLs + metadata.

    Example::

        searcher = DeepSearcher()
        report = await searcher.search("impact of LLMs on drug discovery")
        for url in report.unique_urls:
            print(url)
    """

    def __init__(self, config: SearcherConfig | None = None, progress_callback=None) -> None:
        self._cfg = config or SearcherConfig()
        self._progress = progress_callback
        self._client = ollama.AsyncClient(
            host=self._cfg.ollama_host,
            timeout=self._cfg.ollama_timeout,
        )

    def _emit(self, event_type: str, data: dict) -> None:
        """Fire progress callback if registered."""
        if self._progress:
            self._progress(event_type, data)

    # ── query generation (Ollama) ─────────────────────────────────────

    async def generate_queries(self, topic: str) -> list[str]:
        """Ask the local LLM to produce diverse search queries.

        Args:
            topic: The research topic or question.

        Returns:
            A list of search query strings.

        Raises:
            ConnectionError: If the Ollama server is unreachable.
            ValueError: If the LLM response can't be parsed as JSON.
        """
        prompt = _QUERY_GEN_PROMPT.format(
            n=self._cfg.num_queries, topic=topic,
        )

        logger.debug("Sending prompt to %s…", self._cfg.model)

        try:
            response = await self._client.chat(
                model=self._cfg.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a precise JSON generator. "
                            "Output ONLY valid JSON with no extra text."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                options={"temperature": self._cfg.temperature},
            )
        except ollama.ResponseError as exc:
            raise ConnectionError(
                f"Ollama returned an error: {exc}"
            ) from exc
        except Exception as exc:
            raise ConnectionError(
                f"Cannot reach Ollama at {self._cfg.ollama_host}. "
                f"Is `ollama serve` running? ({type(exc).__name__}: {exc})"
            ) from exc

        raw = response.message.content.strip()
        logger.debug("Raw LLM response: %s", raw)

        queries = self._parse_queries(raw)

        if not queries:
            raise ValueError(
                f"LLM returned no parsable queries. Raw output:\n{raw}"
            )

        logger.info(
            "Generated %d queries: %s", len(queries), queries,
        )
        self._emit("queries", {"queries": queries})
        return queries

    @staticmethod
    def _parse_queries(raw: str) -> list[str]:
        """Robustly extract a list of query strings from LLM output.

        Handles JSON arrays, markdown fences, numbered lists, and
        newline-separated queries as fallback.
        """
        # Strip markdown code fences if present
        cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip()
        cleaned = cleaned.rstrip("`").strip()

        # Attempt 1: direct JSON parse
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, list):
                return [str(q).strip() for q in parsed if str(q).strip()]
        except json.JSONDecodeError:
            pass

        # Attempt 2: find JSON array embedded in text
        match = re.search(r"\[.*?\]", cleaned, re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group())
                if isinstance(parsed, list):
                    return [str(q).strip() for q in parsed if str(q).strip()]
            except json.JSONDecodeError:
                pass

        # Attempt 3: numbered list (e.g., "1. query here")
        numbered = re.findall(r"^\d+[\.\)]\s*(.+)$", cleaned, re.MULTILINE)
        if numbered:
            return [q.strip().strip('"\'') for q in numbered]

        # Attempt 4: newline-separated lines
        lines = [
            ln.strip().strip('"\'')
            for ln in cleaned.splitlines()
            if ln.strip() and not ln.strip().startswith(("{", "[", "]", "}"))
        ]
        return lines if lines else []

    # ── web search (DuckDuckGo) ───────────────────────────────────────

    async def _run_single_search(
        self, query: str, semaphore: asyncio.Semaphore,
    ) -> list[SearchResult]:
        """Execute one DuckDuckGo search (sync DDGS wrapped in executor).

        The `duckduckgo_search` DDGS.text() is synchronous, so we
        offload it to a thread pool to keep the event loop responsive.
        """
        async with semaphore:
            logger.debug("Searching DDG: %r", query)

            loop = asyncio.get_running_loop()
            try:
                raw_results = await loop.run_in_executor(
                    None,               # default ThreadPoolExecutor
                    self._sync_ddg_search,
                    query,
                )
            except Exception as exc:
                logger.warning(
                    "Search failed for %r: %s", query, exc,
                )
                return []

            results = [
                SearchResult(
                    title=r.get("title", ""),
                    url=r.get("href", ""),
                    snippet=r.get("body", ""),
                    source_query=query,
                )
                for r in (raw_results or [])
                if r.get("href")
            ]
            logger.debug(
                "Got %d results for %r", len(results), query,
            )
            return results

    def _sync_ddg_search(self, query: str) -> list[dict]:
        """Synchronous DuckDuckGo search — runs in a thread.

        Uses context manager to handle the connection safely and avoid timeouts.
        """
        # 'with' handles the connection safely to avoid timeouts
        with DDGS() as ddgs:
            # text() returns a generator; we convert it to a list
            results = [
                r for r in ddgs.text(
                    query,
                    region=self._cfg.search_region,
                    safesearch=self._cfg.search_safesearch,
                    timelimit=self._cfg.search_timelimit,
                    max_results=self._cfg.results_per_query,
                )
            ]
            return results

    # ── main search pipeline ─────────────────────────────────────────

    async def search(self, topic: str) -> SearchReport:
        """Full pipeline: generate queries → search → deduplicate.

        Args:
            topic: The research topic or question.

        Returns:
            A ``SearchReport`` with queries, results, and unique URLs.
        """
        t0 = time.perf_counter()

        # Step 1 — Generate queries via LLM
        logger.info("Generating search queries for: %r", topic)
        queries = await self.generate_queries(topic)

        # Step 2 — Execute searches in parallel
        logger.info("Executing %d searches…", len(queries))
        semaphore = asyncio.Semaphore(self._cfg.max_concurrent_searches)
        tasks = [
            self._run_single_search(q, semaphore) for q in queries
        ]
        nested_results = await asyncio.gather(*tasks)

        # Step 3 — Flatten and deduplicate
        all_results: list[SearchResult] = []
        seen_urls: set[str] = set()
        unique_urls: list[str] = []

        for batch in nested_results:
            for result in batch:
                all_results.append(result)
                normalised = result.url.rstrip("/").lower()
                if normalised not in seen_urls:
                    seen_urls.add(normalised)
                    unique_urls.append(result.url)
                    self._emit("url_found", {
                        "url": result.url,
                        "title": result.title,
                        "query": result.source_query,
                    })

        elapsed = (time.perf_counter() - t0) * 1000

        logger.info(
            "Found %d total results, %d unique URLs in %.0f ms",
            len(all_results), len(unique_urls), elapsed,
        )

        return SearchReport(
            topic=topic,
            queries=queries,
            results=all_results,
            unique_urls=unique_urls,
            elapsed_ms=elapsed,
        )


# ──────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────
def build_parser() -> argparse.ArgumentParser:
    """Construct the argument parser."""
    parser = argparse.ArgumentParser(
        prog="searcher",
        description=(
            "Generate diverse search queries via a local Ollama LLM, "
            "then execute them on DuckDuckGo and collect unique URLs."
        ),
        epilog=(
            "Examples:\n"
            '  python searcher.py "impact of LLMs on drug discovery"\n'
            '  python searcher.py -v --model llama3.1 "quantum computing"\n'
            '  python searcher.py --top 5 "renewable energy"\n'
            "  python searcher.py              # interactive prompt\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "topic",
        nargs="?",
        default=None,
        help="Research topic. If omitted, you'll be prompted interactively.",
    )
    parser.add_argument(
        "-m", "--model",
        type=str,
        default="llama3.1:8b-instruct-q8_0",
        help="Ollama model name (default: llama3.1:8b-instruct-q8_0).",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="http://localhost:11434",
        help="Ollama server URL (default: http://localhost:11434).",
    )
    parser.add_argument(
        "-n", "--num-queries",
        type=int,
        default=3,
        help="Number of search queries to generate (default: 3).",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=3,
        help="Number of results per query from DuckDuckGo (default: 3).",
    )
    parser.add_argument(
        "-t", "--timelimit",
        type=str,
        default=None,
        choices=["d", "w", "m", "y"],
        help="Time filter for search results: d(ay), w(eek), m(onth), y(ear).",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Print detailed status updates.",
    )
    return parser


def resolve_topic(args_topic: Optional[str]) -> str:
    """Get topic from CLI args or interactive prompt."""
    raw = args_topic
    if not raw:
        try:
            raw = input("\n🔍  Enter research topic: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAborted.")
            sys.exit(0)

    if not raw:
        print("Error: No topic provided.", file=sys.stderr)
        sys.exit(1)

    return raw


# ──────────────────────────────────────────────────────────────────────
# Entry-point
# ──────────────────────────────────────────────────────────────────────
async def async_main(args: argparse.Namespace) -> None:
    """Core async workflow: topic → queries → search → report."""
    _configure_logging(verbose=args.verbose)

    topic = resolve_topic(args.topic)

    config = SearcherConfig(
        model=args.model,
        ollama_host=args.host,
        num_queries=args.num_queries,
        results_per_query=args.top,
        search_timelimit=args.timelimit,
    )

    searcher = DeepSearcher(config)

    # ── Run search pipeline ───────────────────────────────────────────
    try:
        report = await searcher.search(topic)
    except ConnectionError as exc:
        print(f"\n❌  Ollama connection error: {exc}", file=sys.stderr)
        print(
            "    Make sure `ollama serve` is running and the model is pulled.",
            file=sys.stderr,
        )
        sys.exit(1)
    except ValueError as exc:
        print(f"\n❌  Query generation error: {exc}", file=sys.stderr)
        sys.exit(1)

    # ── Print report ──────────────────────────────────────────────────
    print(f"\n{'═' * 64}")
    print(f"  🔍  TOPIC : {report.topic}")
    print(f"  ⏱   TIME  : {report.elapsed_ms:.0f} ms")
    print(f"{'═' * 64}")

    print("\n  📝  GENERATED QUERIES:")
    for i, q in enumerate(report.queries, 1):
        print(f"      {i}. {q}")

    print(f"\n  🌐  UNIQUE URLs ({len(report.unique_urls)}):")
    for i, url in enumerate(report.unique_urls, 1):
        print(f"      {i:>2}. {url}")

    # Also show which query each result came from in verbose mode
    if args.verbose and report.results:
        print(f"\n  📊  DETAILED RESULTS ({len(report.results)}):")
        for r in report.results:
            print(f"      [{r.source_query}]")
            print(f"        {r.title}")
            print(f"        {r.url}")
            print(f"        {r.snippet[:120]}…" if len(r.snippet) > 120 else f"        {r.snippet}")
            print()

    print(f"{'═' * 64}\n")


def main() -> None:
    """Synchronous entry-point."""
    parser = build_parser()
    args = parser.parse_args()
    asyncio.run(async_main(args))


if __name__ == "__main__":
    main()