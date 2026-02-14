# 🚀 APEX SIGNAL™ - Production-Grade AI Trading Bot

**A fully verified, production-ready algorithmic trading signal platform with institutional-grade strategies, multi-source price verification, and professional Telegram integration.**

---

## 🎉 Version 3.0.0 - Production Hardened

**This release includes comprehensive production hardening with zero feature removal:**

✅ **Safe Mode**: Application boots without API keys (features auto-disable gracefully)  
✅ **Centralized Config**: Single `config.py` with validation and safe mode flags  
✅ **Production Entry Point**: New `main.py` with graceful startup/shutdown  
✅ **Docker Optimization**: No compiler toolchains, < 300MB image  
✅ **Health Checks**: Non-blocking `/healthz` endpoint always available  
✅ **Import Verification**: `test_env.py` validates all dependencies  

---

## ✨ Key Features

### 🧩 Multi-Source Price Verification
- **7 Data Sources**: Alpaca, Polygon, Yahoo Finance, CoinGecko, CoinCap, MetalsLive, TradingView
- **0.05% Deviation Check**: Ensures price accuracy
- **SHA-256 Checksums**: Data integrity verification
- **Automatic Fallback**: Seamless switch between sources
- **Circuit Breaker**: Isolates failing data sources

### 📊 18 Institutional-Grade Strategies
- **Trend & MA**: EMA (multi), SMA (multi), VWAP, multi-timeframe EMA alignment, dynamic MA crossover
- **Momentum**: RSI, MACD, Stochastic, ADX, divergence detection
- **Volatility**: Bollinger Bands, ATR, Supertrend, volatility breakout, range expansion
- **Liquidity/Smart Money**: Order blocks, liquidity sweeps, structure break, trend structure mapping, supply/demand zones
- **Volume**: Volume spikes, relative volume, volume confirmation
- **Advanced**: Confluence scoring, confidence (0–100%), multi-timeframe confirmation, session filters

### 📈 22 Professional Indicators
All major technical indicators implemented and tested
- EMA, SMA, VWAP, RSI, MACD, ATR, Bollinger Bands
- Stochastic, ADX, CCI, Williams %R, ROC
- Ichimoku Cloud, Heikin Ashi, SuperTrend, Parabolic SAR
- Keltner Channels, Donchian Channels, Pivot Points
- Z-Score, Volume Profile, OBV

### 📱 Telegram Integration
- **Professional Signal Formatting**: APEX SIGNAL™ branded messages
- **Real-Time Alerts**: Instant notification of trading opportunities
- **Command Interface**: `/status`, `/health`, `/lastsignal`
- **Educational Disclaimers**: Clear risk warnings
- **Multi-Level TP/SL**: TP1, TP2, TP3 with calculated risk-reward

### 🛡️ Risk Management
- **Default Capital**: $50 USD (configurable)
- **Risk Per Trade**: 1.5% (configurable)
- **ATR-Based TP/SL**: Dynamic take-profit and stop-loss
- **Position Sizing**: Automatic calculation based on risk
- **Daily Loss Cap**: 5% maximum daily loss
- **Max Trades Per Session**: Configurable limit

### 🚢 Production Features
- **Automatic Mode Detection**: VERIFIED_TEST or LIVE_SIGNAL
- **Health Monitoring**: `/healthz` endpoint for Railway
- **Graceful Shutdown**: Clean shutdown procedures
- **Restart-Safe**: Railway deployment ready
- **Safe Mode Without Secrets**: Boots without API keys
- **Structured Logging**: Branded `[APEX_SIGNAL][subsystem]` format

---

## 🏗️ System Requirements

- **Python**: 3.11+
- **Docker**: For containerized deployment (recommended)
- **Railway Account**: For cloud deployment (optional)
- **Telegram Bot Token**: For live mode (optional)

---

## 📦 Quick Start

### 1. Clone and Setup

```bash
# Clone the repository
git clone <repository-url>
cd apex-signal-bot

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install --no-cache-dir -r requirements.txt
```

### 2. Configuration

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your settings
nano .env  # or use your preferred editor
```

**Minimum Configuration for VERIFIED_TEST mode:**
- No API keys required (runs with mock data)

**For LIVE_SIGNAL mode (requires):**
```bash
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

