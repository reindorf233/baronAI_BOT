"""
Deriv-specific signal generation with breakout analysis
"""
import logging
import asyncio
from datetime import datetime
import pandas as pd
from typing import Dict, Optional, Tuple

from deriv_client import deriv_client, get_deriv_candles, is_deriv_symbol, get_deriv_symbol_name
from breakout_analysis import detect_breakout_retest, format_breakout_signal
from advanced_signals_fixed import AdvancedSignalAnalyzer
from chart_generator import create_technical_chart, create_breakout_chart
from utils import (
    normalize_symbol, check_kill_zone, parse_ai_confidence_score,
    get_ai_commentary, GROQ_API_KEY, AI_APPROVAL_MIN_SCORE,
    get_user_timezone, format_entry_time_display, get_current_market_session
)
from groq import Groq

async def get_deriv_signal(symbol: str, timeframe: str = "15m") -> Dict:
    """
    Get comprehensive signal analysis for Deriv synthetic indices
    
    Args:
        symbol: Deriv symbol (e.g., 'R_50', 'BOOM1000')
        timeframe: Timeframe for analysis
    
    Returns:
        Dictionary with signal analysis
    """
    try:
        symbol = normalize_symbol(symbol)
        
        # Fetch candle data
        df = await get_deriv_candles(symbol, timeframe, 100)
        if df.empty:
            return {
                "error": f"No data available for {symbol}",
                "signal": "neutral",
                "confidence": 0
            }
        
        # Perform breakout analysis
        breakout_analysis = detect_breakout_retest(df)
        
        # Get market session info
        session_info = get_current_market_session()
        kill_zone_info, is_kill_zone = check_kill_zone()
        
        # AI Analysis for confirmation
        ai_analysis = await get_deriv_ai_analysis(symbol, df, breakout_analysis)
        
        # Generate chart
        chart_base64 = create_breakout_chart(df, symbol, breakout_analysis)
        
        # Combine all analysis
        signal_data = {
            "symbol": symbol,
            "symbol_name": get_deriv_symbol_name(symbol),
            "timeframe": timeframe,
            "current_price": round(df['Close'].iloc[-1], 5),
            "signal": breakout_analysis.get("signal", "neutral"),
            "confidence": breakout_analysis.get("confidence", 0),
            "breakout_analysis": breakout_analysis,
            "ai_analysis": ai_analysis,
            "market_session": session_info,
            "kill_zone": kill_zone_info,
            "is_kill_zone": is_kill_zone,
            "chart": chart_base64,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
        }
        
        return signal_data
        
    except Exception as e:
        logging.error(f"Error getting Deriv signal for {symbol}: {e}")
        return {
            "error": str(e),
            "signal": "neutral",
            "confidence": 0
        }

async def get_deriv_ai_analysis(symbol: str, df: pd.DataFrame, breakout_analysis: Dict) -> Dict:
    """Get AI analysis for Deriv synthetic indices"""
    try:
        if not GROQ_API_KEY:
            return {"enabled": False, "reason": "No Groq API key"}
        
        client = Groq(api_key=GROQ_API_KEY)
        
        # Prepare data for AI
        current_price = df['Close'].iloc[-1]
        price_change = (df['Close'].iloc[-1] / df['Close'].iloc[-10] - 1) * 100
        
        # Get recent price action
        recent_highs = df['High'].tail(20).max()
        recent_lows = df['Low'].tail(20).min()
        
        prompt = f"""DERIV SYNTHETIC INDEX ANALYSIS - {symbol}

CURRENT MARKET DATA:
- Current Price: {current_price}
- 10-period Change: {price_change:.2f}%
- Recent High: {recent_highs}
- Recent Low: {recent_lows}
- 20-period Range: {((recent_highs - recent_lows) / recent_lows * 100):.2f}%

BREAKOUT ANALYSIS:
- Signal: {breakout_analysis.get('signal', 'neutral')}
- Confidence: {breakout_analysis.get('confidence', 0)}/10
- Breakout Direction: {breakout_analysis.get('breakout_direction', 'None')}
- Breakout Strength: {breakout_analysis.get('breakout_strength', 0)}%
- Retest Status: {breakout_analysis.get('retest_status', 'None')}

ANALYSIS REQUIREMENTS:
1. Evaluate the breakout pattern quality
2. Assess risk/reward ratio
3. Consider synthetic index characteristics
4. Provide confidence score (1-10)
5. Give specific trade recommendation

Respond with:
- CONFIDENCE SCORE: X/10
- RECOMMENDATION: BUY/SELL/NEUTRAL
- REASONING: [Detailed analysis]
- RISK LEVEL: LOW/MEDIUM/HIGH
"""

        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
            temperature=0.3
        )
        
        ai_response = response.choices[0].message.content
        
        # Parse AI response
        confidence = parse_ai_confidence_score(ai_response) or 5
        
        return {
            "enabled": True,
            "response": ai_response,
            "confidence": confidence,
            "approved": confidence >= AI_APPROVAL_MIN_SCORE
        }
        
    except Exception as e:
        logging.error(f"AI analysis failed: {e}")
        return {"enabled": False, "reason": str(e)}

