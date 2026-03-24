import argparse
import os
from fetch_data import fetch_stock_data
from vcp_rs_analyzer import calculate_daily_signals, print_signal_summary
from chart_plotter import MarketSmithChart
from backtester import run_backtest, VCP_STRATEGY_PARAMS

# ==========================================
# SYSTEM PARAMETERS & CONFIGURATION
# ==========================================
CONFIG = {
    # Data Settings
    "symbol": "AAPL",            # Target stock symbol (e.g., AAPL, TSLA, NVDA)
    "years_of_data": 2,          # Number of years of historical data to fetch
    "benchmark": "^GSPC",        # Benchmark symbol for RS calculation (default: S&P 500)
    
    # Feature Flags
    "print_summary": True,       # Whether to print the signal summary table in console
    "print_latest_data": True,   # Whether to print the latest day's data & signals
    "enable_plotting": True,     # Whether to render the visual chart
    "save_chart": True,          # Whether to save the chart as a PNG image
    "run_backtest": False,       # Whether to run the strategy backtest
    "initial_capital": 100000,   # Initial capital for backtesting
    
    # Chart Settings
    "chart_figsize": (18, 12),   # Dimensions of the generated chart
    
    # Backtest Settings (override VCP_STRATEGY_PARAMS if needed)
    "custom_params": None,       # None = use default VCP_STRATEGY_PARAMS
}
# ==========================================


def run_analysis(config):
    """
    Main execution pipeline using the provided configuration.
    """
    symbol = config["symbol"]
    years = config["years_of_data"]
    benchmark = config["benchmark"]
    
    print(f"Starting analysis for {symbol} ({years} years)")
    print("-" * 50)
    
    # 1. Fetch Data
    df, benchmark_df = fetch_stock_data(symbol, years, benchmark)
    
    if df is None:
        print(f"Failed to fetch data for {symbol}. Exiting.")
        return
        
    print(f"Successfully loaded {len(df)} trading days.")
    
    # 2. Analyze Signals (VCP, RS, etc.)
    df_with_signals = calculate_daily_signals(df, benchmark_df)
    
    # 3. Print Summaries
    if config["print_summary"]:
        print_signal_summary(df_with_signals)
        
    if config["print_latest_data"]:
        latest = df_with_signals.iloc[-1]
        print(f"\nLatest Data ({df_with_signals.index[-1].strftime('%Y-%m-%d')}):")
        print(f"  Close Price: ${latest['Close']:.2f}")
        print(f"  RS Line: {latest['RS_Line']:.1f}")
        print(f"  RS Score: {latest['RS_Score']:.1f}")
        print(f"  Volatility: {latest['Volatility']:.2f}%")
        print(f"  Force Index: {latest['Force_Index']:.0f}")
        print(f"  VCP Signal: {'Yes' if latest['VCP_Signal'] else 'No'}")
        print(f"  Breakout Signal: {'Yes' if latest['Signal'] else 'No'}")

    # 4. Run Backtest
    if config["run_backtest"]:
        run_backtest(
            symbol=symbol,
            years=years,
            initial_capital=config["initial_capital"],
            params=config["custom_params"],
            plot=False  # Backtrader uses its own plot, don't overlap with our chart
        )
        # Skip our custom chart if backtest is enabled
        return

    # 5. Plot Chart
    if config["enable_plotting"]:
        chart = MarketSmithChart(figsize=config["chart_figsize"])
        save_path = None
        if config["save_chart"]:
            output_dir = "output"
            os.makedirs(output_dir, exist_ok=True)
            save_path = os.path.join(output_dir, f"{symbol}_analysis.png")
        
        print("\nRendering chart...")
        chart.plot(df_with_signals, symbol, save_path=save_path)


if __name__ == "__main__":
    # Optional CLI arguments to override config
    parser = argparse.ArgumentParser(description="Stock VCP & RS Analysis System")
    parser.add_argument("--symbol", type=str, help="Stock symbol to analyze")
    parser.add_argument("--years", type=int, help="Years of data to fetch")
    parser.add_argument("--no-plot", action="store_true", help="Disable chart plotting")
    parser.add_argument("--backtest", action="store_true", help="Run strategy backtest")
    parser.add_argument("--capital", type=float, help="Initial capital for backtesting")
    
    args = parser.parse_args()
    
    # Apply CLI overrides if provided
    if args.symbol:
        CONFIG["symbol"] = args.symbol.upper()
    if args.years:
        CONFIG["years_of_data"] = args.years
    if args.no_plot:
        CONFIG["enable_plotting"] = False
        CONFIG["save_chart"] = False
    if args.backtest:
        CONFIG["run_backtest"] = True
        CONFIG["years_of_data"] = max(CONFIG["years_of_data"], 3)
        CONFIG["enable_plotting"] = False
    if args.capital:
        CONFIG["initial_capital"] = args.capital
        
    run_analysis(CONFIG)
