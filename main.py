#!/usr/bin/env python3
"""
main.py — LangGraph research agent that orchestrates searcher + scraper.

Wires DeepSearcher (LLM-powered query gen → DuckDuckGo) and DeepFetcher
(Crawl4AI → pruned Markdown) into a two-node StateGraph:

    START → search_node → scrape_node → END → final_report.md

Architecture
────────────
    ┌──────────┐     ┌──────────────┐     ┌──────────────┐
    │  START    │────▶│  search_node │────▶│  scrape_node │────▶ END
    │  (topic)  │     │  (searcher)  │     │  (scraper)   │
    └──────────┘     └──────────────┘     └──────────────┘
         │                  │                     │
         │                  ▼                     ▼
         │           DeepSearcher           DeepFetcher
         │           ┌──────────┐           ┌──────────┐
         │           │  Ollama  │           │ Crawl4AI │
         │           │  DDG     │           │ (async)  │
         │           └──────────┘           └──────────┘
         │                                        │
         │                                        ▼
         └───────────────────────────────▶ final_report.md

Usage
─────
    python main.py "impact of LLMs on drug discovery"
    python main.py -v "quantum computing breakthroughs"
    python main.py --model llama3.1 --top 5 "renewable energy storage"
    python main.py                          # interactive prompt

Requirements
────────────
    pip install langgraph ollama duckduckgo-search crawl4ai
    crawl4ai-setup
    ollama serve  &&  ollama pull llama3.1:8b-instruct-q8_0
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Optional

from typing_extensions import TypedDict
from dotenv import load_dotenv

from langgraph.graph import END, START, StateGraph

# Load environment variables from .env file (if present)
load_dotenv()

# ──────────────────────────────────────────────────────────────────────
# Local module imports
#   searcher.py  → DeepSearcher, SearcherConfig
#   scraper.py   → DeepFetcher, FetcherConfig
# Both must be in the same directory as main.py (or on PYTHONPATH).
# ──────────────────────────────────────────────────────────────────────
from searcher import DeepSearcher, SearcherConfig
from scraper import DeepFetcher, FetcherConfig

# ──────────────────────────────────────────────────────────────────────
# Logging
# ──────────────────────────────────────────────────────────────────────
logger = logging.getLogger("research_agent")


def _configure_logging(verbose: bool = False) -> None:
    """Set up structured logging."""
    level = logging.DEBUG if verbose else logging.INFO
    for name in ("research_agent", "deep_searcher", "deep_fetcher"):
        log = logging.getLogger(name)
        log.setLevel(level)
        if not log.handlers:
            handler = logging.StreamHandler(sys.stderr)
            handler.setFormatter(
                logging.Formatter(
                    "[%(asctime)s] %(name)-16s %(levelname)-7s │ %(message)s",
                    datefmt="%H:%M:%S",
                )
            )
            log.addHandler(handler)


# ══════════════════════════════════════════════════════════════════════
# 1. STATE DEFINITION
# ══════════════════════════════════════════════════════════════════════
class ResearchState(TypedDict):
    """Shared state that flows through the LangGraph graph.

    Attributes:
        topic:           The user-supplied research topic.
        urls:            URLs discovered by the search node.
        scraped_content: Mapping of URL → extracted markdown.
        errors:          Mapping of URL → error message for failed scrapes.
        elapsed_ms:      Total pipeline wall-time in milliseconds.
    """

    topic: str
    urls: list[str]
    scraped_content: dict[str, str]
    errors: dict[str, str]
    elapsed_ms: float


# ══════════════════════════════════════════════════════════════════════
# 2. SEARCH NODE FACTORY
# ══════════════════════════════════════════════════════════════════════
def make_search_node(
    searcher_config: SearcherConfig,
    progress_callback=None,
):
    """Create a search node bound to its own config (no globals)."""

    async def search_node(state: ResearchState) -> dict[str, Any]:
        """Generate diverse search queries via Ollama and collect URLs."""
        topic = state["topic"]
        logger.info("🔍  SEARCH NODE — topic: %r", topic)

        searcher = DeepSearcher(searcher_config, progress_callback=progress_callback)
        report = await searcher.search(topic)

        logger.info(
            "Search complete: %d queries → %d unique URLs",
            len(report.queries), len(report.unique_urls),
        )

        for i, q in enumerate(report.queries, 1):
            logger.info("  Query %d: %s", i, q)

        return {"urls": report.unique_urls}

    return search_node


# ══════════════════════════════════════════════════════════════════════
# 3. SCRAPE NODE FACTORY
# ══════════════════════════════════════════════════════════════════════
def make_scrape_node(
    fetcher_config: FetcherConfig,
    progress_callback=None,
):
    """Create a scrape node bound to its own config (no globals)."""

    async def scrape_node(state: ResearchState) -> dict[str, Any]:
        """Scrape all URLs in parallel using DeepFetcher."""
        urls = state.get("urls", [])
        if not urls:
            logger.warning("No URLs to scrape — search returned empty results")
            return {"scraped_content": {}, "errors": {}}

        logger.info("📄  SCRAPE NODE — fetching %d URLs in parallel…", len(urls))

        scraped: dict[str, str] = {}
        errors: dict[str, str] = {}

        async with DeepFetcher(fetcher_config, progress_callback=progress_callback) as fetcher:
            results = await fetcher.fetch_many(urls)

        _MAX_CONTENT_CHARS = 100_000  # 100KB per page to prevent OOM

        for result in results:
            if result.success and result.raw_markdown:
                scraped[result.url] = result.raw_markdown[:_MAX_CONTENT_CHARS]
                logger.info(
                    "  ✅ %s — %d chars (%.0f ms)",
                    result.url, len(result.raw_markdown), result.elapsed_ms,
                )
            else:
                error_msg = result.error or "Empty content"
                errors[result.url] = error_msg
                logger.warning("  ❌ %s — %s", result.url, error_msg)

        logger.info(
            "Scrape complete: %d succeeded, %d failed",
            len(scraped), len(errors),
        )
        return {"scraped_content": scraped, "errors": errors}

    return scrape_node


# ══════════════════════════════════════════════════════════════════════
# 4. GRAPH CONSTRUCTION
# ══════════════════════════════════════════════════════════════════════
def build_graph(search_fn, scrape_fn) -> Any:
    """Build and compile the LangGraph StateGraph.

    Graph topology:
        START → search_node → scrape_node → END
    """
    graph = StateGraph(ResearchState)

    graph.add_node("search_node", search_fn)
    graph.add_node("scrape_node", scrape_fn)

    graph.add_edge(START, "search_node")
    graph.add_edge("search_node", "scrape_node")
    graph.add_edge("scrape_node", END)

    return graph.compile()


# ══════════════════════════════════════════════════════════════════════
# 5. REPORT GENERATION
# ══════════════════════════════════════════════════════════════════════
def _sanitize_md(text: str) -> str:
    """Strip HTML tags and dangerous markdown patterns from external content."""
    import re as _re
    # Remove HTML tags (prevents XSS when markdown is rendered to HTML)
    text = _re.sub(r"<[^>]+>", "", text)
    # Remove javascript: URLs
    text = _re.sub(r"\[([^\]]*)\]\(javascript:[^)]*\)", r"\1", text, flags=_re.IGNORECASE)
    return text


def generate_report(final_state: dict[str, Any]) -> str:
    """Assemble the final markdown report from scraped content."""
    topic = final_state.get("topic", "Unknown")
    urls = final_state.get("urls", [])
    scraped = final_state.get("scraped_content", {})
    errors = final_state.get("errors", {})
    elapsed = final_state.get("elapsed_ms", 0)

    sections: list[str] = []

    # ── Header ────────────────────────────────────────────────────────
    sections.append(f"# Research Report: {topic}\n")
    sections.append(
        f"> Auto-generated by the LangGraph Research Agent\n"
        f"> URLs searched: {len(urls)} | "
        f"Scraped: {len(scraped)} | "
        f"Failed: {len(errors)} | "
        f"Time: {elapsed:.0f} ms\n"
    )
    sections.append("---\n")

    # ── Table of Contents ─────────────────────────────────────────────
    if scraped:
        sections.append("## Table of Contents\n")
        for i, url in enumerate(scraped, 1):
            anchor = f"source-{i}"
            sections.append(f"{i}. [{url}](#{anchor})")
        sections.append("\n---\n")

    # ── Scraped Content Sections ──────────────────────────────────────
    for i, (url, content) in enumerate(scraped.items(), 1):
        anchor = f"source-{i}"
        sections.append(f'## <a id="{anchor}"></a>Source {i}\n')
        sections.append(f"**URL:** {_sanitize_md(url)}\n")
        sections.append(f"**Length:** {len(content):,} characters\n")
        sections.append(_sanitize_md(content.strip()))
        sections.append("\n\n---\n")

    # ── Errors ────────────────────────────────────────────────────────
    if errors:
        sections.append("## Failed URLs\n")
        for url, err in errors.items():
            sections.append(f"- **{_sanitize_md(url)}**: {_sanitize_md(err)}")
        sections.append("\n")

    return "\n".join(sections)


def save_report(content: str, path: Path) -> Path:
    """Write the report to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path.resolve()