def format_deriv_signal(signal_data: Dict) -> str:
    """Format Deriv signal for Telegram display"""
    if "error" in signal_data:
        return f"❌ *Error*: {signal_data['error']}"
    
    signal = signal_data["signal"]
    confidence = signal_data["confidence"]
    symbol = signal_data["symbol"]
    symbol_name = signal_data["symbol_name"]
    current_price = signal_data["current_price"]
    
    # Signal emoji and confidence stars
    signal_emoji = "🟢" if signal == "buy" else "🔴" if signal == "sell" else "🟡"
    confidence_stars = "⭐" * min(confidence // 2, 5)
    
    # Breakout analysis
    breakout = signal_data.get("breakout_analysis", {})
    
    message = f"""
{signal_emoji} *{symbol_name} ({symbol})*
{confidence_stars} *Confidence*: {confidence}/10

*Current Price*: {current_price}
*Timeframe*: {signal_data['timeframe']}
*Market Session*: {signal_data['market_session']}
*Kill Zone*: {signal_data['kill_zone']}

*BREAKOUT ANALYSIS*:
• Signal: {breakout.get('signal', 'neutral').upper()}
• Direction: {breakout.get('breakout_direction', 'None')}
• Strength: {breakout.get('breakout_strength', 0)}%
• Retest: {breakout.get('retest_status', 'None')}

*KEY LEVELS*:
• Resistance: {breakout.get('resistance_level', 'N/A')}
• Support: {breakout.get('support_level', 'N/A')}
• Entry: {breakout.get('entry_price', 'N/A')}
• Stop Loss: {breakout.get('stop_loss', 'N/A')}
• Take Profit: {breakout.get('take_profit', 'N/A')}

*INDICATORS*:
• RSI: {breakout.get('rsi', 'N/A')}
• MACD Histogram: {breakout.get('macd_histogram', 'N/A')}
• Volume Confirmation: {"✅" if breakout.get('volume_confirmation') else "❌"}

*AI ANALYSIS*:
"""
    
    # Add AI analysis if available
    ai_analysis = signal_data.get("ai_analysis", {})
    if ai_analysis.get("enabled"):
        ai_confidence = ai_analysis.get("confidence", 0)
        ai_approved = "✅" if ai_analysis.get("approved") else "❌"
        message += f"• AI Confidence: {ai_confidence}/10 {ai_approved}\n"
        message += f"• AI Reasoning: {ai_analysis.get('response', 'N/A')[:200]}...\n"
    else:
        message += f"• AI Analysis: {ai_analysis.get('reason', 'Unavailable')}\n"
    
    message += f"""
*Last Updated*: {signal_data['timestamp']}

⚠️ *Risk Warning*: Synthetic indices carry high risk. Trade with caution.
"""
    
    return message

async def get_deriv_market_summary() -> str:
    """Get market summary for all major Deriv synthetic indices"""
    try:
        major_indices = ["R_10", "R_25", "R_50", "R_75", "R_100", "BOOM1000", "CRASH1000"]
        summary_lines = ["📊 *DERIV SYNTHETIC INDICES SUMMARY*\n"]
        
        for symbol in major_indices:
            try:
                df = await get_deriv_candles(symbol, "15m", 50)
                if not df.empty:
                    current_price = df['Close'].iloc[-1]
                    price_change = (df['Close'].iloc[-1] / df['Close'].iloc[-10] - 1) * 100
                    
                    # Simple signal
                    if price_change > 0.5:
                        signal_emoji = "🟢"
                    elif price_change < -0.5:
                        signal_emoji = "🔴"
                    else:
                        signal_emoji = "🟡"
                    
                    symbol_name = get_deriv_symbol_name(symbol)
                    summary_lines.append(f"{signal_emoji} *{symbol_name}*: {current_price} ({price_change:+.2f}%)")
                    
            except Exception as e:
                logging.warning(f"Failed to get data for {symbol}: {e}")
                continue
        
        summary_lines.append(f"\n*Generated*: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
        return "\n".join(summary_lines)
        
    except Exception as e:
        logging.error(f"Error generating market summary: {e}")
        return "❌ Error generating market summary"
