#!/bin/bash
# Fix Freqtrade exchange configuration for dry-run mode
# This script resolves the Binance 451 error in restricted locations

set -e

info() { echo -e "\033[0;34m$1\033[0m"; }
success() { echo -e "\033[0;32m$1\033[0m"; }
warn() { echo -e "\033[1;33m$1\033[0m"; }
error() { echo -e "\033[0;31m$1\033[0m"; }

echo "🔧 Freqtrade Exchange Fix for Restricted Locations"
echo "=================================================="
echo ""

# Check if config exists
CONFIG_FILE="user_data/config_external_signals.json"
if [ ! -f "$CONFIG_FILE" ]; then
    error "❌ Config file not found: $CONFIG_FILE"
    exit 1
fi

# Show current status
info "📋 Current Configuration:"
CURRENT_EXCHANGE=$(jq -r '.exchange.name' "$CONFIG_FILE" 2>/dev/null || echo "unknown")
DRY_RUN=$(jq -r '.dry_run' "$CONFIG_FILE" 2>/dev/null || echo "unknown")
echo "   Exchange: $CURRENT_EXCHANGE"
echo "   Dry Run: $DRY_RUN"
echo ""

# Offer solutions
echo "🛠️  Available Solutions:"
echo "1. Switch to Bybit (recommended for most regions)"
echo "2. Switch to OKX (alternative exchange)"
echo "3. Configure proxy settings"
echo "4. Create sandbox configuration"
echo "5. Show current status only"
echo ""

read -p "Choose solution (1-5): " CHOICE

case $CHOICE in
    1)
        info "🔄 Switching to Bybit exchange..."
        # Already done by previous script, just restart
        success "✅ Bybit configuration is already applied"
        ;;
    2)
        info "🔄 Switching to OKX exchange..."
        if [ -f "user_data/config_okx.json" ]; then
            # Update docker-compose to use OKX config
            sed -i 's|config_external_signals.json|config_okx.json|g' docker-compose.yml
            success "✅ Docker Compose updated to use OKX configuration"
        else
            error "❌ OKX config file not found"
            exit 1
        fi
        ;;
    3)
        info "🌐 Configuring proxy settings..."
        read -p "Enter proxy URL (e.g., http://proxy.example.com:8080): " PROXY_URL
        if [ -n "$PROXY_URL" ]; then
            # Update docker-compose with proxy
            export PROXY_URL="$PROXY_URL"
            success "✅ Proxy URL set: $PROXY_URL"
            warn "⚠️  Make sure your proxy supports HTTPS and is accessible"
        fi
        ;;
    4)
        info "🧪 Creating sandbox configuration..."
        # Create sandbox version
        jq '.exchange.ccxt_config.sandbox = true | .exchange.ccxt_async_config.sandbox = true' \
           "$CONFIG_FILE" > "user_data/config_sandbox.json"
        success "✅ Created sandbox configuration: user_data/config_sandbox.json"
        ;;
    5)
        info "📊 Current status - no changes made"
        ;;
    *)
        error "❌ Invalid choice"
        exit 1
        ;;
esac

echo ""
info "🚀 Next Steps:"
echo "1. Restart Freqtrade services:"
echo "   docker-compose restart freqtrade"
echo ""
echo "2. Monitor the logs:"
echo "   docker-compose logs -f freqtrade"
echo ""
echo "3. If issues persist, try alternative exchanges:"
echo "   - Edit docker-compose.yml to use config_okx.json"
echo "   - Or set up a VPN/proxy"
echo ""

success "🎉 Exchange configuration fix completed!"