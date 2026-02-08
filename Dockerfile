# ============================================================================
# Production Dockerfile for Local Research Agent
# ============================================================================
FROM mcr.microsoft.com/playwright/python:v1.58.0-jammy

# Metadata
LABEL maintainer="Local Research Agent"
LABEL description="LangGraph Research Agent with Crawl4AI and Ollama"

# Python environment optimizations
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Copy requirements first for layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Run crawl4ai-setup (installs browser binaries and dependencies)
RUN crawl4ai-setup

# Create non-root user for security (use UID 1001 to avoid conflict with pwuser)
RUN groupadd -r researcher && \
    useradd -r -g researcher -u 1001 researcher && \
    mkdir -p /app /home/researcher && \
    chown -R researcher:researcher /app /home/researcher

# Copy application code
COPY --chown=researcher:researcher main.py searcher.py scraper.py run_web.py ./
COPY --chown=researcher:researcher web/ ./web/

# Switch to non-root user
USER researcher

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Default environment (can be overridden by docker-compose or CLI)
ENV OLLAMA_HOST=http://ollama:11434 \
    OLLAMA_MODEL=llama3.1:8b-instruct-q8_0 \
    OUTPUT_FILE=final_report.md \
    WEB_HOST=0.0.0.0 \
    WEB_PORT=8000

EXPOSE 8000

# Use exec form for proper signal handling
ENTRYPOINT ["python", "main.py"]

# Default topic (override with docker run args)
CMD ["--help"]
