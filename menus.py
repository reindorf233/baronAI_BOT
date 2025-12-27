"""
Persistent keyboards and menu definitions
"""
from telegram import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# Main menu with all trading pairs
main_menu = ReplyKeyboardMarkup([
    ["🥇 Gold (GC=F)", "🥇 Gold Spot", "₿ Bitcoin"],
    ["📈 EURUSD", "📈 GBPUSD", "📈 USDJPY"],
    ["📈 USDCHF", "📈 USDCAD", "📈 AUDUSD"],
    ["📈 NZDUSD", "📈 USDMXN", "📈 USDZAR"],
    ["📈 USDTRY", "🌍 USDAED", "🌍 USDARS"],
    ["🌍 USDAMD", "🌍 USDAZN", "🌍 USDBDT"],
    ["🌍 USDBGN", "🌍 USDBHD", "🌍 USDBND"],
    ["🛠 Custom Analysis", "📡 Bot Status", "⚙️ Settings"],
    ["📊 Synthetics", "⭐ 10/10 Signals", "📈 Daily Summary"]
], resize_keyboard=True)

# Synthetics submenu
synthetics_menu = ReplyKeyboardMarkup([
    ["📊 Volatility 75", "📊 Volatility 100"],
    ["📊 Boom Index", "📊 Crash Index"],
    ["📊 Step Index", "📊 Jump Index"],
    ["🔙 Back to Main Menu"]
], resize_keyboard=True)

# Settings submenu
settings_menu = ReplyKeyboardMarkup([
    ["⚙️ Toggle Martingale", "⚙️ Risk Management"],
    ["⚙️ Favorite Indices", "⚙️ Balance"],
    ["🔙 Back to Main Menu"]
], resize_keyboard=True)

# Forex submenu (expanded)
forex_menu = ReplyKeyboardMarkup([
    ["📈 EURUSD", "📈 GBPUSD", "📈 USDJPY"],
    ["📈 USDCHF", "📈 USDCAD", "📈 AUDUSD"],
    ["📈 NZDUSD", "📈 USDMXN", "📈 USDZAR"],
    ["📈 USDTRY", "🔙 Back to Main Menu"]
], resize_keyboard=True)

# Inline keyboard for signal actions
def get_signal_actions_keyboard(symbol: str) -> InlineKeyboardMarkup:
    """Get inline keyboard for signal actions"""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Take Trade", callback_data=f"trade_{symbol}"),
            InlineKeyboardButton("📊 More Info", callback_data=f"info_{symbol}")
        ],
        [
            InlineKeyboardButton("⭐ Favorite", callback_data=f"fav_{symbol}"),
            InlineKeyboardButton("❌ Dismiss", callback_data=f"dismiss_{symbol}")
        ]
    ])

# Inline keyboard for martingale toggle
def get_martingale_keyboard() -> InlineKeyboardMarkup:
    """Get inline keyboard for martingale settings"""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Enable", callback_data="martingale_on"),
            InlineKeyboardButton("❌ Disable", callback_data="martingale_off")
        ],
        [InlineKeyboardButton("🔙 Back", callback_data="settings_back")]
    ])

# Inline keyboard for risk management
def get_risk_keyboard() -> InlineKeyboardMarkup:
    """Get inline keyboard for risk percentage"""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("1%", callback_data="risk_1"),
            InlineKeyboardButton("2%", callback_data="risk_2"),
            InlineKeyboardButton("3%", callback_data="risk_3")
        ],
        [InlineKeyboardButton("🔙 Back", callback_data="settings_back")]
    ])

