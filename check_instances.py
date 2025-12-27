#!/usr/bin/env python3
"""
Diagnostic script to check for multiple bot instances
"""
import os
import subprocess
import requests
from telegram import Bot

BOT_TOKEN = os.getenv('BOT_TOKEN', '8455972124:AAFJ8sWuQGEbKFxIktXDBj_CQyU84A3pbMU')

def check_local_processes():
    """Check for local Python/bot processes"""
    print("CHECKING LOCAL PROCESSES...")

    try:
        # Check for Python processes
        if os.name == 'nt':  # Windows
            result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq python.exe'], capture_output=True, text=True)
            python_processes = [line for line in result.stdout.split('\n') if 'python.exe' in line]
        else:  # Unix/Linux
            result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
            python_processes = [line for line in result.stdout.split('\n') if 'python' in line.lower()]

        print(f"Found {len(python_processes)} Python processes:")
        for proc in python_processes[:5]:  # Show first 5
            print(f"  {proc.strip()}")

        return len(python_processes) > 0

    except Exception as e:
        print(f"Could not check processes: {e}")
        return False

def check_telegram_webhook():
    """Check current webhook status"""
    print("\nCHECKING TELEGRAM WEBHOOK STATUS...")

    try:
        import asyncio
        bot = Bot(token=BOT_TOKEN)

        # Create event loop to run async function
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        webhook_info = loop.run_until_complete(bot.get_webhook_info())
        loop.close()

        print(f"Webhook URL: {webhook_info.url}")
        print(f"Pending updates: {webhook_info.pending_update_count}")
        print(f"Max connections: {webhook_info.max_connections}")

        if webhook_info.url:
            print("WEBHOOK IS SET - This could conflict with polling!")
            return True
        else:
            print("No webhook set - polling mode should work")
            return False

    except Exception as e:
        print(f"Could not check webhook: {e}")
        return False

def check_render_services():
    """Check if multiple Render services exist"""
    print("\nCHECKING RENDER SERVICES...")
    print("Cannot check Render services programmatically")
    print("Please manually verify at: https://dashboard.render.com")
    print("- Should have ONLY ONE 'baronAI_BOT' service")
    print("- Status should be 'Live' (green)")

def main():
    print("BARON AI BOT - INSTANCE DIAGNOSTIC")
    print("=" * 50)

    has_local = check_local_processes()
    has_webhook = check_telegram_webhook()
    check_render_services()

    print("\n" + "=" * 50)
    print("DIAGNOSIS:")

    if has_local and has_webhook:
        print("CRITICAL: Local bot + webhook conflict!")
        print("Solution: Kill local processes OR delete webhook")
    elif has_local:
        print("WARNING: Local bot running - could conflict with Render")
        print("Solution: Kill local Python processes")
    elif has_webhook:
        print("WARNING: Webhook set - only webhook mode should be used")
        print("Solution: Ensure Render uses webhook mode only")
    else:
        print("No obvious conflicts detected")
        print("If still getting errors, check Render logs")

    print("\nQUICK FIXES:")
    print("1. Kill local bots: taskkill /f /im python.exe (Windows)")
    print("2. Check Render: Only ONE service should exist")
    print("3. Redeploy: Manual deploy in Render dashboard")
    print("4. Test: Send /start to bot after fixes")

if __name__ == '__main__':
    main()
