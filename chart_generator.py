"""
Live Chart Generation for Deriv Synthetic Indices
"""
import logging
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import io
import base64
from typing import Dict, Optional
import ta

# Configure matplotlib for better output
plt.style.use('dark_background')
plt.rcParams['figure.figsize'] = (12, 8)
plt.rcParams['font.size'] = 10

def create_technical_chart(df: pd.DataFrame, symbol: str, timeframe: str, 
                          breakout_analysis: Optional[Dict] = None) -> str:
    """
    Create a comprehensive technical analysis chart using Plotly
    
    Returns:
        Base64 encoded image string
    """
    try:
        # Create subplots
        fig = make_subplots(
            rows=3, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.05,
            subplot_titles=(f'{symbol} - {timeframe}', 'RSI', 'MACD'),
            row_width=[0.2, 0.2, 0.7]
        )
        
        # Main price chart
        fig.add_trace(
            go.Candlestick(
                x=df.index,
                open=df['Open'],
                high=df['High'],
                low=df['Low'],
                close=df['Close'],
                name='Price',
                increasing_line_color='#00ff88',
                decreasing_line_color='#ff4444'
            ),
            row=1, col=1
        )
        
        # Add moving averages
        if len(df) > 20:
            ma20 = df['Close'].rolling(20).mean()
            ma50 = df['Close'].rolling(50).mean() if len(df) > 50 else None
            
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=ma20,
                    mode='lines',
                    name='MA20',
                    line=dict(color='orange', width=1)
                ),
                row=1, col=1
            )
            
            if ma50 is not None:
                fig.add_trace(
                    go.Scatter(
                        x=df.index,
                        y=ma50,
                        mode='lines',
                        name='MA50',
                        line=dict(color='blue', width=1)
                    ),
                    row=1, col=1
                )
        
        # Add breakout levels if available
        if breakout_analysis and breakout_analysis.get("pattern") == "breakout_retest":
            resistance = breakout_analysis.get("resistance_level")
            support = breakout_analysis.get("support_level")
            
            if resistance:
                fig.add_hline(
                    y=resistance,
                    line_dash="dash",
                    line_color="red",
                    annotation_text=f"R: {resistance}",
                    row=1, col=1
                )
            
            if support:
                fig.add_hline(
                    y=support,
                    line_dash="dash",
                    line_color="green",
                    annotation_text=f"S: {support}",
                    row=1, col=1
                )
        
        # RSI Chart
        rsi = ta.momentum.RSIIndicator(df['Close']).rsi()
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=rsi,
                mode='lines',
                name='RSI',
                line=dict(color='purple', width=2)
            ),
            row=2, col=1
        )
        
        # RSI levels
        fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)
        fig.add_hline(y=50, line_dash="dash", line_color="gray", row=2, col=1)
        
        # MACD Chart
        macd = ta.trend.MACD(df['Close'])
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=macd.macd(),
                mode='lines',
                name='MACD',
                line=dict(color='blue', width=2)
            ),
            row=3, col=1
        )
        
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=macd.macd_signal(),
                mode='lines',
                name='Signal',
                line=dict(color='red', width=2)
            ),
            row=3, col=1
        )
        
        # MACD Histogram
        colors = ['green' if x >= 0 else 'red' for x in macd.macd_histogram()]
        fig.add_trace(
            go.Bar(
                x=df.index,
                y=macd.macd_histogram(),
                name='Histogram',
                marker_color=colors,
                opacity=0.6
            ),
            row=3, col=1
        )
        
        # Update layout
        fig.update_layout(
            title=f'{symbol} Technical Analysis - {datetime.now().strftime("%Y-%m-%d %H:%M")}',
            xaxis_rangeslider_visible=False,
            template='plotly_dark',
            height=800,
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )
        
        # Update y-axes
        fig.update_yaxes(title_text="Price", row=1, col=1)
        fig.update_yaxes(title_text="RSI", row=2, col=1, range=[0, 100])
        fig.update_yaxes(title_text="MACD", row=3, col=1)
        
        # Convert to image
        img_bytes = fig.to_image(format="png", width=1200, height=800)
        img_base64 = base64.b64encode(img_bytes).decode()
        
        return img_base64
        
    except Exception as e:
        logging.error(f"Error creating chart: {e}")
        return ""

