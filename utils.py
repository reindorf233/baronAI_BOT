"""
Utility functions, helpers, logging, and configuration
"""
import logging
import os
import sys
import pickle
import sqlite3

# Platform-specific imports
try:
    import fcntl
except ImportError:
    fcntl = None  # Windows doesn't have fcntl
from pathlib import Path
from datetime import datetime, timedelta

# Verify timedelta import
try:
    _test_timedelta = timedelta(hours=1)
except NameError:
    logging.error("timedelta import failed in utils.py")
    raise ImportError("timedelta could not be imported")
import pytz
import re
import random
from typing import Optional, Dict, Any

# === CONFIGURATION ===
USER_TIMEZONE = os.getenv("USER_TIMEZONE", "Africa/Accra")

# Trade timing and reminder system
TRADE_REMINDERS = {}  # user_id -> list of reminder timestamps
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
AI_APPROVAL_MIN_SCORE = int(os.getenv("AI_APPROVAL_MIN_SCORE", "7"))
MIN_SIGNAL_CONFIDENCE = int(os.getenv("MIN_SIGNAL_CONFIDENCE", "8"))
PERFECT_SIGNAL_ENABLED = os.getenv("PERFECT_SIGNAL_ENABLED", "true").lower() == "true"

# Webhook configuration
WEBHOOK_MODE = os.getenv("WEBHOOK_MODE", "false").lower() == "true"
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
PORT = int(os.getenv("PORT", "8443"))

# Deriv API Configuration
DERIV_API_TOKEN = os.getenv("DERIV_API_TOKEN", "")
DERIV_APP_ID = os.getenv("DERIV_APP_ID", "12345")
DERIV_ENVIRONMENT = os.getenv("DERIV_ENVIRONMENT", "demo")
# Weltrade Demo: "Weltrade-Demo"
# Weltrade Live: "Weltrade-Live"
# IC Markets Demo: "ICMarkets-Demo"
# IC Markets Live: "ICMarkets-Live"

# Signal monitoring - Deriv Synthetic Indices only
MONITORING_ENABLED = True
MONITORED_SYMBOLS = ["R_10", "R_25", "R_50", "R_75", "R_100", "BOOM1000", "CRASH1000", "STEP INDEX"]
SIGNAL_COOLDOWN_MINUTES = 30
PERFECT_SIGNAL_COOLDOWN_MINUTES = 10

# File paths
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "bot_data.db"
STATE_PATH = DATA_DIR / "bot_state.pkl"
LOCK_FILE = DATA_DIR / "bot.lock"

# Global state
LAST_SIGNALS: Dict[str, datetime] = {}
LAST_PERFECT_SIGNALS: Dict[str, datetime] = {}
PERFECT_SIGNAL_USERS = set()


