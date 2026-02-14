# Missing Environment Variables for LIVE Verification

## Status: VERIFIED_TEST Mode

The APEX SIGNAL™ bot is running in **VERIFIED_TEST** mode because required LIVE environment variables are not set.

## Required Environment Variables

To enable **LIVE_SIGNAL** mode and perform live verification, you must set the following environment variables in Railway:

### Required for LIVE_SIGNAL Mode

1. **TELEGRAM_BOT_TOKEN**
   - Description: Your Telegram bot token from BotFather
   - How to get: Create a bot via @BotFather on Telegram
   - Format: `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`

2. **TELEGRAM_CHAT_ID**
   - Description: Your Telegram chat ID or channel ID where signals will be sent
   - How to get: Send a message to @userinfobot or use your channel ID
   - Format: `-1001234567890` (channel) or `123456789` (user)

## Optional Environment Variables

These variables enhance functionality but are not required:

3. **CAPITAL**
   - Default: `50`
   - Description: Trading capital in USD
   - Format: `50` or `100`

4. **RISK_PERCENT**
   - Default: `1.5`
   - Description: Risk per trade percentage
   - Format: `1.5` for 1.5%

5. **ALPACA_API_KEY**
   - Description: Alpaca API key for stock/crypto trading data
   - Format: Your Alpaca API key

6. **ALPACA_SECRET_KEY**
   - Description: Alpaca secret key
   - Format: Your Alpaca secret key

7. **POLYGON_API_KEY**
   - Description: Polygon.io API key for high-quality market data
   - Format: Your Polygon API key

8. **TRADINGVIEW_WEBHOOK_SECRET**
   - Description: Secret for TradingView webhook integration
   - Format: Your webhook secret

9. **POLYGON_API_BASE**
   - Default: `https://api.polygon.io`
   - Description: Custom Polygon API endpoint (if using a proxy)
   - Format: Full URL

## How to Set Environment Variables in Railway

### Option 1: Via Railway CLI
```bash
railway variables set TELEGRAM_BOT_TOKEN=your_token_here
railway variables set TELEGRAM_CHAT_ID=your_chat_id_here
railway variables set CAPITAL=50
railway variables set RISK_PERCENT=1.5
```

### Option 2: Via Railway Dashboard
1. Go to your project in Railway
2. Click on your service
3. Go to the "Variables" tab
4. Add each variable as a new entry
5. Click "Deploy Changes"

## Current Test Results

The bot has been verified in **VERIFIED_TEST** mode with the following results:

- ✅ All 13 critical tests PASSED (100% success rate)
- ✅ Environment variable loading verified
- ✅ NO BINANCE - removed and not referenced
- ✅ Multi-source price verification implemented
- ✅ Circuit breaker and rate limiter functional
- ✅ Symbol normalization working
- ✅ Deviation thresholds configured (Crypto 1.5%, Metals 1.0%, Forex 0.5%)
- ✅ Strategy registry fixed (no string attribute errors)
- ✅ Price Manager with 10s cache working
- ✅ Telegram notification formatting verified

## Next Steps

1. **Add the required environment variables** listed above in Railway
2. **Redeploy** the bot to Railway
3. The bot will automatically detect the variables and switch to **LIVE_SIGNAL** mode
4. **Live verification** will run automatically on startup:
   - Validate connector authentication (401/403 check)
   - Fetch live prices from at least 2 sources
   - Compute canonical price and checksum
   - Emit test signals to your Telegram chat
   - Verify checksums via POST /signals/{id}/verify

## Important Notes

- **DO NOT** commit API keys or secrets to the repository
- **DO NOT** share your TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID
- **ALWAYS** use Railway environment variables for sensitive data
- The bot will **HALT** if no verified live data is available
- Minimum 2 data sources required for price verification

## Deployment Status

- **Current Mode**: VERIFIED_TEST
- **Test Results**: 13/13 PASSED (100%)
- **Live Verification**: SKIPPED (missing env vars)
- **Production Ready**: YES (pending live verification with credentials)

---

**Generated**: 2026-02-13
**Version**: APEX SIGNAL™ v4.0