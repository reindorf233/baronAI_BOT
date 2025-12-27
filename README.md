# 🤖 Baron AI Trading Bot

Advanced ICT/SMC Trading Bot with AI-powered signal validation, synthetic indices, and 24/7 market monitoring.

## 🌟 Features

### Core Trading Features
- **ICT/SMC Analysis**: Fair Value Gaps (FVG), Market Structure Shifts (MSS), EMA200 bias
- **Multi-Asset Support**: Forex (EURUSD, GBPUSD, etc.), Gold, Bitcoin, Cryptocurrencies
- **Synthetic Indices**: Volatility, Boom/Crash, Step, Jump indices
- **AI-Powered Validation**: Real-time trade approval using Groq AI (Llama 3.1)
- **Risk Management**: Position sizing, stop-loss calculation, balance simulation

### Advanced Features
- **10/10 Confidence Signals**: Filtered for AI-approved perfect setups
- **Martingale Recovery**: Optional recovery system for losses
- **Kill Zone Timing**: London (2-5 AM EST) and NY (8:30-11 AM EST) sessions
- **Daily Market Summary**: Comprehensive market overview
- **Persistent Settings**: SQLite database for user preferences

### Deployment Options
- **Local Development**: Polling mode for testing
- **Production**: Webhook mode for 24/7 uptime
- **Cloud Ready**: Render, Heroku, Railway, VPS

## 🚀 Quick Start

### Local Development
```bash
# Clone repository
git clone https://github.com/yourusername/baronAI_BOT.git
cd baronAI_BOT

# Install dependencies
pip install -r requirements.txt

# Set environment variables
cp .env.example .env
# Edit .env with your BOT_TOKEN and GROQ_API_KEY

# Run bot
python main.py
```

### Production Deployment (Render)

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy)

See [RENDER_DEPLOYMENT.md](RENDER_DEPLOYMENT.md) for detailed instructions.

## 📱 Usage

### Commands
- `/start` - Main menu and bot introduction
- `/analyze [symbol]` - Get ICT/SMC analysis for any symbol
- `/alerts` - View recent strong signals
- `/monitor` - Toggle automatic signal monitoring
- `/summary` - Daily market summary

### Menu Options
- **🥇 Gold Signals**: XAUUSD/GOLD analysis
- **📈 Forex Pairs**: EURUSD, GBPUSD, USDJPY, etc.
- **₿ Bitcoin**: BTC-USD analysis
- **📊 Synthetics**: Volatility, Boom/Crash indices
- **⭐ 10/10 Signals**: AI-approved perfect setups
- **⚙️ Settings**: Risk management and preferences

## 🔧 Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `BOT_TOKEN` | ✅ | Telegram bot token from @BotFather |
| `GROQ_API_KEY` | ✅ | Groq API key for AI features |
| `WEBHOOK_MODE` | ❌ | `true` for production, `false` for local |
| `WEBHOOK_URL` | ❌ | Auto-set by Render/Heroku |
| `PORT` | ❌ | Auto-set by cloud provider |
| `USER_TIMEZONE` | ❌ | Your timezone (default: Africa/Accra) |

### Advanced Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `MIN_SIGNAL_CONFIDENCE` | 8 | Minimum confidence for alerts |
| `AI_APPROVAL_MIN_SCORE` | 7 | Minimum AI score for approval |
| `LOG_LEVEL` | INFO | Logging verbosity |

## 🤖 AI Features

### AI Approval System
- **Real-time Analysis**: Every signal validated by AI
- **Conservative Approach**: Only approves high-probability setups
- **Detailed Reasoning**: AI explains why trades are approved/rejected
- **Confluence Detection**: Evaluates multiple technical factors

### Signal Quality
- **FVG Detection**: Identifies Fair Value Gaps with precision
- **Structure Analysis**: Bullish/bearish market structure shifts
- **Kill Zone Timing**: Optimal trading windows
- **Risk Assessment**: Position size and stop-loss recommendations

## 📊 Supported Markets

### Forex
- EURUSD, GBPUSD, USDJPY, USDCHF, USDCAD, AUDUSD, NZDUSD
- USDTRY, USDMXN, USDZAR, USDAED, USDARS, USDAMD, USDAZN
- USDBDT, USDBGN, USDBHD, USDBND

### Commodities
- Gold (GC=F, XAUUSD), Silver, Platinum

### Cryptocurrencies
- Bitcoin (BTC-USD), Ethereum, major altcoins

### Synthetic Indices
- Volatility 75/100 (V75, V100)
- Boom/Crash 500/1000
- Step Index
- Jump Index

## 🏗️ Architecture

```
baronAI_BOT/
├── main.py              # Entry point & webhook setup
├── handlers.py          # Telegram command handlers
├── signals.py           # Trading signal generation
├── menus.py             # UI keyboards & buttons
├── utils.py             # Helper functions & database
├── requirements.txt     # Python dependencies
├── Procfile             # Heroku/Render deployment
├── render.yaml          # Render deployment config
└── data/                # SQLite DB & logs
    ├── bot_data.db
    └── bot.log
```

## 🔒 Security & Risk

### Trading Risks
- **No Financial Advice**: This bot is for educational purposes
- **Risk Management**: Always use proper position sizing
- **Stop Losses**: Never trade without stop-loss orders
- **Paper Trading**: Test strategies with demo accounts first

### API Security
- **Environment Variables**: Never commit secrets to code
- **Rate Limiting**: Built-in cooldowns prevent spam
- **Error Handling**: Graceful degradation on API failures

## 📈 Performance

- **Response Time**: < 2 seconds for signal generation
- **AI Analysis**: < 3 seconds per signal validation
- **24/7 Uptime**: Webhook mode for production reliability
- **Memory Efficient**: Lightweight async architecture

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new features
4. Submit a pull request

## 📄 License

MIT License - see LICENSE file for details.

## 🆘 Support

- **Issues**: Open GitHub issues for bugs
- **Discussions**: Use GitHub Discussions for questions
- **Documentation**: Check RENDER_DEPLOYMENT.md for deployment help

---

**⚠️ Disclaimer**: This software is for educational purposes. Trading involves substantial risk of loss. Past performance does not guarantee future results. Always do your own research and risk only what you can afford to lose.
