# 🎯 Deriv AI Trading Bot

Professional Telegram trading bot specialized in **Deriv Synthetic Indices** with AI-powered breakout & retest analysis and live chart generation.

## 🌟 Features

### Core Trading Features
- **Deriv Synthetic Indices Only**: R_10 to R_100, Boom/Crash, Jump, Step indices
- **Breakout & Retest Analysis**: Advanced pattern detection with entry/exit levels
- **AI-Powered Validation**: Real-time trade approval using Groq AI (Llama 3.1)
- **Live Chart Generation**: Professional technical charts with key levels
- **24/7 Trading**: Synthetic indices never close

### Advanced Features
- **Multi-Timeframe Analysis**: 1m to 1d chart analysis
- **Risk Management**: Automatic stop-loss and take-profit calculation
- **Market Sessions**: Kill zone timing for optimal entries
- **Signal Confidence**: 1-10 scoring system with AI validation
- **Real-time Data**: Direct Deriv API integration

## 🚀 Quick Start

### Local Development
```bash
# Clone repository
git clone https://github.com/yourusername/deriv-ai-trading-bot.git
cd deriv-ai-trading-bot

# Install dependencies
pip install -r requirements.txt

# Set environment variables
cp .env.example .env
# Edit .env with your BOT_TOKEN and GROQ_API_KEY

# Run bot
python main.py
```

### Railway Deployment (Production)

**Deploy to Railway:**
1. Go to [Railway.app](https://railway.app)
2. Connect your GitHub repository
3. Railway auto-deploys with `railway.json` config

## 📱 Usage

### Commands
- `/start` - Main menu and bot introduction
- `/analyze [symbol]` - Get breakout analysis for any Deriv symbol
- `/summary` - Market overview of all synthetic indices
- `/chart [symbol]` - Generate live technical chart

### Supported Symbols
- **Volatility Indices**: R_10, R_25, R_50, R_75, R_100
- **Boom & Crash**: BOOM1000, CRASH1000, BOOM500, CRASH500, etc.
- **Jump Indices**: JUMP10, JUMP25, JUMP50, JUMP75, JUMP100
- **Step Index**: STEP INDEX

### Menu Options
- **📈 Volatility Indices** - All R_ series symbols
- **💥 Boom & Crash** - High volatility indices
- **🚀 Jump Indices** - Sudden movement indices
- **🎯 Breakout Analysis** - Advanced pattern detection
- **📊 Live Charts** - Real-time chart generation
- **⚙️ Settings** - Risk management and preferences

## 🔧 Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `BOT_TOKEN` | ✅ | Telegram bot token from @BotFather |
| `GROQ_API_KEY` | ✅ | GroqCloud AI API (for AI trade validation) |
| `DERIV_API_TOKEN` | ✅ | Deriv API token for live data |
| `DERIV_APP_ID` | ✅ | Deriv app ID from developers.deriv.com |
| `WEBHOOK_MODE` | ❌ | `true` for production, `false` for local |
| `WEBHOOK_URL` | ❌ | Auto-set by Railway |
| `PORT` | ❌ | Auto-set by Railway (10000) |

### Advanced Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `MIN_SIGNAL_CONFIDENCE` | 8 | Minimum confidence for alerts |
| `AI_APPROVAL_MIN_SCORE` | 7 | Minimum AI score for approval |
| `LOG_LEVEL` | INFO | Logging verbosity |

## 🤖 AI Features

### Breakout & Retest Analysis
- **Pattern Detection**: Identifies support/resistance breakouts
- **Retest Confirmation**: Waits for price retest of broken levels
- **Entry Optimization**: Calculates optimal entry prices
- **Risk Management**: Automatic stop-loss and take-profit levels

### AI Validation System
- **Real-time Analysis**: Every signal validated by AI
- **Market Context**: Considers synthetic index characteristics
- **Confidence Scoring**: 1-10 rating system
- **Detailed Reasoning**: AI explains trade decisions

## 📊 Technical Analysis

### Chart Features
- **Live Price Charts**: Real-time OHLC visualization
- **Technical Indicators**: RSI, MACD, Moving Averages
- **Key Levels**: Support, resistance, entry, exit points
- **Multiple Timeframes**: 1m, 5m, 15m, 1h, 4h, 1d

### Signal Generation
- **Breakout Detection**: Identifies price breakouts from ranges
- **Retest Analysis**: Confirms breakout through retest
- **Volume Confirmation**: Validates strength with volatility
- **Risk Assessment**: Calculates position sizing and stops

## 🏗️ Architecture

```
deriv-ai-trading-bot/
├── main.py              # Entry point & Railway deployment
├── deriv_client.py       # Deriv API client for live data
├── deriv_signals.py      # Signal generation & analysis
├── deriv_handlers.py     # Telegram command handlers
├── deriv_menus.py        # UI keyboards & navigation
├── breakout_analysis.py  # Breakout & retest logic
├── chart_generator.py    # Live chart creation
├── utils.py             # Helper functions & database
├── requirements.txt     # Python dependencies
├── railway.json         # Railway deployment config
├── runtime.txt          # Python version specification
├── .env.example         # Environment variables template
└── data/                # SQLite DB & logs (gitignored)
    ├── bot_data.db
    ├── bot.lock
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

## 🚀 Deployment

### Railway (Recommended)
1. **Create Railway Account**: [railway.app](https://railway.app)
2. **Connect GitHub**: Link your repository
3. **Set Environment Variables**: Add all required variables
4. **Deploy**: Railway auto-builds and deploys
5. **Webhook URL**: `https://your-app.up.railway.app`

### Environment Variables on Railway
```
BOT_TOKEN=your_telegram_bot_token
GROQ_API_KEY=your_groqcloud_api_key_here
DERIV_API_TOKEN=2jlH6mvdlys29z8
DERIV_APP_ID=your_deriv_app_id
WEBHOOK_MODE=true
PORT=10000
```

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
- **Documentation**: Check this README for setup help

---

**⚠️ Disclaimer**: This software is for educational purposes. Trading synthetic indices involves substantial risk of loss. Past performance does not guarantee future results. Always do your own research and risk only what you can afford to lose.

**🔗 Live Demo**: [Deployed on Railway](https://web-production-8535f.up.railway.app)
