import logging
import os
import yfinance as yf
import pandas as pd
from datetime import datetime
import re
import pytz
import asyncio
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from groq import Groq
try:
    import MetaTrader5 as mt5
except Exception:
    mt5 = None

# === CONFIGURATION ===
USER_TIMEZONE = "Africa/Accra"  # Ghana timezone
TOKEN = "8455972124:AAFJ8sWuQGEbKFxIktXDBj_CQyU84A3pbMU"  # Bot token configured
GROQ_API_KEY = "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"  # Groq API key (free tier)
AI_APPROVAL_MIN_SCORE = 7

# Signal monitoring settings
MONITORING_ENABLED = True
MIN_SIGNAL_CONFIDENCE = 8  # Only send alerts for 8/10+ confidence
PERFECT_SIGNAL_ENABLED = True  # Send instant alerts for 10/10 + AI Approved
MONITORED_SYMBOLS = ["GC=F", "XAUUSD", "EURUSD=X", "GBPUSD=X", "BTC-USD"]  # Key symbols to monitor
LAST_SIGNALS = {}  # Track last signals to avoid duplicates
LAST_PERFECT_SIGNALS = {}  # Track last perfect signals separately
SIGNAL_COOLDOWN_MINUTES = 30  # Wait 30 minutes before sending same signal again
PERFECT_SIGNAL_COOLDOWN_MINUTES = 10  # Shorter cooldown for perfect signals
PERFECT_SIGNAL_USERS = set()  # Users who want instant perfect signal notifications

MT5_LOGIN = os.getenv("MT5_LOGIN", "")
MT5_PASSWORD = os.getenv("MT5_PASSWORD", "")
MT5_SERVER = os.getenv("MT5_SERVER", "")

# Check if running on Render (cloud environment)
IS_RENDER = os.getenv("RENDER", "") != ""

# Only use MT5 if not on Render and credentials are provided
USE_MT5_FIRST = (mt5 is not None) and (not IS_RENDER) and all([MT5_LOGIN, MT5_PASSWORD, MT5_SERVER])

def format_last_candles_ohlc(df: pd.DataFrame, n: int = 30) -> str:
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


def compute_strategy_recommendation(
    *,
    current_price: float,
    htf_bias: str,
    effective_bias: str,
    structure: str,
    mss_direction: str | None,
    in_kill_zone: bool,
    data_15m: pd.DataFrame,
    fvg: dict | None,
):
    score = 0
    reasons: list[str] = []

    # EMA200 HTF bias
    if "Bullish" in htf_bias:
        score += 2
        reasons.append("HTF EMA200 bullish")
    elif "Bearish" in htf_bias:
        score -= 2
        reasons.append("HTF EMA200 bearish")

    # Market structure / effective bias
    if effective_bias == "bullish":
        score += 2
        reasons.append("Structure bullish")
    elif effective_bias == "bearish":
        score -= 2
        reasons.append("Structure bearish")

    # MSS confirmation
    if mss_direction == "bullish":
        score += 1
        reasons.append("Bullish MSS")
    elif mss_direction == "bearish":
        score -= 1
        reasons.append("Bearish MSS")

    # Simple momentum (15m)
    try:
        sma20 = float(data_15m['Close'].rolling(20).mean().iloc[-1])
        if current_price > sma20:
            score += 1
            reasons.append("15m momentum above SMA20")
        else:
            score -= 1
            reasons.append("15m momentum below SMA20")
    except Exception:
        pass

    # FVG alignment (if present)
    if fvg is not None:
        if fvg.get('direction') == 'bullish':
            score += 1
            reasons.append("Bullish FVG present")
        elif fvg.get('direction') == 'bearish':
            score -= 1
            reasons.append("Bearish FVG present")

        # extra boost when FVG aligns with EMA200 bias
        if (("Bullish" in htf_bias) and (fvg.get('direction') == 'bullish')) or (("Bearish" in htf_bias) and (fvg.get('direction') == 'bearish')):
            score += 1
            reasons.append("FVG aligns with EMA200")

    # Kill zone confidence boost (not direction)
    if in_kill_zone:
        reasons.append("In Kill Zone")

    recommendation = "BUY" if score >= 0 else "SELL"
    # map score to 1..10 confidence
    confidence = max(1, min(10, int(round(5 + score))))
    return recommendation, confidence, reasons


