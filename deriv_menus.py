"""
Deriv Synthetic Indices Menu System
"""
from telegram import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# Main menu with Deriv synthetic indices only
deriv_main_menu = ReplyKeyboardMarkup([
    ["📈 Volatility 10", "📈 Volatility 25", "📈 Volatility 50"],
    ["📈 Volatility 75", "📈 Volatility 100", "💥 Boom 1000"],
    ["💥 Crash 1000", "👣 Step Index", "🚀 Jump Indices"],
    ["🔍 Custom Analysis", "📊 Market Summary", "⚙️ Settings"],
    ["⭐ Perfect Signals", "📈 Live Charts", "🎯 Breakout Analysis"]
], resize_keyboard=True)

# Volatility Indices submenu
volatility_menu = ReplyKeyboardMarkup([
    ["📈 R_10", "📈 R_25", "📈 R_50"],
    ["📈 R_75", "📈 R_100"],
    ["🔙 Back to Main Menu"]
], resize_keyboard=True)

# Boom & Crash submenu
boom_crash_menu = ReplyKeyboardMarkup([
    ["💥 Boom 1000", "💥 Boom 500", "💥 Boom 300"],
    ["💥 Crash 1000", "💥 Crash 500", "💥 Crash 300"],
    ["🔙 Back to Main Menu"]
], resize_keyboard=True)

# Jump Indices submenu
jump_menu = ReplyKeyboardMarkup([
    ["🚀 Jump 10", "🚀 Jump 25", "🚀 Jump 50"],
    ["🚀 Jump 75", "🚀 Jump 100"],
    ["🔙 Back to Main Menu"]
], resize_keyboard=True)

# Timeframe selection menu
timeframe_menu = InlineKeyboardMarkup([
    [InlineKeyboardButton("1 Minute", callback_data="tf_1m")],
    [InlineKeyboardButton("5 Minutes", callback_data="tf_5m")],
    [InlineKeyboardButton("15 Minutes", callback_data="tf_15m")],
    [InlineKeyboardButton("30 Minutes", callback_data="tf_30m")],
    [InlineKeyboardButton("1 Hour", callback_data="tf_1h")],
    [InlineKeyboardButton("4 Hours", callback_data="tf_4h")],
    [InlineKeyboardButton("1 Day", callback_data="tf_1d")]
])

# Analysis type menu
analysis_menu = InlineKeyboardMarkup([
    [InlineKeyboardButton("🎯 Breakout & Retest", callback_data="analysis_breakout")],
    [InlineKeyboardButton("📊 Technical Analysis", callback_data="analysis_technical")],
    [InlineKeyboardButton("🤖 AI Analysis", callback_data="analysis_ai")],
    [InlineKeyboardButton("📈 Complete Analysis", callback_data="analysis_complete")]
])

# Signal actions menu
signal_actions_menu = InlineKeyboardMarkup([
    [InlineKeyboardButton("📈 Live Chart", callback_data="action_chart")],
    [InlineKeyboardButton("🔄 Refresh", callback_data="action_refresh")],
    [InlineKeyboardButton("⏰ Set Alert", callback_data="action_alert")],
    [InlineKeyboardButton("📋 Detailed Report", callback_data="action_report")]
])

# Settings menu
deriv_settings_menu = InlineKeyboardMarkup([
    [InlineKeyboardButton("⚠️ Risk Management", callback_data="settings_risk")],
    [InlineKeyboardButton("🔔 Alert Preferences", callback_data="settings_alerts")],
    [InlineKeyboardButton("🤖 AI Settings", callback_data="settings_ai")],
    [InlineKeyboardButton("📊 Chart Settings", callback_data="settings_charts")]
])

# Risk management menu
risk_menu = InlineKeyboardMarkup([
    [InlineKeyboardButton("Low Risk (1%)", callback_data="risk_low")],
    [InlineKeyboardButton("Medium Risk (2%)", callback_data="risk_medium")],
    [InlineKeyboardButton("High Risk (3%)", callback_data="risk_high")],
    [InlineKeyboardButton("Custom Risk %", callback_data="risk_custom")]
])

# Alert preferences menu
alert_menu = InlineKeyboardMarkup([
    [InlineKeyboardButton("🔔 Enable Alerts", callback_data="alerts_enable")],
    [InlineKeyboardButton("🔕 Disable Alerts", callback_data="alerts_disable")],
    [InlineKeyboardButton("⭐ Perfect Signals Only", callback_data="alerts_perfect")],
    [InlineKeyboardButton("📈 All Signals", callback_data="alerts_all")]
])

# Perfect signals menu
perfect_signals_menu = InlineKeyboardMarkup([
    [InlineKeyboardButton("⭐ Enable Perfect Signals", callback_data="perfect_enable")],
    [InlineKeyboardButton("⭐ Disable Perfect Signals", callback_data="perfect_disable")],
    [InlineKeyboardButton("📊 View Recent Perfect Signals", callback_data="perfect_recent")],
    [InlineKeyboardButton("⚙️ Perfect Signal Settings", callback_data="perfect_settings")]
])

