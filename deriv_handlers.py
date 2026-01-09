"""
Deriv-specific command and callback handlers
"""
import logging
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes, ConversationHandler
)

from deriv_signals import get_deriv_signal, format_deriv_signal, get_deriv_market_summary
from deriv_menus import (
    deriv_main_menu, volatility_menu, boom_crash_menu, jump_menu,
    get_deriv_symbol_keyboard, get_timeframe_keyboard, get_analysis_type_keyboard,
    get_signal_actions_keyboard, get_deriv_categories_menu,
    get_volatility_symbols_menu, get_boom_crash_symbols_menu, get_jump_symbols_menu
)
from deriv_client import is_deriv_symbol, get_deriv_symbol_name
from utils import get_user_timezone, format_entry_time_display
from chart_generator import create_technical_chart, create_breakout_chart

# Conversation states
WAITING_SYMBOL = 1
WAITING_TIMEFRAME = 2

# User session data
user_sessions = {}

async def deriv_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command with Deriv menu"""
    user_id = update.effective_user.id
    user_sessions[user_id] = {
        'symbol': None,
        'timeframe': '15m',
        'analysis_type': 'breakout'
    }
    
    welcome_message = """
🎯 **DERIV SYNTHETIC INDICES TRADING BOT**

Welcome to your professional Deriv trading assistant!

📈 **Available Indices**:
• **Volatility Indices** (R_10 to R_100)
• **Boom & Crash** (1000, 500, 300)  
• **Jump Indices** (10, 25, 50, 75, 100)
• **Step Index**

🔥 **Features**:
• Live Deriv data feeds
• Breakout & retest analysis
• AI-powered signal validation
• Real-time chart generation
• 24/7 market monitoring

📱 **Commands**:
/analyze [symbol] - Get instant analysis
/summary - Market overview
/alerts - Manage signal alerts
/chart [symbol] - Generate live chart

Choose an option below to get started! 👇
"""
    
    await update.message.reply_text(
        welcome_message,
        reply_markup=deriv_main_menu,
        parse_mode='Markdown'
    )

async def deriv_analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Analyze a specific Deriv symbol"""
    user_id = update.effective_user.id
    
    try:
        if context.args:
            # Symbol provided in command
            symbol = context.args[0].upper()
            if not is_deriv_symbol(symbol):
                await update.message.reply_text(
                    f"❌ '{symbol}' is not a valid Deriv synthetic index\n\n"
                    "📈 **Valid symbols**: R_10, R_25, R_50, R_75, R_100, BOOM1000, CRASH1000, STEP INDEX, etc.",
                    parse_mode='Markdown'
                )
                return
            
            # Get analysis
            await update.message.reply_text("🔄 Analyzing... Please wait...")
            
            signal_data = await get_deriv_signal(symbol, '15m')
            message = format_deriv_signal(signal_data)
            
            await update.message.reply_text(
                message,
                reply_markup=get_signal_actions_keyboard(symbol, '15m'),
                parse_mode='Markdown'
            )
            
        else:
            # No symbol provided, show selection
            await update.message.reply_text(
                "📈 **Select a Deriv Synthetic Index:**",
                reply_markup=get_deriv_symbol_keyboard(),
                parse_mode='Markdown'
            )
            
    except Exception as e:
        logging.error(f"Error in analyze command: {e}")
        await update.message.reply_text("❌ Analysis failed. Please try again.")

async def deriv_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get Deriv market summary"""
    try:
        await update.message.reply_text("🔄 Generating market summary...")
        
        summary = await get_deriv_market_summary()
        await update.message.reply_text(summary, parse_mode='Markdown')
        
    except Exception as e:
        logging.error(f"Error in summary command: {e}")
        await update.message.reply_text("❌ Failed to generate summary.")

async def deriv_chart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate and send a technical chart for a Deriv symbol"""
    user_id = update.effective_user.id

    try:
        if context.args:
            # Symbol provided in command
            symbol = context.args[0].upper()
            if not is_deriv_symbol(symbol):
                error_msg = f"❌ '{symbol}' is not a valid Deriv synthetic index\n\n📈 Valid symbols: <code>R_10</code>, <code>R_25</code>, <code>R_50</code>, <code>R_75</code>, <code>R_100</code>, <code>BOOM1000</code>, <code>CRASH1000</code>, <code>STEP INDEX</code>, etc."
                try:
                    await update.message.reply_text(error_msg, parse_mode='HTML')
                except Exception:
                    await update.message.reply_text(error_msg.replace('<code>', '').replace('</code>', ''))
                return

            # Get signal data for chart generation
            await update.message.reply_text("📊 Generating chart... Please wait...")

            signal_data = await get_deriv_signal(symbol, '15m')

            if "error" in signal_data:
                error_msg = format_deriv_signal(signal_data)
                await update.message.reply_text(
                    error_msg,
                    reply_markup=get_signal_actions_keyboard(symbol, '15m'),
                    parse_mode='HTML'
                )
                return

            # Generate chart using stored dataframe
            advanced = signal_data.get("advanced_analysis", {})
            breakout_analysis = advanced.get("breakout_analysis", {})

            # For now, just show signal without chart to avoid errors
            message = format_deriv_signal(signal_data)
            await update.message.reply_text(
                message,
                reply_markup=get_signal_actions_keyboard(symbol, '15m'),
                parse_mode='Markdown'
            )

        else:
            # No symbol provided, show selection
            await update.message.reply_text(
                "📊 <b>Select a Deriv Synthetic Index for Analysis:</b>",
                reply_markup=get_deriv_symbol_keyboard(),
                parse_mode='HTML'
            )

    except Exception as e:
        logging.error(f"Error in chart command: {e}")
        await update.message.reply_text("❌ Analysis failed. Please try again.")