def _mt5_timeframe(tf: str):
    if mt5 is None:
        raise ValueError("MetaTrader5 is not available")
    tf = tf.upper()
    if tf in ("15M", "M15"):
        return mt5.TIMEFRAME_M15
    if tf in ("60M", "1H", "H1"):
        return mt5.TIMEFRAME_H1
    raise ValueError(f"Unsupported timeframe: {tf}")


def mt5_connect() -> bool:
    if mt5 is None:
        return False
    if mt5.terminal_info() is not None and mt5.account_info() is not None:
        return True
    if not mt5.initialize():
        return False
    if not MT5_LOGIN or not MT5_PASSWORD or not MT5_SERVER:
        return False
    try:
        login_int = int(MT5_LOGIN)
    except ValueError:
        return False
    return bool(mt5.login(login_int, password=MT5_PASSWORD, server=MT5_SERVER))


def fetch_candles_mt5(symbol: str, timeframe: str, bars: int) -> pd.DataFrame:
    if mt5 is None:
        return pd.DataFrame()
    if not mt5_connect():
        return pd.DataFrame()

    mt5_symbol = symbol.replace("=X", "").upper()
    if not mt5.symbol_select(mt5_symbol, True):
        return pd.DataFrame()

    tf = _mt5_timeframe(timeframe)
    rates = mt5.copy_rates_from_pos(mt5_symbol, tf, 0, int(bars))
    if rates is None or len(rates) == 0:
        return pd.DataFrame()

    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df = df.set_index("time")
    df = df.rename(columns={
        "open": "Open",
        "high": "High",
        "low": "Low",
        "close": "Close",
        "tick_volume": "Volume",
    })
    # Keep only standard OHLCV if present
    cols = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in df.columns]
    return df[cols].dropna()


def normalize_yfinance_symbol(symbol: str) -> str:
    s = symbol.upper().strip()
    if s in {"GC=F", "BTC-USD"}:
        return s
    if "=" in s or "-" in s:
        return s
    # assume FX pair
    return s + "=X"


def fetch_candles(symbol: str, timeframe: str, bars: int) -> pd.DataFrame:
    # Prefer MT5 for broker-grade candles
    if USE_MT5_FIRST:
        df_mt5 = fetch_candles_mt5(symbol, timeframe=timeframe, bars=bars)
        if not df_mt5.empty:
            return df_mt5

    # Fallback to yfinance
    yf_symbol = normalize_yfinance_symbol(symbol)
    interval = "15m" if timeframe.upper() in ("15M", "M15") else "60m"
    period = "60d" if interval == "15m" else "200d"
    df = yf.download(yf_symbol, period=period, interval=interval, progress=False)
    if isinstance(df, pd.DataFrame) and not df.empty:
        return df.dropna()
    return pd.DataFrame()

# Setup Logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Persistent Keyboard Menu
main_menu = ReplyKeyboardMarkup([
    ["🥇 Gold (GC=F)", "🥇 Gold Spot", "₿ Bitcoin"],
    ["📈 EURUSD", "📈 GBPUSD", "📈 USDJPY"],
    ["📈 USDCHF", "📈 USDCAD", "📈 AUDUSD"],
    ["📈 NZDUSD", "📈 USDMXN", "📈 USDZAR"],
    ["🌍 USDAED", "🌍 USDARS", "🌍 USDAMD"],
    ["🌍 USDAZN", "🌍 USDBDT", "🌍 USDBGN"],
    ["🌍 USDBHD", "🌍 USDBND", "📈 USDTRY"],
    ["🛠 Custom Analysis", "📡 Bot Status"]
], resize_keyboard=True)

