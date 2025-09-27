#!/bin/bash

# Deployment script for Freqtrade
# Prerequisites: .env file must exist (run ./generate_credentials.sh first)
set -e

command_exists() { command -v "$1" >/dev/null 2>&1; }

info() { echo -e "\033[0;34m$1\033[0m"; }
success() { echo -e "\033[0;32m$1\033[0m"; }
warn() { echo -e "\033[1;33m$1\033[0m"; }
error() { echo -e "\033[0;31m$1\033[0m"; }

# Function to check if credentials exist or generate them
check_or_generate_credentials() {
    if [ ! -f ".env" ]; then
        error "❌ No .env file found!"
        echo ""
        info "🔐 To generate credentials, run:"
        echo "  ./generate_credentials.sh"
        echo ""
        info "📝 Or create .env file manually with required variables:"
        echo "  FREQTRADE_API_USERNAME, FREQTRADE_API_PASSWORD, JWT_SECRET_KEY, WS_TOKEN"
        echo ""
        exit 1
    fi
    
    # Load credentials from existing .env file
    info "🔧 Loading credentials from .env file..."
    if ! grep -q "^FREQTRADE_API_USERNAME=" .env; then
        error "❌ Missing FREQTRADE_API_USERNAME in .env file"
        exit 1
    fi
    
    FREQTRADE_USERNAME=$(grep "^FREQTRADE_API_USERNAME=" .env | cut -d'=' -f2)
    FREQTRADE_PASSWORD=$(grep "^FREQTRADE_API_PASSWORD=" .env | cut -d'=' -f2)
    JWT_SECRET=$(grep "^JWT_SECRET_KEY=" .env | cut -d'=' -f2)
    WS_TOKEN=$(grep "^WS_TOKEN=" .env | cut -d'=' -f2)
    FREQTRADE_HOST=$(grep "^FREQTRADE_HOST=" .env 2>/dev/null | cut -d'=' -f2)
    if [ -z "$FREQTRADE_HOST" ]; then
        FREQTRADE_HOST="freq.subx.fun"
    fi
    PROXY_URL=$(grep "^PROXY_URL=" .env | cut -d'=' -f2 || echo "")
    
    success "✅ Loaded credentials from .env file"
}

# Single-service deployment: freqtrade only (no modes)
COMPOSE_FILE="docker-compose.yml"
info "🚀 Starting freqtrade deployment..."

# Create necessary directories
info "📁 Creating directories..."
mkdir -p data

# Ensure Freqtrade user_data directory exists, create from template if missing
if [ ! -d "user_data" ]; then
  if [ -d "user_data_template" ]; then
    info "📁 Creating user_data from template..."
    cp -r user_data_template user_data
    success "✅ Created user_data directory from user_data_template"
    
    # Replace template placeholders immediately after creation
    if [ -f "user_data/config_price-act_strategy.json" ]; then
      info "🔧 Replacing template placeholders with temporary values..."
      sed -i.bak 's/"\${FREQTRADE_USERNAME}"/"temp_admin"/g' user_data/config_price-act_strategy.json 2>/dev/null && rm -f user_data/config_price-act_strategy.json.bak || true
      sed -i.bak 's/"\${FREQTRADE_PASSWORD}"/"temp_password"/g' user_data/config_price-act_strategy.json 2>/dev/null && rm -f user_data/config_price-act_strategy.json.bak || true
      sed -i.bak 's/"\${JWT_SECRET}"/"temp_jwt_secret"/g' user_data/config_price-act_strategy.json 2>/dev/null && rm -f user_data/config_price-act_strategy.json.bak || true
      sed -i.bak 's/"\${WS_TOKEN}"/"temp_ws_token"/g' user_data/config_price-act_strategy.json 2>/dev/null && rm -f user_data/config_price-act_strategy.json.bak || true
      sed -i.bak 's/"\${OKX_API_KEY}"/""/g' user_data/config_price-act_strategy.json 2>/dev/null && rm -f user_data/config_price-act_strategy.json.bak || true
      sed -i.bak 's/"\${OKX_SECRET}"/""/g' user_data/config_price-act_strategy.json 2>/dev/null && rm -f user_data/config_price-act_strategy.json.bak || true
      sed -i.bak 's/"\${PROXY_URL}"/""/g' user_data/config_price-act_strategy.json 2>/dev/null && rm -f user_data/config_price-act_strategy.json.bak || true
      success "✅ Template placeholders replaced with temporary values"
    fi
  else
    error "❌ 缺少 user_data_template 目录，无法创建 user_data"
    exit 1
  fi
