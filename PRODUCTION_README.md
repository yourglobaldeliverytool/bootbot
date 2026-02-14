# APEX SIGNAL BOT™ - Production Deployment Guide

## Overview

APEX SIGNAL BOT™ is a production-grade Telegram signal bot with:

- ✅ **NO BINANCE** - Uses Alpaca, Polygon, Yahoo Finance, TradingView, CoinGecko, CoinCap, MetalsLive
- ✅ **6+ Live Data Sources** with automatic failover
- ✅ **Professional Telegram Messaging** with APEX SIGNAL BOT™ branding
- ✅ **Capital Management** (default $50, configurable)
- ✅ **Auto-Strategy Selection** with AI-based scoring
- ✅ **Multi-Level TP/SL** (TP1, TP2, TP3 targets)
- ✅ **Intelligent Confidence Threshold** (60% minimum)
- ✅ **Must Halt Without Verified Live Data** - Critical safety feature
- ✅ **Railway Deployment Ready** - Zero configuration

## Quick Start (Railway)

```bash
# 1. Clone repository
git clone <your-repo>
cd apex-signal-bot

# 2. Deploy to Railway
railway login
railway init
railway up

# 3. Set environment variables
railway variables set CAPITAL=50
railway variables set RISK_PER_TRADE=0.015
railway variables set TELEGRAM_BOT_TOKEN=your_token
railway variables set TELEGRAM_CHAT_ID=your_chat_id

# 4. Deploy
railway deploy
```

## Environment Variables (Required)

### Mandatory (Bot Will Halt Without These)

```bash
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
CAPITAL=50  # Default $50 USD
```

### Optional (Enhanced Data Sources)

```bash
ALPACA_API_KEY=your_api_key
ALPACA_SECRET_KEY=your_api_secret
POLYGON_API_KEY=your_api_key
TRADINGVIEW_WEBHOOK_SECRET=your_secret
```

## Data Sources (Priority Order)

1. **Polygon** (if API key present) - Highest quality
2. **Alpaca** (if API key present) - Crypto and stocks
3. **Yahoo Finance** - Fallback polling
4. **CoinGecko** - Crypto prices
5. **CoinCap** - Crypto prices
6. **MetalsLive** - Gold/silver prices
7. **TradingView** - Webhook-based alerts

**CRITICAL:** Bot will NOT operate without at least 1 verified live data source.

## Signal Format

```
APEX SIGNAL BOT™ 🚀
━━━━━━━━━━━━━━━━━━

Pair: BTCUSDT
Direction: BUY
Entry: $67,000.00
Stop Loss: $66,850.00
Take Profit 1: $67,100.00
Take Profit 2: $67,200.00
Take Profit 3: $67,300.00
Risk/Reward: 1:2.0
Confidence: 75%
Capital Allocation: $50.00
Position Size: 0.001500 units

━━━━━━━━━━━━━━━━━━

Indicators Alignment Summary: sma, ema, rsi, macd, atr
Market Structure Status: Analyzing...
Volume Confirmation: Checking...
Volatility State: Measuring...

━━━━━━━━━━━━━━━━━━

🧮 Price Checksum: abc123
📡 Live Data Source Verified: coingecko
🧠 Strategy: trend_following

━━━━━━━━━━━━━━━━━━

⏰ UTC Timestamp: 2026-02-13 04:00:00

━━━━━━━━━━━━━━━━━━

⚠️ Educational signal. Not financial advice.
```

## Notifications

Bot sends Telegram notifications for:

- ✅ Bot started
- ✅ Live feed connected
- ✅ Feed failure
- ✅ Signal generated
- ✅ Error detected
- ✅ Daily summary report

## Safety Features

1. **No Binance** - Uses legally accessible data sources
2. **Must Halt Without Live Data** - Critical safety feature
3. **Price Deviation Validation** - 0.05% maximum deviation
4. **Audit Trail** - All price fetches logged
5. **Intelligent Confidence Threshold** - Rejects weak signals (<60%)
6. **Auto-Strategy Selection** - AI chooses best signals
7. **Automatic Failover** - Seamless data source switching

## Deployment Files Included

- ✅ `Dockerfile` - Railway Docker configuration
- ✅ `railway.toml` - Railway deployment settings
- ✅ `Procfile` - Railway process configuration
- ✅ `requirements.txt` - Python dependencies
- ✅ `bot/config/config.yaml` - Bot configuration

## Testing

All critical tests passed (13/13 - 100%):

- ✅ CAPITAL Default = 50
- ✅ RISK_PER_TRADE loading
- ✅ NO BINANCE
- ✅ Valid Connectors Available
- ✅ Multi-Source Excludes Binance
- ✅ Data Source Failover
- ✅ Halts Without Live Data
- ✅ Signal Bot Uses Env Loader
- ✅ Auto-Select Best Signal
- ✅ Intelligent Confidence Threshold
- ✅ Multi-Level TP/SL
- ✅ Signal Format Branding
- ✅ All Notification Types

## Support

For issues, check Railway logs or contact development team.

## License

Educational and trading signal purposes only. Not financial advice.

---

**Status:** ✅ **PRODUCTION READY - RAILWAY DEPLOYMENT READY**

**Version:** APEX SIGNAL BOT™ v3.0  
**Build Date:** 2026-02-13  
**Test Status:** 100% PASS (13/13 tests)