"""
Breakout and Retest Analysis for Deriv Synthetic Indices
"""
import logging
import pandas as pd
import numpy as np
from typing import Dict, Tuple, List, Optional
from datetime import datetime, timedelta
import ta

def detect_breakout_retest(df: pd.DataFrame, lookback: int = 20) -> Dict:
    """
    Detect breakout and retest patterns in price data
    
    Args:
        df: DataFrame with OHLC data
        lookback: Number of periods to look back for support/resistance
    
    Returns:
        Dictionary with breakout analysis results
    """
    if len(df) < lookback + 10:
        return {
            "pattern": "insufficient_data",
            "signal": "neutral",
            "confidence": 0,
            "reasoning": "Not enough data for analysis"
        }
    
    try:
        # Calculate key levels
        resistance_level = df['High'].rolling(lookback).max().iloc[-2]
        support_level = df['Low'].rolling(lookback).min().iloc[-2]
        
        # Current price
        current_price = df['Close'].iloc[-1]
        previous_close = df['Close'].iloc[-2]
        
        # Detect breakout direction
        breakout_direction = None
        breakout_strength = 0
        
        # Bullish breakout detection
        if previous_close <= resistance_level and current_price > resistance_level:
            breakout_direction = "bullish"
            breakout_strength = (current_price - resistance_level) / resistance_level * 100
        # Bearish breakout detection  
        elif previous_close >= support_level and current_price < support_level:
            breakout_direction = "bearish"
            breakout_strength = (support_level - current_price) / support_level * 100
        
        # Check for retest
        retest_status = check_retest(df, resistance_level, support_level, breakout_direction)
        
        # Calculate additional indicators
        rsi = ta.momentum.RSIIndicator(df['Close']).rsi().iloc[-1]
        # Calculate MACD
        macd = ta.trend.MACD(df['Close'])
        df['macd'] = macd.macd()
        df['macd_signal'] = macd.macd_signal()
        macd_histogram = macd.macd_diff().iloc[-1]
        
        # Volume confirmation (using price range as proxy since volume not available)
        price_range = (df['High'] - df['Low']).rolling(10).mean().iloc[-1]
        avg_range = (df['High'] - df['Low']).rolling(lookback).mean().iloc[-1]
        volume_confirmation = price_range > avg_range * 1.2
        
        # Determine signal and confidence
        signal, confidence, reasoning = generate_signal(
            breakout_direction, retest_status, breakout_strength,
            rsi, macd_histogram, volume_confirmation
        )
        
        return {
            "pattern": "breakout_retest",
            "signal": signal,
            "confidence": confidence,
            "reasoning": reasoning,
            "breakout_direction": breakout_direction,
            "breakout_strength": round(breakout_strength, 2) if breakout_strength else 0,
            "resistance_level": round(resistance_level, 5),
            "support_level": round(support_level, 5),
            "current_price": round(current_price, 5),
            "retest_status": retest_status,
            "rsi": round(rsi, 2),
            "macd_histogram": round(macd_histogram, 5),
            "volume_confirmation": volume_confirmation,
            "entry_price": round(calculate_entry_price(df, breakout_direction, retest_status), 5),
            "stop_loss": round(calculate_stop_loss(df, breakout_direction, support_level, resistance_level), 5),
            "take_profit": round(calculate_take_profit(df, breakout_direction, support_level, resistance_level), 5)
        }
        
    except Exception as e:
        logging.error(f"Error in breakout analysis: {e}")
        return {
            "pattern": "error",
            "signal": "neutral", 
            "confidence": 0,
            "reasoning": f"Analysis error: {str(e)[:50]}"
        }

def check_retest(df: pd.DataFrame, resistance: float, support: float, direction: str) -> str:
    """Check if price is retesting a broken level"""
    if direction is None:
        return "no_breakout"
    
    current_price = df['Close'].iloc[-1]
    tolerance = 0.002  # 0.2% tolerance for retest
    
    if direction == "bullish":
        # Check if price is pulling back to resistance level (now support)
        if abs(current_price - resistance) / resistance < tolerance:
            return "retesting_resistance"
        # Check if retest already completed
        for i in range(min(5, len(df)-1)):
            price = df['Close'].iloc[-(i+2)]
            if abs(price - resistance) / resistance < tolerance:
                return "retest_completed"
    elif direction == "bearish":
        # Check if price is pulling back to support level (now resistance)
        if abs(current_price - support) / support < tolerance:
            return "retesting_support"
        # Check if retest already completed
        for i in range(min(5, len(df)-1)):
            price = df['Close'].iloc[-(i+2)]
            if abs(price - support) / support < tolerance:
                return "retest_completed"
    
    return "no_retest"

