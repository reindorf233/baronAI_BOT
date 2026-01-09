"""
Advanced Signal Analyzer combining multiple trading techniques
ICT, SMC, CRT, Breakout, and Retest analysis
"""
import logging
import pandas as pd
import numpy as np
from typing import Dict, Optional
from datetime import datetime

class AdvancedSignalAnalyzer:
    """
    Advanced signal analyzer combining multiple trading techniques:
    - ICT (Inner Circle Trader)
    - SMC (Smart Money Concepts)
    - CRT (Change of Character/Volume Profile)
    - Breakout and Retest patterns
    """

    def __init__(self):
        self.min_confidence = 3
        self.max_confidence = 10

    def generate_professional_signal(self, df: pd.DataFrame, symbol: str) -> Dict:
        """
        Generate comprehensive trading signal using multiple techniques

        Args:
            df: Price dataframe with OHLC data
            symbol: Trading symbol

        Returns:
            Dictionary with comprehensive analysis
        """
        try:
            if df.empty or len(df) < 50:
                return self._create_empty_signal(symbol)

            # Perform all technique analyses
            breakout_analysis = self._analyze_breakout_retest(df)
            ict_analysis = self._analyze_ict(df)
            smc_analysis = self._analyze_smc(df)
            crt_analysis = self._analyze_crt(df)

            # Generate risk management
            risk_management = self._calculate_risk_management(df, breakout_analysis)

            # Combine signals from all techniques
            composite_signal = self._combine_technique_signals(
                breakout_analysis, ict_analysis, smc_analysis, crt_analysis
            )

            # Calculate final confidence based on technique agreement
            final_confidence = self._calculate_final_confidence(
                composite_signal, breakout_analysis, ict_analysis, smc_analysis, crt_analysis
            )

            return {
                "symbol": symbol,
                "current_price": round(df['Close'].iloc[-1], 5),
                "composite_signal": {
                    "signal": composite_signal["signal"],
                    "confidence": final_confidence,
                    "techniques_agreeing": composite_signal["techniques_count"]
                },
                "breakout_analysis": breakout_analysis,
                "ict_analysis": ict_analysis,
                "smc_analysis": smc_analysis,
                "crt_analysis": crt_analysis,
                "risk_management": risk_management,
                "data": df,  # Keep dataframe for chart generation if needed
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
            }

        except Exception as e:
            logging.error(f"Error in advanced signal analysis for {symbol}: {e}")
            return self._create_empty_signal(symbol)

    def _analyze_breakout_retest(self, df: pd.DataFrame) -> Dict:
        """Analyze breakout and retest patterns"""
        try:
            # Calculate support and resistance levels
            recent_high = df['High'].tail(20).max()
            recent_low = df['Low'].tail(20).min()
            current_price = df['Close'].iloc[-1]

            # Simple breakout detection
            breakout_up = current_price > recent_high * 0.999  # Near resistance
            breakout_down = current_price < recent_low * 1.001  # Near support

            # Retest detection (price returning to breakout level)
            retest_up = abs(current_price - recent_high) / recent_high < 0.005
            retest_down = abs(current_price - recent_low) / recent_low < 0.005

            # Determine signal
            if breakout_up or (breakout_up and retest_up):
                signal = "buy"
                confidence = 7
                direction = "bullish"
            elif breakout_down or (breakout_down and retest_down):
                signal = "sell"
                confidence = 7
                direction = "bearish"
            else:
                signal = "neutral"
                confidence = 3
                direction = "sideways"

            return {
                "pattern": "breakout_retest",
                "signal": signal,
                "confidence": confidence,
                "direction": direction,
                "breakout_strength": 75,  # Simplified
                "retest_status": "confirmed" if (retest_up or retest_down) else "pending",
                "resistance_level": round(recent_high, 5),
                "support_level": round(recent_low, 5),
                "entry_price": round(current_price, 5)
            }

        except Exception as e:
            logging.error(f"Breakout analysis error: {e}")
            return {"signal": "neutral", "confidence": 0}

    def _analyze_ict(self, df: pd.DataFrame) -> Dict:
        """Analyze using ICT (Inner Circle Trader) concepts"""
        try:
            # Simplified ICT analysis
            current_price = df['Close'].iloc[-1]

            # Market structure analysis
            highs = df['High'].tail(50)
            lows = df['Low'].tail(50)

            # Determine market structure
            if highs.is_monotonic_increasing and lows.is_monotonic_increasing:
                market_structure = "strong_uptrend"
                signal = "buy"
            elif highs.is_monotonic_decreasing and lows.is_monotonic_decreasing:
                market_structure = "strong_downtrend"
                signal = "sell"
            else:
                market_structure = "ranging"
                signal = "neutral"

            return {
                "market_structure": market_structure,
                "liquidity_zones": f"Above {highs.max():.5f}",
                "order_flow": "institutional" if abs(df['Volume'].iloc[-1] - df['Volume'].mean()) > df['Volume'].std() else "retail",
                "signal": signal,
                "confidence": 6
            }

        except Exception as e:
            logging.error(f"ICT analysis error: {e}")
            return {"signal": "neutral", "confidence": 0}

    def _analyze_smc(self, df: pd.DataFrame) -> Dict:
        """Analyze using SMC (Smart Money Concepts)"""
        try:
            # Simplified SMC analysis
            current_price = df['Close'].iloc[-1]

            # Look for order blocks (simplified)
            recent_swing_high = df['High'].tail(20).max()
            recent_swing_low = df['Low'].tail(20).min()

            # Determine smart money signal
            if current_price > recent_swing_high:
                smart_money_signal = "bullish_order_block"
                signal = "buy"
            elif current_price < recent_swing_low:
                smart_money_signal = "bearish_order_block"
                signal = "sell"
            else:
                smart_money_signal = "accumulation"
                signal = "neutral"

            return {
                "smart_money_signal": smart_money_signal,
                "order_blocks": f"Bullish above {recent_swing_high:.5f}",
                "internal_structure": "bullish" if signal == "buy" else "bearish" if signal == "sell" else "neutral",
                "signal": signal,
                "confidence": 6
            }

        except Exception as e:
            logging.error(f"SMC analysis error: {e}")
            return {"signal": "neutral", "confidence": 0}

    def _analyze_crt(self, df: pd.DataFrame) -> Dict:
        """Analyze using CRT (Change of Character)"""
        try:
            # Simplified volume profile and change of character
            volumes = df['Volume'].tail(20)
            avg_volume = volumes.mean()

            # Change of character detection
            recent_volume = volumes.iloc[-5:].mean()
            previous_volume = volumes.iloc[-10:-5].mean()

            if recent_volume > previous_volume * 1.5:
                change_of_character = "high_volume_breakout"
                signal = "buy" if df['Close'].iloc[-1] > df['Close'].iloc[-6] else "sell"
            else:
                change_of_character = "normal_volume"
                signal = "neutral"

            return {
                "change_of_character": change_of_character,
                "volume_profile": f"Avg: {avg_volume:.0f}",
                "fair_value_gaps": "identified" if abs(recent_volume - avg_volume) > avg_volume * 0.3 else "none",
                "signal": signal,
                "confidence": 5
            }

        except Exception as e:
            logging.error(f"CRT analysis error: {e}")
            return {"signal": "neutral", "confidence": 0}

    def _calculate_risk_management(self, df: pd.DataFrame, breakout_analysis: Dict) -> Dict:
        """Calculate comprehensive risk management parameters"""
        try:
            current_price = df['Close'].iloc[-1]
            atr = self._calculate_atr(df)

            # Position sizing and risk management
            signal = breakout_analysis.get("signal", "neutral")

            if signal == "buy":
                entry_price = current_price
                stop_loss = entry_price - (atr * 1.5)  # 1.5 ATR stop
                take_profit = entry_price + (atr * 3)  # 3:1 reward ratio
                risk_reward_ratio = "1:2"
            elif signal == "sell":
                entry_price = current_price
                stop_loss = entry_price + (atr * 1.5)
                take_profit = entry_price - (atr * 3)
                risk_reward_ratio = "1:2"
            else:
                entry_price = current_price
                stop_loss = "N/A"
                take_profit = "N/A"
                risk_reward_ratio = "N/A"

            # Breakeven calculation
            if signal in ["buy", "sell"]:
                breakeven_price = entry_price
                breakeven_trigger = "After 50% profit target reached"
            else:
                breakeven_price = "N/A"
                breakeven_trigger = "N/A"

            return {
                "entry_price": round(entry_price, 5),
                "stop_loss": round(stop_loss, 5) if isinstance(stop_loss, (int, float)) else stop_loss,
                "take_profit": round(take_profit, 5) if isinstance(take_profit, (int, float)) else take_profit,
                "breakeven": breakeven_price,
                "breakeven_trigger": breakeven_trigger,
                "risk_reward_ratio": risk_reward_ratio,
                "atr": round(atr, 5),
                "position_size": "Calculate based on 1-2% risk per trade",
                "max_loss": f"${(entry_price - stop_loss):.5f}" if isinstance(stop_loss, (int, float)) else "N/A"
            }

        except Exception as e:
            logging.error(f"Risk management calculation error: {e}")
            return {
                "entry_price": "Market",
                "stop_loss": "N/A",
                "take_profit": "N/A",
                "breakeven": "N/A",
                "risk_reward_ratio": "N/A",
                "atr": 0,
                "position_size": "N/A",
                "max_loss": "N/A"
            }

    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        """Calculate Average True Range"""
        try:
            high = df['High']
            low = df['Low']
            close = df['Close'].shift(1)

            tr1 = high - low
            tr2 = abs(high - close)
            tr3 = abs(low - close)

            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = tr.rolling(period).mean()

            return atr.iloc[-1] if not atr.empty else 0.0001
        except:
            return 0.0001

    def _combine_technique_signals(self, breakout: Dict, ict: Dict, smc: Dict, crt: Dict) -> Dict:
        """Combine signals from all techniques"""
        signals = [breakout, ict, smc, crt]

        # Count signals by type
        buy_signals = sum(1 for s in signals if s.get("signal") == "buy")
        sell_signals = sum(1 for s in signals if s.get("signal") == "sell")
        neutral_signals = sum(1 for s in signals if s.get("signal") == "neutral")

        # Determine composite signal
        if buy_signals >= 3:  # Majority buy signals
            composite_signal = "buy"
            techniques_count = buy_signals
        elif sell_signals >= 3:  # Majority sell signals
            composite_signal = "sell"
            techniques_count = sell_signals
        else:
            composite_signal = "neutral"
            techniques_count = max(buy_signals, sell_signals, neutral_signals)

        return {
            "signal": composite_signal,
            "techniques_count": techniques_count,
            "buy_agreement": buy_signals,
            "sell_agreement": sell_signals,
            "total_techniques": len(signals)
        }

    def _calculate_final_confidence(self, composite: Dict, breakout: Dict, ict: Dict, smc: Dict, crt: Dict) -> int:
        """Calculate final confidence based on technique agreement"""
        base_confidence = 5  # Base confidence

        # Agreement bonus
        techniques_agreeing = composite["techniques_count"]
        agreement_bonus = techniques_agreeing * 1.5

        # Technique quality bonus
        quality_bonus = 0
        if breakout.get("confidence", 0) >= 7:
            quality_bonus += 1
        if ict.get("confidence", 0) >= 6:
            quality_bonus += 1
        if smc.get("confidence", 0) >= 6:
            quality_bonus += 1
        if crt.get("confidence", 0) >= 5:
            quality_bonus += 1

        final_confidence = min(self.max_confidence, base_confidence + agreement_bonus + quality_bonus)

        return int(final_confidence)

    def _create_empty_signal(self, symbol: str) -> Dict:
        """Create empty signal structure for error cases"""
        return {
            "symbol": symbol,
            "current_price": 0,
            "composite_signal": {
                "signal": "neutral",
                "confidence": 0,
                "techniques_agreeing": 0
            },
            "breakout_analysis": {"signal": "neutral", "confidence": 0},
            "ict_analysis": {"signal": "neutral", "confidence": 0},
            "smc_analysis": {"signal": "neutral", "confidence": 0},
            "crt_analysis": {"signal": "neutral", "confidence": 0},
            "risk_management": {
                "entry_price": "N/A",
                "stop_loss": "N/A",
                "take_profit": "N/A",
                "breakeven": "N/A",
                "risk_reward_ratio": "N/A"
            },
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
        }