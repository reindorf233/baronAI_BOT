#!/usr/bin/env python3
"""
Main entry point for the trading bot
Handles app setup, webhook/polling configuration, and startup
"""
import asyncio
import logging
import os
import sys
import signal
from argparse import ArgumentParser
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent))

from telegram.ext import ApplicationBuilder, Application

from handlers import setup_handlers
from utils import (
    setup_logging, validate_env, WEBHOOK_MODE, WEBHOOK_URL, PORT,
    acquire_lock, release_lock, init_db, BOT_TOKEN
)

# Global app reference for graceful shutdown
app_instance = None


def parse_args():
    """Parse command line arguments"""
    parser = ArgumentParser(description="Trading Bot")
    parser.add_argument("--webhook", action="store_true", help="Run in webhook mode")
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", 8443)), help="Port for webhook")
    parser.add_argument("--url", type=str, default=os.getenv("WEBHOOK_URL", ""), help="Webhook URL")
    parser.add_argument("--skip-lock", action="store_true", help="Skip file lock check (for testing)")
    return parser.parse_args()


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    logging.info("Received shutdown signal, cleaning up...")
    release_lock()
    sys.exit(0)


def main():
    """Main application entry point (synchronous for polling compatibility)"""
    global app_instance
    args = parse_args()
    
    # Setup logging and environment
    setup_logging()
    validate_env()
    
    # Initialize database
    init_db()
    
    # Acquire file lock to prevent multiple instances (unless skipped)
    if not args.skip_lock:
        if not acquire_lock():
            logging.error("Another instance is already running. Use --skip-lock to override.")
            sys.exit(1)
        logging.info("File lock acquired")
    
    # Register signal handlers for graceful shutdown
    if sys.platform != "win32":
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    else:
        # Windows: use SIGINT only
        signal.signal(signal.SIGINT, signal_handler)
    
    # Get bot token
    token = BOT_TOKEN or os.getenv("BOT_TOKEN")
    if not token:
        logging.error("BOT_TOKEN environment variable required")
        sys.exit(1)
    
    # Build application
    logging.info("Building application...")
    app = ApplicationBuilder().token(token).build()
    app_instance = app
    
    # Setup all handlers
    setup_handlers(app)
    
    # Configure webhook or polling mode
    if args.webhook or WEBHOOK_MODE:
        webhook_url = args.url or WEBHOOK_URL
        port = args.port or PORT
        
        if not webhook_url:
            logging.error("Webhook URL required for webhook mode")
            logging.error("Set WEBHOOK_URL environment variable or use --url")
            sys.exit(1)
        
        logging.info(f"Starting webhook mode on port {port}")
        logging.info(f"Webhook URL: {webhook_url}")
        
        # Webhook mode uses async
        async def run_webhook():
            try:
                await app.bot.set_webhook(webhook_url)
                logging.info("Webhook set successfully")
                await app.run_webhook(
                    listen="0.0.0.0",
                    port=port,
                    webhook_url=webhook_url,
                    drop_pending_updates=True
                )
            except Exception as e:
                logging.error(f"Webhook setup failed: {e}")
                sys.exit(1)
        
        asyncio.run(run_webhook())
    else:
        logging.info("Starting polling mode")
        logging.info("For production, use --webhook with WEBHOOK_URL set")
        try:
            # Use synchronous run_polling() like the old bot.py
            app.run_polling(
                drop_pending_updates=True,
                allowed_updates=["message", "callback_query"]
            )
        except Exception as e:
            logging.error(f"Polling failed: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.info("Bot stopped by user")
        release_lock()
    except Exception as e:
        logging.error(f"Fatal error: {e}", exc_info=True)
        import traceback
        traceback.print_exc()
        release_lock()
        sys.exit(1)
