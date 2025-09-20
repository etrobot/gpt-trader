#!/bin/bash

# Script to update exchange API credentials in Freqtrade config
set -e

info() { echo -e "\033[0;34m$1\033[0m"; }
success() { echo -e "\033[0;32m$1\033[0m"; }
warn() { echo -e "\033[1;33m$1\033[0m"; }
error() { echo -e "\033[0;31m$1\033[0m"; }

CONFIG_FILE="user_data/config_classic_strategy.json"

if [ ! -f "$CONFIG_FILE" ]; then
    error "❌ Config file not found: $CONFIG_FILE"
    error "Please run ./deploy.sh first to create the configuration"
    exit 1
fi

echo "🔐 Update Exchange API Credentials"
echo "=================================="
echo ""

# Get current exchange name
CURRENT_EXCHANGE=$(jq -r '.exchange.name' "$CONFIG_FILE" 2>/dev/null || echo "okx")
echo "Current exchange: $CURRENT_EXCHANGE"
echo ""

read -p "Enter your API Key: " API_KEY
read -s -p "Enter your API Secret: " API_SECRET
echo ""
read -p "Use sandbox mode? (y/N): " USE_SANDBOX

# Convert sandbox input to boolean
if [[ "$USE_SANDBOX" =~ ^[Yy]$ ]]; then
    SANDBOX="true"
    warn "⚠️  Sandbox mode enabled - this is for testing only"
else
    SANDBOX="false"
    info "Production mode selected"
fi

if [ -z "$API_KEY" ] || [ -z "$API_SECRET" ]; then
    error "❌ API Key and Secret are required"
    exit 1
fi

# Backup existing config
BACKUP_FILE="$CONFIG_FILE.backup.$(date +%Y%m%d_%H%M%S)"
cp "$CONFIG_FILE" "$BACKUP_FILE"
info "📋 Backed up config to: $BACKUP_FILE"

# Update config using jq
if command -v jq >/dev/null 2>&1; then
    jq --arg api_key "$API_KEY" \
       --arg api_secret "$API_SECRET" \
       --argjson sandbox "$SANDBOX" \
       '.exchange.key = $api_key | 
        .exchange.secret = $api_secret | 
        .exchange.ccxt_config.sandbox = $sandbox |
        .exchange.ccxt_async_config.sandbox = $sandbox' \
       "$CONFIG_FILE" > temp_config.json && mv temp_config.json "$CONFIG_FILE"
    
    success "✅ Successfully updated exchange credentials"
    
    if [ "$SANDBOX" = "true" ]; then
        warn "⚠️  Remember to disable sandbox mode for live trading"
    else
        warn "⚠️  You are now configured for LIVE TRADING"
        warn "⚠️  Make sure to change 'dry_run' to false when ready"
    fi
    
    echo ""
    info "🔄 Restart services to apply changes:"
    echo "docker-compose restart freqtrade"
    
else
    error "❌ jq is required but not installed"
    error "Please install jq or manually update the config file"
    exit 1
fi