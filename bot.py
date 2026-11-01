import os
import time
import ccxt
import pandas as pd

# ------------------------------------------------------------------
# 1. CONFIGURATION & API SETUP
# ------------------------------------------------------------------
SYMBOL = 'BTC/USDT'           # Symbol to trade
TP_RANGE_PCT = 0.60           # 60% of daily range as TP target
LEVERAGE = 1                  # Adjust leverage as needed
RISK_AMOUNT_USDT = 100        # Position value or risk allocation in USDT

# Exchange API Credentials (Set via Environment Variables or paste directly for testing)
API_KEY = os.getenv('EXCHANGE_API_KEY', 'YOUR_API_KEY')
API_SECRET = os.getenv('EXCHANGE_API_SECRET', 'YOUR_API_SECRET')

# Initialize Exchange (Using Bybit USDT Perpetual - change to binance/okx if needed)
exchange = ccxt.bybit({
    'apiKey': API_KEY,
    'secret': API_SECRET,
    'enableRateLimit': True,
    'options': {'defaultType': 'future'}
})


def fetch_klines(symbol, timeframe, limit=5):
    """Fetches OHLCV data from the exchange into a Pandas DataFrame."""
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df


def get_previous_daily_range(symbol):
    """Fetches the high and low of the previous fully closed daily candle."""
    df_daily = fetch_klines(symbol, timeframe='1d', limit=3)
    # df_daily.iloc[-2] is the previous fully closed 1D candle
    prev_day = df_daily.iloc[-2]
    day_high = float(prev_day['high'])
    day_low = float(prev_day['low'])
    day_range = day_high - day_low
    return day_high, day_low, day_range


def check_sweep_signal(symbol):
    """
    Checks rule 2-4:
    - 4H candle breaks above/below daily range (sweep wick)
    - 4H candle closes BACK inside the daily range
    """
    day_high, day_low, day_range = get_previous_daily_range(symbol)
    df_4h = fetch_klines(symbol, timeframe='4h', limit=3)
    
    # Last completed 4H candle
    last_4h = df_4h.iloc[-2]
    c_open = float(last_4h['open'])
    c_high = float(last_4h['high'])
    c_low = float(last_4h['low'])
    c_close = float(last_4h['close'])

    signal = None
    sl_price = 0.0
    tp_price = 0.0

    # SHORT SETUP: 4H High swept Daily High, but 4H Close is BACK INSIDE (below Daily High)
    if c_high > day_high and c_close < day_high:
        signal = 'SHORT'
        sl_price = c_high  # SL above the sweep high
        entry_price = c_close
        tp_distance = day_range * TP_RANGE_PCT
        tp_price = entry_price - tp_distance

    # LONG SETUP: 4H Low swept Daily Low, but 4H Close is BACK INSIDE (above Daily Low)
    elif c_low < day_low and c_close > day_low:
        signal = 'LONG'
        sl_price = c_low  # SL below the sweep low
        entry_price = c_close
        tp_distance = day_range * TP_RANGE_PCT
        tp_price = entry_price + tp_distance

    return signal, c_close, sl_price, tp_price, day_high, day_low


def execute_trade(signal, entry_price, sl_price, tp_price):
    """Executes Market Order with attached Stop-Loss and Take-Profit."""
    print(f"🚀 EXECUTING {signal} TRADE!")
    print(f"Entry: {entry_price} | SL: {sl_price} | TP: {tp_price}")

    # Calculate position size in base currency (e.g. BTC)
    qty = RISK_AMOUNT_USDT / entry_price

    side = 'buy' if signal == 'LONG' else 'sell'
    
    try:
        # Place Market Order with TP/SL params (CCXT standard format)
        order = exchange.create_order(
            symbol=SYMBOL,
            type='market',
            side=side,
            amount=qty,
            params={
                'stopLoss': {'triggerPrice': str(sl_price)},
                'takeProfit': {'triggerPrice': str(tp_price)}
            }
        )
        print("✅ Order placed successfully:", order['id'])
    except Exception as e:
        print("❌ Order execution failed:", e)


def run_bot():
    """Main execution loop running every 4 hours."""
    print("🤖 Daily Candle Sweep Trading Bot Started...")
    
    while True:
        try:
            signal, entry, sl, tp, day_high, day_low = check_sweep_signal(SYMBOL)
            
            print(f"Checking {SYMBOL} | Daily High: {day_high} | Daily Low: {day_low}")
            
            if signal:
                execute_trade(signal, entry, sl, tp)
            else:
                print("No sweep signal detected on last 4H close.")

        except Exception as e:
            print("Error in bot loop:", e)

        # Wait 15 minutes before re-checking
        time.sleep(900) 


if __name__ == '__main__':
    run_bot()
