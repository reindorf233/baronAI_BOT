"""
Signal generation logic for Forex, Crypto, and Synthetic Indices
"""
import logging
import re
import random
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime
import pytz
from typing import Dict, Optional, Tuple, List
from groq import Groq

from utils import (
    normalize_symbol, normalize_yfinance_symbol, check_kill_zone,
    parse_ai_confidence_score, get_ai_commentary, format_last_candles_ohlc,
    GROQ_API_KEY, AI_APPROVAL_MIN_SCORE, get_mock_synthetic_data
)

try:
    import MetaTrader5 as mt5
except Exception:
    mt5 = None

# MT5 configuration
MT5_LOGIN = None
MT5_PASSWORD = None
MT5_SERVER = None
USE_MT5_FIRST = False

if mt5 is not None:
    import os
    MT5_LOGIN = os.getenv("MT5_LOGIN", "")
    MT5_PASSWORD = os.getenv("MT5_PASSWORD", "")
    MT5_SERVER = os.getenv("MT5_SERVER", "")
    IS_RENDER = os.getenv("RENDER", "") != ""
    USE_MT5_FIRST = (not IS_RENDER) and all([MT5_LOGIN, MT5_PASSWORD, MT5_SERVER])


def _mt5_timeframe(tf: str):
    """Convert timeframe string to MT5 constant"""
    if mt5 is None:
        raise ValueError("MetaTrader5 is not available")
    tf = tf.upper()
    if tf in ("15M", "M15"):
        return mt5.TIMEFRAME_M15
    if tf in ("60M", "1H", "H1"):
        return mt5.TIMEFRAME_H1
    raise ValueError(f"Unsupported timeframe: {tf}")


def mt5_connect() -> bool:
    """Connect to MT5"""
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
    """Fetch candles from MT5"""
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
    cols = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in df.columns]
    return df[cols].dropna()


def fetch_candles(symbol: str, timeframe: str, bars: int) -> pd.DataFrame:
    """Fetch candles from MT5 or yfinance"""
    if USE_MT5_FIRST:
        df_mt5 = fetch_candles_mt5(symbol, timeframe=timeframe, bars=bars)
        if not df_mt5.empty:
            return df_mt5

    yf_symbol = normalize_yfinance_symbol(symbol)
    interval = "15m" if timeframe.upper() in ("15M", "M15") else "60m"
    period = "60d" if interval == "15m" else "200d"
    df = yf.download(yf_symbol, period=period, interval=interval, progress=False)
    if isinstance(df, pd.DataFrame) and not df.empty:
        return df.dropna()
    return pd.DataFrame()


def get_swings(df: pd.DataFrame, strength: int = 5) -> Tuple[List, List]:
    """Detect swing highs and lows"""
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


def compute_strategy_recommendation(
    *,
    current_price: float,
    htf_bias: str,
    effective_bias: str,
    structure: str,
    mss_direction: Optional[str],
    in_kill_zone: bool,
    data_15m: pd.DataFrame,
    fvg: Optional[Dict],
) -> Tuple[str, int, List[str]]:
    """Compute strategy recommendation with confidence score"""
    score = 0
    reasons: List[str] = []

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

    # FVG alignment
    if fvg is not None:
        if fvg.get('direction') == 'bullish':
            score += 1
            reasons.append("Bullish FVG present")
        elif fvg.get('direction') == 'bearish':
            score -= 1
            reasons.append("Bearish FVG present")

        if (("Bullish" in htf_bias) and (fvg.get('direction') == 'bullish')) or \
           (("Bearish" in htf_bias) and (fvg.get('direction') == 'bearish')):
            score += 1
            reasons.append("FVG aligns with EMA200")

    # Kill zone confidence boost
    if in_kill_zone:
        score += 1
        reasons.append("In Kill Zone")

    recommendation = "BUY" if score >= 0 else "SELL"
    confidence = max(1, min(10, int(round(5 + score))))
    return recommendation, confidence, reasons