def check_kill_zone():
    """Checks if current time is within ICT Kill Zones (in EST)"""
    est = pytz.timezone('US/Eastern')
    now_est = datetime.now(est).time()
    
    london_start = datetime.strptime("02:00", "%H:%M").time()
    london_end = datetime.strptime("05:00", "%H:%M").time()
    ny_start = datetime.strptime("08:30", "%H:%M").time()
    ny_end = datetime.strptime("11:00", "%H:%M").time()

    if london_start <= now_est <= london_end:
        return "🇬🇧 London Kill Zone – High Probability"
    elif ny_start <= now_est <= ny_end:
        return "🇺🇸 New York Kill Zone – High Probability"
    else:
        return "😴 Outside Kill Zones – Lower Volatility"

def get_swings(df, strength=5):
    """Safe swing high/low detection"""
    if len(df) < strength * 2 + 1:
        return [], []
    df = df.dropna().reset_index(drop=True)
    if len(df) < strength * 2 + 1:
        return [], []
    
    highs = []
    lows = []
    high_series = df['High']
    low_series = df['Low']
    
    for i in range(strength, len(df) - strength):
        left = slice(i - strength, i)
        right = slice(i + 1, i + strength + 1)
        current_high = high_series.iloc[i]
        current_low = low_series.iloc[i]
        
        if current_high >= high_series[left].max() and current_high >= high_series[right].max():
            highs.append((df.index[i], current_high))
        if current_low <= low_series[left].min() and current_low <= low_series[right].min():
            lows.append((df.index[i], current_low))
    
    return highs[-20:], lows[-20:]

