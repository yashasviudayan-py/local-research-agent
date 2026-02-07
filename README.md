# 🧠 Local Research Agent

> An autonomous AI-powered research agent that performs deep web research and generates comprehensive, cited reports—completely locally on your machine.

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![LangGraph](https://img.shields.io/badge/LangGraph-StateGraph-green.svg)](https://github.com/langchain-ai/langgraph)
[![Crawl4AI](https://img.shields.io/badge/Crawl4AI-Async-orange.svg)](https://github.com/unclecode/crawl4ai)

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Usage](#usage)
- [Configuration](#configuration)
- [Project Structure](#project-structure)
- [How It Works](#how-it-works)
- [Examples](#examples)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)
- [Acknowledgments](#acknowledgments)

---

## 🎯 Overview

**Local Research Agent** is a sophisticated autonomous research assistant built with **LangGraph** that orchestrates an end-to-end research pipeline:

1. **Query Generation**: Uses local LLM (Llama 3.1 via Ollama) to generate diverse, multi-angle search queries
2. **Web Search**: Executes parallel searches on DuckDuckGo to gather relevant URLs
3. **Content Extraction**: Scrapes web pages using Crawl4AI with intelligent content filtering
4. **Report Generation**: Compiles findings into a structured, citation-rich markdown report

**Privacy-First**: All processing happens on your MacBook Pro M4 (or any Apple Silicon Mac) — no data leaves your machine.

---

## ✨ Features

- 🤖 **LLM-Powered Query Generation**: Automatically generates diverse search queries from a single research topic
- 🔍 **Parallel Web Search**: Concurrent DuckDuckGo searches with deduplication
- 📄 **Intelligent Scraping**: Crawl4AI with PruningContentFilter extracts clean markdown from web pages
- ⚡ **Optimized for Apple Silicon**: Metal-accelerated inference on M-series chips
- 🔄 **LangGraph Orchestration**: Stateful, multi-node research pipeline
- 📊 **Structured Reporting**: Auto-generated markdown reports with citations and metrics
- 🎛️ **Highly Configurable**: Tunable parameters for queries, search depth, timeouts, and more
- 🛡️ **Robust Error Handling**: Retry logic, timeout management, and graceful degradation

---

## 🏗️ Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                     LANGGRAPH STATE GRAPH                      │
│                                                                │
│  START → search_node → scrape_node → END → final_report.md    │
│            │              │                                    │
│            ▼              ▼                                    │
│      ┌─────────┐    ┌──────────┐                              │
│      │ Ollama  │    │ Crawl4AI │                              │
│      │ Llama3  │    │  (async) │                              │
│      └─────────┘    └──────────┘                              │
│            │              │                                    │
│            ▼              ▼                                    │
│    ┌─────────────┐  ┌──────────────┐                          │
│    │ DuckDuckGo  │  │ PruningFilter│                          │
│    │   Search    │  │  + Markdown  │                          │
│    └─────────────┘  └──────────────┘                          │
└────────────────────────────────────────────────────────────────┘
```

### Core Components

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Orchestrator** | [LangGraph](https://github.com/langchain-ai/langgraph) | Manages the stateful research workflow |
| **Brain** | [Ollama](https://ollama.ai/) + Llama 3.1-8B | Local LLM for query generation |
| **Search** | [DuckDuckGo Search](https://pypi.org/project/duckduckgo-search/) | Privacy-focused web search |
| **Scraper** | [Crawl4AI](https://github.com/unclecode/crawl4ai) | Async web crawler with markdown extraction |

---

## 📦 Prerequisites

### System Requirements
- **Hardware**: MacBook Pro with Apple Silicon (M1/M2/M3/M4) or any x86 system with sufficient RAM
- **OS**: macOS 12.0+ (optimized for Apple Silicon) or Linux
- **RAM**: Minimum 8GB (16GB+ recommended for larger models)
- **Storage**: ~8GB for Llama 3.1-8B model

### Software Dependencies
- **Python**: 3.9 or higher
- **Ollama**: For running local LLM ([Install Ollama](https://ollama.ai/))
- **Git**: For cloning the repository

---

## 🚀 Installation

### 1. Clone the Repository
```bash
git clone https://github.com/yashasviudayan-py/local-research-agent.git
cd local-research-agent
```

### 2. Create a Virtual Environment (Recommended)
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Python Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Set Up Crawl4AI
```bash
crawl4ai-setup
```

### 5. Install and Configure Ollama

#### Install Ollama
```bash
# macOS / Linux
curl -fsSL https://ollama.ai/install.sh | sh
```

#### Start Ollama Server
```bash
ollama serve
```

#### Pull Llama 3.1 Model (in a new terminal)
```bash
ollama pull llama3.1:8b-instruct-q8_0
```

> **Note**: The model download is ~8GB and may take several minutes depending on your internet speed.

---

## 🎬 Quick Start

### Interactive Mode
Simply run the agent without arguments to be prompted for a research topic:

```bash
python main.py
```

You'll see:
```
🧠  Enter research topic:
```

Type your research question (e.g., `impact of LLMs on drug discovery`) and press Enter.

### Command-Line Mode
Pass the research topic directly as an argument:

```bash
python main.py "impact of LLMs on drug discovery"
```

### Example Output
```
════════════════════════════════════════════════════════════════
  🧠  RESEARCH AGENT
  📋  Topic : impact of LLMs on drug discovery
  🤖  Model : llama3.1:8b-instruct-q8_0
  📊  Queries: 3 × 3 results each
════════════════════════════════════════════════════════════════

🔍  SEARCH NODE — generating queries…
✅  Generated 3 queries
📄  SCRAPE NODE — fetching 9 URLs in parallel…
✅  Scraped 7 pages, 2 failed

════════════════════════════════════════════════════════════════
  ✅  PIPELINE COMPLETE
  ⏱   Total time     : 18,423 ms
  🔗  URLs found     : 9
  📄  Pages scraped  : 7
  ❌  Failed         : 2
  📝  Report chars   : 45,123
  💾  Saved to       : /path/to/final_report.md
════════════════════════════════════════════════════════════════
```

The report will be saved as [`final_report.md`](final_report.md) with:
- Auto-generated table of contents
- Scraped content from each successful URL
- Metadata (timing, success/failure counts)
- Citations for every source

---

## 📖 Usage

### Basic Usage
```bash
python main.py "your research topic here"
```

### Advanced Options

```bash
# Verbose mode with custom model
python main.py -v --model llama3.1 "quantum computing breakthroughs"

# Custom number of queries and results per query
python main.py --num-queries 5 --top 5 "renewable energy storage"

# Custom output file
python main.py -o my_report.md "artificial general intelligence timeline"

# Full example with all options
python main.py \
  -v \
  --model llama3.1:8b-instruct-q8_0 \
  --host http://localhost:11434 \
  --num-queries 4 \
  --top 3 \
  -o custom_report.md \
  "climate change mitigation strategies"
```

### Command-Line Arguments

| Argument | Short | Type | Default | Description |
|----------|-------|------|---------|-------------|
| `topic` | - | `str` | (prompt) | Research topic (optional positional) |
| `--output` | `-o` | `str` | `final_report.md` | Output path for the report |
| `--model` | `-m` | `str` | `llama3.1:8b-instruct-q8_0` | Ollama model name |
| `--host` | - | `str` | `http://localhost:11434` | Ollama server URL |
| `--num-queries` | `-n` | `int` | `3` | Number of search queries to generate |
| `--top` | - | `int` | `3` | Results per search query |
| `--verbose` | `-v` | flag | `False` | Enable detailed logging |

### Running Individual Components

#### Test the Searcher
```bash
python searcher.py "machine learning explainability"
```

#### Test the Scraper
```bash
python scraper.py https://example.com
```

---

## ⚙️ Configuration

### Searcher Configuration ([searcher.py](searcher.py))

```python
SearcherConfig(
    model="llama3.1:8b-instruct-q8_0",
    ollama_host="http://localhost:11434",
    ollama_timeout=60.0,
    num_queries=3,
    temperature=0.7,
    results_per_query=3,
    search_region="wt-wt",
    search_safesearch="moderate",
    search_timelimit=None,  # Options: "d", "w", "m", "y", None
    max_concurrent_searches=3,
)
```

### Fetcher Configuration ([scraper.py](scraper.py))

```python
FetcherConfig(
    headless=True,
    verbose=False,
    page_timeout=30_000,          # ms
    request_timeout=15_000,       # ms
    pruning_threshold=0.48,
    pruning_threshold_type="fixed",
    min_word_threshold=30,
    excluded_tags=("nav", "footer", "header", "aside", "form", "iframe"),
    max_retries=2,
    retry_backoff=0.5,
    semaphore_limit=6,
    cache_mode="BYPASS",
)
```

---

## 📂 Project Structure

```
local-research-agent/
├── main.py                 # Main orchestrator (LangGraph pipeline)
├── searcher.py             # Query generator + DuckDuckGo search module
├── scraper.py              # Crawl4AI-based web scraper module
├── spec.md                 # Original project specification
├── requirements.txt        # Python dependencies
├── .gitignore              # Git ignore patterns
├── README.md               # This file
├── LICENSE                 # MIT License
├── CONTRIBUTING.md         # Contribution guidelines
├── final_report.md         # Generated research report (example)
└── __pycache__/            # Python bytecode (gitignored)
```

---

## 🔍 How It Works

### 1. **Query Generation** ([searcher.py](searcher.py))
- Sends the research topic to Ollama (Llama 3.1-8B)
- LLM generates N diverse queries (default: 3) from different angles
- Queries are parsed and validated

### 2. **Web Search** ([searcher.py](searcher.py))
- Each query is executed against DuckDuckGo in parallel
- Results are collected and URLs are deduplicated
- Metadata (title, snippet, source query) is preserved

### 3. **Content Extraction** ([scraper.py](scraper.py))
- URLs are fetched concurrently using Crawl4AI's `AsyncWebCrawler`
- `PruningContentFilter` removes boilerplate (nav, footer, ads)
- Clean markdown is extracted from main content

### 4. **Report Compilation** ([main.py](main.py))
- Scraped content is assembled into a structured markdown report
- Table of contents with anchors is auto-generated
- Metadata includes timing, success/failure counts, and source URLs

### 5. **LangGraph Orchestration** ([main.py](main.py))
```python
StateGraph:
  START → search_node → scrape_node → END
```

- **State**: Shared dict with `topic`, `urls`, `scraped_content`, `errors`, `elapsed_ms`
- **search_node**: Calls `DeepSearcher.search()` → returns `urls`
- **scrape_node**: Calls `DeepFetcher.fetch_many()` → returns `scraped_content` + `errors`

---

## 💡 Examples

### Example 1: Research Latest AI Models
```bash
python main.py "latest developments in large language models 2024"
```

### Example 2: Generate 5 Queries with 5 Results Each
```bash
python main.py --num-queries 5 --top 5 "sustainable agriculture practices"
```

### Example 3: Use a Different Model
```bash
# First, pull the model:
ollama pull llama3.2

# Then run:
python main.py --model llama3.2 "ethical considerations in AI"
```

### Example 4: Verbose Debugging
```bash
python main.py -v "how does photosynthesis work"
```

### Example 5: Save to Custom Location
```bash
python main.py -o ~/Documents/research_reports/quantum.md "quantum entanglement applications"
```

---

## 🐛 Troubleshooting

### Issue: `Connection refused` error

**Cause**: Ollama server is not running.

**Solution**:
```bash
ollama serve
```

Keep this terminal running, and execute the agent in a new terminal window.

---

### Issue: `Model not found` error

**Cause**: The specified model hasn't been pulled.

**Solution**:
```bash
ollama pull llama3.1:8b-instruct-q8_0
```

---

### Issue: Scraper timeouts or failures

**Cause**: Some websites block headless browsers or have slow response times.

**Solution**: Adjust timeout values:
```bash
# In scraper.py, modify FetcherConfig:
request_timeout=30_000  # Increase to 30 seconds
```

---

### Issue: Empty markdown or low-quality output

**Cause**: `PruningContentFilter` is too aggressive.

**Solution**: Lower the pruning threshold:
```python
# In scraper.py, modify FetcherConfig:
pruning_threshold=0.3  # Lower = less aggressive pruning
```

---

### Issue: `crawl4ai-setup` command not found

**Cause**: Crawl4AI package not installed correctly.

**Solution**:
```bash
pip uninstall crawl4ai
pip install --upgrade crawl4ai
crawl4ai-setup
```

---

## 🤝 Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for:
- Code of Conduct
- Development setup
- Pull request process
- Coding standards

### Quick Contribution Steps
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **[LangGraph](https://github.com/langchain-ai/langgraph)** by LangChain AI for the state-management framework
- **[Crawl4AI](https://github.com/unclecode/crawl4ai)** by unclecode for the blazing-fast async web crawler
- **[Ollama](https://ollama.ai/)** for making local LLM inference effortless
- **[DuckDuckGo](https://duckduckgo.com/)** for privacy-focused search
- **Meta AI** for the Llama 3.1 model

---

## 📧 Contact

**Yashasvi Udayan**
- GitHub: [@yashasviudayan-py](https://github.com/yashasviudayan-py)

---

## ⭐ Star History

If you find this project useful, please consider giving it a star! It helps others discover this work.

---

**Built with ❤️ for privacy-first AI research**
