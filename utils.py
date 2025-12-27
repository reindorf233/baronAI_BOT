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
from datetime import datetime
import pytz
import re
import random
from typing import Optional, Dict, Any

# === CONFIGURATION ===
USER_TIMEZONE = os.getenv("USER_TIMEZONE", "Africa/Accra")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
AI_APPROVAL_MIN_SCORE = int(os.getenv("AI_APPROVAL_MIN_SCORE", "7"))
MIN_SIGNAL_CONFIDENCE = int(os.getenv("MIN_SIGNAL_CONFIDENCE", "8"))
PERFECT_SIGNAL_ENABLED = os.getenv("PERFECT_SIGNAL_ENABLED", "true").lower() == "true"

# Webhook configuration
WEBHOOK_MODE = os.getenv("WEBHOOK_MODE", "false").lower() == "true"
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
PORT = int(os.getenv("PORT", "8443"))

# MT5 Configuration
MT5_LOGIN = os.getenv("MT5_LOGIN", "")
MT5_PASSWORD = os.getenv("MT5_PASSWORD", "")
MT5_SERVER = os.getenv("MT5_SERVER", "")

# Signal monitoring
MONITORING_ENABLED = True
MONITORED_SYMBOLS = ["GC=F", "XAUUSD", "EURUSD=X", "GBPUSD=X", "BTC-USD"]
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
    """Normalize symbol with proper suffixes"""
    symbol = symbol.upper().strip()

    # Handle forex pairs - add =X if missing
    forex_pairs = ['EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF', 'USDCAD', 'AUDUSD', 'NZDUSD',
                   'USDNOK', 'USDSEK', 'USDDKK', 'USDZAR', 'USDMXN', 'USDTRY',
                   'XAUUSD', 'USDAED', 'USDAMD', 'USDARS', 'USDAZN',
                   'USDBDT', 'USDBGN', 'USDBHD', 'USDBND']

    for pair in forex_pairs:
        if symbol == pair and not symbol.endswith('=X'):
            return symbol + '=X'

    # Handle special cases
    if symbol == 'GC=F':
        return 'GC=F'
    elif symbol == 'BTC-USD':
        return 'BTC-USD'
    elif symbol == 'XAUUSD':
        return 'GC=F'  # Use gold futures instead of spot

    return symbol


def normalize_yfinance_symbol(symbol: str) -> str:
    """Normalize symbol for yfinance API"""
    s = symbol.upper().strip()
    if s in {"GC=F", "BTC-USD"}:
        return s
    if "=" in s or "-" in s:
        return s
    # assume FX pair
    return s + "=X"


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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

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


# === Mock Data Functions ===

def get_mock_synthetic_data(index_name: str) -> Dict[str, Any]:
    """Generate mock data for synthetic indices"""
    base_prices = {
        "V75": 10000,
        "V100": 10000,
        "BOOM": 10000,
        "CRASH": 10000,
        "STEP": 10000,
        "JUMP": 10000,
    }
    base = base_prices.get(index_name.upper(), 10000)
    variation = random.uniform(-0.02, 0.02)
    current_price = base * (1 + variation)

    return {
        "price": current_price,
        "volume": random.randint(1000, 10000),
        "trend": random.choice(["up", "down", "sideways"]),
        "volatility": random.uniform(0.5, 2.0),
    }


def test_utils():
    """Simple test function for utils"""
    print("Testing utils...")
    assert normalize_symbol("EURUSD") == "EURUSD=X"
    assert normalize_symbol("GC=F") == "GC=F"
    assert normalize_symbol("BTC-USD") == "BTC-USD"
    print("✓ Utils tests passed")


if __name__ == "__main__":
    test_utils()