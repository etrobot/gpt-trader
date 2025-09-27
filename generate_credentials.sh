#!/bin/bash

# Credentials Generation Script for Freqtrade
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
    OKX_API_KEY="DEMO_API_KEY_FOR_DRY_RUN"
    OKX_SECRET="DEMO_SECRET_FOR_DRY_RUN"

    success "✅ Generated secure credentials"
    info "ℹ️  Dry-run mode enabled - using demo API keys (safe for testing)"
    warn "⚠️  For live trading, update OKX API credentials using: ./update_exchange_credentials.sh"

    echo ""
    info "🔐 Generated Freqtrade Credentials:"
    echo "  Username: ${FREQTRADE_USERNAME}"
    echo "  Password: ${FREQTRADE_PASSWORD}"
    echo "  JWT Secret: ${JWT_SECRET}"
    echo "  WebSocket Token: ${WS_TOKEN}"
}

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

# Function to update Freqtrade config with credentials
update_freqtrade_config() {
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
        else
            warn "⚠️  jq not available - please manually update API credentials in user_data/config_price-act_strategy.json"
        fi
    fi
}

# Main execution
main() {
    info "🚀 Freqtrade Credentials Generator"
    echo ""

    # Check if .env file already exists
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
            info "ℹ️  Keeping existing .env file."
            echo ""
            info "📝 If you need to update credentials later, you can:"
            echo "  - Run this script again and choose to recreate"
            echo "  - Edit .env file manually"
            echo ""
            exit 0
        else
            info "💾 Backing up existing .env file..."
            BACKUP_NAME=".env.backup.$(date +%Y%m%d_%H%M%S)"
            cp .env "$BACKUP_NAME"
            success "✅ Backup created: $BACKUP_NAME"
            echo ""
        fi
    fi

    # Generate new credentials
    generate_api_credentials

    # Ask if user wants to use generated credentials
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
        info "📋 Please enter your preferred credentials:"
        read -p "Freqtrade Username: " FREQTRADE_USERNAME
        read -p "Freqtrade Password: " FREQTRADE_PASSWORD
        read -p "JWT Secret Key: " JWT_SECRET
        read -p "WebSocket Token: " WS_TOKEN
    else
        info "✅ Using newly generated secure credentials"
    fi

    # Get HOST configuration
    echo ""
    info "🌐 Host Configuration"
    echo "Configure the domain/host for Freqtrade access:"
    echo "  - Leave empty: Use localhost (development mode)"
    echo "  - Enter domain: Use custom domain with Traefik (production mode)"
    echo "  - Examples: ft01.subx.fun, trading.mydomain.com"
    read -p "Enter host domain (or press Enter for localhost): " FREQTRADE_HOST

    # Normalize accidental 'N'/'n' answers to empty
    if [ "$FREQTRADE_HOST" = "N" ] || [ "$FREQTRADE_HOST" = "n" ]; then
        FREQTRADE_HOST=""
    fi

    if [ -n "$FREQTRADE_HOST" ]; then
        info "✅ Production mode: Using domain $FREQTRADE_HOST"
        DEPLOY_MODE_DISPLAY="Production (with domain)"
    else
        info "✅ Development mode: Using localhost"
        DEPLOY_MODE_DISPLAY="Development (localhost)"
        FREQTRADE_HOST="localhost"
    fi

    # Get proxy configuration
    echo ""
    info "🌐 Proxy Configuration (for restricted countries)"
    read -p "Do you need to use a proxy for Freqtrade? (y/N): " USE_PROXY

    PROXY_URL=""
    if [[ "$USE_PROXY" =~ ^[Yy]$ ]]; then
        read -p "Enter proxy URL (format: http://username:password@proxy.server:port): " PROXY_URL
        if [ -n "$PROXY_URL" ]; then
            success "✅ Proxy configured: ${PROXY_URL}"
        else
            warn "⚠️  No proxy URL provided, skipping proxy configuration"
        fi
    else
        info "ℹ️  No proxy configured"
    fi

    # Create .env file
    info "📝 Creating .env file with credentials..."
    cat > .env << EOF
# Freqtrade API Configuration
FREQTRADE_API_URL=\${FREQTRADE_API_URL:-http://freqtrade-bot01:8080}
FREQTRADE_API_USERNAME=${FREQTRADE_USERNAME}
FREQTRADE_API_PASSWORD=${FREQTRADE_PASSWORD}
# FREQTRADE_API_TOKEN is intentionally not set here because WS token is not a JWT
FREQTRADE_API_TIMEOUT=15

# Host Configuration
FREQTRADE_HOST=${FREQTRADE_HOST}

# Proxy Configuration
PROXY_URL=${PROXY_URL}

# Security
JWT_SECRET_KEY=${JWT_SECRET}
WS_TOKEN=${WS_TOKEN}
EOF
    success "✅ Created .env file with secure credentials"

    # Update Freqtrade config if it exists
    if [ -f "user_data/config_price-act_strategy.json" ]; then
        update_freqtrade_config
        update_proxy_config "$PROXY_URL"
        
        # Update CORS origins if domain is specified
        if [ -n "$FREQTRADE_HOST" ] && [ "$FREQTRADE_HOST" != "localhost" ] && command_exists jq; then
            info "🔧 Adding domain to CORS origins..."
            jq --arg domain "$FREQTRADE_HOST" \
               '.api_server.CORS_origins = ["http://localhost:3000", "http://localhost:14251", ("https://" + $domain), ("http://" + $domain)]' \
               user_data/config_price-act_strategy.json > user_data/config_temp.json && \
            mv user_data/config_temp.json user_data/config_price-act_strategy.json
            success "✅ Added $FREQTRADE_HOST to CORS origins"
        fi
    else
        warn "⚠️  user_data/config_price-act_strategy.json not found - config not updated"
    fi

    echo ""
    success "🎉 Credentials generated successfully!"
    echo ""
    info "🔐 Generated Configuration:"
    echo "  - Deploy Mode: ${DEPLOY_MODE_DISPLAY}"
    echo "  - Freqtrade Username: ${FREQTRADE_USERNAME}"
    echo "  - Freqtrade Password: ${FREQTRADE_PASSWORD}"
    echo "  - Host: ${FREQTRADE_HOST}"
    if [ -n "$PROXY_URL" ]; then
        echo "  - Proxy: ${PROXY_URL}"
    fi
    echo ""
    info "📁 Files created/updated:"
    echo "  - .env (environment variables)"
    if [ -f "user_data/config_price-act_strategy.json" ]; then
        echo "  - user_data/config_price-act_strategy.json (Freqtrade config)"
    fi
    echo ""
    warn "⚠️  IMPORTANT:"
    echo "  - Save these credentials in a secure location"
    echo "  - Never commit .env file to version control"
    echo "  - Run ./deploy.sh to deploy with these credentials"
}

# Execute main function
main "$@"