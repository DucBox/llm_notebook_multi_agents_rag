#!/bin/bash
set -e

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

# ── Colors ────────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()    { echo -e "${GREEN}[INFO]${NC} $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
error()   { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# ── Check prerequisites ───────────────────────────────────────────────────────
info "Checking prerequisites..."

command -v docker >/dev/null 2>&1 || error "Docker is not installed."
docker info >/dev/null 2>&1      || error "Docker daemon is not running."

# ── Check .env ────────────────────────────────────────────────────────────────
if [ ! -f ".env" ]; then
    warn ".env not found — copying from .env.example"
    cp .env.example .env
    warn "Please fill in OPENAI_API_KEY in .env before continuing."
    exit 1
fi

if ! grep -q "^OPENAI_API_KEY=sk-" .env; then
    warn "OPENAI_API_KEY in .env looks empty or invalid. Embedding will fail."
fi

# ── Build & start ─────────────────────────────────────────────────────────────
info "Building and starting containers..."
docker compose up --build -d

# ── Wait for API health ────────────────────────────────────────────────────────
info "Waiting for API to be ready..."
MAX_RETRIES=30
COUNT=0

until curl -sf http://localhost:8000/api/v1/health >/dev/null 2>&1; do
    COUNT=$((COUNT + 1))
    if [ $COUNT -ge $MAX_RETRIES ]; then
        error "API did not start after ${MAX_RETRIES} attempts. Run: docker compose logs api"
    fi
    sleep 2
done

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Backend is up!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "  API docs  : http://localhost:8000/docs"
echo "  Health    : http://localhost:8000/api/v1/health"
echo ""
echo "  Stop      : docker compose down"
echo "  Logs      : docker compose logs -f api"
echo ""
