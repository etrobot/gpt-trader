# 🚀 Crypto Trading Analysis Dashboard

An intelligent crypto trading analysis platform with automated factor analysis, news evaluation, and integrated FreqTrade support.

## ✨ Features

- 📊 **Comprehensive Market Analysis** - Multi-factor technical analysis
- 🤖 **AI-Powered Insights** - LLM-driven news and market evaluation  
- 💹 **Integrated Trading** - FreqTrade + FreqUI for automated trading
- 🛡️ **Security First** - Auto-generated credentials and dry-run safety
- 📱 **Modern Interface** - Responsive React dashboard with real-time updates
- 🐳 **Docker Ready** - One-command deployment

## 🎯 Quick Start

**Choose your preferred setup workflow:**

### Option 1: Set API Key First (Recommended)
```bash
# 1. Configure OpenAI API key
./update_openai_credentials.sh

# 2. Deploy everything
./deploy.sh

# 3. Access dashboard: http://localhost:14250
```

### Option 2: Deploy and Configure Later
```bash
# 1. Deploy with demo settings (safe!)
./deploy.sh

# 2. Configure when ready
./update_openai_credentials.sh
```

## ⚙️ Environment Configuration

### Proxy Settings

The application supports proxy configuration for users in restricted countries. You can configure proxy settings in the `.env` file:

```bash
# Copy the example environment file
cp .env.example .env

# Edit proxy settings
# To enable proxy:
HTTP_PROXY=http://127.0.0.1:7890
HTTPS_PROXY=http://127.0.0.1:7890
NO_PROXY=freqtrade-bot,localhost,127.0.0.1

# To disable proxy (leave empty):
HTTP_PROXY=
HTTPS_PROXY=
NO_PROXY=
```

### Other Environment Variables

- `OPENAI_API_KEY`: Your OpenAI API key for AI-powered analysis
- `OPENAI_BASE_URL`: OpenAI API base URL (default: https://api.openai.com/v1)
- `FREQTRADE_API_USERNAME`: Freqtrade API username (auto-configured)
- `FREQTRADE_API_PASSWORD`: Freqtrade API password (auto-configured)

📖 **See `.env.example` for all available configuration options**

## 🏗️ Project Structure

### Prerequisites

- Node.js (with pnpm installed)
- Python (with UV installed)

### Installation

1. **Install all dependencies (frontend and backend):**

   ```bash
   pnpm run install:all
   ```

### Running the Development Servers

To run both the frontend and backend development servers concurrently:

```bash
pnpm run dev
```

This will start:
- The backend server (FastAPI/Uvicorn) with auto-reloading.
- The frontend development server (Vite).

### Building the Project

To build both the frontend and backend:

```bash
pnpm run build
```

This will:
- Build the frontend for production.
- (Note: Backend build step is currently a placeholder and not fully implemented.)
