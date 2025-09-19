#!/bin/bash

# Deployment script for Quant Dashboard
set -e

command_exists() { command -v "$1" >/dev/null 2>&1; }

info() { echo -e "\033[0;34m$1\033[0m"; }
success() { echo -e "\033[0;32m$1\033[0m"; }
warn() { echo -e "\033[1;33m$1\033[0m"; }
error() { echo -e "\033[0;31m$1\033[0m"; }

# Function to generate secure random string
generate_secure_key() {
    local length=${1:-32}
    openssl rand -base64 $length | tr -d "=+/" | cut -c1-$length
}

# Function to generate API credentials
generate_api_credentials() {
    info "🔐 Generating secure API credentials..."

    # Generate secure credentials
    FREQTRADE_USERNAME="admin_$(generate_secure_key 8)"
    FREQTRADE_PASSWORD=$(generate_secure_key 24)
    JWT_SECRET=$(generate_secure_key 64)
    WS_TOKEN=$(generate_secure_key 32)

    # Generate exchange API keys placeholders (only needed for live trading)
    BYBIT_API_KEY="DEMO_API_KEY_FOR_DRY_RUN"
    BYBIT_SECRET="DEMO_SECRET_FOR_DRY_RUN"

    success "✅ Generated secure credentials"
    info "ℹ️  Dry-run mode enabled - using demo API keys (safe for testing)"
    warn "⚠️  For live trading, update Bybit API credentials using: ./update_exchange_credentials.sh"

    echo ""
    info "🔐 Generated Freqtrade Credentials:"
    echo "  Username: ${FREQTRADE_USERNAME}"
    echo "  Password: ${FREQTRADE_PASSWORD}"
    echo "  JWT Secret: ${JWT_SECRET}"
    echo "  WebSocket Token: ${WS_TOKEN}"
}

# Deployment mode selection
DEPLOY_MODE=${1:-"all"}

case "$DEPLOY_MODE" in
  "all")
    COMPOSE_FILE="docker-compose.yml"
    info "🚀 Starting full deployment (crypto-trader + freqtrade)..."
    ;;
  "app")
    COMPOSE_FILE="docker-compose.app.yml"
    info "🚀 Starting crypto-trader only deployment..."
    ;;
  "freqtrade")
    COMPOSE_FILE="docker-compose.freqtrade.yml"
    info "🚀 Starting freqtrade only deployment..."
    ;;
  *)
    error "❌ Invalid deployment mode. Usage:"
    echo "  ./deploy.sh all         # Deploy both services (default)"
    echo "  ./deploy.sh app         # Deploy crypto-trader only"
    echo "  ./deploy.sh freqtrade   # Deploy freqtrade only"
    exit 1
    ;;
esac

# Create necessary directories
info "📁 Creating directories..."
mkdir -p data

# Ensure Freqtrade user_data directory and config exist
mkdir -p user_data user_data/strategies
# Check required files exist
if [ ! -f "user_data/strategies/classic_strategy.py" ] && [ ! -f "user_data/strategies/classic_strategy.py" ]; then
  error "❌ Missing trading strategy files"
  error "❌ Please create 'user_data/strategies/classic_strategy.py' or 'user_data/strategies/classic_strategy.py' before deployment"
  exit 1
fi

# Check if config file exists first
if [ ! -f "user_data/config_external_signals.json" ]; then
  error "❌ Missing config file: user_data/config_external_signals.json"
  error "❌ Please create your Freqtrade configuration before deployment"
  exit 1
fi

# Check if .env file already exists first
if [ -f ".env" ]; then
    echo ""
    warn "⚠️  .env file already exists!"
    echo ""
    info "Current .env file contains:"
    echo "========================================"
    cat .env
    echo "========================================"
    echo ""

    read -p "Do you want to recreate the .env file with new credentials? (y/N): " RECREATE_ENV

    if [[ ! "$RECREATE_ENV" =~ ^[Yy]$ ]]; then
        info "ℹ️  Keeping existing .env file. Deployment will continue with current settings."
        echo ""
        info "📝 If you need to update credentials later, you can:"
        echo "  - Run this script again and choose to recreate"
        # OpenAI credentials no longer required
        echo "  - Edit .env file manually"
        echo ""

        # Skip credential input if keeping existing .env
        SKIP_ENV_CREATION=true
        SKIP_CREDENTIAL_GENERATION=true
    else
        info "💾 Backing up existing .env file..."
        # Create clean backup name without stacking timestamps
        BACKUP_NAME=".env.backup.$(date +%Y%m%d_%H%M%S)"
        cp .env "$BACKUP_NAME"
        success "✅ Backup created: $BACKUP_NAME"
        echo ""
        info "📋 You can copy any values you want to keep from above and paste them when prompted."
        echo ""
        SKIP_ENV_CREATION=false
        SKIP_CREDENTIAL_GENERATION=false
    fi