# ══════════════════════════════════════════════════════════════════════
# 6. CLI
# ══════════════════════════════════════════════════════════════════════
def build_parser() -> argparse.ArgumentParser:
    """Construct the argument parser."""
    parser = argparse.ArgumentParser(
        prog="research_agent",
        description=(
            "LangGraph research agent: generate search queries via Ollama, "
            "search DuckDuckGo, scrape results with Crawl4AI, and compile "
            "a markdown report."
        ),
        epilog=(
            "Examples:\n"
            '  python main.py "impact of LLMs on drug discovery"\n'
            '  python main.py -v --model llama3.1 "quantum computing"\n'
            '  python main.py --top 5 -o report.md "renewable energy"\n'
            "  python main.py              # interactive prompt\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "topic",
        nargs="?",
        default=None,
        help="Research topic. If omitted, you'll be prompted.",
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        default=os.getenv("OUTPUT_FILE", "final_report.md"),
        help="Output path for the report (default: final_report.md or $OUTPUT_FILE).",
    )
    parser.add_argument(
        "-m", "--model",
        type=str,
        default=os.getenv("OLLAMA_MODEL", "llama3.1:8b-instruct-q8_0"),
        help="Ollama model name (default: $OLLAMA_MODEL or llama3.1:8b-instruct-q8_0).",
    )
    parser.add_argument(
        "--host",
        type=str,
        default=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
        help="Ollama server URL (default: $OLLAMA_HOST or http://localhost:11434).",
    )
    parser.add_argument(
        "-n", "--num-queries",
        type=int,
        default=SearcherConfig().num_queries,
        help="Number of search queries to generate (default: $SEARCH_NUM_QUERIES or 3).",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=SearcherConfig().results_per_query,
        help="Results per search query (default: $SEARCH_RESULTS_PER_QUERY or 3).",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        default=os.getenv("VERBOSE", "false").lower() == "true",
        help="Enable detailed logging (default: $VERBOSE or false).",
    )
    return parser


def resolve_topic(args_topic: Optional[str]) -> str:
    """Get topic from CLI args or interactive prompt."""
    raw = args_topic
    if not raw:
        try:
            raw = input("\n🧠  Enter research topic: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAborted.")
            sys.exit(0)

    if not raw:
        print("Error: No topic provided.", file=sys.stderr)
        sys.exit(1)

    return raw


# ══════════════════════════════════════════════════════════════════════
# 7. REUSABLE PIPELINE (used by both CLI and web API)
# ══════════════════════════════════════════════════════════════════════
async def run_research(
    topic: str,
    searcher_config: SearcherConfig,
    fetcher_config: FetcherConfig,
    progress_callback=None,
) -> dict[str, Any]:
    """Run the research pipeline. Returns the final state dict.

    This is the shared core used by both CLI and web API.
    Each invocation creates its own node closures, so concurrent
    calls never share mutable state.
    """
    search_fn = make_search_node(searcher_config, progress_callback)
    scrape_fn = make_scrape_node(fetcher_config, progress_callback)

    app = build_graph(search_fn, scrape_fn)
    initial_state: ResearchState = {
        "topic": topic,
        "urls": [],
        "scraped_content": {},
        "errors": {},
        "elapsed_ms": 0.0,
    }

    t0 = time.perf_counter()
    final_state = await app.ainvoke(initial_state)
    final_state["elapsed_ms"] = (time.perf_counter() - t0) * 1000
    return final_state


# ══════════════════════════════════════════════════════════════════════
# 9. CLI ENTRY-POINT
# ══════════════════════════════════════════════════════════════════════
async def async_main(args: argparse.Namespace) -> None:
    """Run the full research pipeline from CLI."""
    _configure_logging(verbose=args.verbose)
    topic = resolve_topic(args.topic)
    output_path = Path(args.output)

    searcher_config = SearcherConfig(
        model=args.model,
        ollama_host=args.host,
        num_queries=args.num_queries,
        results_per_query=args.top,
    )
    fetcher_config = FetcherConfig(verbose=args.verbose)

    # ── Banner ────────────────────────────────────────────────────────
    print(f"\n{'═' * 64}")
    print(f"  🧠  RESEARCH AGENT")
    print(f"  📋  Topic : {topic}")
    print(f"  🤖  Model : {args.model}")
    print(f"  📊  Queries: {args.num_queries} × {args.top} results each")
    print(f"{'═' * 64}\n")

    final_state = await run_research(topic, searcher_config, fetcher_config)

    # ── Generate and save report ──────────────────────────────────────
    report = generate_report(final_state)
    saved = save_report(report, output_path)

    # ── Summary ───────────────────────────────────────────────────────
    scraped = final_state.get("scraped_content", {})
    errors = final_state.get("errors", {})
    urls = final_state.get("urls", [])
    elapsed = final_state.get("elapsed_ms", 0)

    print(f"\n{'═' * 64}")
    print(f"  ✅  PIPELINE COMPLETE")
    print(f"  ⏱   Total time     : {elapsed:,.0f} ms")
    print(f"  🔗  URLs found     : {len(urls)}")
    print(f"  📄  Pages scraped  : {len(scraped)}")
    print(f"  ❌  Failed         : {len(errors)}")
    print(f"  📝  Report chars   : {len(report):,}")
    print(f"  💾  Saved to       : {saved}")
    print(f"{'═' * 64}\n")

    if errors:
        print("  ⚠️  Failed URLs:")
        for url, err in errors.items():
            print(f"      • {url}: {err}")
        print()


def main() -> None:
    """Synchronous entry-point."""
    parser = build_parser()
    args = parser.parse_args()
    asyncio.run(async_main(args))


if __name__ == "__main__":
    main()