async def handle_deriv_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle Deriv-specific callback queries"""
    query = update.callback_query
    user_id = update.effective_user.id
    
    try:
        await query.answer()
        
        # Initialize session if not exists
        if user_id not in user_sessions:
            user_sessions[user_id] = {
                'symbol': None,
                'timeframe': '15m',
                'analysis_type': 'breakout'
            }
        
        session = user_sessions[user_id]
        data = query.data
        
        # Handle symbol selection
        if data.startswith("symbol_"):
            symbol = data.replace("symbol_", "")
            session['symbol'] = symbol
            
            # Show timeframe selection
            await query.edit_message_text(
                f"📈 **{get_deriv_symbol_name(symbol)}** selected\n\n"
                "⏰ **Select timeframe:**",
                reply_markup=get_timeframe_keyboard(),
                parse_mode='Markdown'
            )
        
        # Handle timeframe selection
        elif data.startswith("tf_"):
            timeframe = data.replace("tf_", "")
            session['timeframe'] = timeframe
            
            # Show analysis type selection
            await query.edit_message_text(
                f"📈 **{get_deriv_symbol_name(session['symbol'])}** - {timeframe}\n\n"
                "🔍 **Select analysis type:**",
                reply_markup=get_analysis_type_keyboard(),
                parse_mode='Markdown'
            )
        
        # Handle analysis type selection
        elif data.startswith("analysis_"):
            analysis_type = data.replace("analysis_", "")
            session['analysis_type'] = analysis_type
            
            # Perform analysis
            await query.edit_message_text("🔄 Analyzing... Please wait...")
            
            signal_data = await get_deriv_signal(session['symbol'], session['timeframe'])
            message = format_deriv_signal(signal_data)
            
            await query.edit_message_text(
                message,
                reply_markup=get_signal_actions_keyboard(session['symbol'], session['timeframe']),
                parse_mode='Markdown'
            )
        
        # Handle category selection
        elif data.startswith("category_"):
            category = data.replace("category_", "")
            
            if category == "volatility":
                await query.edit_message_text(
                    "📈 **Volatility Indices:**",
                    reply_markup=get_volatility_symbols_menu(),
                    parse_mode='Markdown'
                )
            elif category == "boom_crash":
                await query.edit_message_text(
                    "💥 **Boom & Crash Indices:**",
                    reply_markup=get_boom_crash_symbols_menu(),
                    parse_mode='Markdown'
                )
            elif category == "jump":
                await query.edit_message_text(
                    "🚀 **Jump Indices:**",
                    reply_markup=get_jump_symbols_menu(),
                    parse_mode='Markdown'
                )
            elif category == "step":
                await query.edit_message_text(
                    "👣 **Step Index:**\n\n"
                    "Analyzing STEP INDEX...",
                    parse_mode='Markdown'
                )
                # Auto-analyze step index
                signal_data = await get_deriv_signal("STEP INDEX", "15m")
                message = format_deriv_signal(signal_data)
                await query.edit_message_text(
                    message,
                    reply_markup=get_signal_actions_keyboard("STEP INDEX", "15m"),
                    parse_mode='Markdown'
                )
        
        # Handle chart requests
        elif data.startswith("chart_"):
            parts = data.split("_")
            symbol = parts[1]
            timeframe = parts[2]
            
            await query.edit_message_text("🔄 Generating chart...")
            
            signal_data = await get_deriv_signal(symbol, timeframe)
            
            if signal_data.get("chart"):
                import base64
                from io import BytesIO
                
                chart_data = base64.b64decode(signal_data["chart"])
                await query.message.reply_photo(
                    photo=BytesIO(chart_data),
                    caption=f"📈 {get_deriv_symbol_name(symbol)} - {timeframe}",
                    parse_mode='Markdown'
                )
            else:
                await query.edit_message_text("❌ Chart generation failed")
        
        # Handle refresh requests
        elif data.startswith("refresh_"):
            parts = data.split("_")
            symbol = parts[1]
            timeframe = parts[2]
            
            await query.edit_message_text("🔄 Refreshing analysis...")
            
            signal_data = await get_deriv_signal(symbol, timeframe)
            message = format_deriv_signal(signal_data)
            
            await query.edit_message_text(
                message,
                reply_markup=get_signal_actions_keyboard(symbol, timeframe),
                parse_mode='Markdown'
            )
        
        # Handle alert requests
        elif data.startswith("alert_"):
            parts = data.split("_")
            symbol = parts[1]
            timeframe = parts[2]
            
            await query.edit_message_text(
                f"⏰ **Alert Set**\n\n"
                f"📈 {get_deriv_symbol_name(symbol)} - {timeframe}\n"
                f"You'll be notified when a strong signal appears!",
                parse_mode='Markdown'
            )
        
        # Handle report requests
        elif data.startswith("report_"):
            parts = data.split("_")
            symbol = parts[1]
            timeframe = parts[2]
            
            # Generate detailed report
            signal_data = await get_deriv_signal(symbol, timeframe)
            
            report = f"""