else
  info "ℹ️  user_data directory already exists"
fi

# Check required files exist
if [ ! -f "user_data/strategies/price-act_strategy.py" ]; then
  error "❌ Missing trading strategy file: user_data/strategies/price-act_strategy.py"
  exit 1
fi

# Check if config file exists
if [ ! -f "user_data/config_price-act_strategy.json" ]; then
  error "❌ Missing config file: user_data/config_price-act_strategy.json"
  exit 1
fi

# Check and load credentials
check_or_generate_credentials

# Function to update Freqtrade config with proxy settings
update_proxy_config() {
    local proxy_url="$1"
    if [ -f "user_data/config_price-act_strategy.json" ] && command_exists jq; then
        info "🔧 Updating Freqtrade config with proxy settings..."
        
        if [ -n "$proxy_url" ] && [ "$proxy_url" != "" ]; then
            # Set proxy configuration
            jq --arg proxy_url "$proxy_url" \
               '.exchange.ccxt_config.proxies = {
                  "http": $proxy_url,
                  "https": $proxy_url
                } |
                .exchange.ccxt_async_config.proxies = {
                  "http": $proxy_url,
                  "https": $proxy_url
                }' \
               user_data/config_price-act_strategy.json > user_data/config_temp.json && \
            mv user_data/config_temp.json user_data/config_price-act_strategy.json
            success "✅ Applied proxy settings: $proxy_url"
        else
            # Remove proxy configuration or set to null
            jq 'del(.exchange.ccxt_config.proxies) | del(.exchange.ccxt_async_config.proxies)' \
               user_data/config_price-act_strategy.json > user_data/config_temp.json && \
            mv user_data/config_temp.json user_data/config_price-act_strategy.json
            success "✅ Removed proxy settings"
        fi
        
        # Also replace template placeholders if they exist
        sed -i.bak 's/"\${PROXY_URL}"/""/g' user_data/config_price-act_strategy.json 2>/dev/null && rm -f user_data/config_price-act_strategy.json.bak || true
    fi
}

# Update Freqtrade config with credentials (either new or existing)
if [ -f "user_data/config_price-act_strategy.json" ] && [ -n "$FREQTRADE_USERNAME" ]; then
    info "🔧 Updating Freqtrade config with credentials..."

    # Create clean backup name without stacking timestamps
    if [ -f "user_data/config_price-act_strategy.json.backup" ]; then
        rm -f user_data/config_price-act_strategy.json.backup
    fi
    cp user_data/config_price-act_strategy.json user_data/config_price-act_strategy.json.backup

    # Update existing config with credentials using jq if available
    if command_exists jq; then
        jq --arg username "$FREQTRADE_USERNAME" \
           --arg password "$FREQTRADE_PASSWORD" \
           --arg jwt_secret "$JWT_SECRET" \
           --arg ws_token "$WS_TOKEN" \
           '.api_server.username = $username |
            .api_server.password = $password |
            .api_server.jwt_secret_key = $jwt_secret |
            .api_server.ws_token = [$ws_token] |
            .api_server.CORS_origins = ["http://localhost:3000", "http://localhost:14251"]' \
           user_data/config_price-act_strategy.json > user_data/config_temp.json && \
        mv user_data/config_temp.json user_data/config_price-act_strategy.json
        success "✅ Updated Freqtrade config with credentials"
        
        # Apply proxy settings if available
        update_proxy_config "$PROXY_URL"
    else
        warn "⚠️  jq not available - please manually update API credentials in user_data/config_price-act_strategy.json"
    fi
