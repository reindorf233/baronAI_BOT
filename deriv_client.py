"""
Deriv API Client for fetching live synthetic indices data
"""
import logging
import asyncio
import json
import websockets
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import pandas as pd
import os

# Deriv API Configuration
DERIV_API_TOKEN = os.getenv("DERIV_API_TOKEN")
DERIV_APP_ID = os.getenv("DERIV_APP_ID", "12345")  # Default demo app ID
DERIV_ENVIRONMENT = os.getenv("DERIV_ENVIRONMENT", "demo")

# Deriv WebSocket URLs
DERIV_DEMO_URL = "wss://ws.binaryws.com/websockets/v3?app_id=" + DERIV_APP_ID
DERIV_LIVE_URL = "wss://ws.binaryws.com/websockets/v3?app_id=" + DERIV_APP_ID

# All Deriv Synthetic Indices
DERIV_SYNTHETIC_INDICES = {
    # Volatility Indices
    "R_10": "Volatility 10 Index",
    "R_25": "Volatility 25 Index", 
    "R_50": "Volatility 50 Index",
    "R_75": "Volatility 75 Index",
    "R_100": "Volatility 100 Index",
    
    # Boom & Crash Indices
    "BOOM1000": "Boom 1000 Index",
    "BOOM500": "Boom 500 Index", 
    "BOOM300": "Boom 300 Index",
    "CRASH1000": "Crash 1000 Index",
    "CRASH500": "Crash 500 Index",
    "CRASH300": "Crash 300 Index",
    
    # Step Index
    "STEP INDEX": "Step Index",
    
    # Jump Indices
    "JUMP10": "Jump 10 Index",
    "JUMP25": "Jump 25 Index",
    "JUMP50": "Jump 50 Index",
    "JUMP75": "Jump 75 Index",
    "JUMP100": "Jump 100 Index",
    
    # Range Break Indices
    "RANGE BREAK 200": "Range Break 200 Index",
    "RANGE BREAK 100": "Range Break 100 Index",
    "RANGE BREAK 50": "Range Break 50 Index"
}

class DerivClient:
    def __init__(self):
        self.ws_url = DERIV_DEMO_URL if DERIV_ENVIRONMENT == "demo" else DERIV_LIVE_URL
        self.websocket = None
        self.authorized = False
        self.req_id = 0
        
    async def connect(self):
        """Connect to Deriv WebSocket API"""
        try:
            self.websocket = await websockets.connect(self.ws_url)
            logging.info(f"Connected to Deriv {DERIV_ENVIRONMENT} environment")
            
            # Authorize with API token
            await self.authorize()
            return True
        except Exception as e:
            logging.error(f"Failed to connect to Deriv: {e}")
            return False
    
    async def authorize(self):
        """Authorize with Deriv API"""
        if not DERIV_API_TOKEN:
            logging.error("DERIV_API_TOKEN not found in environment variables")
            return False
            
        try:
            auth_msg = {
                "authorize": DERIV_API_TOKEN
            }
            await self.websocket.send(json.dumps(auth_msg))
            response = await self.websocket.recv()
            data = json.loads(response)
            
            if "error" in data:
                logging.error(f"Authorization failed: {data['error']['message']}")
                return False
            
            self.authorized = True
            logging.info("Successfully authorized with Deriv API")
            return True
        except Exception as e:
            logging.error(f"Authorization error: {e}")
            return False
    
    async def get_candles(self, symbol: str, timeframe: str, count: int = 100) -> pd.DataFrame:
        """
        Fetch candle data from Deriv
        
        Args:
            symbol: Deriv symbol (e.g., 'R_50', 'BOOM1000')
            timeframe: Timeframe ('1m', '5m', '15m', '1h', '4h', '1d')
            count: Number of candles to fetch
        """
        if not self.authorized:
            if not await self.connect():
                return pd.DataFrame()
        
        try:
            # Convert timeframe to Deriv format
            granularity = self._convert_timeframe(timeframe)
            
            # Request ticks history
            self.req_id += 1
            request = {
                "ticks_history": symbol,
                "adjust_start_time": 1,
                "count": count,
                "end": "latest",
                "style": "candles",
                "granularity": granularity,
                "req_id": self.req_id
            }
            
            await self.websocket.send(json.dumps(request))
            response = await self.websocket.recv()
            data = json.loads(response)
            
            if "error" in data:
                logging.error(f"Error fetching candles: {data['error']['message']}")
                return pd.DataFrame()
            
            # Convert to DataFrame
            if "candles" in data:
                candles = data["candles"]
                df_data = []
                
                for candle in candles:
                    df_data.append({
                        "time": pd.to_datetime(candle["epoch"], unit="s"),
                        "Open": float(candle["open"]),
                        "High": float(candle["high"]),
                        "Low": float(candle["low"]),
                        "Close": float(candle["close"]),
                        "Volume": 0  # Volume not provided by Deriv
                    })
                
                df = pd.DataFrame(df_data)
                df.set_index("time", inplace=True)
                df.sort_index(inplace=True)
                
                logging.info(f"Successfully fetched {len(df)} candles for {symbol}")
                return df
            else:
                logging.warning(f"No candles data received for {symbol}")
                return pd.DataFrame()
                
        except Exception as e:
            logging.error(f"Error fetching candles for {symbol}: {e}")
            return pd.DataFrame()
    
    def _convert_timeframe(self, timeframe: str) -> int:
        """Convert timeframe string to Deriv granularity in seconds"""
        timeframe_map = {
            "1m": 60,
            "5m": 300,
            "15m": 900,
            "30m": 1800,
            "1h": 3600,
            "2h": 7200,
            "4h": 14400,
            "1d": 86400
        }
        return timeframe_map.get(timeframe.lower(), 300)  # Default to 5m
    
    async def get_available_symbols(self) -> List[str]:
        """Get list of available synthetic indices"""
        if not self.authorized:
            if not await self.connect():
                return []
        
        try:
            self.req_id += 1
            request = {
                "active_symbols": "brief",
                "product_type": "basic",
                "req_id": self.req_id
            }
            
            await self.websocket.send(json.dumps(request))
            response = await self.websocket.recv()
            data = json.loads(response)
            
            if "error" in data:
                logging.error(f"Error fetching symbols: {data['error']['message']}")
                return []
            
            symbols = []
            if "active_symbols" in data:
                for symbol_data in data["active_symbols"]:
                    symbol = symbol_data["symbol"]
                    if symbol in DERIV_SYNTHETIC_INDICES:
                        symbols.append(symbol)
            
            return symbols
            
        except Exception as e:
            logging.error(f"Error fetching symbols: {e}")
            return []
    
    async def close(self):
        """Close WebSocket connection"""
        if self.websocket:
            await self.websocket.close()
            self.authorized = False

# Global client instance
deriv_client = DerivClient()

async def get_deriv_candles(symbol: str, timeframe: str, count: int = 100) -> pd.DataFrame:
    """Convenience function to get candles from Deriv"""
    return await deriv_client.get_candles(symbol, timeframe, count)

def is_deriv_symbol(symbol: str) -> bool:
    """Check if symbol is a valid Deriv synthetic index"""
    return symbol.upper() in DERIV_SYNTHETIC_INDICES

def get_deriv_symbol_name(symbol: str) -> str:
    """Get the full name of a Deriv symbol"""
    return DERIV_SYNTHETIC_INDICES.get(symbol.upper(), symbol)