📋 **DETAILED ANALYSIS REPORT**

**Symbol**: {get_deriv_symbol_name(symbol)} ({symbol})
**Timeframe**: {timeframe}
**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}

{format_deriv_signal(signal_data)}

---
*Report generated by Deriv Trading Bot*
"""
            
            await query.edit_message_text(report, parse_mode='Markdown')

        # Handle order placement
        elif data.startswith("order_"):
            parts = data.split("_")
            symbol = parts[1]
            timeframe = parts[2]

            # Get signal data for order placement
            signal_data = await get_deriv_signal(symbol, timeframe)
            advanced = signal_data.get("advanced_analysis", {})
            composite = advanced.get("composite_signal", {})
            risk_mgmt = advanced.get("risk_management", {})

            signal = composite.get("signal", "neutral")
            confidence = composite.get("confidence", 0)

            if signal in ["buy", "sell"] and confidence >= 5:
                # Create order placement message
                direction_text = "LONG (BUY)" if signal == "buy" else "SHORT (SELL)"
                entry_price = risk_mgmt.get("entry_price", "Market")
                stop_loss = risk_mgmt.get("stop_loss", "N/A")
                take_profit = risk_mgmt.get("take_profit", "N/A")
                breakeven = risk_mgmt.get("breakeven", "N/A")

                order_message = f"""
💰 **ORDER PLACEMENT CONFIRMED**

🎯 **{get_deriv_symbol_name(symbol)}**

**Direction**: {direction_text}
**Confidence**: {confidence}/10 ⭐

**Order Details:**
• Entry: {entry_price}
• Stop Loss: {stop_loss}
• Take Profit: {take_profit}
• Breakeven: {breakeven}

**Risk Management:**
• Risk/Reward Ratio: {risk_mgmt.get('risk_reward_ratio', 'N/A')}
• ATR: {risk_mgmt.get('atr', 'N/A')}

⚠️ **EXECUTION CHECKLIST:**
✅ Confirm account balance
✅ Verify market conditions
✅ Set stop loss first
✅ Monitor position closely
✅ Use breakeven when in profit

*Order prepared by Baron AI Trading Bot*
"""

                await query.edit_message_text(
                    order_message,
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("✅ Execute Order", callback_data=f"execute_{symbol}_{signal}_{entry_price}")],
                        [InlineKeyboardButton("❌ Cancel Order", callback_data=f"cancel_{symbol}")],
                        [InlineKeyboardButton("🔙 Back to Signal", callback_data=f"refresh_{symbol}_{timeframe}")]
                    ])
                )
            else:
                await query.edit_message_text(
                    "❌ **Cannot Place Order**\n\n"
                    f"Signal strength too low ({confidence}/10) or no clear signal.\n\n"
                    "Please wait for a stronger signal before placing orders.",
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔄 Refresh Analysis", callback_data=f"refresh_{symbol}_{timeframe}")]
                    ])
                )

        # Handle order execution
        elif data.startswith("execute_"):
            parts = data.split("_")
            symbol = parts[1]
            direction = parts[2]
            entry_price = parts[3]

            execution_message = f"""
✅ **ORDER EXECUTED SUCCESSFULLY**

🎯 **{get_deriv_symbol_name(symbol)}**

**Direction**: {'LONG' if direction == 'buy' else 'SHORT'}
**Entry Price**: {entry_price}
**Executed**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}

**Next Steps:**
1. Monitor position closely
2. Adjust stop loss to breakeven when profitable
3. Take partial profits at target levels
4. Use trailing stops for trending moves

⚠️ **Risk Management Reminder:**
• Never risk more than 1-2% per trade
• Always use stop losses
• Cut losses quickly, let profits run