fi

# Generate docker-compose.yml based on configuration
info "🔧 Generating docker-compose.yml..."

if [ -n "$FREQTRADE_HOST" ] && [ "$FREQTRADE_HOST" != "localhost" ]; then
    DEPLOY_MODE_DISPLAY="Production (with domain)"
    HOST_RULE="Host(\`${FREQTRADE_HOST}\`)"
else
    DEPLOY_MODE_DISPLAY="Development (localhost)"
    FREQTRADE_HOST="localhost"
    HOST_RULE="Host(\`localhost\`)"
fi

# Ensure FREQTRADE_HOST is persisted in .env file
if [ -f ".env" ]; then
    if grep -q "^FREQTRADE_HOST=" .env; then
        # Update existing FREQTRADE_HOST line
        sed -i.bak "s/^FREQTRADE_HOST=.*/FREQTRADE_HOST=${FREQTRADE_HOST}/" .env && rm -f .env.bak
    else
        # Add FREQTRADE_HOST to .env file if it doesn't exist
        echo "FREQTRADE_HOST=${FREQTRADE_HOST}" >> .env
    fi
    info "🔧 Updated FREQTRADE_HOST in .env file: ${FREQTRADE_HOST}"
fi

# Generate docker-compose.yml
cat > docker-compose.yml << EOF
services:
  freqtrade:
    image: freqtradeorg/freqtrade:stable
    container_name: freqtrade-bot01
    restart: unless-stopped
    volumes:
      - ./user_data:/freqtrade/user_data
      - ./data:/freqtrade/data
    command: >
      trade --config /freqtrade/user_data/config_price-act_strategy.json
            --strategy PriceActionStrategy
            --dry-run
    environment:
      - FREQTRADE__API_SERVER__ENABLED=true
      - FREQTRADE__API_SERVER__LISTEN_IP_ADDRESS=0.0.0.0
      - FREQTRADE__API_SERVER__LISTEN_PORT=8080
EOF

# Add proxy settings if configured
if [ -n "$PROXY_URL" ]; then
    cat >> docker-compose.yml << EOF
      # Proxy settings for restricted countries
      - HTTP_PROXY=${PROXY_URL}
      - HTTPS_PROXY=${PROXY_URL}
      - NO_PROXY=localhost,127.0.0.1
EOF
fi

# Continue with ports and labels
cat >> docker-compose.yml << EOF
    ports:
      - "6677:8080"
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.freqtrade.rule=${HOST_RULE}"
      - "traefik.http.routers.freqtrade.entrypoints=websecure"
      - "traefik.http.routers.freqtrade.tls.certresolver=letsencrypt"
      - "traefik.http.services.freqtrade.loadbalancer.server.port=8080"
    networks:
      - traefik
      - default

networks:
  traefik:
    external: true
EOF

success "✅ Generated docker-compose.yml for ${DEPLOY_MODE_DISPLAY}"

# Update Freqtrade config with proxy settings
if [ -n "$PROXY_URL" ]; then
    update_proxy_config "$PROXY_URL"
    info "ℹ️  Proxy configured: ${PROXY_URL}"
else
    update_proxy_config ""
fi

# Backup existing database if it exists
backup_database() {
  local db_path="./data/crypto_data.db"
  local backup_path="./data/crypto_data.db.backup"

  if [ -f "$db_path" ]; then
    info "💾 Backing up existing database..."
    # Remove old backup if it exists to avoid stacking names
    [ -f "$backup_path" ] && rm -f "$backup_path"
    cp "$db_path" "$backup_path"
    success "✅ Database backed up to: $backup_path"
    echo "$backup_path" > ./data/.last_backup_path
  else
    info "ℹ️  No existing database found to backup - this is normal for first-time setup"
  fi
  # Always return success to continue deployment
  return 0
}

