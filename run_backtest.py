"""
Standalone VCP + RS Backtest Runner
====================================
Run directly: python3 run_backtest.py --symbol AAPL --years 3 --capital 100000
"""
from backtester import run_backtest, VCP_STRATEGY_PARAMS

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="VCP + RS Strategy Backtester")
    parser.add_argument("--symbol", type=str, default="NVDA", help="Stock symbol (e.g., AAPL, TSLA, NVDA)")
    parser.add_argument("--years", type=int, default=3, help="Years of historical data")
    parser.add_argument("--capital", type=float, default=100000, help="Initial capital")
    parser.add_argument("--no-plot", action="store_true", help="Disable backtrader plot")
    args = parser.parse_args()

    run_backtest(
        symbol=args.symbol,
        years=args.years,
        initial_capital=args.capital,
        plot=not args.no_plot
    )
