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

        # Fetch candle data with retry
        df = await get_deriv_candles(symbol, timeframe, 100)
        if df.empty:
            # Try alternative symbol format
            alt_symbol = symbol.replace("_", " ").strip()
            if alt_symbol != symbol:
                logging.info(f"Trying alternative symbol format: {alt_symbol}")
                df = await get_deriv_candles(alt_symbol, timeframe, 100)

            if df.empty:
                return {
                    "error": f"No data available for {symbol}. Please check if the symbol is correct and try again.",
                    "signal": "neutral",
                    "confidence": 0,
                    "symbol": symbol,
                    "symbol_name": get_deriv_symbol_name(symbol)
                }

        # Perform advanced multi-technique analysis
        analyzer = AdvancedSignalAnalyzer()
        advanced_signal = analyzer.generate_professional_signal(df, symbol)

        # Get market session info
        session_info = get_current_market_session()
        kill_zone_info, is_kill_zone = check_kill_zone()

        # AI Analysis for confirmation
        ai_analysis = await get_deriv_ai_analysis(symbol, df, advanced_signal)

        # Calculate price movement
        price_change = 0
        price_change_pct = 0
        if len(df) >= 10:
            prev_price = df['Close'].iloc[-10]
            current_price_val = df['Close'].iloc[-1]
            price_change = current_price_val - prev_price
            price_change_pct = (price_change / prev_price) * 100 if prev_price > 0 else 0

        # Combine all analysis
        signal_data = {
            "symbol": symbol,
            "symbol_name": get_deriv_symbol_name(symbol),
            "timeframe": timeframe,
            "current_price": advanced_signal.get("current_price", round(df['Close'].iloc[-1], 5)),
            "price_change": price_change,
            "price_change_pct": price_change_pct,
            "signal": advanced_signal.get("composite_signal", {}).get("signal", "neutral"),
            "confidence": advanced_signal.get("composite_signal", {}).get("confidence", 0),
            "advanced_analysis": advanced_signal,
            "ai_analysis": ai_analysis,
            "market_session": session_info,
            "kill_zone": kill_zone_info,
            "is_kill_zone": is_kill_zone,
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

async def get_deriv_ai_analysis(symbol: str, df: pd.DataFrame, advanced_signal: Dict) -> Dict:
    """Get AI analysis for Deriv synthetic indices using multiple techniques"""
    try:
        if not GROQ_API_KEY:
            return {"enabled": False, "reason": "No Groq API key"}

        client = Groq(api_key=GROQ_API_KEY)

        # Extract data from advanced signal
        composite = advanced_signal.get("composite_signal", {})
        breakout = advanced_signal.get("breakout_analysis", {})
        ict = advanced_signal.get("ict_analysis", {})
        smc = advanced_signal.get("smc_analysis", {})
        crt = advanced_signal.get("crt_analysis", {})

        current_price = advanced_signal.get("current_price", df['Close'].iloc[-1])
        signal = composite.get("signal", "neutral")
        confidence = composite.get("confidence", 0)

        prompt = f"""PROFESSIONAL DERIV TRADING ANALYSIS - {symbol}

📊 CURRENT MARKET DATA:
• Current Price: {current_price}
• Signal: {signal.upper()}
• Confidence: {confidence}/10

🔍 MULTI-TECHNIQUE ANALYSIS:

ICT ANALYSIS:
• Market Structure: {ict.get('market_structure', 'N/A')}
• Liquidity Zones: {ict.get('liquidity_zones', 'N/A')}
• Institutional Order Flow: {ict.get('order_flow', 'N/A')}

SMC ANALYSIS:
• Smart Money Concepts: {smc.get('smart_money_signal', 'N/A')}
• Order Blocks: {smc.get('order_blocks', 'N/A')}
• Internal Structure: {smc.get('internal_structure', 'N/A')}

CRT ANALYSIS:
• Change of Character: {crt.get('change_of_character', 'N/A')}
• Volume Profile: {crt.get('volume_profile', 'N/A')}
• Fair Value Gaps: {crt.get('fair_value_gaps', 'N/A')}

BREAKOUT ANALYSIS:
• Pattern: {breakout.get('pattern', 'N/A')}
• Retest Status: {breakout.get('retest_status', 'N/A')}
• Breakout Strength: {breakout.get('breakout_strength', 0)}%

📈 TRADING DECISION REQUIRED:
Based on all techniques above, provide a professional trading recommendation.

REQUIRED OUTPUT FORMAT:
SIGNAL: BUY/SELL/HOLD
CONFIDENCE: X/10
REASONING: [2-3 sentences explaining the trade setup]
RISK LEVEL: LOW/MEDIUM/HIGH
ENTRY TRIGGER: [Specific price level or condition]
STOP LOSS: [Price level]
TAKE PROFIT: [Price level or multiple targets]
"""

        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=600,
            temperature=0.2
        )

        ai_response = response.choices[0].message.content

        # Parse AI response for key components
        ai_signal = "neutral"
        ai_confidence = confidence  # Default to technical confidence
        ai_reasoning = ai_response
        ai_risk_level = "MEDIUM"

        # Extract signal from AI response
        if "SIGNAL: BUY" in ai_response.upper():
            ai_signal = "buy"
        elif "SIGNAL: SELL" in ai_response.upper():
            ai_signal = "sell"
        elif "SIGNAL: HOLD" in ai_response.upper():
            ai_signal = "hold"

        # Extract confidence score
        if "CONFIDENCE:" in ai_response:
            try:
                conf_text = ai_response.split("CONFIDENCE:")[1].split("/")[0].strip()
                ai_confidence = int(conf_text) if conf_text.isdigit() else confidence
            except:
                pass

        # Determine final signal (technical + AI confirmation)
        final_signal = signal
        final_confidence = confidence

        # AI confirmation boost
        if ai_signal in ["buy", "sell"] and signal == ai_signal:
            final_confidence = min(10, confidence + 2)  # Boost confidence for agreement
        elif ai_signal in ["buy", "sell"] and signal != ai_signal:
            final_confidence = max(0, confidence - 2)  # Reduce confidence for disagreement

        return {
            "enabled": True,
            "ai_signal": ai_signal,
            "ai_confidence": ai_confidence,
            "ai_reasoning": ai_reasoning,
            "ai_risk_level": ai_risk_level,
            "final_signal": final_signal,
            "final_confidence": final_confidence,
            "ai_approved": ai_confidence >= AI_APPROVAL_MIN_SCORE,
            "technique_agreement": signal == ai_signal
        }

    except Exception as e:
        logging.error(f"AI analysis failed: {e}")
        return {
            "enabled": False,
            "reason": str(e),
            "final_signal": "neutral",
            "final_confidence": 0
        }

