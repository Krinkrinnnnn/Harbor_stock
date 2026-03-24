"""
Stock Screen Filters
====================
Liquidity filter and new high Relative Strength flag for stock screeners.

Liquidity Filter:
- Market cap > $2B
- 21-day average volume > $50M

New High RS Flag:
- Stock's RS Line is at a new N-day high
- Indicates the stock is outperforming the market at its strongest point
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings

warnings.filterwarnings("ignore")


LIQUIDITY_PARAMS = {
    "min_market_cap": 2_000_000_000,  # $2B
    "min_avg_volume": 50_000_000,     # $50M (21-day)
    "min_price": 20,                  # $20 minimum price
    "volume_period": 21,
    "valid_exchanges": ["NYSE", "NASDAQ", "AMEX"],  # Only major US exchanges
}

NEW_HIGH_RS_PARAMS = {
    "lookback_days": 252,  # 1 year
    "confirm_days": 5,      # Must be at new high for this many days
}


def check_liquidity(ticker, params=None):
    """
    Check if stock meets liquidity criteria.
    
    Args:
        ticker: Stock symbol
        params: Optional override parameters
        
    Returns:
        tuple: (passes: bool, details: dict)
    """
    if params is None:
        params = LIQUIDITY_PARAMS
    
    # Skip invalid ticker formats (preferred shares, warrants, etc.)
    if any(c in ticker for c in ['$', '.', '/', '-', 'W', 'PR', 'PB']):
        return False, {"ticker": ticker, "passes": False, "reason": "invalid_format"}
    
    details = {
        "ticker": ticker,
        "exchange": None,
        "price": 0,
        "market_cap": 0,
        "avg_volume_21d": 0,
        "avg_dollar_volume": 0,
        "passes": False,
    }
    
    # Filter out preferred stocks, warrants, units, etc.
    if any(c in ticker for c in ['$', '.W', '.U', '.R', '.P']):
        return False, details
    
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        if not info:
            return False, details
        
        # Get exchange
        exchange = info.get("exchange", "") or ""
        details["exchange"] = exchange
        
        # Check exchange is valid (NYSE, NASDAQ, or AMEX)
        valid_exchanges = params.get("valid_exchanges", ["NYSE", "NASDAQ", "AMEX"])
        exchange_valid = exchange in valid_exchanges
        
        # Get price
        current_price = info.get("currentPrice", 0) or info.get("regularMarketPrice", 0) or 0
        if current_price == 0:
            hist = stock.history(period="1d")
            if not hist.empty:
                current_price = hist['Close'].iloc[-1]
        
        details["price"] = current_price
        
        # Check price >= min_price
        min_price = params.get("min_price", 20)
        price_valid = current_price >= min_price if min_price > 0 else True
        
        # Get market cap
        market_cap = info.get("marketCap", 0) or 0
        details["market_cap"] = market_cap
        
        # Get volume
        avg_volume_21d = info.get("averageVolume", 0) or 0
        if avg_volume_21d == 0:
            hist = stock.history(period="1mo")
            if not hist.empty:
                avg_volume_21d = hist['Volume'].rolling(21).mean().iloc[-1]
        
        details["avg_volume_21d"] = avg_volume_21d
        
        # Calculate dollar volume
        dollar_volume = current_price * avg_volume_21d if current_price > 0 else 0
        details["avg_dollar_volume"] = dollar_volume
        
        # All conditions must pass
        passes = (
            exchange_valid and
            price_valid and
            market_cap >= params["min_market_cap"] and
            dollar_volume >= params["min_avg_volume"]
        )
        details["passes"] = passes
        
        return passes, details
        
    except Exception as e:
        return False, details


def check_new_high_rs(ticker, benchmark_symbol="^GSPC", params=None, df=None):
    """
    Check if stock's RS Line is at a new high.
    
    Args:
        ticker: Stock symbol
        benchmark_symbol: Benchmark ticker (default: ^GSPC)
        params: Optional override parameters
        df: Pre-fetched stock data (optional)
        
    Returns:
        tuple: (is_new_high: bool, details: dict)
    """
    if params is None:
        params = NEW_HIGH_RS_PARAMS
    
    details = {
        "ticker": ticker,
        "rs_line": 0,
        "rs_252d_high": 0,
        "rs_52w_high": 0,
        "is_new_high_252d": False,
        "is_new_high_52w": False,
        "is_new_high_rs": False,
    }
    
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=params["lookback_days"] + 50)
        
        if df is None:
            stock = yf.Ticker(ticker)
            df = stock.history(start=start_date, end=end_date, progress=False)
        
        if df is None or len(df) < 60:
            return False, details
        
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        benchmark = yf.Ticker(benchmark_symbol)
        benchmark_df = benchmark.history(start=start_date, end=end_date, progress=False)
        
        if benchmark_df is None or len(benchmark_df) < 60:
            return False, details
        
        if isinstance(benchmark_df.columns, pd.MultiIndex):
            benchmark_df.columns = benchmark_df.columns.get_level_values(0)
        
        price_col = 'Adj Close' if 'Adj Close' in df.columns else 'Close'
        bench_col = 'Adj Close' if 'Adj Close' in benchmark_df.columns else 'Close'
        
        aligned_bench = benchmark_df.reindex(df.index, method='ffill')
        
        if aligned_bench.empty or df[price_col].iloc[0] <= 0 or aligned_bench[bench_col].iloc[0] <= 0:
            return False, details
        
        base_stock = df[price_col].iloc[0]
        base_bench = aligned_bench[bench_col].iloc[0]
        
        rs_line = (df[price_col] / base_stock) / (aligned_bench[bench_col] / base_bench)
        
        details["rs_line"] = rs_line.iloc[-1]
        
        rs_252d_high = rs_line.rolling(252).max().iloc[-1]
        rs_52w_high = rs_line.rolling(52).max().iloc[-1]
        
        details["rs_252d_high"] = rs_252d_high
        details["rs_52w_high"] = rs_52w_high
        
        current_rs = rs_line.iloc[-1]
        epsilon = 0.0001
        
        details["is_new_high_252d"] = current_rs >= rs_252d_high - epsilon
        details["is_new_high_52w"] = current_rs >= rs_52w_high - epsilon
        
        min_periods = min(params["lookback_days"], len(rs_line))
        rolling_max = rs_line.rolling(params["lookback_days"], min_periods=20).max()
        
        recent_highs = rolling_max.iloc[-params["confirm_days"]:].iloc[0]
        
        details["is_new_high_rs"] = (
            details["is_new_high_252d"] and
            current_rs >= rolling_max.iloc[-params["confirm_days"]] - epsilon if len(rolling_max) >= params["confirm_days"] else details["is_new_high_252d"]
        )
        
        details["is_new_high_rs"] = details["is_new_high_252d"]
        
        return details["is_new_high_rs"], details
        
    except Exception as e:
        return False, details


def filter_liquidity_batch(tickers, params=None):
    """
    Check liquidity for a batch of tickers.
    
    Args:
        tickers: List of stock symbols
        params: Optional override parameters
        
    Returns:
        dict: {ticker: (passes: bool, details: dict)}
    """
    if params is None:
        params = LIQUIDITY_PARAMS
    
    results = {}
    for ticker in tickers:
        passes, details = check_liquidity(ticker, params)
        results[ticker] = (passes, details)
    
    return results


def get_liquid_tickers(tickers, params=None):
    """
    Filter a list of tickers to only those meeting liquidity criteria.
    
    Args:
        tickers: List of stock symbols
        params: Optional override parameters
        
    Returns:
        list: Tickes that pass liquidity filter
    """
    if params is None:
        params = LIQUIDITY_PARAMS
    
    liquid = []
    for ticker in tickers:
        passes, _ = check_liquidity(ticker, params)
        if passes:
            liquid.append(ticker)
    
    return liquid


def add_rs_high_flag(results_df, benchmark_symbol="^GSPC"):
    """
    Add 'new_high_rs' flag to screener results.
    
    Args:
        results_df: DataFrame with 'ticker' column
        benchmark_symbol: Benchmark for RS calculation
        
    Returns:
        DataFrame with new_high_rs column added
    """
    new_high_rs_flags = []
    
    for ticker in results_df['ticker']:
        is_high, _ = check_new_high_rs(ticker, benchmark_symbol)
        new_high_rs_flags.append(is_high)
    
    results_df['new_high_rs'] = new_high_rs_flags
    return results_df


if __name__ == "__main__":
    import sys
    
    test_tickers = ["AAPL", "TSLA", "NVDA", "MSFT", "AMC", "BBBY"]
    
    print("\n" + "="*70)
    print("  LIQUIDITY FILTER TEST")
    print("="*70)
    
    for ticker in test_tickers:
        passes, details = check_liquidity(ticker)
        print(f"\n{ticker}:")
        print(f"  Market Cap: ${details['market_cap']:,.0f}" if details['market_cap'] > 0 else "  Market Cap: N/A")
        print(f"  Avg Vol (21d): {details['avg_volume_21d']:,.0f}" if details['avg_volume_21d'] > 0 else "  Avg Vol: N/A")
        print(f"  Dollar Vol: ${details['avg_dollar_volume']:,.0f}" if details['avg_dollar_volume'] > 0 else "  Dollar Vol: N/A")
        print(f"  Passes: {'YES' if passes else 'NO'}")
    
    print("\n" + "="*70)
    print("  NEW HIGH RS TEST")
    print("="*70)
    
    for ticker in test_tickers:
        is_high, details = check_new_high_rs(ticker)
        print(f"\n{ticker}:")
        print(f"  RS Line: {details['rs_line']:.2f}")
        print(f"  252d RS High: {details['rs_252d_high']:.2f}")
        print(f"  52w RS High: {details['rs_52w_high']:.2f}")
        print(f"  New High RS: {'YES' if is_high else 'NO'}")
    
    print("\n" + "="*70)