# Symbol mapping for menu callbacks
SYMBOL_MAPPING = {
    # Volatility Indices
    "R_10": "📈 Volatility 10",
    "R_25": "📈 Volatility 25", 
    "R_50": "📈 Volatility 50",
    "R_75": "📈 Volatility 75",
    "R_100": "📈 Volatility 100",
    
    # Boom & Crash
    "BOOM1000": "💥 Boom 1000",
    "BOOM500": "💥 Boom 500",
    "BOOM300": "💥 Boom 300",
    "CRASH1000": "💥 Crash 1000",
    "CRASH500": "💥 Crash 500",
    "CRASH300": "💥 Crash 300",
    
    # Other Indices
    "STEP INDEX": "👣 Step Index",
    "JUMP10": "🚀 Jump 10",
    "JUMP25": "🚀 Jump 25",
    "JUMP50": "🚀 Jump 50",
    "JUMP75": "🚀 Jump 75",
    "JUMP100": "🚀 Jump 100"
}

# Reverse mapping for callbacks
REVERSE_SYMBOL_MAPPING = {v: k for k, v in SYMBOL_MAPPING.items()}

def get_deriv_symbol_keyboard():
    """Get inline keyboard for Deriv symbol selection"""
    keyboard = []
    
    # Volatility indices row
    keyboard.append([
        InlineKeyboardButton("📈 R_10", callback_data="symbol_R_10"),
        InlineKeyboardButton("📈 R_25", callback_data="symbol_R_25"),
        InlineKeyboardButton("📈 R_50", callback_data="symbol_R_50")
    ])
    
    # More volatility + boom/crash
    keyboard.append([
        InlineKeyboardButton("📈 R_75", callback_data="symbol_R_75"),
        InlineKeyboardButton("📈 R_100", callback_data="symbol_R_100"),
        InlineKeyboardButton("💥 Boom 1000", callback_data="symbol_BOOM1000")
    ])
    
    # Crash and step
    keyboard.append([
        InlineKeyboardButton("💥 Crash 1000", callback_data="symbol_CRASH1000"),
        InlineKeyboardButton("👣 Step Index", callback_data="symbol_STEP INDEX"),
        InlineKeyboardButton("🚀 Jump 50", callback_data="symbol_JUMP50")
    ])
    
    return InlineKeyboardMarkup(keyboard)

def get_timeframe_keyboard():
    """Get inline keyboard for timeframe selection"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("1m", callback_data="tf_1m"),
         InlineKeyboardButton("5m", callback_data="tf_5m"),
         InlineKeyboardButton("15m", callback_data="tf_15m")],
        [InlineKeyboardButton("30m", callback_data="tf_30m"),
         InlineKeyboardButton("1h", callback_data="tf_1h"),
         InlineKeyboardButton("4h", callback_data="tf_4h")]
    ])

def get_analysis_type_keyboard():
    """Get inline keyboard for analysis type selection"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎯 Breakout Analysis", callback_data="analysis_breakout")],
        [InlineKeyboardButton("📊 Technical Analysis", callback_data="analysis_technical")],
        [InlineKeyboardButton("🤖 AI Enhanced", callback_data="analysis_ai")],
        [InlineKeyboardButton("📈 Complete Analysis", callback_data="analysis_complete")]
    ])

def get_signal_actions_keyboard(symbol: str, timeframe: str):
    """Get action keyboard for signal results"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📈 Live Chart", callback_data=f"chart_{symbol}_{timeframe}")],
        [InlineKeyboardButton("🔄 Refresh", callback_data=f"refresh_{symbol}_{timeframe}")],
        [InlineKeyboardButton("⏰ Set Alert", callback_data=f"alert_{symbol}_{timeframe}")],
        [InlineKeyboardButton("📋 Detailed Report", callback_data=f"report_{symbol}_{timeframe}")]
    ])

def get_deriv_categories_menu():
    """Get menu for Deriv symbol categories"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📈 Volatility Indices", callback_data="category_volatility")],
        [InlineKeyboardButton("💥 Boom & Crash", callback_data="category_boom_crash")],
        [InlineKeyboardButton("🚀 Jump Indices", callback_data="category_jump")],
        [InlineKeyboardButton("👣 Step Index", callback_data="category_step")]
    ])

def get_volatility_symbols_menu():
    """Get menu for volatility indices"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📈 R_10", callback_data="symbol_R_10"),
         InlineKeyboardButton("📈 R_25", callback_data="symbol_R_25")],
        [InlineKeyboardButton("📈 R_50", callback_data="symbol_R_50"),
         InlineKeyboardButton("📈 R_75", callback_data="symbol_R_75")],
        [InlineKeyboardButton("📈 R_100", callback_data="symbol_R_100")]
    ])

def get_boom_crash_symbols_menu():
    """Get menu for boom and crash indices"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💥 Boom 1000", callback_data="symbol_BOOM1000"),
         InlineKeyboardButton("💥 Boom 500", callback_data="symbol_BOOM500")],
        [InlineKeyboardButton("💥 Boom 300", callback_data="symbol_BOOM300"),
         InlineKeyboardButton("💥 Crash 1000", callback_data="symbol_CRASH1000")],
        [InlineKeyboardButton("💥 Crash 500", callback_data="symbol_CRASH500"),
         InlineKeyboardButton("💥 Crash 300", callback_data="symbol_CRASH300")]
    ])

def get_jump_symbols_menu():
    """Get menu for jump indices"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 Jump 10", callback_data="symbol_JUMP10"),
         InlineKeyboardButton("🚀 Jump 25", callback_data="symbol_JUMP25")],
        [InlineKeyboardButton("🚀 Jump 50", callback_data="symbol_JUMP50"),
         InlineKeyboardButton("🚀 Jump 75", callback_data="symbol_JUMP75")],
        [InlineKeyboardButton("🚀 Jump 100", callback_data="symbol_JUMP100")]
    ])
