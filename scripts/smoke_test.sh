#!/usr/bin/env bash
set -euo pipefail

BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info(){ echo -e "${BLUE}$1${NC}"; }
success(){ echo -e "${GREEN}$1${NC}"; }
warn(){ echo -e "${YELLOW}$1${NC}"; }
error(){ echo -e "${RED}$1${NC}"; }

need_cmd(){ command -v "$1" >/dev/null 2>&1 || { error "❌ Missing command: $1"; exit 1; }; }

info "🔍 Smoke test: post-deployment strategy execution (dry-run via Freqtrade)"

# Preconditions
need_cmd curl
if command -v docker >/dev/null 2>&1 && command -v docker-compose >/dev/null 2>&1; then
  info "🐳 Docker & docker-compose found"
else
  warn "⚠️  Docker not detected. This script will only test API endpoints if backend is already running on port 14250."
fi

# Ensure .env exists
if [ ! -f .env ]; then
  error "❌ .env not found. Run ./deploy.sh first."
  exit 1
fi

# Bring up services if Docker exists
if command -v docker >/dev/null 2>&1 && command -v docker-compose >/dev/null 2>&1; then
  info "🔧 Starting services via docker-compose..."
  # Ensure traefik network exists (docker-compose.yml expects it as external)
  docker network create traefik 2>/dev/null || echo "Network 'traefik' already exists"
  info "🧱 Rebuilding images (to pick up latest backend changes)..."
  docker-compose build
  docker-compose up -d
fi

APP_URL="http://localhost:14250"
HEALTH_URL="$APP_URL/api/freqtrade/health"
RUN_NOW_URL="$APP_URL/api/scheduler/run-now"
OPEN_TRADES_URL="$APP_URL/api/freqtrade/open-trades"
SCHED_STATUS_URL="$APP_URL/api/scheduler/status"
REFRESH_TOKEN_URL="$APP_URL/api/freqtrade/refresh-token"

# Wait for app up
info "⏳ Waiting for backend to be ready at $APP_URL ..."
ATTEMPTS=30
for i in $(seq 1 $ATTEMPTS); do
  if curl -fsS "$APP_URL/docs" >/dev/null 2>&1; then
    success "✅ Backend is up"
    break
  fi
  sleep 2
  if [ "$i" = "$ATTEMPTS" ]; then
    error "❌ Backend did not become ready in time"
    exit 1
  fi
done

# Refresh token (optional) and check Freqtrade health with retries
info "🔐 Refreshing Freqtrade API token (optional)"
curl -fsS -X POST "$REFRESH_TOKEN_URL" || true

info "🔎 Checking Freqtrade API health..."
HEALTH_OK=false
for i in $(seq 1 12); do # up to ~60s
  RESP=$(curl -fsS "$HEALTH_URL" || true)
  echo "$RESP" | grep -qi '"healthy": true' && { HEALTH_OK=true; break; }
  sleep 5
  warn "... still waiting for Freqtrade API (try $i)"

done

if [ "$HEALTH_OK" != true ]; then
  error "❌ Freqtrade API not healthy. Last response: ${RESP:-<none>}"
  info "💡 Tips: check 'docker-compose logs -f freqtrade'"
  exit 1
fi
success "✅ Freqtrade API healthy"

# Trigger daily flow now (analysis -> news -> signals -> send to Freqtrade)
info "🚀 Triggering scheduler daily run now"
RUN_RESP=$(curl -fsS -X POST "$RUN_NOW_URL" || true)
echo "$RUN_RESP" | grep -qi '"success": true' || {
  warn "⚠️  Failed to schedule run-now. Response: $RUN_RESP"
}

# Optional: quick scheduler status
info "📊 Scheduler status snapshot"
curl -fsS "$SCHED_STATUS_URL" || true

# Poll open-trades for up to 2 minutes
info "📈 Polling Freqtrade open trades for up to 120s ..."
OPEN_OK=false
for i in $(seq 1 12); do
  TRADES=$(curl -fsS "$OPEN_TRADES_URL" || true)
  COUNT=$(echo "$TRADES" | sed -n 's/.*"count"[[:space:]]*:[[:space:]]*\([0-9]\+\).*/\1/p' | head -n1)
  COUNT=${COUNT:-0}
  if [ "$COUNT" -gt 0 ]; then
    success "✅ Open trades detected: $COUNT"
    echo "$TRADES" | sed -e 's/{"trades":/\n{"trades":/' | head -n 50
    OPEN_OK=true
    break
  fi
  sleep 10
  warn "... no open trades yet (try $i)"

done

if [ "$OPEN_OK" != true ]; then
  warn "⚠️  No open trades detected in 120s window."
  info "➡️  This may be due to market data, analysis results empty, or rate limits."
  info "🔎 Last open-trades response:"; echo "$TRADES"
  info "🪵 Check logs: 'docker-compose logs -f app' and 'docker-compose logs -f freqtrade'"
  exit 2
fi

success "🎉 Smoke test PASSED: Strategy executed and trades appeared in Freqtrade (dry-run)."