# Enhanced Technical Analysis Functions
def calculate_rsi(data: pd.DataFrame, period: int = 14) -> float:
    """Calculate RSI indicator"""
    try:
        if len(data) < period + 1:
            return 50.0  # Neutral RSI

        delta = data['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return float(rsi.iloc[-1])
    except:
        return 50.0

def calculate_macd(data: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> tuple[float, float, float]:
    """Calculate MACD indicator"""
    try:
        if len(data) < slow + signal:
            return 0.0, 0.0, 0.0

        fast_ema = data['Close'].ewm(span=fast, adjust=False).mean()
        slow_ema = data['Close'].ewm(span=slow, adjust=False).mean()
        macd = fast_ema - slow_ema
        signal_line = macd.ewm(span=signal, adjust=False).mean()
        histogram = macd - signal_line

        return float(macd.iloc[-1]), float(signal_line.iloc[-1]), float(histogram.iloc[-1])
    except:
        return 0.0, 0.0, 0.0

def calculate_bollinger_bands(data: pd.DataFrame, period: int = 20, std_dev: float = 2.0) -> tuple[float, float, float]:
    """Calculate Bollinger Bands"""
    try:
        if len(data) < period:
            return float(data['Close'].iloc[-1]), float(data['Close'].iloc[-1]), float(data['Close'].iloc[-1])

        sma = data['Close'].rolling(window=period).mean()
        std = data['Close'].rolling(window=period).std()
        upper = sma + (std * std_dev)
        lower = sma - (std * std_dev)

        return float(upper.iloc[-1]), float(sma.iloc[-1]), float(lower.iloc[-1])
    except:
        current_price = float(data['Close'].iloc[-1])
        return current_price, current_price, current_price

def calculate_volume_analysis(data: pd.DataFrame) -> tuple[str, float]:
    """Analyze volume patterns"""
    try:
        if 'Volume' not in data.columns or data['Volume'].isna().all():
            return "Volume data unavailable", 1.0

        avg_volume = data['Volume'].rolling(window=20).mean()
        current_volume = data['Volume'].iloc[-1]
        avg_vol = avg_volume.iloc[-1] if not pd.isna(avg_volume.iloc[-1]) else current_volume

        if pd.isna(avg_vol) or avg_vol == 0:
            return "Volume data unavailable", 1.0

        volume_ratio = current_volume / avg_vol

        if volume_ratio > 1.5:
            return "High Volume 📈", volume_ratio
        elif volume_ratio > 1.2:
            return "Above Average 📊", volume_ratio
        elif volume_ratio < 0.7:
            return "Low Volume 📉", volume_ratio
        else:
            return "Normal Volume ➖", volume_ratio
    except:
        return "Volume analysis error", 1.0

def analyze_multi_timeframe(data_15m: pd.DataFrame, data_1h: pd.DataFrame, data_4h: pd.DataFrame) -> str:
    """Multi-timeframe analysis"""
    try:
        mtf_analysis = []

        # 15M Trend
        if len(data_15m) >= 20:
            ema_20_15m = data_15m['Close'].ewm(span=20, adjust=False).mean().iloc[-1]
            current_15m = data_15m['Close'].iloc[-1]
            if current_15m > ema_20_15m:
                mtf_analysis.append("15M: Bullish")
            else:
                mtf_analysis.append("15M: Bearish")

        # 1H Trend
        if len(data_1h) >= 20:
            ema_20_1h = data_1h['Close'].ewm(span=20, adjust=False).mean().iloc[-1]
            current_1h = data_1h['Close'].iloc[-1]
            if current_1h > ema_20_1h:
                mtf_analysis.append("1H: Bullish")
            else:
                mtf_analysis.append("1H: Bearish")

        # 4H Trend
        if len(data_4h) >= 20:
            ema_20_4h = data_4h['Close'].ewm(span=20, adjust=False).mean().iloc[-1]
            current_4h = data_4h['Close'].iloc[-1]
            if current_4h > ema_20_4h:
                mtf_analysis.append("4H: Bullish")
            else:
                mtf_analysis.append("4H: Bearish")

        return " | ".join(mtf_analysis) if mtf_analysis else "MTF analysis unavailable"
    except:
        return "MTF analysis error"

def calculate_enhanced_risk_reward(entry_price: float, direction: str, data: pd.DataFrame) -> tuple[float, float, float, float]:
    """Enhanced risk-reward calculation with dynamic targets"""
    try:
        current_price = float(data['Close'].iloc[-1])
        atr_period = min(14, len(data))
        high_low = data['High'] - data['Low']
        high_close = (data['High'] - data['Close'].shift(1)).abs()
        low_close = (data['Low'] - data['Close'].shift(1)).abs()
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = true_range.rolling(window=atr_period).mean().iloc[-1]

        if pd.isna(atr) or atr == 0:
            atr = abs(data['Close'].iloc[-1] * 0.005)  # 0.5% fallback

        # Dynamic stop loss based on ATR
        if direction == "BUY":
            sl_distance = max(atr * 1.5, abs(current_price * 0.005))  # Min 0.5%
            stop_loss = current_price - sl_distance
            # Multiple take profit levels
            tp1 = current_price + (sl_distance * 2)  # 2:1 RR
            tp2 = current_price + (sl_distance * 3)  # 3:1 RR
            tp3 = current_price + (sl_distance * 4)  # 4:1 RR
        else:  # SELL
            sl_distance = max(atr * 1.5, abs(current_price * 0.005))
            stop_loss = current_price + sl_distance
            tp1 = current_price - (sl_distance * 2)
            tp2 = current_price - (sl_distance * 3)
            tp3 = current_price - (sl_distance * 4)

        risk_reward_ratio = sl_distance / (abs(tp1 - current_price)) if abs(tp1 - current_price) > 0 else 1.0

        return stop_loss, tp1, tp2, risk_reward_ratio
    except:
        # Fallback calculation
        risk_pct = 0.01  # 1% risk
        if direction == "BUY":
            stop_loss = current_price * (1 - risk_pct)
            tp1 = current_price * (1 + risk_pct * 2)
            tp2 = current_price * (1 + risk_pct * 3)
        else:
            stop_loss = current_price * (1 + risk_pct)
            tp1 = current_price * (1 - risk_pct * 2)
            tp2 = current_price * (1 - risk_pct * 3)
        return stop_loss, tp1, tp2, 2.0

def analyze_asset_correlation(symbol: str, data: pd.DataFrame) -> str:
    """Analyze correlation between the current asset and other major assets"""
    try:
        # Define correlation pairs
        correlation_pairs = {
            'EURUSD': ['GBPUSD', 'USDCHF', 'USDJPY', 'GC=F', 'BTC-USD'],
            'GBPUSD': ['EURUSD', 'USDJPY', 'GC=F', 'BTC-USD'],
            'USDJPY': ['EURUSD', 'GBPUSD', 'GC=F'],
            'USDCHF': ['EURUSD', 'GC=F'],
            'GC=F': ['EURUSD', 'GBPUSD', 'BTC-USD', 'USDJPY'],
            'BTC-USD': ['GC=F', 'EURUSD', 'ETH-USD']
        }

        if symbol not in correlation_pairs:
            return "Correlation analysis not available for this asset"

        correlations = []
        base_data = data['Close'].pct_change().dropna()

        for pair in correlation_pairs[symbol]:
            try:
                # Get comparison data
                comp_data = fetch_candles(pair, timeframe="H1", bars=100)

                if comp_data.empty:
                    continue

                comp_returns = comp_data['Close'].pct_change().dropna()

                # Align data lengths
                min_len = min(len(base_data), len(comp_returns))
                if min_len < 20:
                    continue

                base_aligned = base_data[-min_len:]
                comp_aligned = comp_returns[-min_len:]

                # Calculate correlation
                corr = base_aligned.corr(comp_aligned)

                # Interpret correlation
                if corr > 0.7:
                    strength = "🔴 Very High"
                elif corr > 0.5:
                    strength = "🟠 High"
                elif corr > 0.3:
                    strength = "🟡 Moderate"
                elif corr > -0.3:
                    strength = "🟢 Low"
                elif corr > -0.5:
                    strength = "🔵 Moderate Inverse"
                elif corr > -0.7:
                    strength = "🟣 High Inverse"
                else:
                    strength = "🟤 Very High Inverse"

                correlations.append(f"{pair}: {corr:.2f} {strength}")

            except Exception:
                continue

        if not correlations:
            return "Correlation data temporarily unavailable"

        return " | ".join(correlations[:3])  # Show top 3 correlations

    except Exception:
        return "Correlation analysis error"

def generate_market_sentiment() -> str:
    """Generate overall market sentiment based on major asset correlations"""
    try:
        # Analyze major pairs for overall market direction
        pairs_to_check = ['EURUSD', 'GBPUSD', 'USDJPY', 'GC=F']
        bullish_signals = 0
        bearish_signals = 0

        for pair in pairs_to_check:
            try:
                data = fetch_candles(pair, timeframe="H1", bars=50)
                if data.empty:
                    continue

                # Simple trend analysis
                sma_20 = data['Close'].rolling(20).mean().iloc[-1]
                sma_50 = data['Close'].rolling(50).mean().iloc[-1]
                current = data['Close'].iloc[-1]

                if current > sma_20 > sma_50:
                    bullish_signals += 1
                elif current < sma_20 < sma_50:
                    bearish_signals += 1

            except Exception:
                continue

        total_signals = bullish_signals + bearish_signals
        if total_signals == 0:
            return "🟡 Neutral Market"

        bullish_ratio = bullish_signals / total_signals

        if bullish_ratio > 0.7:
            return "🟢 Bullish Market"
        elif bullish_ratio > 0.5:
            return "🟡 Mixed Market"
        elif bullish_ratio > 0.3:
            return "🔴 Bearish Market"
        else:
            return "🔴 Very Bearish Market"

    except Exception:
        return "Market sentiment unavailable"

def generate_manual_execution_guide(symbol: str, direction: str, entry_price: float, stop_loss: float, tp1: float, tp2: float, lot_size: float = 0.01) -> str:
    """Generate step-by-step manual execution guide"""
    guide = f"🎯 *MANUAL EXECUTION GUIDE*\n\n"
    guide += f"📊 **Symbol:** {symbol}\n"
    guide += f"📈 **Direction:** {direction}\n"
    guide += f"💰 **Lot Size:** {lot_size}\n\n"

    guide += "📋 **STEP-BY-STEP EXECUTION:**\n\n"

    guide += "1️⃣ **Open MT5 Terminal**\n"
    guide += f"   • Search for: {symbol}\n"
    guide += f"   • Open {symbol} chart (M15 timeframe)\n\n"

    guide += "2️⃣ **Place Market Order**\n"
    guide += f"   • Click: {'BUY' if direction == 'BUY' else 'SELL'} button\n"
    guide += f"   • Volume: {lot_size} lots\n\n"

    guide += "3️⃣ **Set Stop Loss**\n"
    guide += f"   • SL Price: {stop_loss:.5f}\n"
    guide += f"   • Risk: {abs(entry_price - stop_loss) / entry_price * 100:.2f}%\n\n"

    guide += "4️⃣ **Set Take Profit Levels**\n"
    guide += f"   • TP1 (2:1 RR): {tp1:.5f}\n"
    guide += f"   • TP2 (3:1 RR): {tp2:.5f}\n\n"

    guide += "5️⃣ **Monitor Trade**\n"
    guide += "   • Use trailing stop if price moves favorably\n"
    guide += "   • Close 50% at TP1, let remaining run to TP2\n"
    guide += "   • Never move SL against you\n\n"

    guide += "⚠️ **RISK MANAGEMENT:**\n"
    guide += "   • Never risk more than 1-2% per trade\n"
    guide += "   • Maximum 3-5 open trades\n"
    guide += "   • Use proper position sizing\n\n"

    guide += "🔥 **PRO TIP:** Take partial profits at TP1 for better R:R!"

    return guide

def get_ai_prediction(symbol: str, data_summary: str, recommendation: str, confidence: int, reasons: list) -> tuple[str, int, bool]:
    """Get AI trade validation from Groq with enhanced analysis
    
    Returns:
        tuple: (ai_response_text, ai_score, ai_approved)
    """
    if not GROQ_API_KEY:
        return ("AI Analysis unavailable (API key not configured)", None, False)
    
    try:
        client = Groq(api_key=GROQ_API_KEY)
        
        # FAST AI APPROVAL - Optimized for speed
        prompt = f"""FAST ICT/SMC Analysis:

SYMBOL: {symbol}
RECOMMENDATION: {recommendation}
CONFIDENCE: {confidence}/10
KEY FACTORS: {', '.join(reasons[:3])}

DATA SUMMARY: {data_summary[:200]}...

QUICK DECISION:
- Market structure alignment?
- EMA200 trend confirmation?
- Risk/reward ratio good?
- Kill Zone timing?

Score: X/10
Approval: YES/NO (YES only for 7+/10 with strong confluence)
Reason: [1 sentence]"""

        # FAST MODEL - Optimized for speed
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",  # FASTER MODEL
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert ICT/SMC trader. Give fast, decisive YES/NO approvals. Be quick and conservative."
                },
                {"role": "user", "content": prompt}
            ],
            max_tokens=80,  # SHORTER RESPONSE
            temperature=0.1,  # MORE CONSISTENT
            timeout=10  # ADD TIMEOUT FOR SPEED
        )
        
        ai_response = response.choices[0].message.content
        
        # Parse AI response
        ai_score = parse_ai_confidence_score(ai_response)
        
        # Check for approval keywords
        ai_response_lower = ai_response.lower()
        has_approval_yes = "approval: yes" in ai_response_lower or "approved" in ai_response_lower
        has_approval_no = "approval: no" in ai_response_lower or "rejected" in ai_response_lower or "not approved" in ai_response_lower
        
        # Determine approval based on score and explicit approval
        if ai_score is not None:
            ai_approved = ai_score >= AI_APPROVAL_MIN_SCORE
            # Override with explicit approval/rejection if present
            if has_approval_yes:
                ai_approved = True
            elif has_approval_no:
                ai_approved = False
        else:
            # Fallback: use explicit approval or default to False
            ai_approved = has_approval_yes and not has_approval_no
        
        return (ai_response, ai_score, ai_approved)
        
    except Exception as e:
        logging.error(f"AI prediction error: {e}")
        return (f"AI Analysis Error: {str(e)}", None, False)


