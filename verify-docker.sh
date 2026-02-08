#!/usr/bin/env bash
set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "======================================================================"
echo "  Docker Production Readiness Verification"
echo "  Local Research Agent"
echo "======================================================================"
echo ""

# Test counter
PASSED=0
FAILED=0
TOTAL=0

# Helper function for test output
run_test() {
    local test_name="$1"
    local test_command="$2"
    TOTAL=$((TOTAL + 1))

    echo -n "[$TOTAL] $test_name... "

    if eval "$test_command" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ PASSED${NC}"
        PASSED=$((PASSED + 1))
        return 0
    else
        echo -e "${RED}✗ FAILED${NC}"
        FAILED=$((FAILED + 1))
        return 1
    fi
}

# Test 1: Check Docker is installed
echo -n "[$((TOTAL + 1))] Checking Docker installation... "
TOTAL=$((TOTAL + 1))
if ! command -v docker &> /dev/null; then
    echo -e "${RED}✗ FAILED${NC}"
    echo "  Docker is not installed. Install from https://docs.docker.com/get-docker/"
    FAILED=$((FAILED + 1))
    exit 1
fi
DOCKER_VERSION=$(docker --version)
echo -e "${GREEN}✓ PASSED${NC} ($DOCKER_VERSION)"
PASSED=$((PASSED + 1))

# Test 2: Check Docker Compose is installed
echo -n "[$((TOTAL + 1))] Checking Docker Compose... "
TOTAL=$((TOTAL + 1))
if ! docker compose version &> /dev/null; then
    echo -e "${RED}✗ FAILED${NC}"
    echo "  Docker Compose V2 is not installed."
    FAILED=$((FAILED + 1))
    exit 1
fi
COMPOSE_VERSION=$(docker compose version --short)
echo -e "${GREEN}✓ PASSED${NC} (v$COMPOSE_VERSION)"
PASSED=$((PASSED + 1))

# Test 3: Check required files exist
echo -n "[$((TOTAL + 1))] Checking required files... "
TOTAL=$((TOTAL + 1))
missing_files=()
for file in Dockerfile docker-compose.yml docker-compose.host-ollama.yml requirements.txt .env.template .dockerignore; do
    if [ ! -f "$file" ]; then
        missing_files+=("$file")
    fi
done

