"""
Momentum Stock Screener
=======================
Screens for stocks with strong momentum characteristics from NQ100, S&P 500, and Russell 2000.

Usage:
    python3 momentum_screener.py
    python3 momentum_screener.py --index nq100
    python3 momentum_screener.py --tickers AAPL TSLA NVDA
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import sys, os
from multiprocessing import Pool, cpu_count

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from minervini_screener import INDEX_MAP
from filters import check_liquidity, check_new_high_rs, LIQUIDITY_PARAMS

NUM_WORKERS = max(1, cpu_count() - 1)


# ==========================================
# SCREENER PARAMETERS
# ==========================================
SCREENER_PARAMS = {
    # Momentum filters
    "min_price_pct_52w_high": 0.85,    # Must be within 15% of 52-week high
    "min_price_change_1m": 0.05,       # Minimum 5% gain in 1 month
    "min_price_change_3m": 0.10,       # Minimum 10% gain in 3 months
    "min_rs_score": 70,                # Minimum RS percentile vs S&P 500
    "min_rs_line": 1.0,                # Must outperform benchmark

    # Moving average filters
    "sma_short_period": 20,
    "sma_medium_period": 50,
    "sma_long_period": 200,
    "ema_period": 13,

    # Volume filters
    "min_volume_avg": 500000,          # Minimum average volume
    "min_volume_ratio": 1.0,           # Current vol / avg vol

    # Price filters
    "min_price": 20.0,
    "max_price": 10000.0,

    # Data
    "data_period": "1y",
}





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


def calculate_momentum(df, benchmark_df, params):
    """
    Calculate momentum indicators for a stock.
    Returns a dict with scores and signals.
    """
    result = {
        "ticker": None,
        "price": 0,
        "high_52w": 0,
        "pct_from_52w_high": 0,
        "change_1m": 0,
        "change_3m": 0,
        "change_6m": 0,
        "rs_line": 0,
        "rs_score": 0,
        "above_sma20": False,
        "above_sma50": False,
        "above_sma200": False,
        "sma_alignment": False,  # SMA20 > SMA50 > SMA200
        "ema_bullish": False,
        "volume_avg": 0,
        "volume_ratio": 0,
        "momentum_score": 0,
        "signal": False,
        "signal_strength": 0,
    }

    if df is None or len(df) < 200:
        return result

    # Basic price data
    price = df['Close'].iloc[-1]
    result["price"] = price

    # Price filters
    if price < params["min_price"] or price > params["max_price"]:
        return result

    # 52-week high
    if len(df) >= 252:
        high_52w = df['High'].rolling(252).max().iloc[-1]
    else:
        high_52w = df['High'].max()
    result["high_52w"] = high_52w
    result["pct_from_52w_high"] = price / high_52w if high_52w > 0 else 0

    # Price changes
    if len(df) >= 21:
        result["change_1m"] = (price / df['Close'].iloc[-21] - 1)
    if len(df) >= 63:
        result["change_3m"] = (price / df['Close'].iloc[-63] - 1)
    if len(df) >= 126:
        result["change_6m"] = (price / df['Close'].iloc[-126] - 1)

    # Volume
    vol_avg_20 = df['Volume'].rolling(20).mean().iloc[-1]
    result["volume_avg"] = vol_avg_20
    result["volume_ratio"] = df['Volume'].iloc[-1] / vol_avg_20 if vol_avg_20 > 0 else 0

    # Moving Averages
    sma20 = df['Close'].rolling(params["sma_short_period"]).mean()
    sma50 = df['Close'].rolling(params["sma_medium_period"]).mean()
    sma200 = df['Close'].rolling(params["sma_long_period"]).mean()
    ema13 = df['Close'].ewm(span=params["ema_period"], adjust=False).mean()

    result["above_sma20"] = price > sma20.iloc[-1]
    result["above_sma50"] = price > sma50.iloc[-1]
    result["above_sma200"] = price > sma200.iloc[-1]
    result["sma_alignment"] = (sma20.iloc[-1] > sma50.iloc[-1] > sma200.iloc[-1])
    result["ema_bullish"] = price > ema13.iloc[-1]

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

    # Momentum Score (weighted composite)
    weights = {
        "near_52w_high": 20,      # Within 15% of 52w high
        "price_change_1m": 15,    # 1-month performance
        "price_change_3m": 15,    # 3-month performance
        "rs_score": 20,           # Relative strength
        "above_sma50": 10,        # Above 50-day SMA
        "above_sma200": 10,       # Above 200-day SMA
        "sma_alignment": 10,      # SMA stacking
    }

    score = 0
    if result["pct_from_52w_high"] >= params["min_price_pct_52w_high"]:
        score += weights["near_52w_high"]
    if result["change_1m"] >= params["min_price_change_1m"]:
        score += weights["price_change_1m"]
    if result["change_3m"] >= params["min_price_change_3m"]:
        score += weights["price_change_3m"]
    if result["rs_score"] >= params["min_rs_score"]:
        score += weights["rs_score"]
    if result["above_sma50"]:
        score += weights["above_sma50"]
    if result["above_sma200"]:
        score += weights["above_sma200"]
    if result["sma_alignment"]:
        score += weights["sma_alignment"]

    result["momentum_score"] = score

    # Signal: meet core criteria
    conditions = [
        result["pct_from_52w_high"] >= params["min_price_pct_52w_high"],
        result["change_1m"] >= params["min_price_change_1m"],
        result["above_sma50"],
        result["above_sma200"],
        result["rs_score"] >= params["min_rs_score"],
        result["volume_avg"] >= params["min_volume_avg"],
    ]

    result["signal"] = all(conditions)
    result["signal_strength"] = sum(conditions) / len(conditions) * 100

    return result


def run_screener(tickers=None, params=None, benchmark_df=None, indices=None, config=None):
    """
    Run the Momentum screener on a list of tickers.
    
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

    print(f"\n{'='*90}")
    print(f"  MOMENTUM STOCK SCREENER")
    print(f"  Indices: {', '.join(index_names)}")
    print(f"  Total stocks to scan: {len(tickers)}")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*90}")
    
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

    print(f"\n  [Phase 3] Running Momentum screening with {NUM_WORKERS} workers...")
    
    liquid_list = list(liquid_tickers)
    batch_size = max(1, len(liquid_list) // NUM_WORKERS)
    batches = [liquid_list[i:i + batch_size] for i in range(0, len(liquid_list), batch_size)]
    
    def _screen_momentum_batch(batch):
        batch_results = []
        for ticker in batch:
            df = fetch_data(ticker, params["data_period"])
            r = calculate_momentum(df, benchmark_df, params)
            r["ticker"] = ticker
            batch_results.append(r)
        return batch_results
    
    with Pool(NUM_WORKERS) as pool:
        batch_results_list = pool.map(_screen_momentum_batch, batches)
    
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
    print(f"  {'='*86}")

    # Print all results sorted by momentum score
    results.sort(key=lambda x: x["momentum_score"], reverse=True)

    rs_col = " RS>Hi" if enable_new_high_rs else ""
    print(f"\n  {'Ticker':<7} {'Price':>8} {'52wHi%':>7} {'1M%':>6} {'3M%':>6} "
          f"{'RS%':>5} {'SMA200':>6} {'Signal':>7} {'Score':>5}{rs_col}")
    print(f"  {'-'*7} {'-'*8} {'-'*7} {'-'*6} {'-'*6} "
          f"{'-'*5} {'-'*6} {'-'*7} {'-'*5}{'-'*6 if enable_new_high_rs else ''}")

    for r in results:
        if r["price"] == 0:
            continue
        sma200_str = "  ✓" if r["above_sma200"] else "  ✗"
        signal_str = "  ✓ BUY" if r["signal"] else "  ---"
        rs_flag = f"  ★" if enable_new_high_rs and r.get("new_high_rs", False) else ""
        print(f"  {r['ticker']:<7} ${r['price']:>6.2f} {r['pct_from_52w_high']*100:>6.1f}% "
              f"{r['change_1m']*100:>+5.1f} {r['change_3m']*100:>+5.1f} "
              f"{r['rs_score']:>4.0f} {sma200_str:>6} {signal_str:>7} {r['momentum_score']:>5.0f}{rs_flag}")

    # Print top signals
    if signal_stocks:
        print(f"\n  {'='*86}")
        print(f"  🚀 MOMENTUM SIGNALS ({len(signal_stocks)} stocks)")
        print(f"  {'='*86}")
        for r in signal_stocks:
            rs_indicator = " ★RS" if enable_new_high_rs and r.get("new_high_rs", False) else ""
            print(f"  ★ {r['ticker']:<6} ${r['price']:>8.2f}  "
                  f"52w:{r['pct_from_52w_high']*100:.1f}%  "
                  f"1M:{r['change_1m']*100:+.1f}%  "
                  f"3M:{r['change_3m']*100:+.1f}%  "
                  f"RS:{r['rs_score']:.0f}  Score:{r['momentum_score']:.0f}{rs_indicator}")
    else:
        print(f"\n  No momentum signals found at this time.")
        # Show near-signals
        near = [r for r in results if r["momentum_score"] >= 60 and r["price"] > 0]
        if near:
            print(f"\n  📊 Near-Signal Stocks (Score ≥ 60):")
            for r in near[:10]:
                print(f"    {r['ticker']:<6} ${r['price']:>8.2f}  Score:{r['momentum_score']:.0f}")

    print(f"\n{'='*90}\n")

    return pd.DataFrame(results)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Momentum Stock Screener")
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
