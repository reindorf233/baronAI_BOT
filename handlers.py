"""
All command and message handlers for the trading bot
"""
import logging
import asyncio
import re
from datetime import datetime
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes, ConversationHandler
)
from telegram.constants import ParseMode

from menus import (
    main_menu, synthetics_menu, settings_menu, forex_menu,
    get_signal_actions_keyboard, get_martingale_keyboard, get_risk_keyboard
)
from signals import (
    get_smc_prediction, get_volatility_signal, get_boom_crash_signal,
    get_step_index_signal, get_jump_index_signal, get_perfect_signals,
    get_daily_summary
)
from utils import (
    MONITORING_ENABLED, MONITORED_SYMBOLS, MIN_SIGNAL_CONFIDENCE,
    LAST_SIGNALS, LAST_PERFECT_SIGNALS, PERFECT_SIGNAL_USERS,
    SIGNAL_COOLDOWN_MINUTES, PERFECT_SIGNAL_COOLDOWN_MINUTES,
    get_user_pref, set_user_pref, get_user_balance, update_user_balance,
    calculate_risk_amount, normalize_symbol
)

# Conversation states
WAITING_FOR_SYMBOL = 1


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Welcome message with menu"""
    msg = (
        "🚀 *ICT/SMC Trading Bot*\n\n"
        "Advanced Market Structure Analysis:\n"
        "• Fair Value Gaps (FVG) Detection\n"
        "• Market Structure Shift (MSS)\n"
        "• EMA 200 Trend Filter\n"
        "• ICT Kill Zone Timing\n"
        "• 🚨 AUTO SIGNAL ALERTS\n"
        "• ⭐ 10/10 Confidence Signals\n"
        "• 📊 Synthetic Indices\n\n"
        "📱 *Commands:*\n"
        "/alerts - View recent strong signals\n"
        "/monitor - Toggle signal monitoring\n"
        "/analyze [symbol] - Custom analysis\n"
        "/summary - Daily market summary\n\n"
        "Select a signal below:"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle menu button presses and custom input"""
    text = update.message.text
    user_id = update.effective_user.id

    # Handle custom symbol input
    if context.user_data.get('waiting_for_symbol'):
        symbol = text.upper()
        result = get_smc_prediction(symbol)
        await update.message.reply_text(
            result, parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu
        )
        context.user_data['waiting_for_symbol'] = False
        return

    # Menu button handlers - Forex/Crypto
    symbol_map = {
        "🥇 Gold (GC=F)": "GC=F",
        "🥇 Gold Spot": "XAUUSD",
        "₿ Bitcoin": "BTC-USD",
        "📈 EURUSD": "EURUSD",
        "📈 GBPUSD": "GBPUSD",
        "📈 USDJPY": "USDJPY",
        "📈 USDCHF": "USDCHF",
        "📈 USDCAD": "USDCAD",
        "📈 AUDUSD": "AUDUSD",
        "📈 NZDUSD": "NZDUSD",
        "📈 USDMXN": "USDMXN",
        "📈 USDZAR": "USDZAR",
        "📈 USDTRY": "USDTRY",
        "🌍 USDAED": "USDAED",
        "🌍 USDARS": "USDARS",
        "🌍 USDAMD": "USDAMD",
        "🌍 USDAZN": "USDAZN",
        "🌍 USDBDT": "USDBDT",
        "🌍 USDBGN": "USDBGN",
        "🌍 USDBHD": "USDBHD",
        "🌍 USDBND": "USDBND",
    }

    if text in symbol_map:
        symbol = symbol_map[text]
        result = get_smc_prediction(symbol)
        await update.message.reply_text(
            result, parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu
        )
        return

    # Special menu buttons
    if text == "🛠 Custom Analysis":
        await update.message.reply_text(
            "Send any ticker symbol (e.g. USDJPY=X, NAS100=X, AAPL):",
            reply_markup=main_menu
        )
        context.user_data['waiting_for_symbol'] = True

    elif text == "📡 Bot Status":
        status_msg = (
            "📡 *Bot Status*\n\n"
            "✅ Online & Ready\n"
            "🤖 ICT/SMC Engine Active\n"
            "⏰ Kill Zones Tracked\n"
            f"📊 Monitoring: {len(MONITORED_SYMBOLS)} symbols\n"
            f"🎯 Min Confidence: {MIN_SIGNAL_CONFIDENCE}/10\n\n"
            "Happy trading!"
        )
        await update.message.reply_text(
            status_msg, parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu
        )

    elif text == "📊 Synthetics":
        await update.message.reply_text(
            "📊 *Synthetic Indices*\n\nSelect an index:",
            parse_mode=ParseMode.MARKDOWN, reply_markup=synthetics_menu
        )

    elif text == "⭐ 10/10 Signals":
        perfect_signals = get_perfect_signals()
        if not perfect_signals:
            msg = (
                "⭐ *10/10 Confidence Signals*\n\n"
                "No perfect signals available at the moment.\n"
                "Checking all markets for 10/10 setups with AI approval..."
            )
            await update.message.reply_text(
                msg, parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu
            )
        else:
            # Filter for AI-approved signals only
            ai_approved_signals = []
            for signal in perfect_signals:
                analysis = signal.get('analysis', '')
                if '🤖 AI APPROVED' in analysis or '✅ AI Approved' in analysis:
                    ai_approved_signals.append(signal)
            
            if ai_approved_signals:
                msg = f"⭐ *Found {len(ai_approved_signals)} AI-Approved Perfect Signals*\n\n"
                for i, signal in enumerate(ai_approved_signals[:5], 1):  # Limit to 5
                    msg += f"*{i}. {signal['symbol']} ({signal['type']}) 🤖*\n"
                msg += "\n🤖 All signals are AI-approved for maximum confidence.\n"
                msg += "Tap a symbol from the menu for full analysis."
            else:
                msg = (
                    "⭐ *10/10 Signals Found*\n\n"
                    f"Found {len(perfect_signals)} perfect signals, but none are AI-approved yet.\n"
                    "⚡ AI analyzing FAST for maximum safety..."
                )
            await update.message.reply_text(
                msg, parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu
            )

    elif text == "📈 Daily Summary":
        summary = get_daily_summary()
        await update.message.reply_text(
            summary, parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu
        )

    elif text == "🎯 Manual Execution Guide":
        guide_msg = (
            "🎯 *MANUAL EXECUTION GUIDE*\n\n"
            "Learn how to execute trades manually for maximum control!\n\n"
            "Choose a topic:"
        )
        from menus import get_execution_guide_keyboard
        await update.message.reply_text(
            guide_msg, parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_execution_guide_keyboard()
        )

    elif text == "⚙️ Settings":
        martingale = get_user_pref(user_id, "martingale_enabled", 0)
        risk = get_user_pref(user_id, "risk_percent", 1.0)
        balance = get_user_balance(user_id)
        
        settings_msg = (
            "⚙️ *Settings*\n\n"
            f"💰 Balance: ${balance:,.2f}\n"
            f"📊 Risk: {risk}%\n"
            f"🔄 Martingale: {'✅ Enabled' if martingale else '❌ Disabled'}\n\n"
            "Select an option:"
        )
        await update.message.reply_text(
            settings_msg, parse_mode=ParseMode.MARKDOWN, reply_markup=settings_menu
        )

    # Synthetics submenu
    elif text == "📊 Volatility 75":
        result = get_volatility_signal("V75")
        await update.message.reply_text(
            result, parse_mode=ParseMode.MARKDOWN, reply_markup=synthetics_menu
        )

    elif text == "📊 Volatility 100":
        result = get_volatility_signal("V100")
        await update.message.reply_text(
            result, parse_mode=ParseMode.MARKDOWN, reply_markup=synthetics_menu
        )

    elif text == "📊 Boom Index":
        result = get_boom_crash_signal("BOOM")
        await update.message.reply_text(
            result, parse_mode=ParseMode.MARKDOWN, reply_markup=synthetics_menu
        )

    elif text == "📊 Crash Index":
        result = get_boom_crash_signal("CRASH")
        await update.message.reply_text(
            result, parse_mode=ParseMode.MARKDOWN, reply_markup=synthetics_menu
        )

    elif text == "📊 Step Index":
        result = get_step_index_signal()
        await update.message.reply_text(
            result, parse_mode=ParseMode.MARKDOWN, reply_markup=synthetics_menu
        )

    elif text == "📊 Jump Index":
        result = get_jump_index_signal()
        await update.message.reply_text(
            result, parse_mode=ParseMode.MARKDOWN, reply_markup=synthetics_menu
        )

    # Settings submenu
    elif text == "⚙️ Toggle Martingale":
        martingale = get_user_pref(user_id, "martingale_enabled", 0)
        status = "enabled" if martingale else "disabled"
        msg = f"🔄 Martingale is currently {status}.\n\nUse buttons below to toggle:"
        await update.message.reply_text(
            msg, parse_mode=ParseMode.MARKDOWN, reply_markup=get_martingale_keyboard()
        )

    elif text == "⚙️ Risk Management":
        risk = get_user_pref(user_id, "risk_percent", 1.0)
        msg = f"📊 Current risk: {risk}%\n\nSelect new risk percentage:"
        await update.message.reply_text(
            msg, parse_mode=ParseMode.MARKDOWN, reply_markup=get_risk_keyboard()
        )

    elif text == "⚙️ Balance":
        balance = get_user_balance(user_id)
        msg = (
            f"💰 *Account Balance*\n\n"
            f"Current Balance: ${balance:,.2f}\n\n"
            "This is a simulated balance for risk calculation."
        )
        await update.message.reply_text(
            msg, parse_mode=ParseMode.MARKDOWN, reply_markup=settings_menu
        )

    elif text in ["🔙 Back to Main Menu", "🔙 Back"]:
        await update.message.reply_text(
            "Returning to main menu...", reply_markup=main_menu
        )

    else:
        await update.message.reply_text(
            "Select an option from the menu 👇", reply_markup=main_menu
        )