# Restore database from backup if needed
restore_database() {
  local backup_path_file="./data/.last_backup_path"

  if [ -f "$backup_path_file" ]; then
    local backup_path=$(cat "$backup_path_file")
    if [ -f "$backup_path" ]; then
      info "🔄 Checking if database restore is needed..."

      # Check if current database exists and is valid
      if [ ! -f "./data/crypto_data.db" ]; then
        warn "⚠️  Database not found after deployment, restoring from backup..."
        cp "$backup_path" "./data/crypto_data.db"
        success "✅ Database restored from backup"
      else
        # Check if database is accessible (basic validation)
        if ! docker exec crypto-trader sqlite3 /app/data/crypto_data.db ".tables" >/dev/null 2>&1; then
          warn "⚠️  Database appears corrupted, restoring from backup..."
          cp "$backup_path" "./data/crypto_data.db"
          success "✅ Database restored from backup due to corruption"
        else
          success "✅ Database is healthy, backup not needed"
        fi
      fi
    fi
  fi
}

# Backup database before deployment
backup_database

# Require docker and docker-compose
if ! command_exists docker || ! command_exists docker-compose; then
  error "❌ Docker and docker-compose are required to run this deployment."
  error "Please install Docker and docker-compose, then re-run: ./deploy.sh [all|app|freqtrade]"
  exit 1
fi

# Create Traefik network if it doesn't exist
info "🌐 Creating Traefik network..."
docker network create traefik 2>/dev/null || echo "Network 'traefik' already exists"

# Build and start services
info "🔨 Building and starting services..."
docker-compose -f $COMPOSE_FILE down --remove-orphans
if [ "$NO_CACHE" = "1" ]; then
  docker-compose -f $COMPOSE_FILE build --no-cache
else
  docker-compose -f $COMPOSE_FILE build
fi
docker-compose -f $COMPOSE_FILE up -d

# Wait for services to be ready
info "⏳ Waiting for services to start..."
sleep 20

# Dump final freqtrade config (from host bind mount) for debugging
info "🧾 Final freqtrade config (host): user_data/config_price-act_strategy.json"
if command_exists jq; then
  jq '.' user_data/config_price-act_strategy.json | head -200 || cat user_data/config_price-act_strategy.json | head -200
else
  cat user_data/config_price-act_strategy.json | head -200
fi

# Pairlists 仅由 JSON 配置提供，避免 env 深合并冲突

# Check service status
success "✅ Checking service status..."
docker-compose -f $COMPOSE_FILE ps

# Restore database if needed
restore_database

# Test Freqtrade API and start simulation trading
info "🔍 Testing Freqtrade API connectivity..."

# Determine API URL based on deployment mode
if [ "$FREQTRADE_HOST" != "localhost" ] && [ -n "$FREQTRADE_HOST" ]; then
  API_TEST_URL="https://${FREQTRADE_HOST}"
else
  API_TEST_URL="http://localhost:6677"
fi

info "📡 Using API URL: $API_TEST_URL"