**For Trading (optional):**
```bash
ALPACA_API_KEY=your_alpaca_key
ALPACA_SECRET_KEY=your_alpaca_secret
POLYGON_API_KEY=your_polygon_key
```

### 3. Run Import Verification

```bash
# Verify all dependencies import correctly
python test_env.py

# Expected output: "✅ ALL CRITICAL IMPORTS PASSED"
```

### 4. Start the Bot

```bash
# Run with production entry point
python main.py

# Or with module syntax
python -m main
```

**Startup Output:**
```
============================================================
🚀 APEX SIGNAL™ v3.0.0
📦 Build Date: 2026-02-14 00:00:00 UTC
🔧 Mode: VERIFIED_TEST
💰 Capital: $50.00
⚠️  Risk Per Trade: 1.50%
🔌 Trading: ❌ DISABLED
📱 Telegram: ❌ DISABLED
🌐 Port: 8000
============================================================
```

---

## 🐳 Docker Deployment

### Build Docker Image

```bash
docker build -t apex-signal-bot:latest .
```

**Build Characteristics:**
- Base: `python:3.11-slim`
- Size: < 300MB
- No compiler toolchains (build-essential not installed)
- No debconf warnings

### Run Docker Container

```bash
# Without API keys (VERIFIED_TEST mode)
docker run -d \
  -p 8000:8000 \
  -e PORT=8000 \
  --name apex-signal-bot \
  apex-signal-bot:latest

# With API keys (LIVE_SIGNAL mode)
docker run -d \
  -p 8000:8000 \
  -e PORT=8000 \
  -e TELEGRAM_BOT_TOKEN=your_token \
  -e TELEGRAM_CHAT_ID=your_chat_id \
  -e CAPITAL=50 \
  --name apex-signal-bot \
  apex-signal-bot:latest
```

### Check Health

```bash
# Check container health
curl http://localhost:8000/healthz

# Expected response:
# {
#   "status": "healthy",
#   "timestamp": "2026-02-14T00:00:00.000000",
#   "service": "apex-signal-bot",
#   "bot_running": true,
#   "bot_mode": "VERIFIED_TEST"
# }
```

---

## 🚂 Railway Deployment

### Quick Deploy

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Initialize project
railway init

# Deploy
railway up
```

### Configure Environment Variables

In Railway dashboard, set these variables:

**Required for Live Mode:**
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

**Optional:**
- `CAPITAL` (default: 50)
- `RISK_PERCENT` (default: 1.5)
- `LOG_LEVEL` (default: INFO)

**For Trading:**
- `ALPACA_API_KEY`
- `ALPACA_SECRET_KEY`
- `POLYGON_API_KEY`

### Monitor Deployment

```bash
# View logs
railway logs

# Check health status
curl https://your-app-url.railway.app/healthz

# View bot status
curl https://your-app-url.railway.app/status
```

---

## 🧪 Testing

### Run Import Verification

```bash
python test_env.py
```

**Expected Output:**
```
============================================================
🧪 APEX SIGNAL™ - Import Verification Test
============================================================

📦 Testing Critical Dependencies...
✅ PASS: pandas
✅ PASS: numpy
...
Critical Dependencies: 8/8 passed

🧩 Testing Critical Bot Modules...
✅ PASS: config
✅ PASS: bot.core.interfaces
...
Critical Modules: 13/13 passed

============================================================
✅ ALL CRITICAL IMPORTS PASSED
============================================================
```

### Run Production Tests

```bash
# Run comprehensive test suite
python tests/test_system_stabilized.py