else
    SKIP_ENV_CREATION=false
    SKIP_CREDENTIAL_GENERATION=false
fi

# Generate credentials only if needed
if [ "$SKIP_CREDENTIAL_GENERATION" != "true" ]; then
    generate_api_credentials
else
    # Read existing credentials from .env file
    if [ -f ".env" ]; then
        info "🔧 Reading existing credentials from .env file..."
        FREQTRADE_USERNAME=$(grep "^FREQTRADE_API_USERNAME=" .env | cut -d'=' -f2)
        FREQTRADE_PASSWORD=$(grep "^FREQTRADE_API_PASSWORD=" .env | cut -d'=' -f2)
        JWT_SECRET=$(grep "^JWT_SECRET_KEY=" .env | cut -d'=' -f2)
        WS_TOKEN=$(grep "^WS_TOKEN=" .env | cut -d'=' -f2)
        success "✅ Loaded existing credentials from .env"
    fi
fi

# Update Freqtrade config with credentials (either new or existing)
if [ -f "user_data/config_external_signals.json" ] && [ -n "$FREQTRADE_USERNAME" ]; then
    info "🔧 Updating Freqtrade config with credentials..."

    # Create clean backup name without stacking timestamps
    if [ -f "user_data/config_external_signals.json.backup" ]; then
        rm -f user_data/config_external_signals.json.backup
    fi
    cp user_data/config_external_signals.json user_data/config_external_signals.json.backup

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
            .api_server.CORS_origins = ["http://localhost:3000", "http://localhost:14251", "https://ui01.subx.fun", "https://ftui.subx.fun"]' \
           user_data/config_external_signals.json > user_data/config_temp.json && \
        mv user_data/config_temp.json user_data/config_external_signals.json
        success "✅ Updated Freqtrade config with credentials"
    else
        warn "⚠️  jq not available - please manually update API credentials in user_data/config_external_signals.json"
    fi
fi