def setup_logging():
    """Setup logging configuration"""
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    # File logging
    log_file = DATA_DIR / "bot.log"
    logging.basicConfig(
        format=log_format,
        level=getattr(logging, log_level, logging.INFO),
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    logging.info("Logging initialized")


def validate_env():
    """Validate required environment variables"""
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN environment variable is required")

    if not GROQ_API_KEY:
        logging.warning("GROQ_API_KEY not set - AI features will be limited")
    else:
        # Validate API key format
        if not GROQ_API_KEY.startswith("gsk_"):
            logging.warning("GROQ_API_KEY appears to be invalid format (should start with 'gsk_')")
        elif len(GROQ_API_KEY) < 50:
            logging.warning("GROQ_API_KEY appears to be too short")
        else:
            logging.info("GROQ_API_KEY validation passed")


def acquire_lock() -> bool:
    """Acquire file lock to prevent multiple instances (Unix/Windows compatible)"""
    try:
        if sys.platform == "win32":
            # Windows: use msvcrt
            import msvcrt
            lock_file = open(LOCK_FILE, 'w')
            try:
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                return True
            except IOError:
                lock_file.close()
                return False
        else:
            # Unix: use fcntl
            if fcntl is None:
                return False
            lock_file = open(LOCK_FILE, 'w')
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
    except Exception as e:
        logging.warning(f"Could not acquire lock: {e}")
        return False


def release_lock():
    """Release file lock"""
    try:
        if LOCK_FILE.exists():
            LOCK_FILE.unlink()
    except Exception as e:
        logging.warning(f"Could not release lock: {e}")


def check_kill_zone() -> tuple[str, bool]:
    """Check if current time is within ICT Kill Zones (in EST)"""
    est = pytz.timezone('US/Eastern')
    now_est = datetime.now(est).time()

    london_start = datetime.strptime("02:00", "%H:%M").time()
    london_end = datetime.strptime("05:00", "%H:%M").time()
    ny_start = datetime.strptime("08:30", "%H:%M").time()
    ny_end = datetime.strptime("11:00", "%H:%M").time()

    if london_start <= now_est <= london_end:
        return "🇬🇧 London Kill Zone – High Probability", True
    elif ny_start <= now_est <= ny_end:
        return "🇺🇸 New York Kill Zone – High Probability", True
    else:
        return "😴 Outside Kill Zones – Lower Volatility", False


def normalize_symbol(symbol: str) -> str:
    """Normalize symbol for Deriv API"""
    symbol = symbol.upper().strip()
    
    # Handle common variations
    symbol_map = {
        'VOL10': 'R_10',
        'VOL25': 'R_25', 
        'VOL50': 'R_50',
        'VOL75': 'R_75',
        'VOL100': 'R_100',
        'BOOM': 'BOOM1000',
        'CRASH': 'CRASH1000',
        'STEP': 'STEP INDEX'
    }
    
    return symbol_map.get(symbol, symbol)


def normalize_yfinance_symbol(symbol: str) -> str:
    """Normalize symbol for Deriv API"""
    return normalize_symbol(symbol)


def parse_ai_confidence_score(ai_text: str) -> Optional[int]:
    """Parse confidence score from AI response"""
    if not ai_text:
        return None
    m = re.search(r"(?i)confidence\s*score\s*[:\-]?\s*(\d{1,2})\s*(?:/\s*10)?", ai_text)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return None
    m2 = re.search(r"(?<!\d)(\d{1,2})\s*/\s*10(?!\d)", ai_text)
    if m2:
        try:
            return int(m2.group(1))
        except ValueError:
            return None
    return None


def get_ai_commentary(symbol: str, direction: str, confidence: int, reasons: list) -> str:
    """Generate AI-like commentary for signals"""
    commentaries = [
        f"This {symbol} {direction.lower()} signal aligns with {', '.join(reasons[:2])}, showing {confidence*10}% confidence.",
        f"Strong {direction} opportunity detected for {symbol}. Key factors: {', '.join(reasons[:2])}.",
        f"{symbol} {direction} setup presents favorable risk/reward with {confidence}/10 confidence based on {reasons[0] if reasons else 'market analysis'}.",
        f"High-probability {direction} signal for {symbol} with confluence from {', '.join(reasons[:2]) if len(reasons) >= 2 else reasons[0] if reasons else 'technical analysis'}.",
    ]
    return random.choice(commentaries)


def format_last_candles_ohlc(df, n: int = 30) -> str:
    """Format last N candles as OHLC text"""
    try:
        tail = df.tail(n)
        lines = []
        for idx, row in tail.iterrows():
            ts = idx.strftime('%Y-%m-%d %H:%M') if hasattr(idx, 'strftime') else str(idx)
            lines.append(
                f"{ts} | O:{float(row['Open']):.5f} H:{float(row['High']):.5f} L:{float(row['Low']):.5f} C:{float(row['Close']):.5f}"
            )
        return "\n".join(lines)
    except Exception:
        return "(OHLC unavailable)"


def get_disclaimer() -> str:
    """Get trading disclaimer"""
    return "⚠️ *Disclaimer: Trading involves risk. Always use proper risk management. This is not financial advice.*"


# === Database Functions ===

def init_db():
    """Initialize SQLite database for persistent state"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # User preferences table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_prefs (
            user_id INTEGER PRIMARY KEY,
            favorite_indices TEXT,
            martingale_enabled INTEGER DEFAULT 0,
            perfect_signals_enabled INTEGER DEFAULT 0,
            risk_percent REAL DEFAULT 1.0,
            balance REAL DEFAULT 10000.0,
            timezone TEXT DEFAULT 'Africa/Accra',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Add timezone column if it doesn't exist (for existing databases)
    try:
        # Check if timezone column exists
        cursor.execute("PRAGMA table_info(user_prefs)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]

        if 'timezone' not in column_names:
            cursor.execute("ALTER TABLE user_prefs ADD COLUMN timezone TEXT DEFAULT 'Africa/Accra'")
            print("Added timezone column to user_prefs table")
    except sqlite3.OperationalError as e:
        print(f"Database operation failed: {e}")
        pass

    # Trade history table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trade_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            symbol TEXT,
            direction TEXT,
            entry REAL,
            exit REAL,
            profit REAL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()
    logging.info("Database initialized")


def get_user_pref(user_id: int, key: str, default: Any = None) -> Any:
    """Get user preference from database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT {} FROM user_prefs WHERE user_id = ?".format(key), (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else default


def set_user_pref(user_id: int, key: str, value: Any):
    """Set user preference in database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(f"""
        INSERT OR REPLACE INTO user_prefs (user_id, {key}, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
    """, (user_id, value))
    conn.commit()
    conn.close()


def get_user_balance(user_id: int) -> float:
    """Get user's simulated balance"""
    return get_user_pref(user_id, "balance", 10000.0)


def update_user_balance(user_id: int, amount: float):
    """Update user's simulated balance"""
    current = get_user_balance(user_id)
    new_balance = max(0, current + amount)
    set_user_pref(user_id, "balance", new_balance)
    return new_balance


def calculate_risk_amount(user_id: int, entry: float, stop_loss: float) -> float:
    """Calculate position size based on risk percentage"""
    risk_percent = get_user_pref(user_id, "risk_percent", 1.0) / 100.0
    balance = get_user_balance(user_id)
    risk_amount = balance * risk_percent
    risk_per_unit = abs(entry - stop_loss)
    if risk_per_unit > 0:
        position_size = risk_amount / risk_per_unit
        return min(position_size, balance * 0.1)  # Max 10% of balance
    return 0.0


# === Timezone and Trade Timing Functions ===

def get_user_timezone(user_id: int) -> str:
    """Get user's timezone preference"""
    return get_user_pref(user_id, "timezone", USER_TIMEZONE)


def set_user_timezone(user_id: int, timezone: str) -> bool:
    """Set user's timezone preference"""
    try:
        # Validate timezone
        import pytz
        pytz.timezone(timezone)
        set_user_pref(user_id, "timezone", timezone)
        return True
    except:
        return False


def calculate_trade_entry_time(current_time: datetime, kill_zone_active: bool, market_session: str) -> datetime:
    """Calculate optimal trade entry time based on market conditions"""
    # If in kill zone, entry can be immediate
    if kill_zone_active:
        return current_time

    # Otherwise, calculate next optimal entry window
    # For forex: typically 2 hours after session open
    if market_session == "London":
        # London session: optimal entry 2 hours after open
        return current_time.replace(hour=10, minute=0, second=0, microsecond=0)
    elif market_session == "New York":
        # New York session: optimal entry 1 hour after open
        return current_time.replace(hour=14, minute=30, second=0, microsecond=0)
    else:
        # Default: next hour
        next_hour = current_time + timedelta(hours=1)
        return next_hour.replace(minute=0, second=0, microsecond=0)


def add_trade_reminder(user_id: int, entry_time: datetime, symbol: str, direction: str):
    """Add a trade reminder for the user"""
    global TRADE_REMINDERS
    if user_id not in TRADE_REMINDERS:
        TRADE_REMINDERS[user_id] = []

    reminder = {
        'entry_time': entry_time,
        'symbol': symbol,
        'direction': direction,
        'reminder_sent': False,
        'created_at': datetime.now()
    }

    TRADE_REMINDERS[user_id].append(reminder)


def get_pending_reminders(user_id: int, current_time: datetime) -> list:
    """Get pending trade reminders for a user"""
    if user_id not in TRADE_REMINDERS:
        return []

    pending = []
    for reminder in TRADE_REMINDERS[user_id]:
        if not reminder['reminder_sent'] and reminder['entry_time'] <= current_time:
            pending.append(reminder)
            reminder['reminder_sent'] = True

    return pending


def format_entry_time_display(entry_time: datetime, user_timezone: str) -> str:
    """Format entry time for display in user's timezone"""
    try:
        import pytz
        user_tz = pytz.timezone(user_timezone)
        localized_time = entry_time.astimezone(user_tz)
        return localized_time.strftime("%Y-%m-%d %H:%M %Z")
    except:
        return entry_time.strftime("%Y-%m-%d %H:%M EST")


def get_current_market_session(current_time: datetime) -> str:
    """Determine current market session based on time"""
    hour = current_time.hour

    # London session: 8:00-16:00 GMT (3:00-11:00 EST)
    if 8 <= hour < 16:
        return "London"
    # New York session: 13:30-20:00 GMT (8:30-15:00 EST)
    elif 13 <= hour < 20:
        return "New York"
    # Asian session or overlap
    else:
        return "Asian/Overlap"


# === Mock Data Functions ===

def get_mock_synthetic_data(index_name: str) -> Dict[str, Any]:
    """Generate mock data for Deriv synthetic indices (fallback)"""
    # Base prices for different Deriv synthetic indices
    deriv_base_prices = {
        # Volatility Indices
        "R_10": 1000,
        "R_25": 1000,
        "R_50": 1000,
        "R_75": 1000,
        "R_100": 1000,
        
        # Boom & Crash Indices
        "BOOM1000": 1000,
        "BOOM500": 1000,
        "BOOM300": 1000,
        "CRASH1000": 1000,
        "CRASH500": 1000,
        "CRASH300": 1000,
        
        # Step Index
        "STEP INDEX": 1000,
        
        # Jump Indices
        "JUMP10": 1000,
        "JUMP25": 1000,
        "JUMP50": 1000,
        "JUMP75": 1000,
        "JUMP100": 1000,
        
        # Range Break Indices
        "RANGE BREAK 200": 1000,
        "RANGE BREAK 100": 1000,
        "RANGE BREAK 50": 1000
    }

    # Legacy synthetic indices (keeping for backward compatibility)
    legacy_base_prices = {
        "V75": 10000,
        "V100": 10000,
        "BOOM": 10000,
        "CRASH": 10000,
        "STEP": 10000,
        "JUMP": 10000,
    }

    # Combine all base prices
    base_prices = {**deriv_base_prices, **legacy_base_prices}

    # Get volatility characteristics for each asset type
    volatility_profiles = {
        # Volatility Indices - controlled volatility
        "R_10": {"vol_range": (0.01, 0.03), "volume_range": (5000, 15000)},
        "R_25": {"vol_range": (0.02, 0.05), "volume_range": (6000, 18000)},
        "R_50": {"vol_range": (0.03, 0.08), "volume_range": (7000, 20000)},
        "R_75": {"vol_range": (0.05, 0.12), "volume_range": (8000, 25000)},
        "R_100": {"vol_range": (0.08, 0.20), "volume_range": (10000, 30000)},
        
        # Boom & Crash - high volatility
        "BOOM1000": {"vol_range": (0.15, 0.40), "volume_range": (15000, 50000)},
        "BOOM500": {"vol_range": (0.12, 0.35), "volume_range": (12000, 45000)},
        "BOOM300": {"vol_range": (0.10, 0.30), "volume_range": (10000, 40000)},
        "CRASH1000": {"vol_range": (0.15, 0.40), "volume_range": (15000, 50000)},
        "CRASH500": {"vol_range": (0.12, 0.35), "volume_range": (12000, 45000)},
        "CRASH300": {"vol_range": (0.10, 0.30), "volume_range": (10000, 40000)},
        
        # Step Index - gradual movements
        "STEP INDEX": {"vol_range": (0.02, 0.06), "volume_range": (5000, 15000)},
        
        # Jump Indices - sudden movements
        "JUMP10": {"vol_range": (0.05, 0.15), "volume_range": (8000, 20000)},
        "JUMP25": {"vol_range": (0.08, 0.20), "volume_range": (10000, 25000)},
        "JUMP50": {"vol_range": (0.12, 0.30), "volume_range": (12000, 35000)},
        "JUMP75": {"vol_range": (0.15, 0.40), "volume_range": (15000, 45000)},
        "JUMP100": {"vol_range": (0.20, 0.50), "volume_range": (18000, 55000)}
    }

    base = base_prices.get(index_name.upper(), 10000)
    profile = volatility_profiles.get(index_name.upper(),
                                     {"vol_range": (0.1, 0.3), "volume_range": (5000, 20000)})

    # Generate price variation based on asset volatility
    vol_min, vol_max = profile["vol_range"]
    volatility = random.uniform(vol_min, vol_max)
    variation = random.uniform(-volatility, volatility)
    current_price = base * (1 + variation)

    # Generate volume based on asset characteristics
    vol_min, vol_max = profile["volume_range"]
    volume = random.randint(vol_min, vol_max)

    # Determine trend based on volatility (higher vol = more extreme trends)
    if volatility > 0.5:
        trend = random.choice(["up", "down", "volatile"])
    else:
        trend = random.choice(["up", "down", "sideways"])

    return {
        "price": current_price,
        "volume": volume,
        "trend": trend,
        "volatility": volatility * 100,  # Convert to percentage
        "asset_type": "syntX" if index_name.upper() in syntx_base_prices else "synthetic",
    }


def test_api_key():
    """Test API key connectivity"""
    if not GROQ_API_KEY:
        print("No API key configured")
        return False

    try:
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)

        # Simple test request
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": "Test"}],
            max_tokens=5
        )

        if response.choices and response.choices[0].message.content:
            print("SUCCESS: API key is valid and working")
            return True
        else:
            print("FAILED: API returned empty response")
            return False

    except Exception as e:
        error_str = str(e).lower()
        if "invalid" in error_str and "key" in error_str:
            print("FAILED: API key is invalid or expired")
        elif "unauthorized" in error_str:
            print("FAILED: API key unauthorized")
        elif "quota" in error_str:
            print("FAILED: API quota exceeded")
        else:
            print(f"FAILED: API connection error: {str(e)[:100]}")
        return False


def test_utils():
    """Simple test function for utils"""
    print("Testing utils...")
    assert normalize_symbol("EURUSD") == "EURUSD=X"
    assert normalize_symbol("GC=F") == "GC=F"
    assert normalize_symbol("BTC-USD") == "BTC-USD"
    print("✓ Utils tests passed")


if __name__ == "__main__":
    test_utils()
    print()
    test_api_key()