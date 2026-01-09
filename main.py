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

# Try to import and test JobQueue - make it optional
JOB_QUEUE_AVAILABLE = False
try:
    from telegram.ext import JobQueue
    # Test if JobQueue can be instantiated
    test_queue = JobQueue()
    JOB_QUEUE_AVAILABLE = True
    logging.info("JobQueue available - automatic monitoring enabled")
except (ImportError, RuntimeError) as e:
    JOB_QUEUE_AVAILABLE = False
    logging.warning(f"JobQueue not available - automatic monitoring disabled: {e}")
    # Define a dummy JobQueue class to prevent errors
    class JobQueue:
        pass

from deriv_handlers import setup_deriv_handlers
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

    # Check for Railway environment
    on_railway = (os.getenv('RAILWAY_ENVIRONMENT') or
                  os.getenv('RAILWAY_PROJECT_ID') or
                  os.getenv('RAILWAY_STATIC_URL'))

    logging.info("=" * 60)
    logging.info("BARON AI TRADING BOT STARTUP")
    logging.info("=" * 60)
    logging.info(f"On Railway: {bool(on_railway)}")
    logging.info(f"Railway Environment: {os.getenv('RAILWAY_ENVIRONMENT')}")
    logging.info(f"Railway Project ID: {os.getenv('RAILWAY_PROJECT_ID')}")
    logging.info("Using POLLING MODE for Railway compatibility")
    logging.info("=" * 60)

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
    if JOB_QUEUE_AVAILABLE:
        app = ApplicationBuilder().token(token).job_queue(JobQueue()).build()
        logging.info("Job queue enabled for automatic monitoring")
    else:
        app = ApplicationBuilder().token(token).build()
        logging.info("Job queue not available - monitoring via manual commands only")
    app_instance = app
    
    # Setup all handlers
    setup_deriv_handlers(app)
    
    # Configure webhook or polling mode
    if args.webhook or WEBHOOK_MODE:
        webhook_url = args.url or WEBHOOK_URL
        port = args.port or PORT

        # For Render deployment, construct webhook URL from environment
        if not webhook_url:
            # Render provides the service URL via RENDER_EXTERNAL_URL
            render_url = os.getenv("RENDER_EXTERNAL_URL")
            if render_url:
                webhook_url = render_url
                logging.info(f"Using Render service URL: {webhook_url}")
            else:
                # Check if we're on Render (multiple ways)
                on_render = (os.getenv("ON_RENDER", "").lower() == "true" or
                           os.getenv("RENDER") == "true" or
                           os.getenv("DYNO") is not None or  # Heroku style
                           "render" in os.getenv("PATH", "").lower())

                if on_render:
                    # Try different Render environment variables for service URL
                    service_name = (os.getenv("RENDER_SERVICE_NAME") or
                                  os.getenv("SERVICE_NAME") or
                                  "baron-ai-bot")

                    # Try to get the external URL from various sources
                    external_url = (os.getenv("RENDER_EXTERNAL_URL") or
                                  os.getenv("EXTERNAL_URL"))

                    if external_url:
                        webhook_url = external_url
                    else:
                        # Construct URL from service name
                        webhook_url = f"https://{service_name}.onrender.com"

                    logging.info(f"Constructed webhook URL for Render: {webhook_url}")
                else:
                    # Debug: show what environment variables are available
                    logging.error("Webhook URL required for webhook mode")
                    logging.error("Available environment variables:")
                    for key in ["RENDER_EXTERNAL_URL", "ON_RENDER", "RENDER", "RENDER_SERVICE_NAME"]:
                        value = os.getenv(key, "NOT_SET")
                        logging.error(f"  {key}: {value}")
                    logging.error("Set WEBHOOK_URL environment variable or ensure you're on Render")
                    sys.exit(1)
        
        logging.info(f"Starting webhook mode on port {port}")
        logging.info(f"Webhook URL: {webhook_url}")
        
        # For Render deployment, use polling instead of webhook to avoid event loop conflicts
        on_render = (os.getenv("ON_RENDER", "").lower() == "true" or
                    os.getenv("RENDER") == "true" or
                    "render" in os.getenv("PATH", "").lower())

        if on_render:
            logging.info("Running on Render - using polling mode instead of webhook")
            # Use polling mode for Render (simpler, no event loop issues)
            try:
                app.run_polling(
                    drop_pending_updates=True,
                    allowed_updates=["message", "callback_query"]
                )
            except Exception as e:
                logging.error(f"Polling failed: {e}")
                sys.exit(1)
        else:
            # Webhook mode for other deployments
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
                    import traceback
                    traceback.print_exc()
                    sys.exit(1)

            # Handle event loop
            try:
                loop = asyncio.get_running_loop()
                logging.warning("Event loop already running, using nest_asyncio")
                import nest_asyncio
                nest_asyncio.apply()
                asyncio.run(run_webhook())
            except RuntimeError:
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
            error_msg = str(e).lower()
            if "conflict" in error_msg and "getupdates" in error_msg:
                logging.error("=" * 60)
                logging.error("TELEGRAM CONFLICT ERROR!")
                logging.error("Multiple bot instances are running!")
                logging.error("=" * 60)
                logging.error("Solutions:")
                logging.error("1. Stop local bot: Ctrl+C if running locally")
                logging.error("2. Check Railway: Only one deployment should be active")
                logging.error("3. Stop other Railway deployments if multiple exist")
                logging.error("4. Wait 30 seconds, then restart")
                logging.error("5. Use --skip-lock if needed for testing")
                logging.error("=" * 60)
            else:
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