# Expected: All tests pass (19/19)
```

---

## 📡 API Endpoints

### Health Check
```bash
GET /healthz
```
Returns service health status (always HTTP 200 if running)

### Status
```bash
GET /status
```
Returns bot status, mode, capital, and configuration

### Signals
```bash
GET /signals?limit=100&symbol=BTCUSDT
GET /signals/{id}
GET /lastsignal
```

### Metrics
```bash
GET /metrics
```
Returns Prometheus-style metrics

### API Docs
```bash
GET /docs
```
Interactive API documentation (Swagger UI)

---

## 🔧 Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | No* | - | Telegram bot token |
| `TELEGRAM_CHAT_ID` | No* | - | Telegram chat ID |
| `ALPACA_API_KEY` | No | - | Alpaca API key |
| `ALPACA_SECRET_KEY` | No | - | Alpaca secret key |
| `POLYGON_API_KEY` | No | - | Polygon API key |
| `CAPITAL` | No | 50 | Trading capital (USD) |
| `RISK_PERCENT` | No | 1.5 | Risk per trade (%) |
| `LOG_LEVEL` | No | INFO | Logging level |
| `PORT` | No | 8000 | Web server port |

*Required only for LIVE_SIGNAL mode

### Safe Mode Behavior

The bot automatically detects available credentials and adjusts:

**No Credentials (VERIFIED_TEST mode):**
- ✅ Trading disabled
- ✅ Telegram disabled
- ✅ Uses mock data for testing
- ✅ Health endpoint functional

**Telegram Credentials Only:**
- ✅ Trading disabled
- ✅ Telegram enabled
- ✅ Uses free public APIs

**All Credentials (LIVE_SIGNAL mode):**
- ✅ Trading enabled
- ✅ Telegram enabled
- ✅ Full functionality

---

## 📁 Project Structure

```
apex-signal-bot/
├── config.py                 # Centralized configuration with safe mode
├── main.py                   # Production entry point
├── test_env.py              # Import verification test
├── .env.example             # Environment variables template
├── Dockerfile               # Optimized Docker configuration
├── requirements.txt         # Pinned dependencies
├── CHANGELOG.md            # Version history
├── system_metadata.json    # Build and version metadata
├── bot/
│   ├── core/
│   │   ├── interfaces.py   # Abstract base classes
│   │   ├── registry.py     # Component registry
│   │   ├── engine.py       # Trading engine
│   │   ├── circuit_breaker.py
│   │   ├── rate_limiter.py
│   │   └── price_manager.py
│   ├── connectors/         # 7 data source connectors
│   ├── strategies/         # 18 trading strategies
│   ├── indicators/         # 22 technical indicators
│   ├── notifiers/          # Telegram/email notifications
│   ├── api/               # REST API (FastAPI)
│   └── utils/             # Utilities (logger, env_loader)
└── tests/                 # Test suites
```

---

## 🔒 Security & Safety

- ✅ No secrets in code
- ✅ Environment variable loading
- ✅ Safe mode without credentials
- ✅ Config validation before startup
- ✅ Graceful degradation
- ✅ SHA-256 checksums for data integrity
- ✅ Circuit breaker pattern for fault isolation
- ✅ Rate limiting to prevent API abuse

---

## 📊 System Monitoring

### Health Check
Always available at `/healthz` - returns HTTP 200 if service is running

### Logging
Structured logging with branded format:
```
[APEX_SIGNAL][config] INFO: ✅ Configuration validation passed
[APEX_SIGNAL][trading] INFO: Trading disabled - missing API keys
[APEX_SIGNAL][telegram] WARN: Telegram disabled - missing credentials
```

### Metrics
Available at `/metrics` endpoint:
- Signal counts
- Connector health
- Performance metrics
- Error rates

---

## 🤝 Support

- **Documentation**: See CHANGELOG.md for version history
- **Issues**: Report bugs via repository issues
- **Questions**: Check existing documentation first

---

## 📜 License

This project is proprietary software. All rights reserved.

---

## ⚠️ Disclaimer

**This software is for educational purposes only.**

- Trading involves substantial risk of loss
- Past performance is not indicative of future results
- This is not financial advice
- Always do your own research
- Never trade with money you cannot afford to lose

**The developers are not responsible for any financial losses incurred.**

---

## 🎯 Version 3.0.0 Highlights

### Production Hardening
- ✅ Zero startup crashes without API keys
- ✅ Trading and Telegram auto-disable gracefully
- ✅ Non-blocking health endpoint
- ✅ Docker image optimized (< 300MB)
- ✅ No compiler toolchains required
- ✅ Import verification suite
- ✅ Centralized configuration management

### Safety Features
- ✅ Circuit breaker pattern
- ✅ Rate limiter
- ✅ Price deviation checks
- ✅ Graceful shutdown
- ✅ Config validation
- ✅ Safe mode flags

### Observability
- ✅ Branded logging
- ✅ System metadata tracking
- ✅ Health endpoints
- ✅ Metrics collection
- ✅ Startup banner

**See CHANGELOG.md for complete version history.**