"""
Minervini Trend Template Screener
=================================
Screens all stocks in NQ100, S&P 500, and Russell 2000
using Mark Minervini's 8-condition Trend Template.

Usage:
    python3 minervini_screener.py
    python3 minervini_screener.py --index nq100
    python3 minervini_screener.py --tickers AAPL NVDA TSLA
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
import sys
import os
from multiprocessing import Pool, cpu_count
from functools import partial

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from filters import check_liquidity, check_new_high_rs, LIQUIDITY_PARAMS

warnings.filterwarnings("ignore")

LIQUIDITY_FILTER_ENABLED = os.environ.get("LIQUIDITY_FILTER", "1") == "1"
NEW_HIGH_RS_FLAG_ENABLED = os.environ.get("NEW_HIGH_RS_FLAG", "1") == "1"

NUM_WORKERS = max(1, cpu_count() - 1)

SCREENER_CONFIG = {
    "enable_liquidity_filter": LIQUIDITY_FILTER_ENABLED,
    "enable_new_high_rs": NEW_HIGH_RS_FLAG_ENABLED,
    "liquidity_params": LIQUIDITY_PARAMS,
}


# ==========================================
# TICKER SOURCES
# ==========================================

def get_all_us_tickers():
    """Load all US stock tickers from tickers.txt file."""
    tickers_file = os.path.join(os.path.dirname(__file__), "tickers.txt")
    if not os.path.exists(tickers_file):
        print(f"Error: {tickers_file} not found. Run tickers.py first.")
        return []
    
    with open(tickers_file, "r") as f:
        return [line.strip() for line in f if line.strip()]


INDEX_MAP = {
    "all": ("All US Stocks", get_all_us_tickers),
}


def _screen_ticker_worker(ticker):
    """Worker function for parallel screening."""
    try:
        passed, details = minervini_screener(ticker)
        details["ticker"] = ticker
        return passed, details
    except Exception as e:
        return False, {"ticker": ticker, "price": 0, "score": 0, "pass": False}


def _screen_batch(batch):
    """Process a batch of tickers."""
    results = []
    for ticker in batch:
        passed, details = _screen_ticker_worker(ticker)
        results.append((passed, details))
    return results


def _check_liquidity_batch(batch):
    """Check liquidity for a batch of tickers (for multiprocessing)."""
    return [t for t in batch if check_liquidity(t)[0]]


# ==========================================
# MINERVINI SCREENER
# ==========================================

def minervini_screener(ticker, df=None):
    """
    Mark Minervini's 8-condition Trend Template.
    Returns (pass: bool, details: dict).
    """
    details = {
        "ticker": ticker,
        "price": 0,
        "market_cap": 0,
        "industry": "",
        "sma50": 0,
        "sma150": 0,
        "sma200": 0,
        "high_52w": 0,
        "low_52w": 0,
        "pct_from_high": 0,
        "pct_from_low": 0,
        "sma200_trending_up": False,
        "cond_1": False,
        "cond_2": False,
        "cond_3": False,
        "cond_4": False,
        "cond_5": False,
        "cond_6": False,
        "cond_7": False,
        "cond_8": False,
        "score": 0,
        "pass": False,
    }

    try:
        # Fetch market cap and industry from yfinance
        stock = yf.Ticker(ticker)
        info = stock.info or {}
        details["market_cap"] = info.get("marketCap", 0) or 0
        details["industry"] = info.get("industry", "") or ""
        
        if df is None:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=365 * 2)
            df = yf.download(ticker, start=start_date, end=end_date, progress=False)

        if df is None or len(df) < 200:
            return False, details

        # Handle multi-level columns from yfinance
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # Use Adj Close if available, otherwise Close
        price_col = 'Adj Close' if 'Adj Close' in df.columns else 'Close'

        # Calculate SMAs
        df['SMA_50'] = df[price_col].rolling(window=50).mean()
        df['SMA_150'] = df[price_col].rolling(window=150).mean()
        df['SMA_200'] = df[price_col].rolling(window=200).mean()

        current_price = df[price_col].iloc[-1]
        sma_50 = df['SMA_50'].iloc[-1]
        sma_150 = df['SMA_150'].iloc[-1]
        sma_200 = df['SMA_200'].iloc[-1]

        # 200-day MA trend (check 20 days ago)
        sma_200_past = df['SMA_200'].iloc[-20] if len(df) >= 220 else sma_200

        # 52-week high/low
        df_52w = df.iloc[-252:]
        high_52w = df_52w[price_col].max()
        low_52w = df_52w[price_col].min()

        # Fill details
        details["price"] = current_price
        details["sma50"] = sma_50
        details["sma150"] = sma_150
        details["sma200"] = sma_200
        details["high_52w"] = high_52w
        details["low_52w"] = low_52w
        details["pct_from_high"] = (current_price / high_52w - 1) * 100
        details["pct_from_low"] = (current_price / low_52w - 1) * 100
        details["sma200_trending_up"] = sma_200 > sma_200_past

        # --- 8 Condition Checks ---

        # Condition 1: Price > 150MA and Price > 200MA
        details["cond_1"] = current_price > sma_150 and current_price > sma_200

        # Condition 2: 150MA > 200MA
        details["cond_2"] = sma_150 > sma_200

        # Condition 3: 200MA trending up (at least 1 month)
        details["cond_3"] = sma_200 > sma_200_past

        # Condition 4: 50MA > 150MA and 50MA > 200MA
        details["cond_4"] = sma_50 > sma_150 and sma_50 > sma_200

        # Condition 5: Price > 50MA
        details["cond_5"] = current_price > sma_50

        # Condition 6: Price >= 30% above 52-week low
        details["cond_6"] = current_price >= (low_52w * 1.30)

        # Condition 7: Price within 25% of 52-week high
        details["cond_7"] = current_price >= (high_52w * 0.75)

        # Condition 8: RS Rating (simplified: stock outperformed)
        # We calculate basic RS as price change vs 252 days ago
        if len(df) >= 252:
            stock_return = (current_price / df[price_col].iloc[-252] - 1) * 100
            details["cond_8"] = stock_return > 0  # Positive 1-year return
        else:
            details["cond_8"] = True

        # Score
        conditions = [
            details["cond_1"], details["cond_2"], details["cond_3"],
            details["cond_4"], details["cond_5"], details["cond_6"],
            details["cond_7"], details["cond_8"]
        ]
        details["score"] = sum(conditions)
        details["pass"] = all(conditions)

        return details["pass"], details

    except Exception as e:
        return False, details


# ==========================================
# SCREENER RUNNER
# ==========================================

def run_screener(indices=None, tickers=None, config=None):
    """
    Run Minervini Trend Template screener.
    
    Args:
        indices: List of index keys (nq100, sp500, russell2000)
        tickers: Custom list of tickers
        config: Dict with 'enable_liquidity_filter' and 'enable_new_high_rs' keys
    """
    if config is None:
        config = SCREENER_CONFIG
    
    enable_liquidity = config.get("enable_liquidity_filter", True)
    enable_new_high_rs = config.get("enable_new_high_rs", True)
    
    if indices is None:
        indices = ["all"]

    # Collect all tickers
    all_tickers = []
    index_names = []

    if tickers:
        all_tickers = [t.upper() for t in tickers]
        index_names = ["Custom"]
    else:
        for idx in indices:
            if idx in INDEX_MAP:
                name, getter = INDEX_MAP[idx]
                idx_tickers = getter()
                all_tickers.extend(idx_tickers)
                index_names.append(name)

    # Deduplicate
    all_tickers = list(dict.fromkeys(all_tickers))

    print(f"\n{'='*90}")
    print(f"  MINERVIINI TREND TEMPLATE SCREENER")
    print(f"  Indices: {', '.join(index_names)}")
    print(f"  Total stocks to scan: {len(all_tickers)}")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*90}")

    print(f"\n  Filters:")
    print(f"    Liquidity Filter: {'ON' if enable_liquidity else 'OFF'} (Market Cap > $2B, Vol > $50M)")
    print(f"    New High RS Flag: {'ON' if enable_new_high_rs else 'OFF'}")
    
    print(f"\n  Conditions:")
    print(f"    1. Price > 150MA and Price > 200MA")
    print(f"    2. 150MA > 200MA")
    print(f"    3. 200MA trending UP (past 20 days)")
    print(f"    4. 50MA > 150MA and 50MA > 200MA")
    print(f"    5. Price > 50MA")
    print(f"    6. Price >= 30% above 52-week low")
    print(f"    7. Price within 25% of 52-week high")
    print(f"    8. Positive 1-year return")

    passing = []
    near_passing = []
    all_results = []
    liquid_tickers = set()
    
    # Phase 1: Liquidity filter with multiprocessing
    if enable_liquidity:
        print(f"\n  [Phase 1] Checking liquidity with {NUM_WORKERS} workers...")
        
        batch_size = max(1, len(all_tickers) // NUM_WORKERS)
        batches = [all_tickers[i:i + batch_size] for i in range(0, len(all_tickers), batch_size)]
        
        with Pool(NUM_WORKERS) as pool:
            results = pool.map(_check_liquidity_batch, batches)
        
        for r in results:
            liquid_tickers.update(r)
        
        print(f"    Liquid stocks: {len(liquid_tickers)}/{len(all_tickers)}")
    else:
        liquid_tickers = set(all_tickers)

    # Phase 2: Screening with multiprocessing
    print(f"\n  [Phase 2] Running Minervini screening with {NUM_WORKERS} workers...")
    liquid_list = list(liquid_tickers)
    batch_size = max(1, len(liquid_list) // NUM_WORKERS)
    batches = [liquid_list[i:i + batch_size] for i in range(0, len(liquid_list), batch_size)]
    
    print(f"    Split into {len(batches)} batches...")
    
    all_results = []
    with Pool(NUM_WORKERS) as pool:
        for batch_idx, batch_results in enumerate(pool.imap_unordered(_screen_batch, batches)):
            for passed, details in batch_results:
                ticker = details.get("ticker", "")
                details["liquidity_pass"] = True
                
                # Add new high RS flag
                if enable_new_high_rs and passed and ticker:
                    is_new_high, rs_details = check_new_high_rs(ticker)
                    details["new_high_rs"] = is_new_high
                    details["rs_line"] = rs_details.get("rs_line", 0)
                else:
                    details["new_high_rs"] = False
                    details["rs_line"] = 0
                
                all_results.append(details)
                
                if passed:
                    passing.append(details)
                elif details.get("score", 0) >= 6:
                    near_passing.append(details)
            
            print(f"    Batch {batch_idx + 1}/{len(batches)} completed", end="", flush=True)
    
    print(f"\n    Processed {len(all_results)} stocks")

    print(f"\n\n  Screening complete: {len(all_results)} stocks analyzed")

    # Print results
    def format_market_cap(cap):
        if cap >= 1_000_000_000_000:
            return f"${cap/1_000_000_000_000:.2f}T"
        elif cap >= 1_000_000_000:
            return f"${cap/1_000_000_000:.2f}B"
        elif cap >= 1_000_000:
            return f"${cap/1_000_000:.2f}M"
        else:
            return "$0"
    
    rs_col = " RS>Hi" if enable_new_high_rs else ""
    print(f"\n  {'Ticker':<7} {'Price':>8} {'MktCap':>10} {'Industry':<18} {'SMA50':>8} {'SMA200':>8} "
          f"{'52wHi%':>7} {'Score':>5} {'Pass':>5}{rs_col}")
    print(f"  {'-'*7} {'-'*8} {'-'*10} {'-'*18} {'-'*8} {'-'*8} {'-'*7} "
          f"{'-'*5} {'-'*5}{'-'*6 if enable_new_high_rs else ''}")

    def fmt(val, details_key):
        v = details.get(details_key, False) if isinstance(details, dict) else False
        return " ✓" if v else " ✗"

    for d in sorted(all_results, key=lambda x: x["score"], reverse=True):
        if d["price"] == 0:
            continue
        c = lambda k: " ✓" if d[k] else " ✗"
        rs_flag = f"  ★" if enable_new_high_rs and d.get("new_high_rs", False) else ""
        industry = (d.get("industry", "") or "N/A")[:16]
        print(f"  {d['ticker']:<7} ${d['price']:>6.2f} {format_market_cap(d.get('market_cap', 0)):>10} "
              f"{industry:<18} ${d['sma50']:>6.2f} ${d['sma200']:>6.2f} "
              f"{d['pct_from_high']:>+6.1f}% "
              f"{d['score']:>5}/8 {' PASS' if d['pass'] else '   --':>5}{rs_flag}")

    # Print passing stocks
    if passing:
        print(f"\n  {'='*96}")
        print(f"  🚀 MINERVIINI TREND TEMPLATE — PASS ({len(passing)} stocks)")
        print(f"  {'='*96}")
        for d in passing:
            rs_indicator = " ★RS" if enable_new_high_rs and d.get("new_high_rs", False) else ""
            industry = (d.get("industry", "") or "N/A")[:20]
            mkt_cap = format_market_cap(d.get("market_cap", 0))
            print(f"  ★ {d['ticker']:<6} ${d['price']:>7.2f}  {mkt_cap:>9}  {industry:<20} "
                  f"52wHi:{d['pct_from_high']:+.1f}%{rs_indicator}")
    else:
        print(f"\n  No stocks passed all 8 conditions.")

    if near_passing:
        print(f"\n  📊 Near-Passing (6-7/8 conditions):")
        for d in sorted(near_passing, key=lambda x: x["score"], reverse=True)[:20]:
            mkt_cap = format_market_cap(d.get("market_cap", 0))
            print(f"    {d['ticker']:<6} ${d['price']:>7.2f}  {mkt_cap:>9}  Score:{d['score']}/8")

    print(f"\n{'='*90}\n")

    return pd.DataFrame(all_results)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Minervini Trend Template Screener")
    parser.add_argument("--index", nargs="+", choices=["nq100", "sp500", "russell2000", "all"],
                        help="Indices to scan")
    parser.add_argument("--tickers", nargs="+", help="Custom ticker list")
    parser.add_argument("--no-liquidity", action="store_true", help="Disable liquidity filter")
    parser.add_argument("--no-rs-flag", action="store_true", help="Disable new high RS flag")
    args = parser.parse_args()

    config = {
        "enable_liquidity_filter": not args.no_liquidity,
        "enable_new_high_rs": not args.no_rs_flag,
    }
    
    run_screener(indices=args.index, tickers=args.tickers, config=config)