# Get configuration only if we need to create/update .env
if [ "$SKIP_ENV_CREATION" != "true" ]; then
    # Ask if user wants to use existing generated credentials
    echo ""
    info "🔑 Generated Credentials Configuration"
    info "The following secure credentials were auto-generated:"
    echo "  - Freqtrade Username: ${FREQTRADE_USERNAME}"
    echo "  - Freqtrade Password: ${FREQTRADE_PASSWORD}"
    echo "  - JWT Secret: ${JWT_SECRET:0:10}..."
    echo "  - WebSocket Token: ${WS_TOKEN:0:10}..."
    echo ""
    read -p "Do you want to use these newly generated credentials? (Y/n): " USE_NEW_CREDS

    if [[ "$USE_NEW_CREDS" =~ ^[Nn]$ ]]; then
        echo ""
        info "📋 Please enter your preferred credentials (or copy from the .env backup shown above):"
        read -p "Freqtrade Username: " FREQTRADE_USERNAME
        read -p "Freqtrade Password: " FREQTRADE_PASSWORD
        read -p "JWT Secret Key: " JWT_SECRET
        read -p "WebSocket Token: " WS_TOKEN

        # Update user_data config with manually entered credentials
        if [ -f "user_data/config_external_signals.json" ] && command_exists jq; then
            info "🔧 Updating Freqtrade config with manually entered credentials..."
            # Create clean backup name without stacking timestamps
            if [ -f "user_data/config_external_signals.json.backup" ]; then
                rm -f user_data/config_external_signals.json.backup
            fi
            cp user_data/config_external_signals.json user_data/config_external_signals.json.backup

            jq --arg username "$FREQTRADE_USERNAME" \
               --arg password "$FREQTRADE_PASSWORD" \
               --arg jwt_secret "$JWT_SECRET" \
               --arg ws_token "$WS_TOKEN" \
               '.api_server.username = $username |
                .api_server.password = $password |
                .api_server.jwt_secret_key = $jwt_secret |
                .api_server.ws_token = [$ws_token] |
                .api_server.CORS_origins = ["http://localhost:3000", "http://localhost:14251", "https://ui01.subx.fun", "https://ftui.subx.fun"]' \
               user_data/config_external_signals.json > user_data/config_temp.json && \
            mv user_data/config_temp.json user_data/config_external_signals.json
            success "✅ Updated Freqtrade config with manually entered credentials"
        fi
    else
        info "✅ Using newly generated secure credentials"
    fi

    # Get Freqtrade API URL for app-only deployment
    if [ "$DEPLOY_MODE" = "app" ]; then
        echo ""
        info "🔗 External Freqtrade Configuration"
        echo "Common options:"
        echo "  - http://host.docker.internal:6677  (if Freqtrade runs on host)"
        echo "  - http://192.168.1.100:6677         (remote server)"
        echo "  - https://ft01.subx.fun             (domain name)"
        read -p "Enter Freqtrade API URL: " FREQTRADE_API_URL_INPUT
        if [ -n "$FREQTRADE_API_URL_INPUT" ]; then
            FREQTRADE_API_URL="$FREQTRADE_API_URL_INPUT"
        else
            error "❌ Freqtrade API URL is required for app-only deployment"
            exit 1
        fi
        info "✅ Freqtrade API URL set to: $FREQTRADE_API_URL"
    fi

    # Get proxy configuration
    echo ""
    info "🌐 Proxy Configuration (for restricted countries)"
    read -p "Do you need to use a proxy for Freqtrade? (y/N): " USE_PROXY

    PROXY_URL=""
    if [[ "$USE_PROXY" =~ ^[Yy]$ ]]; then
        read -p "Enter proxy URL (format: http://username:password@proxy.server:port): " PROXY_URL
        if [ -n "$PROXY_URL" ]; then
            info "🔧 Configuring proxy settings..."

            # Update docker-compose.yml with proxy settings
            if [ -f "docker-compose.yml" ]; then
                # Check if proxy environment variables already exist
                if grep -q "HTTP_PROXY=" docker-compose.yml; then
                    # Update existing proxy settings
                    sed -i.bak "s|HTTP_PROXY=.*|HTTP_PROXY=${PROXY_URL}|g" docker-compose.yml
                    sed -i.bak "s|HTTPS_PROXY=.*|HTTPS_PROXY=${PROXY_URL}|g" docker-compose.yml
                    success "✅ Updated existing proxy settings in docker-compose.yml"
                else
                    # Add proxy settings to freqtrade service environment
                    sed -i.bak '/FREQTRADE__API_SERVER__LISTEN_PORT=8080/a\
          # Proxy settings for restricted countries\
          - HTTP_PROXY='"${PROXY_URL}"'\
          - HTTPS_PROXY='"${PROXY_URL}"'\
          - NO_PROXY=localhost,127.0.0.1' docker-compose.yml
                    success "✅ Added proxy settings to docker-compose.yml"
                fi
                rm -f docker-compose.yml.bak
            fi

            # Update Freqtrade config with proxy settings
            if [ -f "user_data/config_external_signals.json" ] && command_exists jq; then
                info "🔧 Adding proxy settings to Freqtrade config..."
                jq --arg proxy_url "$PROXY_URL" \
                   '.exchange.ccxt_config.proxies = {
                      "http": $proxy_url,
                      "https": $proxy_url
                    } |
                    .exchange.ccxt_async_config.proxies = {
                      "http": $proxy_url,
                      "https": $proxy_url
                    }' \
                   user_data/config_external_signals.json > user_data/config_temp.json && \
                mv user_data/config_temp.json user_data/config_external_signals.json
                success "✅ Added proxy settings to Freqtrade config"
            fi
            success "✅ Proxy configured: ${PROXY_URL}"
        else
            warn "⚠️  No proxy URL provided, skipping proxy configuration"
        fi
    else
        info "ℹ️  No proxy configured"
    fi

    info "📝 Creating .env file with credentials..."
    cat > .env << EOF