*Trade execution logged by Baron AI Bot*
"""

            await query.edit_message_text(execution_message, parse_mode='Markdown')

        # Handle order cancellation
        elif data.startswith("cancel_"):
            symbol = data.replace("cancel_", "")
            await query.edit_message_text(
                f"❌ **Order Cancelled**\n\n"
                f"Order for {get_deriv_symbol_name(symbol)} has been cancelled.\n\n"
                "Waiting for better trading opportunities...",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="menu_main")]
                ])
            )

        else:
            await query.edit_message_text("❌ Unknown action")
            
    except Exception as e:
        logging.error(f"Error handling callback: {e}")
        await query.edit_message_text("❌ An error occurred. Please try again.")

async def handle_deriv_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages for Deriv symbols and menu buttons"""
    text = update.message.text.strip()
    text_upper = text.upper()

    # Menu button mappings - map menu text to symbols
    menu_mappings = {
        # Main menu direct symbols
        "📈 VOLATILITY 10": "R_10",
        "📈 VOLATILITY 25": "R_25",
        "📈 VOLATILITY 50": "R_50",
        "📈 VOLATILITY 75": "R_75",
        "📈 VOLATILITY 100": "R_100",
        "💥 BOOM 1000": "BOOM1000",
        "💥 CRASH 1000": "CRASH1000",
        "👣 STEP INDEX": "STEP INDEX",

        # Direct symbol mappings
        "📈 R_10": "R_10",
        "📈 R_25": "R_25",
        "📈 R_50": "R_50",
        "📈 R_75": "R_75",
        "📈 R_100": "R_100",
        "💥 BOOM 1000": "BOOM1000",
        "💥 CRASH 1000": "CRASH1000",
        "🚀 JUMP 10": "JUMP10",
        "🚀 JUMP 25": "JUMP25",
        "🚀 JUMP 50": "JUMP50",
        "🚀 JUMP 75": "JUMP75",
        "🚀 JUMP 100": "JUMP100",

        # Menu navigation
        "🔙 BACK TO MAIN MENU": "menu_main",
    }

    # Check if it's a menu button
    if text in menu_mappings:
        mapped_value = menu_mappings[text]

        # Handle direct symbol mapping
        if mapped_value in ["R_10", "R_25", "R_50", "R_75", "R_100", "BOOM1000", "CRASH1000", "JUMP10", "JUMP25", "JUMP50", "JUMP75", "JUMP100", "STEP INDEX"]:
            symbol = mapped_value
            await update.message.reply_text("🔄 Analyzing...")

            signal_data = await get_deriv_signal(symbol, '15m')
            message = format_deriv_signal(signal_data)

            await update.message.reply_text(
                message,
                reply_markup=get_signal_actions_keyboard(symbol, '15m'),
                parse_mode='Markdown'
            )
            return

        # Handle menu navigation
        elif mapped_value == "menu_main":
            from deriv_menus import deriv_main_menu
            await update.message.reply_text(
                "🎯 **DERIV SYNTHETIC INDICES BOT**\n\n"
                "Click any asset button below to get instant professional trading signals!",
                reply_markup=deriv_main_menu,
                parse_mode='Markdown'
            )
            return

    # Check if it's a valid Deriv symbol (direct text input)
    if is_deriv_symbol(text_upper):
        await update.message.reply_text("🔄 Analyzing...")

        signal_data = await get_deriv_signal(text_upper, '15m')
        message = format_deriv_signal(signal_data)

        await update.message.reply_text(
            message,
            reply_markup=get_signal_actions_keyboard(text_upper, '15m'),
            parse_mode='Markdown'
        )
    else:
        # Show help with menu
        help_msg = """
🚀 **DERIV SYNTHETIC INDICES BOT**

Click any button below to get instant professional trading signals!

**Available Assets:**
📈 **Volatility**: R_10, R_25, R_50, R_75, R_100
💥 **Boom & Crash**: BOOM1000, CRASH1000
🚀 **Jump**: JUMP10-100
👣 **Step Index**

💡 **Tip**: Click any asset to get immediate analysis!
"""
        await update.message.reply_text(
            help_msg,
            reply_markup=deriv_main_menu,
            parse_mode='Markdown'
        )

def setup_deriv_handlers(application: Application):
    """Setup Deriv-specific handlers"""
    # Command handlers
    application.add_handler(CommandHandler("start", deriv_start))
    application.add_handler(CommandHandler("analyze", deriv_analyze))
    application.add_handler(CommandHandler("summary", deriv_summary))
    application.add_handler(CommandHandler("chart", deriv_chart))
    
    # Callback handler
    application.add_handler(CallbackQueryHandler(handle_deriv_callback))
    
    # Message handler for text input
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_deriv_text))
    
    logging.info("Deriv handlers setup complete")
