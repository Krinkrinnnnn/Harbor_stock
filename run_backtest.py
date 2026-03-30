"""
Standalone Strategy Backtest Runner
====================================
Supports VCP + RS strategy and Oversold Spring Trap strategy.

Usage:
    python run_backtest.py --strategy vcp --symbol AAPL --years 3 --capital 100000
    python run_backtest.py --strategy oversold --symbol MU --years 5 --capital 10000
"""

import argparse
from backtester import run_backtest as run_vcp_backtest
from backtest_oversold import run_backtest as run_oversold_backtest

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Strategy Backtester")
    parser.add_argument("--strategy", type=str, choices=["vcp", "oversold"], default="vcp", 
                        help="Strategy to backtest: 'vcp' (default) or 'oversold'")
    parser.add_argument("--symbol", type=str, default="NVDA", help="Stock symbol (e.g., AAPL, TSLA, NVDA)")
    parser.add_argument("--years", type=int, default=3, help="Years of historical data")
    parser.add_argument("--capital", type=float, default=100000, help="Initial capital")
    parser.add_argument("--no-plot", action="store_true", help="Disable chart plotting")
    args = parser.parse_args()

    if args.strategy == "vcp":
        run_vcp_backtest(
            symbol=args.symbol,
            years=args.years,
            initial_capital=args.capital,
            plot=not args.no_plot
        )
    elif args.strategy == "oversold":
        run_oversold_backtest(
            tickers=[args.symbol],
            period=f"{args.years}y",
            cash=args.capital,
            plot=not args.no_plot
        )