if command_exists curl; then
  # Wait for Freqtrade to be fully initialized (check for STOPPED state)
  info "⏳ Waiting for Freqtrade to complete initialization..."
  INIT_TIMEOUT=60
  INIT_COUNT=0
  
  while [ $INIT_COUNT -lt $INIT_TIMEOUT ]; do
    if curl -sSf "${API_TEST_URL}/api/v1/ping" | grep -qi "pong" 2>/dev/null; then
      # Check if bot is in STOPPED state (fully initialized)
      if docker logs freqtrade-bot01 2>/dev/null | tail -10 | grep -q "state='STOPPED'"; then
        success "✅ Freqtrade fully initialized and ready"
        break
      fi
    fi
    sleep 2
    INIT_COUNT=$((INIT_COUNT + 2))
    if [ $((INIT_COUNT % 10)) -eq 0 ]; then
      info "⏳ Still waiting for initialization... (${INIT_COUNT}s/${INIT_TIMEOUT}s)"
    fi
  done
  
  # Test API ping
  if curl -sSf "${API_TEST_URL}/api/v1/ping" | grep -qi "pong"; then
    success "✅ Freqtrade API is responding correctly"
    
    # Test API authentication
    info "🔐 Testing API authentication..."
    if curl -sSf -u "${FREQTRADE_USERNAME}:${FREQTRADE_PASSWORD}" "${API_TEST_URL}/api/v1/whitelist" | grep -qi "whitelist"; then
      success "✅ Freqtrade API authentication successful"
      
      # Start simulation trading with retry logic
      info "🚀 Starting simulation trading..."
      RETRY_COUNT=0
      MAX_RETRIES=3
      
      while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
        TRADING_RESPONSE=$(curl -s -X POST -u "${FREQTRADE_USERNAME}:${FREQTRADE_PASSWORD}" "${API_TEST_URL}/api/v1/start")
        
        if echo "$TRADING_RESPONSE" | grep -qi "starting\|already running"; then
          success "✅ Simulation trading started successfully"
          break
        else
          RETRY_COUNT=$((RETRY_COUNT + 1))
          if [ $RETRY_COUNT -lt $MAX_RETRIES ]; then
            warn "⚠️  Attempt $RETRY_COUNT failed, retrying in 5 seconds..."
            sleep 5
          else
            warn "⚠️  Failed to start simulation trading after $MAX_RETRIES attempts: $TRADING_RESPONSE"
            break
          fi
        fi
      done
      
      # Only proceed if trading started successfully
      if echo "$TRADING_RESPONSE" | grep -qi "starting\|already running"; then
        
        # Wait a moment for trades to initialize
        info "⏳ Waiting for initial trades to execute..."
        sleep 10
        
        # Check trading status
        info "📊 Checking trading status..."
        TRADE_COUNT=$(curl -s -u "${FREQTRADE_USERNAME}:${FREQTRADE_PASSWORD}" "${API_TEST_URL}/api/v1/status" | grep -o '"trade_id"' | wc -l)
        if [ "$TRADE_COUNT" -gt 0 ]; then
          success "✅ Active trades detected: $TRADE_COUNT trades"
        else
          info "ℹ️  No active trades yet (this is normal for new strategies)"
        fi
        
        # Show trading pairs
        info "📈 Trading pairs loaded:"
        curl -s -u "${FREQTRADE_USERNAME}:${FREQTRADE_PASSWORD}" "${API_TEST_URL}/api/v1/whitelist" | grep -o '"[A-Z][A-Z]*/[A-Z][A-Z]*"' | head -5 | sed 's/"//g' | sed 's/^/  - /'
        
      else
        warn "⚠️  Failed to start simulation trading: $TRADING_RESPONSE"
      fi
    else
      warn "⚠️  Freqtrade API authentication failed"
    fi
  else
    warn "⚠️  Freqtrade API is not responding"
  fi
else
  warn "⚠️  curl not available - skipping API tests"
fi

success "🎉 Deployment completed!"
echo ""
info "🚀 Deploy Mode: ${DEPLOY_MODE_DISPLAY:-Development (localhost)}"
echo ""

# Show access URLs
if [ "$FREQTRADE_HOST" != "localhost" ] && [ -n "$FREQTRADE_HOST" ]; then
  echo "  🌐 Production URL: https://${FREQTRADE_HOST}"
else
  echo "  🌐 Local URL: http://localhost:6677"
fi
echo ""

info "🔐 Credentials (from .env file):"
echo "  - Username: ${FREQTRADE_USERNAME}"
echo "  - Password: ${FREQTRADE_PASSWORD}"
echo ""

warn "⚠️  IMPORTANT NOTES:"
echo "  1. System is in DRY-RUN mode (safe, no real trading)"
echo "  2. For live trading: ./update_exchange_credentials.sh"
echo "  3. To update credentials: ./generate_credentials.sh"
echo ""

info "🔧 Useful commands:"
echo "  - View logs: docker-compose logs -f freqtrade"
echo "  - Stop: docker-compose down"
echo "  - Restart: docker-compose restart"
echo "  - Generate new credentials: ./generate_credentials.sh"