if [ ${#missing_files[@]} -ne 0 ]; then
    echo -e "${RED}✗ FAILED${NC}"
    echo "  Missing files: ${missing_files[*]}"
    FAILED=$((FAILED + 1))
    exit 1
fi
echo -e "${GREEN}✓ PASSED${NC}"
PASSED=$((PASSED + 1))

# Test 4: Check Python source files
echo -n "[$((TOTAL + 1))] Checking Python source files... "
TOTAL=$((TOTAL + 1))
missing_py=()
for file in main.py searcher.py scraper.py; do
    if [ ! -f "$file" ]; then
        missing_py+=("$file")
    fi
done

if [ ${#missing_py[@]} -ne 0 ]; then
    echo -e "${RED}✗ FAILED${NC}"
    echo "  Missing Python files: ${missing_py[*]}"
    FAILED=$((FAILED + 1))
    exit 1
fi
echo -e "${GREEN}✓ PASSED${NC}"
PASSED=$((PASSED + 1))

# Test 5: Build Docker image
echo -n "[$((TOTAL + 1))] Building Docker image... "
TOTAL=$((TOTAL + 1))
if ! docker build -t research-agent-test:latest . > /tmp/docker-build.log 2>&1; then
    echo -e "${RED}✗ FAILED${NC}"
    echo "  Build failed. Check /tmp/docker-build.log for details."
    echo "  Last 20 lines:"
    tail -20 /tmp/docker-build.log
    FAILED=$((FAILED + 1))
    exit 1
fi
echo -e "${GREEN}✓ PASSED${NC}"
PASSED=$((PASSED + 1))

# Test 6: Check if host Ollama is available
echo -n "[$((TOTAL + 1))] Checking for host Ollama... "
TOTAL=$((TOTAL + 1))
HOST_OLLAMA_AVAILABLE=false
if curl -s -f http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo -e "${GREEN}✓ FOUND${NC}"
    HOST_OLLAMA_AVAILABLE=true
    PASSED=$((PASSED + 1))
else
    echo -e "${YELLOW}⊗ NOT FOUND${NC} (will use dockerized Ollama)"
    PASSED=$((PASSED + 1))
fi

# Decide which compose file to use
if [ "$HOST_OLLAMA_AVAILABLE" = true ]; then
    COMPOSE_FILE="docker-compose.host-ollama.yml"
    echo ""
    echo -e "${BLUE}→ Using host Ollama (docker-compose.host-ollama.yml)${NC}"
    echo ""
else
    COMPOSE_FILE="docker-compose.yml"
    echo ""
    echo -e "${BLUE}→ Using dockerized Ollama (docker-compose.yml)${NC}"
    echo ""
fi

# Test 7: Start services
echo -n "[$((TOTAL + 1))] Starting Docker Compose services... "
TOTAL=$((TOTAL + 1))
if ! docker compose -f "$COMPOSE_FILE" up -d > /tmp/docker-compose.log 2>&1; then
    echo -e "${RED}✗ FAILED${NC}"
    echo "  Services failed to start. Check /tmp/docker-compose.log"
    cat /tmp/docker-compose.log
    FAILED=$((FAILED + 1))
    exit 1
fi
echo -e "${GREEN}✓ PASSED${NC}"
PASSED=$((PASSED + 1))

# Test 8: Wait for services to be ready
if [ "$HOST_OLLAMA_AVAILABLE" = false ]; then
    echo -n "[$((TOTAL + 1))] Waiting for Ollama to be healthy (max 60s)... "
    TOTAL=$((TOTAL + 1))
    timeout=60
    elapsed=0
    while [ $elapsed -lt $timeout ]; do
        if docker compose -f "$COMPOSE_FILE" ps | grep -q "ollama.*healthy"; then
            echo -e "${GREEN}✓ PASSED${NC}"
            PASSED=$((PASSED + 1))
            break
        fi
        sleep 2
        elapsed=$((elapsed + 2))
    done

    if [ $elapsed -ge $timeout ]; then
        echo -e "${RED}✗ FAILED${NC}"
        echo "  Ollama did not become healthy within ${timeout}s"
        docker compose -f "$COMPOSE_FILE" logs ollama | tail -30
        docker compose -f "$COMPOSE_FILE" down
        FAILED=$((FAILED + 1))
        exit 1
    fi

    # Test 9: Check Ollama API is accessible
    echo -n "[$((TOTAL + 1))] Testing Ollama API connectivity... "
    TOTAL=$((TOTAL + 1))
    sleep 2  # Give it a moment
    if ! curl -s -f http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo -e "${RED}✗ FAILED${NC}"
        echo "  Cannot reach Ollama API at http://localhost:11434"
        docker compose -f "$COMPOSE_FILE" logs ollama | tail -20
        docker compose -f "$COMPOSE_FILE" down
        FAILED=$((FAILED + 1))
        exit 1
    fi
    echo -e "${GREEN}✓ PASSED${NC}"
    PASSED=$((PASSED + 1))

    # Test 10: Check if model needs to be pulled
    echo -n "[$((TOTAL + 1))] Checking for Ollama model... "
    TOTAL=$((TOTAL + 1))
    if ! docker exec research-ollama ollama list 2>/dev/null | grep -q "llama3.1:8b-instruct-q8_0"; then
        echo -e "${YELLOW}⊗ NOT FOUND${NC}"
        echo "  Pulling model (this may take 5-10 minutes for ~8GB download)..."
        if docker exec research-ollama ollama pull llama3.1:8b-instruct-q8_0; then
            echo -e "  ${GREEN}Model pulled successfully${NC}"
            PASSED=$((PASSED + 1))
        else
            echo -e "  ${RED}Failed to pull model${NC}"
            docker compose -f "$COMPOSE_FILE" down
            FAILED=$((FAILED + 1))
            exit 1
        fi
    else
        echo -e "${GREEN}✓ FOUND${NC}"
        PASSED=$((PASSED + 1))
    fi
else
    # Using host Ollama - verify model exists
    echo -n "[$((TOTAL + 1))] Checking for Ollama model on host... "
    TOTAL=$((TOTAL + 1))
    if ! ollama list 2>/dev/null | grep -q "llama3.1:8b-instruct-q8_0"; then
        echo -e "${YELLOW}⊗ NOT FOUND${NC}"
        echo "  Please pull the model on your host:"
        echo "  ollama pull llama3.1:8b-instruct-q8_0"
        docker compose -f "$COMPOSE_FILE" down
        FAILED=$((FAILED + 1))
        exit 1
    else
        echo -e "${GREEN}✓ FOUND${NC}"
        PASSED=$((PASSED + 1))
    fi
fi

# Test 11: Verify container is running
echo -n "[$((TOTAL + 1))] Verifying research-agent container... "
TOTAL=$((TOTAL + 1))
if ! docker ps | grep -q "research-agent"; then
    echo -e "${RED}✗ FAILED${NC}"
    echo "  research-agent container is not running"
    docker compose -f "$COMPOSE_FILE" ps
    docker compose -f "$COMPOSE_FILE" down
    FAILED=$((FAILED + 1))
    exit 1
fi
echo -e "${GREEN}✓ PASSED${NC}"
PASSED=$((PASSED + 1))

# Test 12: Run help command
echo -n "[$((TOTAL + 1))] Testing research agent CLI (--help)... "
TOTAL=$((TOTAL + 1))
if ! docker compose -f "$COMPOSE_FILE" run --rm research-agent --help > /tmp/agent-help.log 2>&1; then
    echo -e "${RED}✗ FAILED${NC}"
    echo "  Agent CLI failed. Check /tmp/agent-help.log"
    cat /tmp/agent-help.log
    docker compose -f "$COMPOSE_FILE" down
    FAILED=$((FAILED + 1))
    exit 1
fi
echo -e "${GREEN}✓ PASSED${NC}"
PASSED=$((PASSED + 1))

# Test 13: Create reports directory
echo -n "[$((TOTAL + 1))] Creating reports directory... "
TOTAL=$((TOTAL + 1))
mkdir -p reports
chmod 755 reports
echo -e "${GREEN}✓ PASSED${NC}"
PASSED=$((PASSED + 1))

# Test 14: Run quick end-to-end test
echo ""
echo -e "${BLUE}→ Running end-to-end test (quick research with 1 query × 1 result)${NC}"
echo -e "${BLUE}  This may take 10-20 seconds...${NC}"
echo ""
echo -n "[$((TOTAL + 1))] Executing research agent... "
TOTAL=$((TOTAL + 1))
if ! docker compose -f "$COMPOSE_FILE" run --rm \
    -e SEARCH_NUM_QUERIES=1 \
    -e SEARCH_RESULTS_PER_QUERY=1 \
    -e VERBOSE=false \
    research-agent \
    "Docker containerization benefits" > /tmp/e2e-test.log 2>&1; then
    echo -e "${RED}✗ FAILED${NC}"
    echo "  End-to-end test failed. Check /tmp/e2e-test.log"
    echo "  Last 30 lines:"
    tail -30 /tmp/e2e-test.log
    docker compose -f "$COMPOSE_FILE" down
    FAILED=$((FAILED + 1))
    exit 1
fi
echo -e "${GREEN}✓ PASSED${NC}"
PASSED=$((PASSED + 1))

# Test 15: Verify report was generated
echo -n "[$((TOTAL + 1))] Verifying report generation... "
TOTAL=$((TOTAL + 1))
if [ ! -f "reports/final_report.md" ]; then
    echo -e "${RED}✗ FAILED${NC}"
    echo "  Report file was not generated"
    ls -la reports/ || echo "  reports/ directory is empty or missing"
    docker compose -f "$COMPOSE_FILE" down
    FAILED=$((FAILED + 1))
    exit 1
fi

# Check report has content
REPORT_SIZE=$(wc -c < reports/final_report.md)
if [ "$REPORT_SIZE" -lt 100 ]; then
    echo -e "${RED}✗ FAILED${NC}"
    echo "  Report file is too small ($REPORT_SIZE bytes)"
    cat reports/final_report.md
    docker compose -f "$COMPOSE_FILE" down
    FAILED=$((FAILED + 1))
    exit 1
fi

echo -e "${GREEN}✓ PASSED${NC} (${REPORT_SIZE} bytes)"
PASSED=$((PASSED + 1))

# Cleanup
echo ""
echo -n "[$((TOTAL + 1))] Cleaning up test containers... "
TOTAL=$((TOTAL + 1))
if docker compose -f "$COMPOSE_FILE" down > /dev/null 2>&1; then
    echo -e "${GREEN}✓ DONE${NC}"
    PASSED=$((PASSED + 1))
else
    echo -e "${YELLOW}⊗ WARNING${NC} (manual cleanup may be required)"
    PASSED=$((PASSED + 1))
fi

# Summary
echo ""
echo "======================================================================"
if [ $FAILED -eq 0 ]; then
    echo -e "  ${GREEN}ALL TESTS PASSED!${NC} 🎉"
else
    echo -e "  ${RED}SOME TESTS FAILED${NC}"
fi
echo "======================================================================"
echo ""
echo "  Total Tests: $TOTAL"
echo -e "  ${GREEN}Passed: $PASSED${NC}"
if [ $FAILED -gt 0 ]; then
    echo -e "  ${RED}Failed: $FAILED${NC}"
fi
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}Your Local Research Agent is production-ready!${NC}"
    echo ""
    echo "Quick Start Commands:"
    echo ""
    if [ "$HOST_OLLAMA_AVAILABLE" = true ]; then
        echo "  # Using host Ollama (recommended):"
        echo "  docker compose -f docker-compose.host-ollama.yml up -d"
        echo "  docker compose -f docker-compose.host-ollama.yml exec research-agent \\"
        echo "    python main.py 'your research topic'"
        echo "  ls -lh reports/"
        echo "  docker compose -f docker-compose.host-ollama.yml down"
    else
        echo "  # Using dockerized Ollama:"
        echo "  docker compose up -d"
        echo "  docker compose exec research-agent python main.py 'your research topic'"
        echo "  ls -lh reports/"
        echo "  docker compose down"
    fi
    echo ""
    echo "For detailed documentation, see DOCKER.md"
    echo ""

    # Show sample report snippet
    if [ -f "reports/final_report.md" ]; then
        echo "Sample report preview:"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        head -20 reports/final_report.md
        echo "..."
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
    fi

    exit 0
else
    echo -e "${RED}Production readiness verification failed.${NC}"
    echo "Please review the errors above and fix the issues."
    echo ""
    exit 1
fi