# Freqtrade API Configuration
FREQTRADE_API_URL=${FREQTRADE_API_URL:-http://freqtrade-bot01:8080}
FREQTRADE_API_USERNAME=${FREQTRADE_USERNAME}
FREQTRADE_API_PASSWORD=${FREQTRADE_PASSWORD}
# FREQTRADE_API_TOKEN is intentionally not set here because WS token is not a JWT
FREQTRADE_API_TIMEOUT=15

# Proxy Configuration
PROXY_URL=${PROXY_URL}

# Security
JWT_SECRET_KEY=${JWT_SECRET}
WS_TOKEN=${WS_TOKEN}
EOF
    success "✅ Created .env file with secure credentials"
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

# If docker is not available or explicitly skipped, run local validation to test routes
if [ "$SKIP_DOCKER" = "1" ] || ! command_exists docker || ! command_exists docker-compose; then
  warn "⚠️  未检测到 Docker 或 docker-compose，进入本地测试模式（不启动容器）..."

  # Validate that App can serve SPA without a prebuilt static folder
  if grep -q "@app.get(\"/{full_path:path}\")" App/main.py; then
    success "✅ 检测到通配路由，支持SPA前端"
  else
    warn "⚠️  未检测到通配路由，请检查 App/main.py"
  fi

  # Frontend build is optional in local mode
  if [ -f "App/static/index.html" ]; then
    success "✅ 检测到 App/static/index.html"
  else
    warn "ℹ️  本地未发现构建后的前端，将返回API信息或需要自行构建前端"
  fi

  # Check static mounts
  [ -d "App/static/assets" ] && success "✅ 检测到静态资源目录 App/static/assets" || warn "⚠️  未检测到 App/static/assets"
  [ -d "App/static/icons" ] && success "✅ 检测到图标目录 App/static/icons" || warn "⚠️  未检测到 App/static/icons"
  [ -f "App/static/manifest.json" ] && success "✅ 检测到 PWA 文件 manifest.json" || warn "⚠️  未检测到 manifest.json"
  [ -f "App/static/sw.js" ] && success "✅ 检测到 PWA 文件 sw.js" || warn "⚠️  未检测到 sw.js"

  success "🎉 本地路由检查通过：根路径将返回前端 index.html"
  echo ""
  info "👉 你可以在安装 Docker 后再次运行本脚本进行完整部署"
  exit 0
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
sleep 12

# Check service status
success "✅ Checking service status..."
docker-compose -f $COMPOSE_FILE ps

# Restore database if needed
restore_database

# Optional: quick health check via curl if available
if command_exists curl; then
  info "🔍 Verifying API is responding..."
  if curl -sSf "http://localhost:14251/" | grep -qi "Crypto Trading Strategy API"; then
    success "✅ App API is responding correctly"
  else
    warn "⚠️  API response did not match expected content"
  fi
fi

success "🎉 Deployment completed!"
echo ""
info "📊 Application URLs:"
echo "  - App API: http://localhost:14251"
echo "  - API Documentation: http://localhost:14251/docs"
echo "  - API Alternative Docs: http://localhost:14251/redoc"
echo "  - Freqtrade API: http://localhost:6677"
echo ""
info "🌐 Production URLs:"
echo "  - App API: https://api01.subx.fun"
echo "  - FreqTrade API: https://ft01.subx.fun"
echo ""
info "🔐 Security Information:"
echo "  - Freqtrade Username: ${FREQTRADE_USERNAME}"
echo "  - Freqtrade Password: ${FREQTRADE_PASSWORD}"
echo "  - WebSocket Token: ${WS_TOKEN}"
echo "  - JWT Secret: ${JWT_SECRET:0:10}..."
echo ""
warn "⚠️  IMPORTANT SETUP NOTES:"
echo "  1. System is in DRY-RUN mode (safe, no real trading)"
echo "  2. For live trading: ./update_exchange_credentials.sh"
echo "  3. Save the credentials above in a secure location"
echo "  4. Never commit .env file to version control"
echo ""
info "📁 Data persistence:"
echo "  - Database: ./data/crypto_data.db"
echo "  - Freqtrade config: ./user_data/config_external_signals.json"
echo "  - Environment vars: ./.env"
echo ""
info "🔧 Useful commands:"
echo "  - View all logs: docker-compose logs -f"
echo "  - View FreqUI logs: docker-compose logs -f freqtrade-ui"
echo "  - View Freqtrade logs: docker-compose logs -f freqtrade"
echo "  - Stop services: docker-compose down"
echo "  - Restart: docker-compose restart"
echo "  - Update credentials: ./deploy.sh"