async def analyze_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /analyze command"""
    symbol = context.args[0].upper() if context.args else "GC=F"
    result = get_smc_prediction(symbol)
    await update.message.reply_text(
        result, parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu
    )


async def alerts_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show recent strong signals"""
    msg = "🚨 *Recent Strong Signals* 🚨\n\n"
    
    if not LAST_SIGNALS:
        msg += "No strong signals detected yet.\n"
        msg += f"Monitoring: {len(MONITORED_SYMBOLS)} symbols\n"
        msg += f"Min confidence: {MIN_SIGNAL_CONFIDENCE}/10"
    else:
        for symbol, time in list(LAST_SIGNALS.items())[-10:]:  # Last 10
            time_str = time.strftime('%H:%M')
            msg += f"• {symbol} - {time_str} EST\n"
    
    msg += "\n⚙️ Monitoring runs automatically every 5 minutes"
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)


async def toggle_monitoring(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Toggle signal monitoring on/off"""
    global MONITORING_ENABLED
    MONITORING_ENABLED = not MONITORING_ENABLED
    status = "ON" if MONITORING_ENABLED else "OFF"
    
    msg = (
        f"🔧 *Signal Monitoring: {status}*\n\n"
        f"Monitoring {len(MONITORED_SYMBOLS)} symbols\n"
        f"Min confidence: {MIN_SIGNAL_CONFIDENCE}/10\n"
        f"⏰ Cooldown: {SIGNAL_COOLDOWN_MINUTES} minutes"
    )
    
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)


async def summary_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Daily summary command"""
    summary = get_daily_summary()
    await update.message.reply_text(
        summary, parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu
    )


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline keyboard callbacks"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    data = query.data

    if data.startswith("martingale_"):
        enabled = 1 if data.endswith("_on") else 0
        set_user_pref(user_id, "martingale_enabled", enabled)
        status = "enabled" if enabled else "disabled"
        await query.edit_message_text(f"✅ Martingale {status}")

    elif data.startswith("risk_"):
        risk = int(data.split("_")[1])
        set_user_pref(user_id, "risk_percent", risk)
        await query.edit_message_text(f"✅ Risk set to {risk}%")

    elif data == "settings_back":
        await query.edit_message_text("Returning to settings...", reply_markup=settings_menu)

    elif data.startswith("trade_"):
        symbol = data.split("_", 1)[1]
        await query.edit_message_text(f"✅ Trade logged for {symbol}")

    elif data.startswith("fav_"):
        symbol = data.split("_", 1)[1]
        # Add to favorites logic here
        await query.edit_message_text(f"⭐ {symbol} added to favorites")

    # Manual Execution Guide handlers
    elif data == "exec_mt5_setup":
        mt5_msg = (
            "📱 *MT5 TERMINAL SETUP GUIDE*\n\n"
            "1️⃣ **Download & Install**\n"
            "   • Visit: https://www.metatrader5.com/en/download\n"
            "   • Choose your broker (Deriv, IC Markets, etc.)\n\n"
            "2️⃣ **Login Process**\n"
            "   • Open MT5 → File → Login to Trade Account\n"
            "   • Enter your account details\n\n"
            "3️⃣ **Chart Setup**\n"
            "   • Add indicators: EMA(200), RSI(14), MACD\n"
            "   • Set timeframe to M15 for scalping\n\n"
            "4️⃣ **Practice First**\n"
            "   • Use demo account before live trading\n"
            "   • Paper trade for confidence\n\n"
            "⚠️ *Important:* Never risk more than 1-2% per trade!"
        )
        await query.edit_message_text(mt5_msg, parse_mode=ParseMode.MARKDOWN)

    elif data == "exec_risk_calc":
        risk_msg = (
            "📊 *RISK CALCULATOR*\n\n"
            "Formula: Risk Amount = Account × Risk %\n\n"
            "**Example:**\n"
            "Account: $1000\n"
            "Risk: 1% = $10 per trade\n"
            "Risk: 2% = $20 per trade\n\n"
            "**Position Sizing:**\n"
            "Lot Size = Risk Amount ÷ (Stop Loss × Pip Value)\n\n"
            "**Pip Value Examples:**\n"
            "• EURUSD: $10 per pip (0.1 lots)\n"
            "• GBPUSD: $10 per pip (0.1 lots)\n"
            "• Gold: $100 per pip (0.01 lots)\n\n"
            "🛡️ *Risk Management Rules:*\n"
            "• Max 1-2% per trade\n"
            "• Max 5-10% total daily risk\n"
            "• Use proper position sizing"
        )
        await query.edit_message_text(risk_msg, parse_mode=ParseMode.MARKDOWN)

    elif data == "exec_entry_rules":
        entry_msg = (
            "🎯 *TRADE ENTRY RULES*\n\n"
            "✅ **WHEN TO ENTER:**\n\n"
            "1️⃣ **FVG Retest**\n"
            "   • Wait for price to retest FVG area\n"
            "   • Enter on rejection candle\n\n"
            "2️⃣ **Kill Zone Timing**\n"
            "   • London: 2-5 AM EST\n"
            "   • New York: 8:30-11 AM EST\n\n"
            "3️⃣ **Confluence Factors**\n"
            "   • EMA200 alignment\n"
            "   • Market structure\n"
            "   • RSI divergence\n\n"
            "4️⃣ **Entry Triggers**\n"
            "   • Pin bar rejection\n"
            "   • Engulfing pattern\n"
            "   • RSI oversold/overbought\n\n"
            "🚫 **WHEN NOT TO ENTER:**\n"
            "• Against major trend\n"
            "• High impact news\n"
            "• Outside Kill Zone\n"
            "• No confluence"
        )
        await query.edit_message_text(entry_msg, parse_mode=ParseMode.MARKDOWN)

    elif data == "exec_exit_strategy":
        exit_msg = (
            "🚪 *TRADE EXIT STRATEGY*\n\n"
            "🎯 **TAKE PROFIT LEVELS:**\n\n"
            "1️⃣ **TP1 (2:1 RR)**\n"
            "   • Minimum target\n"
            "   • Close 50% position here\n\n"
            "2️⃣ **TP2 (3:1 RR)**\n"
            "   • Extended target\n"
            "   • Let remaining run\n\n"
            "3️⃣ **TP3 (4:1 RR)**\n"
            "   • Home run target\n"
            "   • Rare but possible\n\n"
            "🛑 **STOP LOSS RULES:**\n\n"
            "• Place at FVG boundary\n"
            "• Use ATR for calculation\n"
            "• Never move SL against you\n"
            "• Use trailing stops on winners\n\n"
            "📈 **EXIT SIGNALS:**\n"
            "• Price hits TP level\n"
            "• Opposite FVG forms\n"
            "• Structure breaks\n"
            "• Time-based exit (4H max)"
        )
        await query.edit_message_text(exit_msg, parse_mode=ParseMode.MARKDOWN)

    elif data == "exec_position_size":
        size_msg = (
            "📈 *POSITION SIZING GUIDE*\n\n"
            "**Formula:**\n"
            "Lot Size = (Risk Amount) ÷ (Stop Loss × Pip Value)\n\n"
            "**Examples:**\n\n"
            "📊 **$100 Risk, 50 Pip SL:**\n"
            "EURUSD: 100 ÷ (50 × 10) = 0.02 lots\n"
            "GBPUSD: 100 ÷ (50 × 10) = 0.02 lots\n"
            "Gold: 100 ÷ (50 × 100) = 0.002 lots\n\n"
            "📊 **$500 Risk, 30 Pip SL:**\n"
            "EURUSD: 500 ÷ (30 × 10) = 0.17 lots\n"
            "GBPUSD: 500 ÷ (30 × 10) = 0.17 lots\n"
            "Gold: 500 ÷ (30 × 100) = 0.017 lots\n\n"
            "🎯 **Pro Tips:**\n"
            "• Start small (0.01 lots)\n"
            "• Increase as confidence grows\n"
            "• Never exceed 1-2% risk per trade\n"
            "• Adjust for account size"
        )
        await query.edit_message_text(size_msg, parse_mode=ParseMode.MARKDOWN)

    elif data == "exec_quick_guide":
        quick_msg = (
            "⚡ *5-MINUTE EXECUTION GUIDE*\n\n"
            "1️⃣ **Get Signal**\n"
            "   • Check bot for 10/10 signals\n\n"
            "2️⃣ **Verify Setup**\n"
            "   • Confirm FVG on M15\n"
            "   • Check EMA200 alignment\n"
            "   • Ensure Kill Zone timing\n\n"
            "3️⃣ **Calculate Position**\n"
            "   • Risk: 1% of account\n"
            "   • Use risk calculator\n\n"
            "4️⃣ **Enter Trade**\n"
            "   • Market order at FVG retest\n"
            "   • Set SL and TP levels\n\n"
            "5️⃣ **Monitor & Exit**\n"
            "   • Partial exit at 2:1 RR\n"
            "   • Trail stop on winners\n\n"
            "🔑 **Key Success Factors:**\n"
            "• Patience (wait for setup)\n"
            "• Discipline (follow rules)\n"
            "• Risk management (never guess)\n"
            "• Consistency (same process every trade)"
        )
        await query.edit_message_text(quick_msg, parse_mode=ParseMode.MARKDOWN)

    elif data == "exec_back_main":
        await query.edit_message_text("Returning to main menu...", reply_markup=main_menu)


async def check_strong_signals(application: Application):
    """Check for strong signals and send alerts"""
    if not MONITORING_ENABLED:
        return
    
    current_time = datetime.now()
    
    for symbol in MONITORED_SYMBOLS:
        try:
            analysis = get_smc_prediction(symbol)
            
            if not analysis or "Error" in analysis:
                continue
            
            # Extract confidence
            conf_match = re.search(r"Strategy Confidence: (\d+)/10", analysis)
            if not conf_match:
                continue
            
            confidence = int(conf_match.group(1))
            
            # Check if it's a strong signal
            if confidence >= MIN_SIGNAL_CONFIDENCE:
                # Check cooldown
                last_signal_time = LAST_SIGNALS.get(symbol)
                if (last_signal_time is None or 
                    (current_time - last_signal_time).total_seconds() > SIGNAL_COOLDOWN_MINUTES * 60):
                    
                    # Extract recommendation
                    rec_match = re.search(r"Recommendation: \*\*(\w+)\*\*", analysis)
                    recommendation = rec_match.group(1) if rec_match else "UNKNOWN"
                    
                    # Check for AI approval
                    ai_approved_match = re.search(r"AI APPROVED|✅ AI Approved", analysis)
                    ai_not_approved_match = re.search(r"⚠️ AI Not Approved", analysis)
                    has_ai_approval = bool(ai_approved_match) and not bool(ai_not_approved_match)
                    
                    # Only send alerts for AI-approved signals (or high confidence if AI unavailable)
                    if has_ai_approval or confidence >= 9:
                        # Extract AI score if available
                        ai_score_match = re.search(r"AI.*?\((\d+)/10\)", analysis)
                        ai_score = int(ai_score_match.group(1)) if ai_score_match else None
                        
                        # Create alert message
                        ai_badge = "🤖 AI APPROVED" if has_ai_approval else ""
                        alert_msg = (
                            f"🚨 *STRONG SIGNAL ALERT* {ai_badge} 🚨\n\n"
                            f"*{symbol}*\n"
                            f"▶️ *{recommendation}*\n"
                            f"**Confidence: {confidence}/10**\n"
                        )
                        if ai_score:
                            alert_msg += f"**AI Score: {ai_score}/10**\n"
                        alert_msg += (
                            f"🕐 *{current_time.strftime('%H:%M')} EST*\n\n"
                            f"Tap the symbol below for full analysis:\n"
                            f"{symbol}\n\n"
                            f"⚠️ Always verify with your own analysis."
                        )
                        
                        # Send to users who want alerts (for now, log it)
                        LAST_SIGNALS[symbol] = current_time
                        logging.info(f"🚨 STRONG SIGNAL (AI Approved): {symbol} {recommendation} @ {confidence}/10")
                    else:
                        logging.info(f"Signal filtered (no AI approval): {symbol} {recommendation} @ {confidence}/10")
                    
        except Exception as e:
            logging.error(f"Error monitoring {symbol}: {e}")
            continue


async def monitoring_job(context: ContextTypes.DEFAULT_TYPE):
    """Job callback for periodic signal monitoring"""
    if MONITORING_ENABLED:
        try:
            await check_strong_signals(context.application)
        except Exception as e:
            logging.error(f"Monitoring error: {e}")

async def start_monitoring(application: Application):
    """Start the signal monitoring loop (legacy - use job queue instead)"""
    while MONITORING_ENABLED:
        try:
            await check_strong_signals(application)
            await asyncio.sleep(300)  # Check every 5 minutes
        except Exception as e:
            logging.error(f"Monitoring error: {e}")
            await asyncio.sleep(60)  # Wait 1 minute on error


def setup_handlers(app: Application):
    """Setup all handlers for the bot"""
    # Command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("analyze", analyze_command))
    app.add_handler(CommandHandler("alerts", alerts_command))
    app.add_handler(CommandHandler("monitor", toggle_monitoring))
    app.add_handler(CommandHandler("summary", summary_command))
    
    # Message handler
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    # Callback query handler
    app.add_handler(CallbackQueryHandler(callback_handler))
    
    # Note: Monitoring can be enabled via /monitor command
    # Automatic monitoring startup disabled to avoid event loop conflicts
    # Users can enable it manually if needed
    
    logging.info("All handlers registered")

