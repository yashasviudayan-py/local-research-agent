# Docker Deployment Guide

This guide covers deploying the Local Research Agent using Docker and Docker Compose.

## Table of Contents
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Deployment Options](#deployment-options)
- [Configuration](#configuration)
- [Model Management](#model-management)
- [Health Checks](#health-checks)
- [Troubleshooting](#troubleshooting)
- [Production Considerations](#production-considerations)

---

## Prerequisites

- **Docker Engine 20.10+** ([Install Docker](https://docs.docker.com/get-docker/))
- **Docker Compose V2** ([Install Compose](https://docs.docker.com/compose/install/))
- **20GB free disk space** (8GB for Ollama model + 5GB for images + overhead)
- **4GB+ RAM available** (6-8GB recommended for optimal performance)

Verify your installation:
```bash
docker --version
docker compose version
```

---

## Quick Start

### Option 1: With Host Ollama (Recommended for Mac/Linux)

If you already have Ollama installed and running on your host machine:

1. **Ensure Ollama is running**:
   ```bash
   ollama serve
   ```

2. **Verify model is available**:
   ```bash
   ollama list
   # If llama3.1:8b-instruct-q8_0 is not listed:
   ollama pull llama3.1:8b-instruct-q8_0
   ```

3. **Build and start the research agent**:
   ```bash
   docker compose -f docker-compose.host-ollama.yml up -d
   ```

4. **Run your first research**:
   ```bash
   docker compose -f docker-compose.host-ollama.yml exec research-agent \
     python main.py "impact of AI on healthcare"
   ```

5. **Find your report**:
   ```bash
   cat ./reports/final_report.md
   ```

---

### Option 2: Fully Dockerized (Ollama in Container)

For complete portability or if you don't have Ollama installed:

1. **Start all services**:
   ```bash
   docker compose up -d
   ```

2. **Wait for Ollama to start** (~15-20 seconds):
   ```bash
   docker compose logs -f ollama
   # Watch for: "Listening on http://0.0.0.0:11434"
   ```

3. **Pull the model** (first time only, ~8GB, 5-10 minutes):
   ```bash
   docker exec research-ollama ollama pull llama3.1:8b-instruct-q8_0
   ```

4. **Verify model availability**:
   ```bash
   docker exec research-ollama ollama list
   ```

5. **Run research**:
   ```bash
   docker compose exec research-agent \
     python main.py "quantum computing applications"
   ```

6. **Check your report**:
   ```bash
   ls -lh ./reports/
   ```

---

## Deployment Options

### One-Shot Execution

Run research and exit (container is removed after completion):

```bash
# With host Ollama
docker compose -f docker-compose.host-ollama.yml run --rm research-agent \
  python main.py "your research topic here"

# With dockerized Ollama
docker compose run --rm research-agent \
  python main.py "your research topic here"
```

### Interactive Mode

Start container with shell access for multiple research runs:

```bash
# Enter container shell
docker compose -f docker-compose.host-ollama.yml exec research-agent bash

# Inside container:
python main.py "first topic"
python main.py "second topic"
ls reports/
exit
```

### Custom Configuration

Override environment variables at runtime:

```bash
docker compose -f docker-compose.host-ollama.yml run --rm \
  -e SEARCH_NUM_QUERIES=5 \
  -e SEARCH_RESULTS_PER_QUERY=5 \
  -e VERBOSE=true \
  research-agent \
  python main.py "machine learning in robotics"
```

### Background Processing

Run research in the background:

```bash
docker compose -f docker-compose.host-ollama.yml run -d --rm research-agent \
  python main.py "long running research topic" &

# Check logs
docker compose logs -f research-agent
```

---

## Configuration

### Environment Variables

Create a `.env` file in the project root:

```bash
cp .env.template .env
# Edit .env with your preferred settings
```

Key configuration variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_HOST` | `http://host.docker.internal:11434` | Ollama server URL (host Ollama mode) |
| `OLLAMA_HOST` | `http://ollama:11434` | Ollama server URL (dockerized mode) |
| `OLLAMA_MODEL` | `llama3.1:8b-instruct-q8_0` | LLM model to use for query generation |
| `OLLAMA_TIMEOUT` | `60.0` | Ollama API timeout in seconds |
| `SEARCH_NUM_QUERIES` | `3` | Number of diverse queries to generate |
| `SEARCH_RESULTS_PER_QUERY` | `3` | Results to fetch per query |
| `SEARCH_REGION` | `wt-wt` | DuckDuckGo search region |
| `SEARCH_SAFESEARCH` | `moderate` | Safe search level (off, moderate, strict) |
| `SCRAPER_HEADLESS` | `true` | Run browser in headless mode |
| `SCRAPER_PAGE_TIMEOUT` | `30000` | Page load timeout (milliseconds) |
| `SCRAPER_REQUEST_TIMEOUT` | `15000` | Request timeout (milliseconds) |
| `SCRAPER_SEMAPHORE_LIMIT` | `6` | Max concurrent scraping tasks |
| `OUTPUT_FILE` | `final_report.md` | Default output filename |
| `VERBOSE` | `false` | Enable debug logging |

### CLI Arguments Override Environment Variables

CLI arguments take precedence over environment variables:

```bash
# This overrides OLLAMA_MODEL and SEARCH_NUM_QUERIES from .env
docker compose exec research-agent python main.py \
  --model llama3.2 \
  --num-queries 5 \
  "your topic"
```

**Precedence order:** CLI args > Environment Variables > Hardcoded Defaults

---

## Model Management

### List Available Models

```bash
# Dockerized Ollama
docker exec research-ollama ollama list

# Host Ollama
ollama list
```

### Pull Additional Models

```bash
# Dockerized Ollama
docker exec research-ollama ollama pull mistral:7b
docker exec research-ollama ollama pull llama3.2

# Host Ollama
ollama pull mistral:7b
```

### Remove Models to Free Space

```bash
# Dockerized Ollama
docker exec research-ollama ollama rm mistral:7b

# Host Ollama
ollama rm mistral:7b
```

### Model Storage Location

**Dockerized Ollama:** Models are stored in a named volume `ollama_models`

```bash
# Inspect volume
docker volume inspect local-research-agent_ollama_models

# Backup models (creates tar.gz in ./backup/)
mkdir -p backup
docker run --rm \
  -v local-research-agent_ollama_models:/data \
  -v $(pwd)/backup:/backup \
  alpine tar czf /backup/ollama-models-$(date +%Y%m%d).tar.gz -C /data .

# Restore models
docker run --rm \
  -v local-research-agent_ollama_models:/data \
  -v $(pwd)/backup:/backup \
  alpine tar xzf /backup/ollama-models-YYYYMMDD.tar.gz -C /data
```

**Host Ollama:** Models are in `~/.ollama/models/`

---

## Health Checks

### Check Service Status

```bash
# View all services
docker compose ps

# Expected output:
# NAME               STATUS         PORTS
# research-agent     Up
# research-ollama    Up (healthy)   0.0.0.0:11434->11434/tcp
```

### Test Ollama Connectivity

```bash
# From host
curl http://localhost:11434/api/tags

# From container
docker compose exec research-agent curl http://ollama:11434/api/tags
```

### View Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f ollama
docker compose logs -f research-agent

# Last 50 lines
docker compose logs --tail=50 research-agent
```

### Monitor Resource Usage

```bash
# Real-time stats
docker stats research-agent research-ollama

# One-time snapshot
docker stats --no-stream
```

---

## Troubleshooting

### Issue: Ollama model not found

**Symptom:**
```
Error: model 'llama3.1:8b-instruct-q8_0' not found
```

**Solution:**
```bash
# Dockerized Ollama
docker exec research-ollama ollama pull llama3.1:8b-instruct-q8_0

# Host Ollama
ollama pull llama3.1:8b-instruct-q8_0
```

---

### Issue: Research agent can't connect to Ollama

**Symptom:**
```
Connection refused to http://ollama:11434
```

**Solution:**
```bash
# Check Ollama is healthy
docker compose ps

# Restart Ollama
docker compose restart ollama

# Verify network connectivity
docker compose exec research-agent ping -c 3 ollama

# Check network configuration
docker network inspect local-research-agent_research-net
```

**For host Ollama mode:**
```bash
# Ensure Ollama is running on host
ollama serve

# Test from host
curl http://localhost:11434/api/tags

# Verify host.docker.internal resolution
docker compose -f docker-compose.host-ollama.yml exec research-agent \
  curl http://host.docker.internal:11434/api/tags
```

---

### Issue: Playwright browser crashes

**Symptom:**
```
Browser closed unexpectedly
playwright._impl._errors.TargetClosedError
```

**Solution:** Increase Docker memory limit

**Docker Desktop:**
1. Open Docker Desktop → Settings → Resources
2. Set Memory to at least 6GB (8GB+ recommended)
3. Apply & Restart

**Alternatively, add memory limits to docker-compose.yml:**
```yaml
services:
  research-agent:
    mem_limit: 4g
    shm_size: 2gb  # Shared memory for browser
```

---

### Issue: Slow scraping performance

**Symptom:** Research takes >60 seconds for 3 queries

**Solution:** Adjust concurrency limits

**Temporary (runtime):**
```bash
docker compose run --rm \
  -e SCRAPER_SEMAPHORE_LIMIT=3 \
  -e MAX_CONCURRENT_SEARCHES=2 \
  research-agent python main.py "topic"
```

**Permanent (in .env):**
```bash
SCRAPER_SEMAPHORE_LIMIT=3
MAX_CONCURRENT_SEARCHES=2
```

---

### Issue: "Reports directory not accessible"

**Symptom:** Generated reports don't appear in `./reports/`

**Solution:**
```bash
# Create reports directory with correct permissions
mkdir -p reports
chmod 755 reports

# Check bind mount
docker compose -f docker-compose.host-ollama.yml exec research-agent ls -la /app/reports

# Verify volume mount in compose file
grep -A 2 "volumes:" docker-compose.host-ollama.yml
```

---

### Issue: Build fails at "crawl4ai-setup"

**Symptom:**
```
ERROR: failed to solve: process "/bin/sh -c crawl4ai-setup" did not complete successfully
```

**Solution:**
```bash
# Clean build cache and rebuild
docker builder prune -a -f
docker compose build --no-cache

# If still fails, check internet connectivity
curl -I https://playwright.azureedge.net/builds/chromium/
```

---

## Production Considerations

### 1. Resource Limits

Add resource constraints to prevent runaway containers:

```yaml
services:
  ollama:
    deploy:
      resources:
        limits:
          cpus: '4'
          memory: 8G
        reservations:
          memory: 4G

  research-agent:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          memory: 2G
```

### 2. GPU Support (Linux + NVIDIA only)

Uncomment GPU support in `docker-compose.yml`:

```yaml
services:
  ollama:
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
```

**Prerequisites:**
- NVIDIA GPU with drivers installed
- [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)

**Verify GPU access:**
```bash
docker run --rm --gpus all nvidia/cuda:12.0-base nvidia-smi
```

### 3. Persistent Logs

Mount log directories for persistent storage:

```yaml
services:
  research-agent:
    volumes:
      - ./reports:/app/reports
      - ./logs:/app/logs  # Add this
```

Configure logging driver:
```yaml
services:
  research-agent:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

### 4. Security Hardening

**a) Run with read-only filesystem (where possible):**
```yaml
services:
  research-agent:
    read_only: true
    tmpfs:
      - /tmp
      - /app/.cache
```

**b) Drop unnecessary capabilities:**
```yaml
services:
  research-agent:
    cap_drop:
      - ALL
    cap_add:
      - CHOWN
      - SETUID
      - SETGID
```

**c) Scan images for vulnerabilities:**
```bash
docker scan local-research-agent_research-agent
# Or use Trivy
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  aquasec/trivy:latest image local-research-agent_research-agent
```

**d) Keep images updated:**
```bash
docker compose pull
docker compose build --no-cache
docker compose up -d
```

### 5. Monitoring & Observability

**Prometheus + Grafana Integration:**

```yaml
services:
  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    ports:
      - "9090:9090"

  cadvisor:
    image: gcr.io/cadvisor/cadvisor:latest
    volumes:
      - /:/rootfs:ro
      - /var/run:/var/run:ro
      - /sys:/sys:ro
      - /var/lib/docker/:/var/lib/docker:ro
    ports:
      - "8080:8080"
```

**Simple monitoring with docker stats:**
```bash
# Continuous monitoring
watch -n 2 'docker stats --no-stream research-agent research-ollama'
```

### 6. Backup Strategy

**Automated backup script:**
```bash
#!/bin/bash
# backup.sh
DATE=$(date +%Y%m%d-%H%M%S)
BACKUP_DIR="./backups/$DATE"

mkdir -p "$BACKUP_DIR"

# Backup reports
cp -r ./reports "$BACKUP_DIR/"

# Backup Ollama models (dockerized mode)
docker run --rm \
  -v local-research-agent_ollama_models:/data \
  -v $(pwd)/$BACKUP_DIR:/backup \
  alpine tar czf /backup/ollama-models.tar.gz -C /data .

echo "Backup completed: $BACKUP_DIR"
```

---

## Cleanup

### Stop Services (Keep Data)

```bash
# Host Ollama mode
docker compose -f docker-compose.host-ollama.yml down

# Dockerized mode
docker compose down
```

### Remove Volumes (Deletes Ollama Models!)

```bash
docker compose down -v
# WARNING: This deletes the ollama_models volume (~8GB)
```

### Remove Images

```bash
docker rmi local-research-agent_research-agent
docker rmi ollama/ollama:latest
docker rmi mcr.microsoft.com/playwright/python:v1.58.0-jammy
```

### Complete Cleanup (All Data Lost)

```bash
docker compose down -v --rmi all
docker system prune -a --volumes -f
```

---

## FAQ

**Q: Can I use a different LLM model?**

A: Yes! Pull the model and set the environment variable:
```bash
# Dockerized Ollama
docker exec research-ollama ollama pull mistral:7b

# Update .env
OLLAMA_MODEL=mistral:7b

# Or override at runtime
docker compose exec research-agent python main.py --model mistral:7b "topic"
```

---

**Q: How do I update to the latest version?**

A:
```bash
git pull origin main
docker compose build --no-cache
docker compose down
docker compose up -d
```

---

**Q: Can I run multiple research jobs concurrently?**

A: Yes, but be mindful of resource limits:
```bash
# Start multiple one-shot containers
docker compose run -d --rm research-agent python main.py "topic 1" &
docker compose run -d --rm research-agent python main.py "topic 2" &
docker compose run -d --rm research-agent python main.py "topic 3" &
wait

# Check all reports
ls -lh reports/
```

---

**Q: How do I backup my reports?**

A: Reports are in `./reports/` on the host (bind mount):
```bash
# Simple backup
cp -r reports reports-backup-$(date +%Y%m%d)

# Compressed backup
tar czf reports-backup-$(date +%Y%m%d).tar.gz reports/
```

---

**Q: Can I deploy this to cloud (AWS, GCP, Azure)?**

A: Yes! The Docker setup is cloud-agnostic. Considerations:
- Use managed container services (ECS, Cloud Run, AKS)
- Store reports in object storage (S3, GCS, Blob)
- Use managed Ollama or cloud LLM APIs
- Ensure sufficient memory (4GB+ per container)

---

**Q: Why is the image so large (~1.5GB)?**

A: The image includes:
- Ubuntu 22.04 base (~100MB)
- Python 3.12 (~200MB)
- Playwright browsers (Chromium + dependencies, ~800MB)
- Python packages (~300MB)

This is normal for browser automation workloads. For production, consider:
- Using multi-stage builds (already implemented)
- Sharing base images across multiple services
- Using image registries with layer caching

---

**Q: How do I enable verbose logging?**

A:
```bash
# Via environment variable
docker compose run --rm -e VERBOSE=true research-agent python main.py "topic"

# Via CLI argument
docker compose exec research-agent python main.py -v "topic"
```

---

## Performance Benchmarks

**Typical research times** (3 queries × 3 results):
- Query generation: 2-4 seconds
- Web search: 1-2 seconds
- Scraping (9 URLs): 5-10 seconds
- Report generation: 1-2 seconds
- **Total: 10-20 seconds**

**Resource usage:**
- Research Agent: ~500MB RAM, ~50% CPU (during scraping)
- Ollama (llama3.1:8b): ~4GB RAM, ~200% CPU (during query gen)
- Docker overhead: ~100MB RAM

---

## Additional Resources

- **Main README:** [README.md](README.md) - Project overview and features
- **Environment Template:** [.env.template](.env.template) - All configuration options
- **Verification Script:** `./verify-docker.sh` - Automated testing
- **Docker Hub:** [Ollama Official Images](https://hub.docker.com/r/ollama/ollama)
- **Playwright Docs:** [Playwright Python](https://playwright.dev/python/)
- **Crawl4AI Docs:** [GitHub](https://github.com/unclecode/crawl4ai)

---

**Need help?** Check the troubleshooting section or open an issue on GitHub.

**Happy researching! 🚀**
