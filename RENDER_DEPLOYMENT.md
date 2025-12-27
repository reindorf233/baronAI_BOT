# Deploy Baron AI Bot on Render

## 🚀 Quick Deploy

### 1. Fork/Clone this repository to GitHub

```bash
git clone https://github.com/yourusername/baronAI_BOT.git
cd baronAI_BOT
```

### 2. Create Render Account

Go to [render.com](https://render.com) and sign up for an account.

### 3. Connect GitHub Repository

1. Click "New" → "Web Service"
2. Connect your GitHub account
3. Select the `baronAI_BOT` repository
4. Choose the branch (usually `main`)

### 4. Configure Build Settings

**Runtime:** Python 3
**Build Command:** `pip install -r requirements.txt`
**Start Command:** `python main.py --webhook`

### 5. Set Environment Variables

In Render Dashboard → Environment:

| Key | Value | Description |
|-----|-------|-------------|
| `BOT_TOKEN` | `8455972124:AAFJ8sWuQGEbKFxIktXDBj_CQyU84A3pbMU` | Your Telegram bot token |
| `GROQ_API_KEY` | `your_groq_api_key` | Groq API key for AI features |
| `WEBHOOK_MODE` | `true` | Enable webhook mode |
| `PORT` | `10000` | Port (Render provides this) |
| `USER_TIMEZONE` | `Africa/Accra` | Your timezone |

**Important:** The `WEBHOOK_URL` will be automatically set by Render to your service URL.

### 6. Deploy

Click "Create Web Service" - Render will build and deploy automatically!

## 📋 Alternative Manual Setup

If you prefer manual configuration:

### Using render.yaml

1. Create a new Web Service
2. Choose "Deploy from GitHub"
3. Render will detect the `render.yaml` file and configure automatically

### Manual Configuration

**Service Type:** Web Service
**Runtime:** Python
**Build Command:** `pip install -r requirements.txt`
**Start Command:** `python main.py --webhook`

## 🔧 Environment Variables Explained

- `BOT_TOKEN`: Get from @BotFather on Telegram
- `GROQ_API_KEY`: Get from [Groq Console](https://console.groq.com/)
- `WEBHOOK_MODE`: Must be `true` for production
- `PORT`: Render automatically provides this
- `WEBHOOK_URL`: Render automatically sets this to your service URL

## 🌐 Webhook URL

Render will automatically provide the webhook URL. It will look like:
```
https://your-service-name.onrender.com
```

The bot will automatically use this URL for webhooks.

## 📊 Monitoring

- **Logs**: View in Render Dashboard → Logs
- **Metrics**: Check response times and uptime
- **Alerts**: Set up email notifications for downtime

## 🔄 Updates

To update your bot:

1. Push changes to your GitHub repository
2. Render will automatically redeploy (usually takes 2-3 minutes)

## 🛠️ Troubleshooting

### Common Issues

**1. Webhook not working**
- Check that `WEBHOOK_MODE=true`
- Verify `BOT_TOKEN` is correct
- Check Render logs for webhook setup errors

**2. AI features not working**
- Verify `GROQ_API_KEY` is set correctly
- Check if Groq API has usage limits

**3. Build failures**
- Ensure all dependencies are in `requirements.txt`
- Check Python version compatibility (3.12 recommended)

### Logs Location

- **Render Logs**: Dashboard → Logs tab
- **Bot Logs**: The bot saves logs to `data/bot.log` (visible in Render file system)

## 💰 Render Pricing

- **Free Tier**: 750 hours/month, suitable for testing
- **Paid Plans**: From $7/month for 24/7 uptime

## 🔒 Security Notes

- Never commit `.env` files to GitHub
- Use Render's environment variable system for secrets
- Regularly rotate API keys
- Monitor usage to avoid unexpected charges

## 🎯 Post-Deployment

Once deployed:

1. **Test the bot**: Send `/start` to your Telegram bot
2. **Check logs**: Monitor Render dashboard for any errors
3. **Set up monitoring**: Enable alerts for downtime
4. **Scale if needed**: Upgrade Render plan as usage grows

## 📞 Support

- **Render Docs**: [render.com/docs](https://render.com/docs)
- **Telegram Bot API**: [core.telegram.org](https://core.telegram.org/)
- **python-telegram-bot**: [python-telegram-bot.org](https://python-telegram-bot.org/)

---

**Happy deploying! 🚀**
