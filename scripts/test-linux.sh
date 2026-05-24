#!/usr/bin/env bash
# Test obsiforge on Linux via OrbStack/Docker
# Usage: ./scripts/test-linux.sh [--full]
#   --full: Run full init (not just dry-run)

set -euo pipefail

IMAGE="obsiforge-test-linux"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

MODE="${1:-dry-run}"

echo "=== Building Linux test image ==="
docker build -t "$IMAGE" -f - "$PROJECT_DIR" <<'DOCKERFILE'
FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl ca-certificates unzip \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

# Install Node.js via NodeSource (reliable for CI/Docker)
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/obsiforge
COPY . .

RUN uv sync --extra dev

# Verify Node.js is accessible
RUN node --version && npm --version
DOCKERFILE

echo ""
echo "=== Running tests on Linux (mode: $MODE) ==="
echo ""

if [ "$MODE" = "--full" ]; then
    docker run --rm -it "$IMAGE" bash -c "
        uv run pytest tests/test_smoke.py -v && \
        echo '---' && \
        echo 'Smoke tests passed. Running full init...' && \
        uv run obsiforge init --name linux-test --path /tmp/linux-test-vault -y
    "
else
    # Run each test group separately so a non-zero exit from one doesn't skip the rest
    FAIL=0

    echo "--- Smoke tests ---"
    docker run --rm "$IMAGE" uv run pytest tests/test_smoke.py -v || FAIL=$((FAIL+1))

    # Dry-run init may exit non-zero if prerequisites missing (expected in Docker)
    # Check that it produces output rather than checking exit code
    echo "--- Dry-run init ---"
    OUTPUT=$(docker run --rm "$IMAGE" uv run obsiforge init --name linux-test --path /tmp/linux-test-vault --dry-run -y 2>&1) || true
    echo "$OUTPUT"
    if echo "$OUTPUT" | grep -q "ObsiForge"; then
        echo "✓ Dry-run init produced expected output"
    else
        echo "✗ Dry-run init did not produce expected output"
        FAIL=$((FAIL+1))
    fi

    echo "--- Platform detection ---"
    docker run --rm "$IMAGE" uv run python -c "from obsiforge.utils.platform import get_platform, detect_package_manager; print(f'Platform: {get_platform()}'); print(f'Package manager: {detect_package_manager()}')" || FAIL=$((FAIL+1))

    echo "--- Port allocation ---"
    docker run --rm "$IMAGE" uv run python -c "from obsiforge.utils.ports import allocate_ports; p = allocate_ports('linux-test'); print(f\"REST API: {p['rest_api']}, MCP HTTP: {p['mcp_http']}\")" || FAIL=$((FAIL+1))

    echo "--- Crypto ---"
    docker run --rm "$IMAGE" uv run python -c "from obsiforge.utils.crypto import generate_api_key, generate_bearer_token; print(f'API key: {generate_api_key(64)[:8]}...'); print(f'Bearer token: {generate_bearer_token(44)[:8]}...')" || FAIL=$((FAIL+1))

    if [ "$FAIL" -gt 0 ]; then
        echo ""
        echo "=== $FAIL test group(s) failed ==="
        exit 1
    fi
fi

echo ""
echo "=== Linux test complete ==="