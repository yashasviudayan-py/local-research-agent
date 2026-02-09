# Local Research Agent

> Autonomous AI-powered research agent with a web interface — runs entirely on your machine.

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Docker Hub](https://img.shields.io/docker/image-size/yashasviudayan/local-research-agent/latest?label=Docker%20Hub)](https://hub.docker.com/r/yashasviudayan/local-research-agent)
[![FastAPI](https://img.shields.io/badge/FastAPI-async-009688.svg)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-StateGraph-green.svg)](https://github.com/langchain-ai/langgraph)
[![Crawl4AI](https://img.shields.io/badge/Crawl4AI-Async-orange.svg)](https://github.com/unclecode/crawl4ai)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Overview

**Local Research Agent** takes a research topic, generates diverse search queries using a local LLM, searches the web, scrapes and extracts content, and compiles everything into a comprehensive markdown report — all through a sleek dark-mode web interface at `http://localhost:8000`.

**Privacy-first**: Every component runs locally. No data leaves your machine. No API keys. No cloud services. $0 cost.

```
┌──────────────────────────────────────────────────────────┐
│  Local Research Agent — Web UI (dark mode)               │
│                                                          │
│  ┌─ Sidebar ─┐  ┌─────────────────────────────────────┐ │
│  │ History   │  │                                     │ │
│  │ > Report 1│  │   "What would you like to research?"│ │
│  │ > Report 2│  │                                     │ │
│  │           │  │   [ Example topic chips... ]         │ │
│  │           │  │                                     │ │
│  └───────────┘  │   ┌─────────────────────────┐       │ │
│                 │   │ Enter a research topic ▶│       │ │
│                 │   └─────────────────────────┘       │ │
│                 └─────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────┘
```

---

## Features

**Web Interface**
- Dark-mode UI with jet-black background and SF font
- Chat-like input at the bottom center
- Real-time progress streaming (SSE) — see queries, URLs, and scraping live
- Sliding sidebar with report history
- Animated example topic suggestions
- Download and delete reports from the browser

**Research Pipeline**
- LLM-powered multi-angle query generation via Ollama (Llama 3.1)
- Parallel DuckDuckGo searches with URL deduplication
- Concurrent web scraping with Crawl4AI and intelligent content filtering
- Structured markdown reports with citations and metrics

**Production Ready**
- Fully containerized with Docker Compose
- Input validation and path traversal protection
- Structured logging and global error handling
- Non-root container execution
- CLI mode for scripting and automation

---

## Architecture

```
Browser (http://localhost:8000)
  │
  │  GET  /                         → Dark-mode SPA
  │  POST /api/research             → Start research job
  │  GET  /api/research/{id}/stream → SSE real-time progress
  │  GET  /api/reports              → List saved reports
  │  GET  /api/reports/{id}         → Get report content
  │  DELETE /api/reports/{id}       → Delete report
  │  GET  /api/health               → Check Ollama connectivity
  │
  ▼
FastAPI Server (web/server.py)
  │
  ▼
Job Runner (web/runner.py)
  │  asyncio.Lock — one job at a time
  │  asyncio.Queue — progress events → SSE
  │
  ▼
LangGraph Pipeline (main.py)
  │
  │  START → search_node → scrape_node → END
  │            │              │
  │            ▼              ▼
  │      DeepSearcher    DeepFetcher
  │      ┌─────────┐    ┌──────────┐
  │      │ Ollama  │    │ Crawl4AI │
  │      │  + DDG  │    │  (async) │
  │      └─────────┘    └──────────┘
  │
  ▼
Report Store (reports/*.md + *.json)
```

### Core Components

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Web UI** | Vanilla JS + CSS | Dark-mode SPA with real-time progress |
| **API** | [FastAPI](https://fastapi.tiangolo.com/) + SSE | Async REST API with streaming |
| **Orchestrator** | [LangGraph](https://github.com/langchain-ai/langgraph) | Stateful research pipeline |
| **LLM** | [Ollama](https://ollama.ai/) + Llama 3.1-8B | Local query generation |
| **Search** | [DuckDuckGo](https://pypi.org/project/ddgs/) | Privacy-focused web search |
| **Scraper** | [Crawl4AI](https://github.com/unclecode/crawl4ai) | Async web crawler with content filtering |

---

## Quick Start

### Prerequisites

- **Ollama** — [Install Ollama](https://ollama.ai/) and pull a model:
  ```bash
  ollama serve
  ollama pull llama3.1:8b-instruct-q8_0
  ```
- **Docker** (recommended) or **Python 3.9+**

---

### Docker (Recommended)

```bash
# 1. Clone
git clone https://github.com/yashasviudayan-py/local-research-agent.git
cd local-research-agent

# 2. Build
docker build -t research-agent:latest .

# 3. Run (make sure Ollama is running on your host)
docker compose -f docker-compose.host-ollama.yml up

# 4. Open http://localhost:8000
```

---

### Python Native

```bash
# 1. Clone
git clone https://github.com/yashasviudayan-py/local-research-agent.git
cd local-research-agent

# 2. Install
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
crawl4ai-setup

# 3. Run
python run_web.py

# 4. Open http://localhost:8000
```

---

### CLI Mode

For scripting or terminal-only workflows:

```bash
# Interactive
python main.py

# Direct
python main.py "impact of LLMs on drug discovery"

# With options
python main.py -v --num-queries 5 --top 5 -o report.md "quantum computing"
```

---

## Web Interface

### Research Flow

1. **Enter a topic** in the input bar at the bottom (or click an example topic)
2. **Watch real-time progress** — queries generated, URLs discovered, pages scraped
3. **View the report** — rendered markdown with metadata and download option
4. **Browse history** — open the sidebar to see and revisit past reports

### Settings

Click "Settings" below the input bar to configure:

| Setting | Default | Description |
|---------|---------|-------------|
| Model | `llama3.1:8b-instruct-q8_0` | Ollama model for query generation |
| Queries | `3` | Number of search queries to generate |
| Results/Query | `3` | DuckDuckGo results per query |

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Web UI |
| `POST` | `/api/research` | Start a research job |
| `GET` | `/api/research/{id}/stream` | SSE progress stream |
| `GET` | `/api/reports` | List all reports |
| `GET` | `/api/reports/{id}` | Get report content |
| `DELETE` | `/api/reports/{id}` | Delete a report |
| `GET` | `/api/health` | Ollama connectivity check |

---

## Configuration

### Environment Variables

See [.env.template](.env.template) for all options. Key variables:

```bash
# Ollama
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b-instruct-q8_0

# Search
SEARCH_NUM_QUERIES=3
SEARCH_RESULTS_PER_QUERY=3

# Scraper
SCRAPER_PAGE_TIMEOUT=30000
SCRAPER_SEMAPHORE_LIMIT=6

# Web
WEB_HOST=0.0.0.0
WEB_PORT=8000
VERBOSE=false
```

### CLI Arguments

| Argument | Short | Default | Description |
|----------|-------|---------|-------------|
| `topic` | | (prompt) | Research topic |
| `--output` | `-o` | `final_report.md` | Output file path |
| `--model` | `-m` | `llama3.1:8b-instruct-q8_0` | Ollama model |
| `--host` | | `http://localhost:11434` | Ollama server URL |
| `--num-queries` | `-n` | `3` | Number of queries |
| `--top` | | `3` | Results per query |
| `--verbose` | `-v` | `false` | Debug logging |

---

## Project Structure

```
local-research-agent/
├── main.py                          # LangGraph pipeline orchestrator
├── searcher.py                      # LLM query generation + DuckDuckGo search
├── scraper.py                       # Crawl4AI web scraper
├── run_web.py                       # Web server entry point
│
├── web/                             # Web application package
│   ├── server.py                    # FastAPI routes + SSE streaming
│   ├── runner.py                    # Job management (API ↔ pipeline bridge)
│   ├── models.py                    # Pydantic request/response models
│   ├── report_store.py              # Report CRUD (JSON + markdown files)
│   ├── static/
│   │   ├── css/style.css            # Dark-mode theme
│   │   └── js/
│   │       ├── api.js               # API client
│   │       ├── app.js               # Hash router + sidebar
│   │       ├── research.js          # Research form + SSE progress
│   │       ├── history.js           # Report history (sidebar)
│   │       └── report.js            # Report viewer
│   └── templates/
│       └── index.html               # Single-page HTML shell
│
├── Dockerfile                       # Production container image
├── docker-compose.host-ollama.yml   # Docker Compose — host Ollama (recommended)
├── docker-compose.yml               # Docker Compose — fully dockerized
├── docker-compose.web.yml           # Docker Compose — web override
│
├── requirements.txt                 # Python dependencies
├── pyproject.toml                   # Project metadata
├── .env.template                    # Environment variable reference
├── .dockerignore                    # Docker build exclusions
├── .gitignore                       # Git ignore patterns
├── verify-docker.sh                 # Automated verification script
├── DOCKER.md                        # Docker deployment guide
├── LICENSE                          # MIT License
└── reports/                         # Generated reports (git-ignored)
```

---

## Docker Deployment

### Recommended: Host Ollama

```bash
# Start web UI
docker compose -f docker-compose.host-ollama.yml up

# Open http://localhost:8000
```

### Fully Dockerized (Ollama in container)

```bash
# Start everything
docker compose up -d

# Pull model (first time)
docker exec research-ollama ollama pull llama3.1:8b-instruct-q8_0

# Add web UI
docker compose -f docker-compose.yml -f docker-compose.web.yml up
```

### CLI via Docker

```bash
docker compose -f docker-compose.host-ollama.yml run --rm research-agent \
  python main.py "your topic" -o /app/reports/output.md
```

### Verification

```bash
chmod +x verify-docker.sh
./verify-docker.sh
```

For the complete Docker guide (resource limits, GPU support, troubleshooting, production hardening), see **[DOCKER.md](DOCKER.md)**.

---

## Troubleshooting

### Web UI not loading

```bash
# Check server is running
curl http://localhost:8000/api/health

# Check logs
python run_web.py  # Look for errors in terminal output
```

### Cannot connect to Ollama

```bash
# Ensure Ollama is running
ollama serve

# Verify it responds
curl http://localhost:11434/api/tags
```

### Model not found

```bash
ollama pull llama3.1:8b-instruct-q8_0
```

### Scraper timeouts

Adjust timeouts via environment variables:
```bash
export SCRAPER_PAGE_TIMEOUT=60000
python run_web.py
```

### Empty or low-quality output

Lower the pruning threshold:
```bash
export SCRAPER_PRUNING_THRESHOLD=0.3
python run_web.py
```

### Docker build fails

```bash
DOCKER_BUILDKIT=1 docker build -t research-agent:latest .
```

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## License

This project is licensed under the MIT License — see [LICENSE](LICENSE) for details.

---

## Acknowledgments

- [LangGraph](https://github.com/langchain-ai/langgraph) — State-management framework
- [Crawl4AI](https://github.com/unclecode/crawl4ai) — Async web crawler
- [Ollama](https://ollama.ai/) — Local LLM inference
- [FastAPI](https://fastapi.tiangolo.com/) — Async Python web framework
- [DuckDuckGo](https://duckduckgo.com/) — Privacy-focused search
- [Meta AI](https://ai.meta.com/) — Llama 3.1 model

---

**Built for privacy-first AI research**
