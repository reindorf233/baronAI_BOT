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

async def error_handler(update, context):
    """Handle bot errors"""
    logging.error(f"Bot error: {context.error}")
    logging.error(f"Update: {update}")

def create_bot_app():
    """Create and configure the Telegram bot application"""
    global bot_app

    if bot_app is None:
        # Create bot application (don't start it yet)
        bot_app = Application.builder().token(BOT_TOKEN).build()

        # Add error handler
        bot_app.add_error_handler(error_handler)

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
def webhook():
    """Handle Telegram webhook"""
    try:
        # Get the update from Telegram
        update_data = request.get_json()
        update = Update.de_json(update_data, bot_app.bot)

        # Process the update asynchronously in a thread
        import asyncio
        from concurrent.futures import ThreadPoolExecutor

        def process_async():
            """Run async bot processing in a new event loop"""
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(bot_app.process_update(update))
                loop.close()
            except Exception as e:
                logging.error(f"Async processing error: {e}")

        # Run in thread pool to avoid blocking
        executor = ThreadPoolExecutor(max_workers=4)
        executor.submit(process_async)

        return Response('OK', status=200)

    except Exception as e:
        logging.error(f"Webhook error: {e}")
        import traceback
        traceback.print_exc()
        return Response('Error', status=500)

@app.route('/set_webhook', methods=['GET'])
def set_webhook():
    """Manually set webhook (for testing)"""
    try:
        webhook_url = os.getenv('WEBHOOK_URL')
        if webhook_url:
            # Run webhook setup in a thread
            def set_hook():
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(bot_app.bot.set_webhook(webhook_url))
                    loop.close()
                    logging.info(f"Webhook set to: {webhook_url}")
                except Exception as e:
                    logging.error(f"Failed to set webhook: {e}")

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

    # Determine mode and handle conflicts
    on_render = (os.getenv('RENDER') == 'true' or
                os.getenv('ON_RENDER', '').lower() == 'true')

    webhook_mode = os.getenv('WEBHOOK_MODE', '').lower() == 'true'
    webhook_url = os.getenv('WEBHOOK_URL')

    logging.info("=" * 50)
    logging.info("BARON AI BOT STARTUP DIAGNOSTIC")
    logging.info("=" * 50)
    logging.info(f"ON_RENDER: {on_render}")
    logging.info(f"WEBHOOK_MODE: {webhook_mode}")
    logging.info(f"WEBHOOK_URL: {webhook_url}")

    if on_render:
        # RENDER: Force polling mode (most reliable)
        logging.info("RENDER DETECTED: Using polling mode (most reliable)")
        logging.info("Polling mode avoids webhook conflicts")
        logging.info("=" * 50)
        run_bot_polling()

    elif webhook_mode and webhook_url:
        # MANUAL WEBHOOK MODE
        logging.info("MANUAL WEBHOOK MODE: Using webhook")

        logging.info(f"Starting Flask server with webhook: {webhook_url}")

        # Clear any existing webhook/polling conflicts
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            # Delete webhook first to clear any conflicts
            loop.run_until_complete(bot_app.bot.delete_webhook())
            logging.info("Cleared existing webhook")
            # Set new webhook
            loop.run_until_complete(bot_app.bot.set_webhook(webhook_url))
            logging.info("Webhook set successfully")
            loop.close()
        except Exception as e:
            logging.error(f"Webhook setup issue: {e}")

        # Start Flask server
        port = int(os.getenv('PORT', 10000))
        logging.info(f"Flask server starting on port {port}")
        logging.info("Bot ready for webhook requests!")
        logging.info("=" * 50)

        app.run(host='0.0.0.0', port=port, debug=False, threaded=True)

    else:
        # LOCAL DEVELOPMENT: Polling mode
        logging.warning("LOCAL DEVELOPMENT MODE: Using polling")
        logging.warning("This should NOT be used in production!")
        logging.warning("For production, use Render (auto-polling) or set WEBHOOK_MODE=true")
        logging.info("=" * 50)

        run_bot_polling()
