import yfinance as yf
import pandas as pd

# Test data loading for common symbols
symbols = ['GC=F', 'BTC-USD', 'EURUSD=X', 'XAUUSD=X']

for symbol in symbols:
    print(f'Testing {symbol}...')
    try:
        data = yf.download(symbol, period='5d', interval='15m', progress=False)
        print(f'  Data shape: {data.shape}')
        print(f'  Empty: {data.empty}')
        if not data.empty:
            print(f'  Last close: {data["Close"].iloc[-1]:.5f}')
        print()
    except Exception as e:
        print(f'  Error: {e}')
        print()