def format_deriv_signal(signal_data: Dict) -> str:
    """Format Deriv signal for professional trading display"""
    if "error" in signal_data:
        return f"❌ *Error*: {signal_data['error']}"

    # Extract data
    symbol = signal_data["symbol"]
    symbol_name = signal_data["symbol_name"]
    current_price = signal_data["current_price"]
    signal = signal_data.get("signal", "neutral")
    confidence = signal_data.get("confidence", 0)
    timeframe = signal_data.get("timeframe", "15m")

    # Advanced analysis data
    advanced = signal_data.get("advanced_analysis", {})
    composite = advanced.get("composite_signal", {})
    risk_mgmt = advanced.get("risk_management", {})

    # AI analysis
    ai_analysis = signal_data.get("ai_analysis", {})
    ai_signal = ai_analysis.get("final_signal", signal)
    ai_confidence = ai_analysis.get("final_confidence", confidence)

    # Determine final trading decision
    final_signal = ai_signal if ai_analysis.get("enabled") else signal
    final_confidence = ai_confidence if ai_analysis.get("enabled") else confidence

    # Signal formatting
    signal_emoji = "🟢 BUY" if final_signal == "buy" else "🔴 SELL" if final_signal == "sell" else "🟡 HOLD"
    confidence_stars = "⭐" * min(final_confidence // 2, 5)
    risk_level = "🔴 HIGH" if final_confidence < 5 else "🟡 MEDIUM" if final_confidence < 8 else "🟢 LOW"

    # Trading levels
    entry_price = risk_mgmt.get("entry_price", current_price)
    stop_loss = risk_mgmt.get("stop_loss", "Calculate based on risk")
    take_profit = risk_mgmt.get("take_profit", "Target 1:2 RR minimum")
    breakeven = risk_mgmt.get("breakeven", "Move to entry after 50% target")

    # Build professional message
    message = f"""
🎯 *PROFESSIONAL TRADING SIGNAL*

📊 *{symbol_name} ({symbol})*
{signal_emoji} • {confidence_stars} Confidence: {final_confidence}/10
⚠️ Risk Level: {risk_level}

💰 *Current Price*: {current_price}
⏰ *Timeframe*: {timeframe}
📅 *Analysis*: {datetime.now().strftime('%H:%M UTC')}

{'─' * 40}

🔥 *TRADING RECOMMENDATION*
"""

    if final_signal in ["buy", "sell"]:
        direction = "LONG (BUY)" if final_signal == "buy" else "SHORT (SELL)"
        message += f"""
✅ *SIGNAL: {direction}*
🎯 *Confidence: {final_confidence}/10*

💵 *ORDER DETAILS:*
• Entry Price: {entry_price}
• Stop Loss: {stop_loss}
• Take Profit: {take_profit}
• Breakeven: {breakeven}
• Risk/Reward: {risk_mgmt.get('risk_reward_ratio', '1:2 minimum')}

📋 *EXECUTION CHECKLIST:*
✅ Account balance verified
✅ Risk per trade ≤ 1-2%
✅ Stop loss set first
✅ Take profit at target levels
✅ Monitor closely after entry
"""

        # AI Reasoning
        if ai_analysis.get("enabled") and ai_analysis.get("ai_reasoning"):
            reasoning = ai_analysis["ai_reasoning"]
            # Extract key parts from AI response
            if "REASONING:" in reasoning:
                ai_reason = reasoning.split("REASONING:")[1].split("\n")[0][:150]
            else:
                ai_reason = reasoning[:150]

            message += f"""
🤖 *AI ANALYSIS:*
{ai_reason}...
"""
    else:
        message += """
⚪ *SIGNAL: HOLD / NEUTRAL*

📊 *Market conditions not favorable for new positions*

⏳ *Wait for stronger signals before entering trades*
"""

    # Technical Analysis Summary
    techniques = []
    if advanced.get("ict_analysis"):
        techniques.append("ICT")
    if advanced.get("smc_analysis"):
        techniques.append("SMC")
    if advanced.get("crt_analysis"):
        techniques.append("CRT")
    if advanced.get("breakout_analysis"):
        techniques.append("BREAKOUT")

    if techniques:
        message += f"""
🔬 *TECHNIQUES USED:*
{", ".join(techniques)} multi-timeframe analysis
"""

    message += f"""
{'─' * 40}

⚠️ *RISK MANAGEMENT:*
• Never risk more than 1-2% per trade
• Always use stop losses
• Cut losses quickly, let profits run
• Trade with proper position sizing

🕒 *Signal expires in 4 hours*
📈 *Trade responsibly with Baron AI*

_Last updated: {signal_data['timestamp']}_
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