def create_breakout_chart(df: pd.DataFrame, symbol: str, breakout_analysis: Dict) -> str:
    """
    Create a specialized breakout chart highlighting key levels
    
    Returns:
        Base64 encoded image string
    """
    try:
        fig = go.Figure()
        
        # Candlestick chart
        fig.add_trace(
            go.Candlestick(
                x=df.index,
                open=df['Open'],
                high=df['High'],
                low=df['Low'],
                close=df['Close'],
                name='Price',
                increasing_line_color='#00ff88',
                decreasing_line_color='#ff4444'
            )
        )
        
        # Add breakout levels
        resistance = breakout_analysis.get("resistance_level")
        support = breakout_analysis.get("support_level")
        entry_price = breakout_analysis.get("entry_price")
        stop_loss = breakout_analysis.get("stop_loss")
        take_profit = breakout_analysis.get("take_profit")
        
        # Resistance level
        if resistance:
            fig.add_hline(
                y=resistance,
                line_dash="dash",
                line_color="red",
                line_width=2,
                annotation_text=f"Resistance: {resistance}",
                annotation_position="top right"
            )
        
        # Support level
        if support:
            fig.add_hline(
                y=support,
                line_dash="dash",
                line_color="green",
                line_width=2,
                annotation_text=f"Support: {support}",
                annotation_position="bottom right"
            )
        
        # Entry price
        if entry_price:
            fig.add_hline(
                y=entry_price,
                line_dash="solid",
                line_color="yellow",
                line_width=2,
                annotation_text=f"Entry: {entry_price}",
                annotation_position="top left"
            )
        
        # Stop loss
        if stop_loss:
            fig.add_hline(
                y=stop_loss,
                line_dash="solid",
                line_color="red",
                line_width=2,
                annotation_text=f"Stop Loss: {stop_loss}",
                annotation_position="bottom left"
            )
        
        # Take profit
        if take_profit:
            fig.add_hline(
                y=take_profit,
                line_dash="solid",
                line_color="green",
                line_width=2,
                annotation_text=f"Take Profit: {take_profit}",
                annotation_position="top left"
            )
        
        # Add volume proxy (price range)
        price_range = df['High'] - df['Low']
        fig.add_trace(
            go.Bar(
                x=df.index,
                y=price_range,
                name='Volatility',
                marker_color='rgba(128, 128, 128, 0.3)',
                yaxis='y2'
            )
        )
        
        # Update layout
        signal_emoji = "🟢" if breakout_analysis.get("signal") == "buy" else "🔴" if breakout_analysis.get("signal") == "sell" else "🟡"
        fig.update_layout(
            title=f'{signal_emoji} {symbol} Breakout Analysis - {breakout_analysis.get("signal", "neutral").upper()}',
            xaxis_rangeslider_visible=False,
            template='plotly_dark',
            height=600,
            showlegend=True,
            yaxis=dict(title="Price"),
            yaxis2=dict(title="Volatility", overlaying="y", side="right", showgrid=False)
        )
        
        # Convert to image
        img_bytes = fig.to_image(format="png", width=1200, height=600)
        img_base64 = base64.b64encode(img_bytes).decode()
        
        return img_base64
        
    except Exception as e:
        logging.error(f"Error creating breakout chart: {e}")
        return ""

def save_chart_to_file(img_base64: str, filename: str) -> str:
    """Save base64 image to file"""
    try:
        img_data = base64.b64decode(img_base64)
        filepath = f"data/{filename}"
        
        with open(filepath, 'wb') as f:
            f.write(img_data)
        
        return filepath
    except Exception as e:
        logging.error(f"Error saving chart: {e}")
        return ""

def create_simple_chart(df: pd.DataFrame, symbol: str) -> str:
    """Create a simple matplotlib chart as fallback"""
    try:
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), gridspec_kw={'height_ratios': [3, 1]})
        
        # Price chart
        ax1.plot(df.index, df['Close'], label='Close Price', color='white', linewidth=2)
        ax1.fill_between(df.index, df['Low'], df['High'], alpha=0.3, color='gray')
        ax1.set_title(f'{symbol} Price Chart')
        ax1.set_ylabel('Price')
        ax1.grid(True, alpha=0.3)
        ax1.legend()
        
        # Volume chart (using price range as proxy)
        volume = df['High'] - df['Low']
        ax2.bar(df.index, volume, color='lightblue', alpha=0.7)
        ax2.set_title('Volatility (Price Range)')
        ax2.set_ylabel('Range')
        ax2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        # Save to bytes
        img_buffer = io.BytesIO()
        plt.savefig(img_buffer, format='png', dpi=100, bbox_inches='tight')
        img_buffer.seek(0)
        
        # Convert to base64
        img_base64 = base64.b64encode(img_buffer.getvalue()).decode()
        plt.close()
        
        return img_base64
        
    except Exception as e:
        logging.error(f"Error creating simple chart: {e}")
        return ""
