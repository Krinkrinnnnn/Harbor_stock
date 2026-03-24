"""
VCP + RS Stock Screener
=======================
Screens a list of stocks for VCP (Volatility Contraction Pattern) + RS (Relative Strength) setups.
Pulls tickers from Nasdaq 100, S&P 500, and Russell 2000.

Usage:
    python3 vcp_screener.py
    python3 vcp_screener.py --index nq100
    python3 vcp_screener.py --tickers AAPL TSLA NVDA MSFT
    python3 vcp_screener.py --file tickers.txt
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import sys, os
from multiprocessing import Pool, cpu_count

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from minervini_screener import INDEX_MAP, get_all_us_tickers
from filters import check_liquidity, check_new_high_rs, LIQUIDITY_PARAMS

NUM_WORKERS = max(1, cpu_count() - 1)


# ==========================================
# SCREENER PARAMETERS (match backtester)
# ==========================================
SCREENER_PARAMS = {
    "rs_score_threshold": 60,       # Minimum RS percentile
    "rs_line_threshold": 1.0,       # RS ratio vs S&P 500
    "volatility_max": 0.12,         # Max ATR/Price ratio
    "volatility_contraction": 0.85, # Volatility contraction threshold
    "breakout_window": 20,          # N-day high breakout
    "ema_short_period": 13,
    "ema_long_period": 120,
    "sma_period": 50,
    "force_index_period": 13,
    "min_volume_avg": 500000,       # Minimum average volume
    "min_price": 20.0,              # Minimum stock price
    "data_period": "1y",           # How much history to fetch
}


# Default watchlist



def fetch_data(ticker, period="1y"):
    """Fetch OHLCV data for a single ticker."""
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=period)
        if df.empty:
            return None
        df.columns = [col.capitalize() for col in df.columns]
        return df
    except Exception:
        return None


def fetch_benchmark(period="1y"):
    """Fetch S&P 500 benchmark data."""
    try:
        spy = yf.Ticker("^GSPC")
        df = spy.history(period=period)
        if df.empty:
            return None
        df.columns = [col.capitalize() for col in df.columns]
        return df
    except Exception:
        return None


def calculate_indicators(df, benchmark_df, params):
    """
    Calculate all screening indicators for a stock.
    Returns a dict with scores and signals.
    """
    result = {
        "ticker": None,
        "price": 0,
        "rs_line": 0,
        "rs_score": 0,
        "volatility": 0,
        "atr_ratio": 0,
        "force_index": 0,
        "above_sma50": False,
        "ema_bullish": False,
        "breakout": False,
        "vol_contracting": False,
        "signal": False,
        "signal_strength": 0,
        "volume_avg": 0,
    }

    if df is None or len(df) < 60:
        return result

    # Basic data
    result["price"] = df['Close'].iloc[-1]
    result["volume_avg"] = df['Volume'].rolling(20).mean().iloc[-1]

    # Price filter
    if result["price"] < params["min_price"]:
        return result
    if result["volume_avg"] < params["min_volume_avg"]:
        return result

    # RS Line vs benchmark
    if benchmark_df is not None and not benchmark_df.empty:
        aligned_bench = benchmark_df.reindex(df.index, method='ffill')
        if not aligned_bench.empty:
            base_stock = df['Close'].iloc[0]
            base_bench = aligned_bench['Close'].iloc[0]
            if base_bench > 0:
                rs_line = (df['Close'] / base_stock) / (aligned_bench['Close'] / base_bench)
                result["rs_line"] = rs_line.iloc[-1]

                # RS Score (percentile)
                rs_min = rs_line.rolling(252, min_periods=20).min().iloc[-1]
                rs_max = rs_line.rolling(252, min_periods=20).max().iloc[-1]
                if rs_max > rs_min:
                    result["rs_score"] = ((result["rs_line"] - rs_min) / (rs_max - rs_min)) * 100

    # Moving Averages
    ema_short = df['Close'].ewm(span=params["ema_short_period"], adjust=False).mean()
    ema_long = df['Close'].ewm(span=params["ema_long_period"], adjust=False).mean()
    sma = df['Close'].rolling(window=params["sma_period"]).mean()

    result["above_sma50"] = result["price"] > sma.iloc[-1] if not pd.isna(sma.iloc[-1]) else False
    result["ema_bullish"] = ema_short.iloc[-1] > ema_long.iloc[-1] if not pd.isna(ema_long.iloc[-1]) else False

    # ATR (volatility)
    high_low = df['High'] - df['Low']
    high_close = abs(df['High'] - df['Close'].shift(1))
    low_close = abs(df['Low'] - df['Close'].shift(1))
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    atr = true_range.rolling(window=20).mean().iloc[-1]
    result["atr_ratio"] = atr / result["price"] if result["price"] > 0 else 0

    # Volatility contraction
    current_vol = (df['High'].rolling(20).max() - df['Low'].rolling(20).min()).iloc[-1] / result["price"]
    past_vol = (df['High'].rolling(20).max() - df['Low'].rolling(20).min()).shift(10).iloc[-1] / df['Close'].shift(10).iloc[-1] if not pd.isna(df['Close'].shift(10).iloc[-1]) else 1
    result["volatility"] = current_vol
    result["vol_contracting"] = current_vol < past_vol * params["volatility_contraction"] if past_vol > 0 else False

    # Breakout
    high_n = df['High'].rolling(window=params["breakout_window"]).max().iloc[-1]
    result["breakout"] = result["price"] >= high_n

    # Force Index
    force = (df['Close'] - df['Close'].shift(1)) * df['Volume']
    force_ema = force.ewm(span=params["force_index_period"]).mean().iloc[-1]
    result["force_index"] = force_ema

    # Composite Signal
    conditions = [
        result["rs_score"] >= params["rs_score_threshold"],
        result["rs_line"] >= params["rs_line_threshold"],
        result["above_sma50"],
        result["ema_bullish"],
        result["atr_ratio"] <= params["volatility_max"],
        result["vol_contracting"],
        result["breakout"],
        result["force_index"] > 0,
    ]

    result["signal"] = all(conditions)
    result["signal_strength"] = sum(conditions) / len(conditions) * 100

    return result


def run_screener(tickers=None, params=None, benchmark_df=None, indices=None, config=None):
    """
    Run the VCP + RS screener on a list of tickers.
    
    Args:
        tickers: List of stock symbols
        params: Screener parameters dict
        benchmark_df: Pre-fetched benchmark data
        indices: List of index keys to pull tickers from
        config: Dict with 'enable_liquidity_filter' and 'enable_new_high_rs' keys
    """
    if params is None:
        params = SCREENER_PARAMS
    
    if config is None:
        config = {
            "enable_liquidity_filter": True,
            "enable_new_high_rs": True,
        }
    
    enable_liquidity = config.get("enable_liquidity_filter", True)
    enable_new_high_rs = config.get("enable_new_high_rs", True)

    # Collect tickers
    if tickers is None:
        if indices is None:
            indices = ["all"]
        tickers = []
        index_names = []
        for idx in indices:
            if idx in INDEX_MAP:
                name, getter = INDEX_MAP[idx]
                tickers.extend(getter())
                index_names.append(name)
        tickers = list(dict.fromkeys(tickers))
    else:
        tickers = [t.upper() for t in tickers]
        index_names = ["Custom"]

    print(f"\n{'='*80}")
    print(f"  VCP + RS STOCK SCREENER")
    print(f"  Indices: {', '.join(index_names)}")
    print(f"  Total stocks to scan: {len(tickers)}")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*80}")
    
    print(f"\n  Filters:")
    print(f"    Liquidity Filter: {'ON' if enable_liquidity else 'OFF'} (Market Cap > $2B, Vol > $50M)")
    print(f"    New High RS Flag: {'ON' if enable_new_high_rs else 'OFF'}")

    # Phase 1: Liquidity filter with multiprocessing
    liquid_tickers = set()
    if enable_liquidity:
        print(f"\n  [Phase 1] Checking liquidity with {NUM_WORKERS} workers...")
        
        def _check_liquidity_batch(batch):
            return [t for t in batch if check_liquidity(t)[0]]
        
        batch_size = max(1, len(tickers) // NUM_WORKERS)
        batches = [tickers[i:i + batch_size] for i in range(0, len(tickers), batch_size)]
        
        with Pool(NUM_WORKERS) as pool:
            results = pool.map(_check_liquidity_batch, batches)
        
        for r in results:
            liquid_tickers.update(r)
        
        print(f"    Liquid stocks: {len(liquid_tickers)}/{len(tickers)}")
    else:
        liquid_tickers = set(tickers)

    # Fetch benchmark
    if benchmark_df is None:
        print("\n  [Phase 2] Fetching S&P 500 benchmark data...")
        benchmark_df = fetch_benchmark(params["data_period"])

    results = []
    signal_stocks = []

    print(f"\n  [Phase 3] Running VCP+RS screening with {NUM_WORKERS} workers...")
    
    liquid_list = list(liquid_tickers)
    batch_size = max(1, len(liquid_list) // NUM_WORKERS)
    batches = [liquid_list[i:i + batch_size] for i in range(0, len(liquid_list), batch_size)]
    
    def _screen_vcp_batch(batch):
        batch_results = []
        for ticker in batch:
            df = fetch_data(ticker, params["data_period"])
            r = calculate_indicators(df, benchmark_df, params)
            r["ticker"] = ticker
            batch_results.append(r)
        return batch_results
    
    with Pool(NUM_WORKERS) as pool:
        batch_results_list = pool.map(_screen_vcp_batch, batches)
    
    for batch_results in batch_results_list:
        for r in batch_results:
            r["liquidity_pass"] = True
            
            # Add new high RS flag for signal stocks
            if enable_new_high_rs and r["signal"]:
                is_new_high, rs_details = check_new_high_rs(r["ticker"], df=None)
                r["new_high_rs"] = is_new_high
            else:
                r["new_high_rs"] = False
            
            results.append(r)
            
            if r["signal"]:
                signal_stocks.append(r)
    
    print(f"    Processed {len(results)} stocks")

    print(f"\n\n  Screening complete: {len(results)} stocks analyzed")
    print(f"  {'='*76}")

    # Print all results sorted by signal strength
    results.sort(key=lambda x: x["signal_strength"], reverse=True)

    rs_col = " RS>Hi" if enable_new_high_rs else ""
    print(f"\n  {'Ticker':<8} {'Price':>8} {'RS Line':>8} {'RS%':>6} {'ATR%':>6} "
          f"{'Force':>10} {'SMA50':>5} {'EMA':>5} {'B/O':>4} {'VCP':>4} {'Signal':>7} {'Str%':>5}{rs_col}")
    print(f"  {'-'*8} {'-'*8} {'-'*8} {'-'*6} {'-'*6} "
          f"{'-'*10} {'-'*5} {'-'*5} {'-'*4} {'-'*4} {'-'*7} {'-'*5}{'-'*6 if enable_new_high_rs else ''}")

    for r in results:
        if r["price"] == 0:
            continue
        rs_flag = f"  ★" if enable_new_high_rs and r.get("new_high_rs", False) else ""
        print(f"  {r['ticker']:<8} ${r['price']:>6.2f} {r['rs_line']:>8.2f} "
              f"{r['rs_score']:>5.0f} {r['atr_ratio']*100:>5.1f} "
              f"{r['force_index']:>10.0f} "
              f"{'  ✓' if r['above_sma50'] else '  ✗':>5} "
              f"{'  ✓' if r['ema_bullish'] else '  ✗':>5} "
              f"{' ✓' if r['breakout'] else ' ✗':>4} "
              f"{' ✓' if r['vol_contracting'] else ' ✗':>4} "
              f"{'  ✓ BUY' if r['signal'] else '  ---':>7} "
              f"{r['signal_strength']:>5.0f}{rs_flag}")

    # Print top signals
    if signal_stocks:
        print(f"\n  {'='*76}")
        print(f"  🚀 TOP VCP + RS SIGNALS ({len(signal_stocks)} stocks)")
        print(f"  {'='*76}")
        for r in signal_stocks:
            rs_indicator = " ★RS" if enable_new_high_rs and r.get("new_high_rs", False) else ""
            print(f"  ★ {r['ticker']:<6} ${r['price']:>8.2f}  RS:{r['rs_score']:.0f}  "
                  f"ATR:{r['atr_ratio']*100:.1f}%  Strength:{r['signal_strength']:.0f}%{rs_indicator}")
    else:
        print(f"\n  No VCP + RS signals found at this time.")
        # Show near-signals
        near = [r for r in results if r["signal_strength"] >= 75 and r["price"] > 0]
        if near:
            print(f"\n  📊 Near-Signal Stocks (≥75% criteria met):")
            for r in near[:10]:
                print(f"    {r['ticker']:<6} ${r['price']:>8.2f}  Strength:{r['signal_strength']:.0f}%")

    print(f"\n{'='*80}\n")

    return pd.DataFrame(results)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="VCP + RS Stock Screener")
    parser.add_argument("--tickers", nargs="+", help="List of tickers to screen")
    parser.add_argument("--file", type=str, help="File with tickers (one per line)")
    parser.add_argument("--index", nargs="+", choices=["nq100", "sp500", "russell2000", "all"],
                        help="Indices to scan (default: all)")
    parser.add_argument("--no-liquidity", action="store_true", help="Disable liquidity filter")
    parser.add_argument("--no-rs-flag", action="store_true", help="Disable new high RS flag")
    args = parser.parse_args()

    tickers = None
    if args.tickers:
        tickers = [t.upper() for t in args.tickers]
    elif args.file:
        with open(args.file, 'r') as f:
            tickers = [line.strip().upper() for line in f if line.strip()]
    
    config = {
        "enable_liquidity_filter": not args.no_liquidity,
        "enable_new_high_rs": not args.no_rs_flag,
    }

    run_screener(tickers, indices=args.index, config=config)
