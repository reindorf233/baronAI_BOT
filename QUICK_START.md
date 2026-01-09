# 🚀 Quick Start Guide

## 1. Get Your Bot Token
1. Open Telegram and search for [@BotFather](https://t.me/BotFather)
2. Send `/newbot` and follow instructions
3. Copy your bot token (starts with `BOT_TOKEN`)

## 2. Get Your Deriv API Credentials
1. Go to [developers.deriv.com](https://developers.deriv.com)
2. Create account and get API token: `2jlH6mvdlys29z8`
3. Get your App ID from the dashboard

## 3. Set Environment Variables
Create `.env` file with:
```env
BOT_TOKEN=your_telegram_bot_token
GROQ_API_KEY=your_groqcloud_api_key_here
DERIV_API_TOKEN=2jlH6mvdlys29z8
DERIV_APP_ID=your_deriv_app_id
WEBHOOK_MODE=true
PORT=10000
```

## 4. Run Locally
```bash
pip install -r requirements.txt
python main.py
```

## 5. Deploy to Railway
1. Push to GitHub
2. Go to [railway.app](https://railway.app)
3. Connect repository and set environment variables
4. Deploy automatically

## 🎯 Test Commands
- `/start` - Main menu
- `/analyze R_50` - Get signal analysis
- `/summary` - Market overview
- `/chart BOOM1000` - Generate chart

**Your bot is now live!** 🚀