def generate_signal(direction: str, retest: str, strength: float, 
                   rsi: float, macd_hist: float, volume_conf: bool) -> Tuple[str, int, str]:
    """Generate trading signal based on breakout analysis"""
    
    # No breakout - neutral signal
    if direction is None:
        return "neutral", 0, "No breakout detected"
    
    # Bullish breakout scenarios
    if direction == "bullish":
        if retest == "retesting_resistance":
            if rsi < 70 and macd_hist > 0 and volume_conf:
                return "buy", 9, "Strong bullish breakout with retest at resistance level"
            else:
                return "buy", 7, "Bullish breakout with retest opportunity"
        elif retest == "retest_completed":
            if rsi < 70 and macd_hist > 0:
                return "buy", 8, "Bullish breakout confirmed after retest"
            else:
                return "buy", 6, "Bullish breakout, retest completed"
        else:  # Initial breakout
            if strength > 1.0 and rsi < 70 and volume_conf:
                return "buy", 8, "Strong bullish breakout detected"
            else:
                return "buy", 5, "Bullish breakout detected"
    
    # Bearish breakout scenarios
    elif direction == "bearish":
        if retest == "retesting_support":
            if rsi > 30 and macd_hist < 0 and volume_conf:
                return "sell", 9, "Strong bearish breakout with retest at support level"
            else:
                return "sell", 7, "Bearish breakout with retest opportunity"
        elif retest == "retest_completed":
            if rsi > 30 and macd_hist < 0:
                return "sell", 8, "Bearish breakout confirmed after retest"
            else:
                return "sell", 6, "Bearish breakout, retest completed"
        else:  # Initial breakout
            if strength > 1.0 and rsi > 30 and volume_conf:
                return "sell", 8, "Strong bearish breakout detected"
            else:
                return "sell", 5, "Bearish breakout detected"
    
    return "neutral", 0, "No clear signal"

def calculate_entry_price(df: pd.DataFrame, direction: str, retest: str) -> float:
    """Calculate optimal entry price"""
    current_price = df['Close'].iloc[-1]
    
    if retest in ["retesting_resistance", "retesting_support"]:
        # Enter during retest
        return current_price
    elif direction == "bullish":
        # Wait for small pullback
        return current_price * 0.998  # 0.2% pullback
    elif direction == "bearish":
        # Wait for small bounce
        return current_price * 1.002  # 0.2% bounce
    
    return current_price

def calculate_stop_loss(df: pd.DataFrame, direction: str, support: float, resistance: float) -> float:
    """Calculate stop loss level"""
    current_price = df['Close'].iloc[-1]
    atr = ta.volatility.AverageTrueRange(df['High'], df['Low'], df['Close']).average_true_range().iloc[-1]
    
    if direction == "bullish":
        # Stop below recent low or broken resistance
        stop_level = min(df['Low'].tail(10).min(), resistance * 0.995)
        return max(stop_level, current_price - (atr * 2))
    elif direction == "bearish":
        # Stop above recent high or broken support
        stop_level = max(df['High'].tail(10).max(), support * 1.005)
        return min(stop_level, current_price + (atr * 2))
    
    return current_price

def calculate_take_profit(df: pd.DataFrame, direction: str, support: float, resistance: float) -> float:
    """Calculate take profit level"""
    current_price = df['Close'].iloc[-1]
    atr = ta.volatility.AverageTrueRange(df['High'], df['Low'], df['Close']).average_true_range().iloc[-1]
    
    if direction == "bullish":
        # Target at previous high or 2x ATR
        target = max(df['High'].tail(20).max(), current_price + (atr * 2))
        return min(target, current_price * 1.02)  # Cap at 2% for synthetic indices
    elif direction == "bearish":
        # Target at previous low or 2x ATR
        target = min(df['Low'].tail(20).min(), current_price - (atr * 2))
        return max(target, current_price * 0.98)  # Cap at 2% for synthetic indices
    
    return current_price

def format_breakout_signal(analysis: Dict) -> str:
    """Format breakout analysis for display"""
    if analysis["pattern"] == "insufficient_data":
        return "❌ *Insufficient data for breakout analysis*"
    
    if analysis["pattern"] == "error":
        return f"❌ *Analysis Error*: {analysis['reasoning']}"
    
    signal_emoji = "🟢" if analysis["signal"] == "buy" else "🔴" if analysis["signal"] == "sell" else "🟡"
    confidence_stars = "⭐" * min(analysis["confidence"] // 2, 5)
    
    message = f"""
{signal_emoji} *BREAKOUT & RETEST ANALYSIS*
{confidence_stars} *Confidence*: {analysis["confidence"]}/10

*Signal*: {analysis["signal"].upper()}
*Pattern*: {analysis["breakout_direction"] or "No Breakout"}
*Breakout Strength*: {analysis["breakout_strength"]}%
*Retest Status*: {analysis["retest_status"].replace('_', ' ').title()}

*Key Levels*:
• Resistance: {analysis["resistance_level"]}
• Support: {analysis["support_level"]}
• Current Price: {analysis["current_price"]}

*Indicators*:
• RSI: {analysis["rsi"]}
• MACD Histogram: {analysis["macd_histogram"]}
• Volume Confirmation: {"✅" if analysis["volume_confirmation"] else "❌"}

*Trade Plan*:
• Entry Price: {analysis["entry_price"]}
• Stop Loss: {analysis["stop_loss"]}
• Take Profit: {analysis["take_profit"]}

*Reasoning*: {analysis["reasoning"]}
"""
    return message