def normalize_symbol(symbol):
    """Normalize symbol with proper suffixes"""
    symbol = symbol.upper()
    
    # Handle forex pairs - add =X if missing
    forex_pairs = ['EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF', 'USDCAD', 'AUDUSD', 'NZDUSD',
                   'USDNOK', 'USDSEK', 'USDDKK', 'USDZAR', 'USDMXN', 'USDTRY',
                   'XAUUSD', 'MBT-USD', 'USDAED', 'USDAMD', 'USDARS', 'USDAZN',
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

def get_gemini_prediction(symbol, data_summary):
    """Get AI trade validation from Groq (Llama 3.1)"""
    try:
        client = Groq(api_key=GROQ_API_KEY)
        
        prompt = f"""As an ICT expert, analyze this {symbol} data:
{data_summary}

Detected ICT patterns: FVGs, Market Structure Shifts, EMA200 bias, Kill Zones.

Check if the FVG aligns with the Market Structure Shift and the 200 EMA. 
Provide a Confidence Score (1-10) and a 2-sentence reasoning on whether to enter this trade.

Format your response as:
Confidence Score: X/10
Reasoning: [Your 2-sentence analysis]"""

        response = client.chat.completions.create(
            model="llama-3.1-70b-versatile",
            messages=[
                {"role": "system", "content": "You are an expert ICT/SMC trader providing trade analysis."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=200,
            temperature=0.3
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"AI Analysis Error: {str(e)}"

def parse_gemini_confidence_score(ai_text: str):
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

async def send_perfect_signal_alert(application, symbol, analysis, user_id):
    """Monitor for strong signals and send alerts"""
    if not MONITORING_ENABLED:
        return
    
    current_time = datetime.now()
    
    for symbol in MONITORED_SYMBOLS:
        try:
            # Get analysis for each symbol
            analysis = get_smc_prediction(symbol)
            
            # Extract confidence from analysis
            confidence_match = re.search(r"Strategy Confidence: (\d+)/10", analysis)
            if confidence_match:
                confidence = int(confidence_match.group(1))
                
                # Check if it's a strong signal
                if confidence >= MIN_SIGNAL_CONFIDENCE:
                    # Check cooldown to avoid spam
                    last_signal_time = LAST_SIGNALS.get(symbol)
                    if (last_signal_time is None or 
                        (current_time - last_signal_time).total_seconds() > SIGNAL_COOLDOWN_MINUTES * 60):
                        
                        # Extract recommendation
                        rec_match = re.search(r"▶️ Recommendation: \*\*(\w+)\*\*", analysis)
                        recommendation = rec_match.group(1) if rec_match else "UNKNOWN"
                        
                        # Extract AI approval
                        ai_approval = "No AI"
                        if "✅ AI Approved" in analysis:
                            ai_approval = "✅ AI Approved"
                        elif "⚠️ AI Not Approved" in analysis:
                            ai_approval = "⚠️ AI Not Approved"
                        
                        # Create alert message
                        alert_msg = f"""🚨 **STRONG SIGNAL ALERT** 🚨

 **{symbol}**
▶️ **{recommendation}**
 **Confidence: {confidence}/10**
🤖 **AI: {ai_approval}**
🕐 **{current_time.strftime('%H:%M')} EST**

Tap the symbol below for full analysis:
{symbol}

⚠️ Always verify with your own analysis."""
                        
                        # Send to all users (you can customize this)
                        # For now, we'll store it and you can retrieve with /alerts
                        LAST_SIGNALS[symbol] = current_time
                        
                        # Log the signal
                        print(f"🚨 STRONG SIGNAL: {symbol} {recommendation} @ {confidence}/10")
                        
        except Exception as e:
            print(f"Error monitoring {symbol}: {str(e)}")
            continue

async def start_monitoring(application):
    """Start the signal monitoring loop"""
    while MONITORING_ENABLED:
        try:
            await check_strong_signals(application)
            await asyncio.sleep(300)  # Check every 5 minutes
        except Exception as e:
            print(f"Monitoring error: {str(e)}")
            await asyncio.sleep(60)  # Wait 1 minute on error

async def alerts_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show recent strong signals"""
    msg = "🚨 **Recent Strong Signals** 🚨\n\n"
    
    if not LAST_SIGNALS:
        msg += "No strong signals detected yet.\n"
        msg += f"Monitoring: {len(MONITORED_SYMBOLS)} symbols\n"
        msg += f"Min confidence: {MIN_SIGNAL_CONFIDENCE}/10"
    else:
        for symbol, time in LAST_SIGNALS.items():
            time_str = time.strftime('%H:%M')
            msg += f" {symbol} - {time_str} EST\n"
    
    msg += "\n⚙️ Monitoring runs automatically every 5 minutes"
    await update.message.reply_text(msg, parse_mode='Markdown')

async def toggle_monitoring(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Toggle signal monitoring on/off"""
    global MONITORING_ENABLED
    MONITORING_ENABLED = not MONITORING_ENABLED
    status = "ON" if MONITORING_ENABLED else "OFF"
    
    msg = f"🔧 **Signal Monitoring: {status}**\n\n"
    msg += f" Monitoring {len(MONITORED_SYMBOLS)} symbols\n"
    msg += f" Min confidence: {MIN_SIGNAL_CONFIDENCE}/10\n"
    msg += f"⏰ Cooldown: {SIGNAL_COOLDOWN_MINUTES} minutes"
    
    await update.message.reply_text(msg, parse_mode='Markdown')

def get_smc_prediction(symbol: str):
    """Complete ICT/SMC analysis function"""
    try:
        symbol = symbol.upper().strip()

        # Get 15m data for FVG analysis
        # 60 days of 15m candles ~= 5760 bars
        data_15m = fetch_candles(symbol, timeframe="M15", bars=6000)
        
        # Error handling for empty data
        if data_15m.empty:
            return "❌ Market is currently closed or ticker invalid."
        if len(data_15m) < 50:
            return "❌ No recent data – market closed or limited history for this pair."

        current_price = float(data_15m['Close'].iloc[-1])

        # Get 1h data for HTF analysis
        htf_data = fetch_candles(symbol, timeframe="H1", bars=5000)
        
        # Error handling for empty HTF data
        if htf_data.empty:
            return "❌ Market is currently closed or ticker invalid."
        if len(htf_data) < 50:
            return "❌ Insufficient historical data for analysis."

        # HTF Bias (EMA200)
        htf_bias = "Neutral ⚪️"
        if len(htf_data) >= 200:
            ema200 = float(htf_data['Close'].ewm(span=200, adjust=False).mean().iloc[-1])
            current_price_val = float(current_price)
            ema200_val = float(ema200)
            if current_price_val > ema200_val * 1.001:
                htf_bias = "Bullish 🟢"
            elif current_price_val < ema200_val * 0.999:
                htf_bias = "Bearish 🔴"

        # Market Structure Analysis
        structure = "Insufficient data for structure analysis"
        effective_bias = "neutral"
        mss_direction = None
        
        try:
            if len(htf_data) >= 50:
                highs, lows = get_swings(htf_data, strength=5)
                
                if len(highs) >= 2 and len(lows) >= 2:
                    last_high = highs[-1][1]
                    prev_high = highs[-2][1]
                    last_low = lows[-1][1]
                    prev_low = lows[-2][1]

                    current_price_val = float(current_price)
                    last_low_val = float(last_low)
                    prev_low_val = float(prev_low)
                    last_high_val = float(last_high)
                    prev_high_val = float(prev_high)
                    
                    hh = last_high_val > prev_high_val
                    hl = last_low_val > prev_low_val
                    lh = last_high_val < prev_high_val
                    ll = last_low_val < prev_low_val

                    if (hh and hl):
                        base = "Bullish (HH + HL)"
                        if current_price_val < (last_low_val * 0.999):  # Broke structure low
                            structure = base + " ⚠️ Bearish MSS"
                            effective_bias = "bearish"
                            mss_direction = "bearish"
                        else:
                            structure = base
                            effective_bias = "bullish"
                    elif (lh and ll):
                        base = "Bearish (LH + LL)"
                        if current_price_val > (last_high_val * 1.001):  # Broke structure high
                            structure = base + " ⚠️ Bullish MSS"
                            effective_bias = "bullish"
                            mss_direction = "bullish"
                        else:
                            structure = base
                            effective_bias = "bearish"
                    else:
                        structure = "Ranging / Internal Structure"
                        effective_bias = "neutral"
        except:
            structure = "Structure analysis unavailable"

        # Kill Zone Status
        kz_status = check_kill_zone()
        in_kill_zone = "High Probability" in kz_status

        # FVG Detection
        fvg = None
        max_lookback = min(400, len(data_15m) - 3)
        gap_threshold = max(0.00005 * current_price, 0.0001)
        
        for k in range(max_lookback):
            c1_idx = len(data_15m) - 3 - k
            if c1_idx < 0:
                break
            c3_idx = c1_idx + 2

            c1_high = data_15m['High'].iloc[c1_idx]
            c1_low = data_15m['Low'].iloc[c1_idx]
            c3_high = data_15m['High'].iloc[c3_idx]
            c3_low = data_15m['Low'].iloc[c3_idx]

            c1_high_val = float(c1_high)
            c1_low_val = float(c1_low)
            c3_high_val = float(c3_high)
            c3_low_val = float(c3_low)
            current_price_val = float(current_price)
            
            # Bullish FVG
            if ((c3_low_val > (c1_high_val + gap_threshold)) & (current_price_val >= c3_low_val)):
                fvg = {
                    'direction': 'bullish',
                    'fvg_low': c1_high,
                    'fvg_high': c3_low,
                    'c1_low': c1_low,
                    'candle_time': data_15m.index[c3_idx]
                }
                break

            # Bearish FVG
            elif ((c3_high_val < (c1_low_val - gap_threshold)) & (current_price_val <= c3_high_val)):
                fvg = {
                    'direction': 'bearish',
                    'fvg_low': c3_high,
                    'fvg_high': c1_low,
                    'c1_high': c1_high,
                    'candle_time': data_15m.index[c3_idx]
                }
                break

        # Time Display
        est = pytz.timezone('US/Eastern')
        now_est = datetime.now(est)
        user_tz = pytz.timezone(USER_TIMEZONE)
        now_user = datetime.now(user_tz)

        # Strategy Engine (Mode 2): always output BUY/SELL
        recommendation, strat_confidence, strat_reasons = compute_strategy_recommendation(
            current_price=current_price,
            htf_bias=htf_bias,
            effective_bias=effective_bias,
            structure=structure,
            mss_direction=mss_direction,
            in_kill_zone=in_kill_zone,
            data_15m=data_15m,
            fvg=fvg,
        )

        # Build Analysis Message
        msg = f"🔍 *ICT/SMC Analysis: {symbol}*\n\n"
        msg += f"📅 EST Time: {now_est.strftime('%Y-%m-%d %H:%M %Z')}\n"
        msg += f"🕐 Your Time: {now_user.strftime('%Y-%m-%d %H:%M %Z')}\n"
        msg += f"💹 Current Price: {current_price:.5f}\n"
        msg += f"📈 HTF Bias (EMA200): {htf_bias}\n"
        msg += f" Market Structure: {structure}\n"
        msg += f"⏰ Session: {kz_status}\n\n"

        msg += "🧠 **STRATEGY ENGINE**\n"
        msg += f"▶️ Recommendation: **{recommendation}**\n"
        msg += f" Strategy Confidence: {strat_confidence}/10\n"
        if strat_reasons:
            msg += f"🧾 Reasons: {', '.join(strat_reasons)}\n\n"
        else:
            msg += "\n"

        if fvg:
            # Use strategy engine recommendation for signal display
            dir_emoji = "🟢" if recommendation == "BUY" else "🔴"
            dir_text = recommendation

            # Confluence Analysis
            confluences = []
            if in_kill_zone:
                confluences.append("Kill Zone")
            if (("Bullish" in htf_bias) & (fvg['direction'] == 'bullish')) | (("Bearish" in htf_bias) & (fvg['direction'] == 'bearish')):
                confluences.append("EMA200 Alignment")
            if fvg['direction'] == effective_bias:
                confluences.append("Structure Alignment")
            if mss_direction == fvg['direction']:
                confluences.append("Post-MSS Confirmation")

            # Trade Setup - use recommendation direction
            entry = (float(fvg['fvg_low']) + float(fvg['fvg_high'])) / 2  # 50% of FVG
            sl = float(fvg['c1_low']) * 0.999 if recommendation == "BUY" else float(fvg['c1_high']) * 1.001
            risk = abs(entry - sl)
            tp_2r = entry + risk * 2 if recommendation == "BUY" else entry - risk * 2

            msg += f"{dir_emoji} **{dir_text} Signal**\n"
            if confluences:
                msg += f"✅ Confluences: {', '.join(confluences)}\n\n"
            else:
                msg += "\n"

            msg += f" FVG Range: {float(fvg['fvg_low']):.5f} – {float(fvg['fvg_high']):.5f}\n"
            msg += f"🕐 FVG Formed: {fvg['candle_time'].strftime('%Y-%m-%d %H:%M')} EST\n"
            msg += f"▶️ Entry (50% FVG): {entry:.5f}\n"
            msg += f"🚫 Stop Loss: {sl:.5f}\n"
            msg += f"🎯 Take Profit (1:2): {tp_2r:.5f}\n"
            msg += f"📝 Best executed during Kill Zone with price retracing into FVG.\n"
            
            # Get AI Trade Validation
            ohlc_text = format_last_candles_ohlc(data_15m, n=30)
            data_summary = f"""
Last 30 candles (15m OHLC):
{ohlc_text}

Current Price: {current_price:.5f}
HTF Bias: {htf_bias}
Market Structure: {structure}
Session: {kz_status}
Strategy Recommendation: {recommendation}
Strategy Confidence: {strat_confidence}/10
FVG Detected: {'Yes' if fvg else 'No'}
"""
            if fvg:
                data_summary += f"""
FVG Direction: {fvg['direction']}
FVG Range: {float(fvg['fvg_low']):.5f} - {float(fvg['fvg_high']):.5f}
Entry: {(float(fvg['fvg_low']) + float(fvg['fvg_high'])) / 2:.5f}
Stop Loss: {sl:.5f}
Take Profit: {tp_2r:.5f}
"""
            
            ai_prediction = get_gemini_prediction(symbol, data_summary)
            score = parse_gemini_confidence_score(ai_prediction)
            if score is not None:
                ai_status = "✅ AI Approved" if score >= AI_APPROVAL_MIN_SCORE else "⚠️ AI Not Approved"
                msg += f"\n🤖 **AI PREDICTION**\n{ai_status} ({score}/10)\n{ai_prediction}\n"
            else:
                msg += f"\n🤖 **AI PREDICTION**\n{ai_prediction}\n"

        else:
            msg += "⚪️ **No Valid FVG Setup**\n"
            msg += "→ Wait for strong displacement to form a fresh FVG.\n"
            if "MSS" in structure:
                msg += "→ Recent Market Structure Shift detected – watch for new FVG.\n"
            
            # Get AI Trade Validation even without FVG
            ohlc_text = format_last_candles_ohlc(data_15m, n=30)
            data_summary = f"""
Last 30 candles (15m OHLC):
{ohlc_text}

Current Price: {current_price:.5f}
HTF Bias: {htf_bias}
Market Structure: {structure}
Session: {kz_status}
Strategy Recommendation: {recommendation}
Strategy Confidence: {strat_confidence}/10
FVG Detected: No
"""
            ai_prediction = get_gemini_prediction(symbol, data_summary)
            score = parse_gemini_confidence_score(ai_prediction)
            if score is not None:
                ai_status = "✅ AI Approved" if score >= AI_APPROVAL_MIN_SCORE else "⚠️ AI Not Approved"
                msg += f"\n🤖 **AI PREDICTION**\n{ai_status} ({score}/10)\n{ai_prediction}\n"
            else:
                msg += f"\n🤖 **AI PREDICTION**\n{ai_prediction}\n"

        msg += "\n⚠️ *Disclaimer: Trading involves risk. Always use proper risk management.*"

        return msg

    except Exception as e:
        return f"⚠️ Error: {str(e)}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Welcome message with menu"""
    msg = (
        "🚀 *ICT/SMC Trading Bot*\n\n"
        "Advanced Market Structure Analysis:\n"
        "• Fair Value Gaps (FVG) Detection\n"
        "• Market Structure Shift (MSS)\n"
        "• EMA 200 Trend Filter\n"
        "• ICT Kill Zone Timing\n"
        "• 🚨 AUTO SIGNAL ALERTS\n\n"
        "📱 *Commands:*\n"
        "/alerts - View recent strong signals\n"
        "/monitor - Toggle signal monitoring\n"
        "/analyze [symbol] - Custom analysis\n\n"
        "Select a signal below:"
    )
    await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=main_menu)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle menu button presses and custom input"""
    text = update.message.text

    # Handle custom symbol input
    if context.user_data.get('waiting_for_symbol'):
        symbol = text.upper()
        result = get_smc_prediction(symbol)
        await update.message.reply_text(result, parse_mode='Markdown', reply_markup=main_menu)
        context.user_data['waiting_for_symbol'] = False
        return

    # Menu button handlers
    if text == "🥇 Gold (GC=F)":
        result = get_smc_prediction("GC=F")
        await update.message.reply_text(result, parse_mode='Markdown', reply_markup=main_menu)

    elif text == "🥇 Gold Spot":
        result = get_smc_prediction("XAUUSD")
        await update.message.reply_text(result, parse_mode='Markdown', reply_markup=main_menu)

    elif text == "₿ Bitcoin":
        result = get_smc_prediction("BTC-USD")
        await update.message.reply_text(result, parse_mode='Markdown', reply_markup=main_menu)

    elif text == "📈 EURUSD":
        result = get_smc_prediction("EURUSD")
        await update.message.reply_text(result, parse_mode='Markdown', reply_markup=main_menu)

    elif text == "📈 GBPUSD":
        result = get_smc_prediction("GBPUSD")
        await update.message.reply_text(result, parse_mode='Markdown', reply_markup=main_menu)

    elif text == "📈 USDJPY":
        result = get_smc_prediction("USDJPY")
        await update.message.reply_text(result, parse_mode='Markdown', reply_markup=main_menu)

    elif text == "📈 USDCHF":
        result = get_smc_prediction("USDCHF")
        await update.message.reply_text(result, parse_mode='Markdown', reply_markup=main_menu)

    elif text == "📈 USDCAD":
        result = get_smc_prediction("USDCAD")
        await update.message.reply_text(result, parse_mode='Markdown', reply_markup=main_menu)

    elif text == "📈 AUDUSD":
        result = get_smc_prediction("AUDUSD")
        await update.message.reply_text(result, parse_mode='Markdown', reply_markup=main_menu)

    elif text == "📈 NZDUSD":
        result = get_smc_prediction("NZDUSD")
        await update.message.reply_text(result, parse_mode='Markdown', reply_markup=main_menu)

    elif text == "📈 USDMXN":
        result = get_smc_prediction("USDMXN")
        await update.message.reply_text(result, parse_mode='Markdown', reply_markup=main_menu)

    elif text == "📈 USDZAR":
        result = get_smc_prediction("USDZAR")
        await update.message.reply_text(result, parse_mode='Markdown', reply_markup=main_menu)

    elif text == "📈 USDTRY":
        result = get_smc_prediction("USDTRY")
        await update.message.reply_text(result, parse_mode='Markdown', reply_markup=main_menu)

    elif text == "🌍 USDAED":
        result = get_smc_prediction("USDAED")
        await update.message.reply_text(result, parse_mode='Markdown', reply_markup=main_menu)

    elif text == "🌍 USDARS":
        result = get_smc_prediction("USDARS")
        await update.message.reply_text(result, parse_mode='Markdown', reply_markup=main_menu)

    elif text == "🌍 USDAMD":
        result = get_smc_prediction("USDAMD")
        await update.message.reply_text(result, parse_mode='Markdown', reply_markup=main_menu)

    elif text == "🌍 USDAZN":
        result = get_smc_prediction("USDAZN")
        await update.message.reply_text(result, parse_mode='Markdown', reply_markup=main_menu)

    elif text == "🌍 USDBDT":
        result = get_smc_prediction("USDBDT")
        await update.message.reply_text(result, parse_mode='Markdown', reply_markup=main_menu)

    elif text == "🌍 USDBGN":
        result = get_smc_prediction("USDBGN")
        await update.message.reply_text(result, parse_mode='Markdown', reply_markup=main_menu)

    elif text == "🌍 USDBHD":
        result = get_smc_prediction("USDBHD")
        await update.message.reply_text(result, parse_mode='Markdown', reply_markup=main_menu)

    elif text == "🌍 USDBND":
        result = get_smc_prediction("USDBND")
        await update.message.reply_text(result, parse_mode='Markdown', reply_markup=main_menu)

    elif text == "🛠 Custom Analysis":
        await update.message.reply_text("Send any ticker symbol (e.g. USDJPY=X, NAS100=X, AAPL):", reply_markup=main_menu)
        context.user_data['waiting_for_symbol'] = True

    elif text == "📡 Bot Status":
        await update.message.reply_text("📡 *Bot Status*\n\n✅ Online & Ready\n🤖 ICT/SMC Engine Active\n⏰ Kill Zones Tracked\n\nHappy trading!", parse_mode='Markdown', reply_markup=main_menu)

    else:
        await update.message.reply_text("Select an option from the menu 👇", reply_markup=main_menu)

async def analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /analyze command"""
    symbol = context.args[0].upper() if context.args else "GC=F"
    result = get_smc_prediction(symbol)
    await update.message.reply_text(result, parse_mode='Markdown', reply_markup=main_menu)

def main():
    """Main function to run the bot"""
    app = ApplicationBuilder().token(TOKEN).build()

    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("analyze", analyze))
    app.add_handler(CommandHandler("alerts", alerts_command))
    app.add_handler(CommandHandler("monitor", toggle_monitoring))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("ICT/SMC Trading Bot is starting...")
    print(f" Monitoring {len(MONITORED_SYMBOLS)} symbols for strong signals...")
    print(f" Min confidence: {MIN_SIGNAL_CONFIDENCE}/10")
    
    # Start monitoring in background
    import threading
    monitor_thread = threading.Thread(target=lambda: asyncio.run(start_monitoring(app)), daemon=True)
    monitor_thread.start()
    
    app.run_polling()

if __name__ == '__main__':
    main()
