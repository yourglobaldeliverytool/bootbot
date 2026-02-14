# 📦 APEX SIGNAL™ - Deployment Guide

Complete guide for deploying APEX SIGNAL™ to Railway and running locally.

---

## 🚀 Railway Deployment

### Prerequisites

1. **Railway Account**
   - Sign up at [railway.app](https://railway.app)
   - Get your Railway API key (optional)

2. **Telegram Bot** (for live mode)
   - Create a bot via [@BotFather](https://t.me/botfather)
   - Get your bot token
   - Get your chat ID from [@userinfobot](https://t.me/userinfobot)

### Step-by-Step Deployment

#### 1. Install Railway CLI

```bash
npm install -g @railway/cli
```

#### 2. Prepare Your Project

```bash
# Extract the ZIP
unzip apex-signal-bot.zip
cd apex-signal-bot
```

#### 3. Initialize Railway Project

```bash
railway init
```

This will:
- Create a new Railway project
- Detect the Dockerfile
- Set up deployment configuration

#### 4. Configure Environment Variables

```bash
# Set Telegram credentials (for live mode)
railway variables set TELEGRAM_BOT_TOKEN=your_bot_token
railway variables set TELEGRAM_CHAT_ID=your_chat_id

# Or use test mode (no credentials needed)
# The bot will automatically detect mode
```

#### 5. Deploy

```bash
railway up
```

Railway will:
- Build the Docker image
- Deploy to Railway infrastructure
- Start the bot
- Monitor health

#### 6. Monitor Deployment

```bash
# View logs
railway logs

# Check status
railway status

# Open health endpoint
railway open
```

### Railway Configuration Files

The project includes:

#### `Dockerfile`
```dockerfile
FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y gcc
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY bot/ ./bot/
CMD ["python", "-m", "bot.signal_bot"]
```

#### `railway.toml`
```toml
[build]
builder = "DOCKERFILE"

[deploy]
startCommand = "python -m bot.signal_bot"
restartPolicyType = "ALWAYS"

[[services]]
name = "apex-signal-bot"
healthCheckPath = "/health"
healthCheckProtocol = "HTTP"
healthCheckInterval = 30
healthCheckTimeout = 10
healthCheckRetries = 3
```

### Health Check

The bot exposes a `/health` endpoint:

```json
{
  "status": "healthy",
  "mode": "LIVE_SIGNAL",
  "uptime": 3600,
  "signals_sent": 5
}
```

Railway will automatically restart the bot if health checks fail.

---

## 💻 Local Deployment

### Prerequisites

- Python 3.11 or higher
- pip package manager

### Installation

```bash
# Install dependencies
pip install -r requirements.txt
```

### Configuration

Edit `bot/config/config.yaml`:

```yaml
capital:
  default: 15

symbols:
  - BTCUSDT
  - ETHUSDT
```

### Running

#### Test Mode (No Telegram)

```bash
python -m bot.signal_bot
```

The bot will:
- Use public market APIs
- Log signals to console
- Not send Telegram messages

#### Live Mode (With Telegram)

```bash
# Set environment variables
export TELEGRAM_BOT_TOKEN=your_token
export TELEGRAM_CHAT_ID=your_chat_id

# Run the bot
python -m bot.signal_bot
```

The bot will:
- Send real Telegram messages
- Use live market data
- Execute all strategies

---

## 🧪 Testing Before Deployment

### Run Test Suite

```bash
python test_production_bot.py
```

Expected output:
```
======================================================================
📊 TEST SUMMARY
======================================================================
Total Tests: 16
✅ Passed: 16
❌ Failed: 0
Success Rate: 100.0%
======================================================================
```

### Test Locally

```bash
# Start in test mode
python -m bot.signal_bot

# Wait for signals (watch console)
# Check logs in logs/trading_bot.log
```

---

## 🔧 Troubleshooting

### Railway Issues

#### Bot Not Starting

```bash
# Check logs
railway logs

# Common issues:
# 1. Build errors - check Dockerfile
# 2. Missing dependencies - check requirements.txt
# 3. Config errors - check config.yaml
```

#### Health Check Failing

```bash
# Check bot is running
railway logs

# Verify health endpoint is accessible
curl https://your-app.railway.app/health
```

#### No Telegram Messages

```bash
# Check environment variables
railway variables

# Verify bot token and chat ID
# Check Telegram bot can send messages
```

### Local Issues

#### Import Errors

```bash
# Ensure PYTHONPATH is set
export PYTHONPATH=/path/to/project

# Or run from project root
python -m bot.signal_bot
```

#### No Market Data

```bash
# Check network connectivity
curl https://api.binance.com/api/v3/ping

# Check logs for errors
tail -f logs/trading_bot.log
```

#### Signals Not Generating

```bash
# Check strategies are enabled
# In bot/config/config.yaml:
strategies:
  trend_following:
    enabled: true

# Check scan interval
scan_interval: 60  # seconds
```

---

## 📊 Monitoring

### Railway Dashboard

Access the Railway dashboard at:
- App logs
- Metrics
- Environment variables
- Health status

### Local Monitoring

```bash
# Follow logs
tail -f logs/trading_bot.log

# Check bot status
# Send /status command to Telegram bot
```

### Performance Metrics

Monitor:
- Signal frequency
- Accuracy of signals
- Market data latency
- Error rates

---

## 🔒 Security

### Environment Variables

Never commit:
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- API keys or secrets

Always use:
- Railway environment variables
- Local environment variables
- `.env` files (in .gitignore)

### API Rate Limits

The bot implements:
- Rate limiting (Binance: 5 req/sec)
- Retry logic with exponential backoff
- Graceful degradation

---

## 📈 Scaling

### Railway Scaling

```bash
# Increase resources
railway variables set RAILWAY_MEMORY_MB=512

# Scale to multiple instances (experimental)
railway scale 3
```

### Performance Tuning

In `bot/config/config.yaml`:

```yaml
scan_interval: 30  # Faster scans (more CPU)
```

---

## 🔄 Updates

### Updating the Bot

```bash
# Pull latest code
git pull

# Rebuild on Railway
railway up

# Local restart
# Kill the bot and restart
python -m bot.signal_bot
```

### Rollback

```bash
# Railway
railway rollback

# Local
# Restore from backup or revert commit
```

---

## 📞 Support

### Getting Help

1. Check logs: `logs/trading_bot.log`
2. Review test results: `FINAL_TEST_REPORT.md`
3. Verify configuration: `bot/config/config.yaml`

### Common Issues

| Issue | Solution |
|-------|----------|
| Bot crashes on start | Check configuration file syntax |
| No signals | Enable strategies in config.yaml |
| No Telegram messages | Set environment variables |
| Health check fails | Check bot is running and port is accessible |

---

## 🎯 Best Practices

### Deployment

1. **Test first**: Run test suite before deployment
2. **Start small**: Deploy with test mode first
3. **Monitor closely**: Check logs after deployment
4. **Use git**: Track changes and enable rollback

### Operation

1. **Regular backups**: Backup configuration and logs
2. **Monitor performance**: Watch signal quality and frequency
3. **Update regularly**: Keep dependencies updated
4. **Review signals**: Analyze signal performance

---

**🚀 APEX SIGNAL™ - Production Verified & Deployment Ready**

*Last Updated: 2026-02-10*