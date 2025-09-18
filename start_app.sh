#!/bin/bash

# Start Crypto Trading Strategy App
echo "🚀 Starting Crypto Trading Strategy App..."

# Check if App directory exists
if [ ! -d "App" ]; then
    echo "❌ App directory not found!"
    exit 1
fi

# Navigate to App and start the server
cd App

echo "📦 Installing dependencies..."
uv sync --quiet

echo "🔥 Starting App server on http://localhost:14250"
echo "📖 API Documentation will be available at http://localhost:14250/docs"
echo ""

uv run uvicorn main:app --host 0.0.0.0 --port 14250 --reload