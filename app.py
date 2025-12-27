"""
Flask-based Telegram Bot for Render Deployment
Handles webhooks properly without event loop conflicts
"""
import os
import logging
from flask import Flask, request, Response
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import asyncio
from threading import Thread

# Import our bot handlers
from handlers import setup_handlers
from utils import setup_logging, validate_env, BOT_TOKEN, GROQ_API_KEY

# Flask app
app = Flask(__name__)

# Global bot application
bot_app = None

def create_bot_app():
    """Create and configure the Telegram bot application"""
    global bot_app

    if bot_app is None:
        # Create bot application (don't start it yet)
        bot_app = Application.builder().token(BOT_TOKEN).build()

        # Setup all handlers
        setup_handlers(bot_app)

        logging.info("Bot application created and configured")

    return bot_app

@app.route('/')
def home():
    """Health check endpoint"""
    return {'status': 'Bot is running', 'health': 'OK'}

@app.route('/health')
def health():
    """Health check for Render"""
    return {'status': 'healthy'}

@app.route(f'/{BOT_TOKEN.split(":")[0]}', methods=['POST'])
async def webhook():
    """Handle Telegram webhook"""
    try:
        # Get the update from Telegram
        update_data = request.get_json()
        update = Update.de_json(update_data, bot_app.bot)

        # Process the update
        await bot_app.process_update(update)

        return Response('OK', status=200)

    except Exception as e:
        logging.error(f"Webhook error: {e}")
        return Response('Error', status=500)

@app.route('/set_webhook', methods=['GET'])
def set_webhook():
    """Manually set webhook (for testing)"""
    try:
        webhook_url = os.getenv('WEBHOOK_URL')
        if webhook_url:
            # Run this in a separate thread to avoid blocking
            def set_hook():
                asyncio.run(bot_app.bot.set_webhook(webhook_url))
            Thread(target=set_hook).start()
            return {'status': 'Webhook setting initiated', 'url': webhook_url}
        else:
            return {'error': 'WEBHOOK_URL not set'}, 400
    except Exception as e:
        return {'error': str(e)}, 500

def run_bot_polling():
    """Run bot in polling mode (fallback)"""
    try:
        logging.info("Starting bot in polling mode")
        bot_app.run_polling(drop_pending_updates=True)
    except Exception as e:
        logging.error(f"Polling failed: {e}")

if __name__ == '__main__':
    # Setup logging and environment
    setup_logging()
    validate_env()

    # Create bot application
    create_bot_app()

    # Check if we should use webhook or polling
    use_webhook = os.getenv('WEBHOOK_MODE', 'false').lower() == 'true'
    webhook_url = os.getenv('WEBHOOK_URL')

    if use_webhook and webhook_url:
        # Webhook mode - Flask will handle HTTP requests
        logging.info(f"Starting Flask server with webhook mode")
        logging.info(f"Webhook URL: {webhook_url}")

        # Set webhook in background
        def init_webhook():
            asyncio.run(bot_app.bot.set_webhook(webhook_url))
            logging.info("Webhook set successfully")
        Thread(target=init_webhook).start()

        # Start Flask server
        port = int(os.getenv('PORT', 10000))
        app.run(host='0.0.0.0', port=port, debug=False)

    else:
        # Polling mode - run bot directly
        logging.info("Starting in polling mode")
        run_bot_polling()
