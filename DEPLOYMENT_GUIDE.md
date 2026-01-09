# 🚀 Railway Deployment Guide

## Prerequisites
- Railway account ([railway.app](https://railway.app))
- GitHub account
- Telegram Bot Token (@BotFather)
- GroqCloud API Key ([groq.com](https://groq.com))
- Deriv API Token & App ID ([developers.deriv.com](https://developers.deriv.com))

## Step 1: Prepare Your Repository

1. **Push to GitHub**:
   ```bash
   git init
   git add .
   git commit -m "Initial commit - Deriv AI Trading Bot"
   git branch -M main
   git remote add origin https://github.com/yourusername/deriv-ai-trading-bot.git
   git push -u origin main
   ```

## Step 2: Deploy to Railway

1. **Create New Project**:
   - Go to [Railway.app](https://railway.app)
   - Click "New Project" → "Deploy from GitHub repo"
   - Connect your GitHub account
   - Select your repository

2. **Configure Environment Variables**:
   ```
   BOT_TOKEN=your_telegram_bot_token
   GROQ_API_KEY=your_groqcloud_api_key_here
   DERIV_API_TOKEN=2jlH6mvdlys29z8
   DERIV_APP_ID=your_deriv_app_id
   WEBHOOK_MODE=true
   PORT=10000
   ```

3. **Deploy Settings**:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python main.py`
   - Port: 10000
   - Webhook URL will be auto-generated

## Step 3: Verify Deployment

1. **Check Logs**: Railway provides real-time logs
2. **Test Bot**: Send `/start` to your Telegram bot
3. **Webhook URL**: Should be `https://your-app.up.railway.app`

## Environment Variables Explained

| Variable | Value | Description |
|----------|--------|-------------|
| `BOT_TOKEN` | From @BotFather | Telegram bot authentication |
| `GROQ_API_KEY` | From GroqCloud | AI analysis features |
| `DERIV_API_TOKEN` | From Deriv | Live market data |
| `DERIV_APP_ID` | From Deriv Developers | API application ID |
| `WEBHOOK_MODE` | `true` | Enable webhook mode |
| `PORT` | `10000` | Railway port |

## Troubleshooting

### Common Issues

1. **Bot Not Responding**:
   - Check Railway logs for errors
   - Verify all environment variables are set
   - Ensure webhook URL is correct

2. **Deriv API Errors**:
   - Verify DERIV_API_TOKEN and DERIV_APP_ID
   - Check if Deriv API is operational
   - Bot will fall back to mock data if API fails

3. **Railway Build Failures**:
   - Check requirements.txt format
   - Verify Python version (runtime.txt)
   - Review build logs

### Getting Help

- **Railway Docs**: [docs.railway.app](https://docs.railway.app)
- **GitHub Issues**: Report bugs in repository
- **Telegram Support**: Contact for bot-specific issues

## Production vs Development

### Production (Railway)
- **Webhook Mode**: Real-time updates
- **24/7 Uptime**: Railway keeps bot running
- **Auto-scaling**: Handles multiple users
- **HTTPS**: Secure webhook endpoint

### Development (Local)
- **Polling Mode**: Manual updates
- **Testing**: Safe environment for changes
- **Debugging**: Full error visibility
- **No Webhook**: Simpler setup

## Security Notes

- **Never commit** `.env` file to Git
- **Use Railway secrets** for production
- **Rotate API keys** regularly
- **Monitor logs** for suspicious activity

## Performance Optimization

- **Enable caching** for frequently accessed data
- **Use Railway's** built-in monitoring
- **Set up alerts** for downtime
- **Monitor API usage** to avoid limits

---

**🎯 Your bot is now live on Railway!**

Users can interact with your Deriv AI Trading Bot at: `https://web-production-8535f.up.railway.app`