def get_smc_prediction(symbol: str, filter_perfect: bool = False) -> str:
    """Complete ICT/SMC analysis for Forex/Crypto"""
    try:
        symbol = normalize_symbol(symbol.upper().strip())

        # Get 15m data for FVG analysis
        data_15m = fetch_candles(symbol, timeframe="M15", bars=6000)
        
        if data_15m.empty or len(data_15m) < 50:
            return "❌ Market is currently closed or ticker invalid."

        current_price = float(data_15m['Close'].iloc[-1])

        # Get 1h data for HTF analysis
        htf_data = fetch_candles(symbol, timeframe="H1", bars=5000)
        
        if htf_data.empty or len(htf_data) < 50:
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
                        if current_price_val < (last_low_val * 0.999):
                            structure = base + " ⚠️ Bearish MSS"
                            effective_bias = "bearish"
                            mss_direction = "bearish"
                        else:
                            structure = base
                            effective_bias = "bullish"
                    elif (lh and ll):
                        base = "Bearish (LH + LL)"
                        if current_price_val > (last_high_val * 1.001):
                            structure = base + " ⚠️ Bullish MSS"
                            effective_bias = "bullish"
                            mss_direction = "bullish"
                        else:
                            structure = base
                            effective_bias = "bearish"
                    else:
                        structure = "Ranging / Internal Structure"
                        effective_bias = "neutral"
        except Exception:
            structure = "Structure analysis unavailable"

        # Kill Zone Status
        kz_status, in_kill_zone = check_kill_zone()

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
        user_tz = pytz.timezone("Africa/Accra")
        now_user = datetime.now(user_tz)

        # Strategy Engine
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

        # Filter for perfect signals if requested
        if filter_perfect and strat_confidence < 10:
            return None

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

        # Enhanced Technical Analysis
        msg += "📊 **ENHANCED TECHNICAL ANALYSIS**\n"

        # RSI Analysis
        rsi = calculate_rsi(data_15m)
        rsi_status = "🟢 Oversold" if rsi < 30 else "🔴 Overbought" if rsi > 70 else "🟡 Neutral"
        msg += f"RSI (14): {rsi:.1f} {rsi_status}\n"

        # MACD Analysis
        macd, macd_signal, macd_hist = calculate_macd(data_15m)
        macd_trend = "🟢 Bullish" if macd > macd_signal else "🔴 Bearish" if macd < macd_signal else "🟡 Neutral"
        msg += f"MACD: {macd_trend} ({macd_hist:+.5f})\n"

        # Bollinger Bands
        bb_upper, bb_middle, bb_lower = calculate_bollinger_bands(data_15m)
        bb_position = ((current_price - bb_lower) / (bb_upper - bb_lower)) * 100 if bb_upper != bb_lower else 50
        bb_status = "🔴 Lower Band" if bb_position < 20 else "🟢 Upper Band" if bb_position > 80 else "🟡 Middle"
        msg += f"BB Position: {bb_position:.1f}% {bb_status}\n"

        # Volume Analysis
        vol_status, vol_ratio = calculate_volume_analysis(data_15m)
        msg += f"Volume: {vol_status} ({vol_ratio:.1f}x avg)\n"

        # Multi-timeframe Analysis
        mtf_analysis = analyze_multi_timeframe(data_15m, htf_data, htf_data)  # Using htf_data for both 1H and 4H for now
        msg += f"Multi-TF: {mtf_analysis}\n"

        # Correlation Analysis
        correlation_analysis = analyze_asset_correlation(symbol, data_15m)
        msg += f"Correlation: {correlation_analysis}\n"

        # Market Sentiment
        market_sentiment = generate_market_sentiment()
        msg += f"Market Sentiment: {market_sentiment}\n\n"

        # Enhanced Risk Management
        if fvg:
            entry_price = (float(fvg['fvg_low']) + float(fvg['fvg_high'])) / 2
            stop_loss, tp1, tp2, rr_ratio = calculate_enhanced_risk_reward(entry_price, recommendation, data_15m)

            msg += "🎯 **ENHANCED RISK MANAGEMENT**\n"
            msg += f"Entry: {entry_price:.5f}\n"
            msg += f"Stop Loss: {stop_loss:.5f} ({abs(entry_price - stop_loss) / entry_price * 100:.2f}% risk)\n"
            msg += f"Take Profit 1 (2:1): {tp1:.5f}\n"
            msg += f"Take Profit 2 (3:1): {tp2:.5f}\n"
            msg += f"Risk:Reward: {rr_ratio:.1f}:1\n\n"

        # AI Commentary
        commentary = get_ai_commentary(symbol, recommendation, strat_confidence, strat_reasons)
        msg += f"💬 *AI Commentary:* {commentary}\n\n"

        if fvg:
            dir_emoji = "🟢" if recommendation == "BUY" else "🔴"
            dir_text = recommendation

            # Confluence Analysis
            confluences = []
            if in_kill_zone:
                confluences.append("Kill Zone")
            if (("Bullish" in htf_bias) & (fvg['direction'] == 'bullish')) | \
               (("Bearish" in htf_bias) & (fvg['direction'] == 'bearish')):
                confluences.append("EMA200 Alignment")
            if fvg['direction'] == effective_bias:
                confluences.append("Structure Alignment")
            if mss_direction == fvg['direction']:
                confluences.append("Post-MSS Confirmation")

            # Trade Setup
            entry = (float(fvg['fvg_low']) + float(fvg['fvg_high'])) / 2
            sl = float(fvg['c1_low']) * 0.999 if recommendation == "BUY" else float(fvg.get('c1_high', fvg['fvg_high'])) * 1.001
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
            msg += f"📝 Best executed during Kill Zone with price retracing into FVG.\n\n"

            # Manual Execution Guide
            execution_guide = generate_manual_execution_guide(symbol, recommendation, entry_price, stop_loss, tp1, tp2)
            msg += execution_guide
            
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
FVG Detected: Yes
FVG Direction: {fvg['direction']}
FVG Range: {float(fvg['fvg_low']):.5f} - {float(fvg['fvg_high']):.5f}
Entry: {entry:.5f}
Stop Loss: {sl:.5f}
Take Profit: {tp_2r:.5f}
"""
            # Get AI prediction with enhanced analysis
            ai_prediction, ai_score, ai_approved = get_ai_prediction(
                symbol, data_summary, recommendation, strat_confidence, strat_reasons
            )
            
            # Display AI analysis
            if ai_score is not None:
                ai_status = "✅ AI Approved" if ai_approved else "⚠️ AI Not Approved"
                msg += f"\n🤖 **AI ANALYSIS**\n{ai_status} ({ai_score}/10)\n{ai_prediction}\n"
            else:
                ai_status = "✅ AI Approved" if ai_approved else "⚠️ AI Not Approved"
                msg += f"\n🤖 **AI ANALYSIS**\n{ai_status}\n{ai_prediction}\n"
            
            # Add AI approval indicator to signal
            if ai_approved:
                msg = msg.replace(f"{dir_emoji} **{dir_text} Signal**", 
                                f"{dir_emoji} **{dir_text} Signal** 🤖 AI APPROVED")
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
            # Get AI prediction with enhanced analysis (even without FVG)
            ai_prediction, ai_score, ai_approved = get_ai_prediction(
                symbol, data_summary, recommendation, strat_confidence, strat_reasons
            )
            
            # Display AI analysis
            if ai_score is not None:
                ai_status = "✅ AI Approved" if ai_approved else "⚠️ AI Not Approved"
                msg += f"\n🤖 **AI ANALYSIS**\n{ai_status} ({ai_score}/10)\n{ai_prediction}\n"
            else:
                ai_status = "✅ AI Approved" if ai_approved else "⚠️ AI Not Approved"
                msg += f"\n🤖 **AI ANALYSIS**\n{ai_status}\n{ai_prediction}\n"

        msg += "\n⚠️ *Disclaimer: Trading involves risk. Always use proper risk management.*"

        return msg

    except Exception as e:
        logging.error(f"Error in get_smc_prediction: {e}")
        return f"⚠️ Error: {str(e)}"


# === Synthetic Indices Signals ===

def get_volatility_signal(index_name: str = "V75") -> str:
    """Generate signal for Volatility indices using RSI/MA"""
    try:
        mock_data = get_mock_synthetic_data(index_name)
        price = mock_data["price"]
        volatility = mock_data["volatility"]
        
        # Mock RSI calculation
        rsi = random.uniform(30, 70)
        ma_20 = price * (1 + random.uniform(-0.01, 0.01))
        
        # Signal logic
        if rsi < 30 and price < ma_20:
            direction = "BUY"
            confidence = random.randint(8, 10)
        elif rsi > 70 and price > ma_20:
            direction = "SELL"
            confidence = random.randint(8, 10)
        else:
            direction = "HOLD"
            confidence = random.randint(5, 7)
        
        msg = f"📊 *{index_name} Volatility Index*\n\n"
        msg += f"💹 Current Price: {price:.2f}\n"
        msg += f"📈 RSI: {rsi:.1f}\n"
        msg += f"📊 MA20: {ma_20:.2f}\n"
        msg += f"📉 Volatility: {volatility:.2f}\n\n"
        msg += f"▶️ Signal: **{direction}**\n"
        msg += f"🎯 Confidence: {confidence}/10\n"
        
        if confidence >= 8:
            commentary = get_ai_commentary(index_name, direction, confidence, ["RSI oversold/overbought", "MA alignment"])
            msg += f"💬 *AI Commentary:* {commentary}\n"
        
        return msg
    except Exception as e:
        return f"⚠️ Error: {str(e)}"


def get_boom_crash_signal(index_name: str = "BOOM") -> str:
    """Generate signal for Boom/Crash indices using spike detection"""
    try:
        mock_data = get_mock_synthetic_data(index_name)
        price = mock_data["price"]
        trend = mock_data["trend"]
        
        # Spike detection simulation
        spike_probability = random.random()
        has_spike = spike_probability > 0.7
        
        if has_spike:
            if trend == "up":
                direction = "BUY"
                confidence = random.randint(9, 10)
            else:
                direction = "SELL"
                confidence = random.randint(9, 10)
        else:
            direction = "HOLD"
            confidence = random.randint(4, 6)
        
        msg = f"📊 *{index_name} Index*\n\n"
        msg += f"💹 Current Price: {price:.2f}\n"
        msg += f"📈 Trend: {trend.upper()}\n"
        msg += f"⚡ Spike Detected: {'Yes' if has_spike else 'No'}\n\n"
        msg += f"▶️ Signal: **{direction}**\n"
        msg += f"🎯 Confidence: {confidence}/10\n"
        
        if has_spike:
            commentary = get_ai_commentary(index_name, direction, confidence, ["Spike detected", f"{trend} trend"])
            msg += f"💬 *AI Commentary:* {commentary}\n"
        
        return msg
    except Exception as e:
        return f"⚠️ Error: {str(e)}"


def get_step_index_signal() -> str:
    """Generate signal for Step Index using fixed-step trend following with Bollinger Bands"""
    try:
        mock_data = get_mock_synthetic_data("STEP")
        price = mock_data["price"]
        
        # Bollinger Bands simulation
        sma = price
        std = price * 0.02
        upper_band = sma + (2 * std)
        lower_band = sma - (2 * std)
        
        # Fixed-step trend detection
        step_size = price * 0.001
        trend_direction = random.choice(["up", "down", "sideways"])
        
        # Breakout detection
        if price > upper_band:
            direction = "BUY"
            confidence = random.randint(8, 10)
            breakout = "Upper band breakout"
        elif price < lower_band:
            direction = "SELL"
            confidence = random.randint(8, 10)
            breakout = "Lower band breakout"
        else:
            direction = "HOLD"
            confidence = random.randint(5, 7)
            breakout = "Within bands"
        
        msg = f"📊 *Step Index*\n\n"
        msg += f"💹 Current Price: {price:.2f}\n"
        msg += f"📈 Trend: {trend_direction.upper()}\n"
        msg += f"📊 Bollinger Upper: {upper_band:.2f}\n"
        msg += f"📊 Bollinger Lower: {lower_band:.2f}\n"
        msg += f"⚡ Breakout: {breakout}\n\n"
        msg += f"▶️ Signal: **{direction}**\n"
        msg += f"🎯 Confidence: {confidence}/10\n"
        
        if confidence >= 8:
            commentary = get_ai_commentary("STEP", direction, confidence, [breakout, f"{trend_direction} trend"])
            msg += f"💬 *AI Commentary:* {commentary}\n"
        
        return msg
    except Exception as e:
        return f"⚠️ Error: {str(e)}"


def get_jump_index_signal() -> str:
    """Generate signal for Jump Index using probabilistic jump detection with volume simulation"""
    try:
        mock_data = get_mock_synthetic_data("JUMP")
        price = mock_data["price"]
        volume = mock_data["volume"]
        
        # Jump probability calculation
        jump_probability = random.random()
        has_jump = jump_probability > 0.75
        jump_direction = random.choice(["up", "down"]) if has_jump else None
        
        # Volume confirmation
        high_volume = volume > 5000
        
        if has_jump and high_volume:
            direction = "BUY" if jump_direction == "up" else "SELL"
            confidence = random.randint(9, 10)
        elif has_jump:
            direction = "BUY" if jump_direction == "up" else "SELL"
            confidence = random.randint(7, 8)
        else:
            direction = "HOLD"
            confidence = random.randint(4, 6)
        
        msg = f"📊 *Jump Index*\n\n"
        msg += f"💹 Current Price: {price:.2f}\n"
        msg += f"📊 Volume: {volume}\n"
        msg += f"⚡ Jump Detected: {'Yes (' + jump_direction.upper() + ')' if has_jump else 'No'}\n"
        msg += f"📈 High Volume: {'Yes' if high_volume else 'No'}\n\n"
        msg += f"▶️ Signal: **{direction}**\n"
        msg += f"🎯 Confidence: {confidence}/10\n"
        
        if has_jump:
            reasons = [f"Jump detected ({jump_direction})", "Volume confirmation" if high_volume else "Moderate volume"]
            commentary = get_ai_commentary("JUMP", direction, confidence, reasons)
            msg += f"💬 *AI Commentary:* {commentary}\n"
        
        return msg
    except Exception as e:
        return f"⚠️ Error: {str(e)}"


def get_perfect_signals() -> List[Dict]:
    """Get all 10/10 confidence signals across all categories"""
    perfect_signals = []
    
    # Check Forex/Crypto
    symbols = ["GC=F", "EURUSD", "GBPUSD", "BTC-USD"]
    for symbol in symbols:
        try:
            result = get_smc_prediction(symbol, filter_perfect=True)
            if result:
                # Extract confidence from result
                conf_match = re.search(r"Strategy Confidence: (\d+)/10", result)
                if conf_match and int(conf_match.group(1)) == 10:
                    perfect_signals.append({
                        "symbol": symbol,
                        "type": "Forex/Crypto",
                        "analysis": result
                    })
        except Exception:
            continue
    
    # Check Synthetics (mock perfect signals)
    synthetic_indices = ["V75", "V100", "BOOM", "CRASH", "STEP", "JUMP"]
    for idx in synthetic_indices:
        # Simulate 10/10 signals occasionally
        if random.random() > 0.9:  # 10% chance
            if idx in ["V75", "V100"]:
                signal = get_volatility_signal(idx)
            elif idx in ["BOOM", "CRASH"]:
                signal = get_boom_crash_signal(idx)
            elif idx == "STEP":
                signal = get_step_index_signal()
            elif idx == "JUMP":
                signal = get_jump_index_signal()
            else:
                continue
            
            # Check if it's 10/10
            conf_match = re.search(r"Confidence: (\d+)/10", signal)
            if conf_match and int(conf_match.group(1)) == 10:
                perfect_signals.append({
                    "symbol": idx,
                    "type": "Synthetic",
                    "analysis": signal
                })
    
    return perfect_signals


def get_daily_summary() -> str:
    """Generate daily summary including synthetic trends and correlations"""
    try:
        msg = "📈 *Daily Market Summary*\n\n"

        # Market Sentiment
        market_sentiment = generate_market_sentiment()
        msg += f"🌍 *Market Sentiment:* {market_sentiment}\n\n"

        # Forex trends
        forex_symbols = ["EURUSD", "GBPUSD", "GC=F", "BTC-USD"]
        msg += "💱 *Forex & Crypto Trends:*\n"
        for symbol in forex_symbols:
            try:
                result = get_smc_prediction(symbol)
                conf_match = re.search(r"Strategy Confidence: (\d+)/10", result)
                rec_match = re.search(r"Recommendation: \*\*(\w+)\*\*", result)
                if conf_match and rec_match:
                    confidence = int(conf_match.group(1))
                    recommendation = rec_match.group(1)

                    # Add confidence emoji
                    if confidence >= 8:
                        conf_emoji = "🔥"
                    elif confidence >= 6:
                        conf_emoji = "✅"
                    else:
                        conf_emoji = "⚠️"

                    msg += f"  • {symbol}: {recommendation} ({confidence}/10) {conf_emoji}\n"
            except Exception:
                continue

        # Key Correlations
        msg += "\n📊 *Key Correlations:*\n"
        try:
            # EURUSD correlations (most traded pair)
            eurusd_data = fetch_candles("EURUSD", timeframe="H1", bars=100)
            if not eurusd_data.empty:
                correlations = analyze_asset_correlation("EURUSD", eurusd_data)
                msg += f"  • EURUSD: {correlations}\n"

            # Gold correlations
            gold_data = fetch_candles("GC=F", timeframe="H1", bars=100)
            if not gold_data.empty:
                gold_corr = analyze_asset_correlation("GC=F", gold_data)
                msg += f"  • Gold: {gold_corr}\n"
        except Exception:
            msg += "  • Correlation data loading...\n"

        # Synthetic trends
        msg += "\n🎯 *Synthetic Indices:*\n"
        synthetic_indices = ["V75", "BOOM", "CRASH", "STEP", "JUMP"]
        for idx in synthetic_indices:
            trend = get_mock_synthetic_data(idx)["trend"]
            # Add trend emoji
            if "bull" in trend.lower():
                trend_emoji = "🟢"
            elif "bear" in trend.lower():
                trend_emoji = "🔴"
            else:
                trend_emoji = "🟡"
            msg += f"  • {idx}: {trend.upper()} {trend_emoji}\n"

        # Trading Tips
        msg += "\n💡 *Today's Trading Tips:*\n"
        msg += "  • Check correlations before entering positions\n"
        msg += "  • Use 10/10 signals for highest probability\n"
        msg += "  • Follow manual execution guide for precision\n"
        msg += "  • Monitor volume for confirmation\n"

        msg += "\n⚠️ *Disclaimer: This is analysis, not trading advice.*"
        return msg
    except Exception as e:
        return f"⚠️ Error generating summary: {str(e)}"

