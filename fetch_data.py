import yfinance as yf
import pandas as pd
from vcp_rs_analyzer import calculate_daily_signals, print_signal_summary


def fetch_stock_data(symbol, years=1, benchmark_symbol="^GSPC"):
    """
    獲取股票數據和標竿數據
    symbol: 股票代碼 (例如: 'AAPL', 'TSLA')
    years: 年數 (默認 1 年)
    benchmark_symbol: 標竿代碼 (默認 S&P 500)
    """
    period = f"{years}y"
    
    print(f"Fetching {years} year(s) of data for {symbol}...")
    stock = yf.Ticker(symbol)
    df = stock.history(period=period)
    
    if df.empty:
        print(f"Error: No data found for {symbol}")
        return None, None
    
    df.columns = [col.capitalize() for col in df.columns]
    
    print(f"Fetching benchmark data ({benchmark_symbol}) for {years} year(s)...")
    benchmark = yf.Ticker(benchmark_symbol)
    benchmark_df = benchmark.history(period=period)
    
    if not benchmark_df.empty:
        benchmark_df.columns = [col.capitalize() for col in benchmark_df.columns]
    
    return df, benchmark_df


if __name__ == "__main__":
    symbol = input("Enter stock symbol (e.g., AAPL, TSLA): ").upper().strip()
    
    years_input = input("Enter number of years (default 1): ").strip()
    years = int(years_input) if years_input else 1
    
    df, benchmark_df = fetch_stock_data(symbol, years)
    
    if df is not None:
        print(f"\nAnalyzing {len(df)} trading days ({years} year(s))...")
        
        df_with_signals = calculate_daily_signals(df, benchmark_df)
        
        print_signal_summary(df_with_signals)
        
        latest = df_with_signals.iloc[-1]
        print(f"\nLatest Data ({df_with_signals.index[-1].strftime('%Y-%m-%d')}):")
        print(f"  Close Price: ${latest['Close']:.2f}")
        print(f"  RS Line: {latest['RS_Line']:.1f}")
        print(f"  RS Score: {latest['RS_Score']:.1f}")
        print(f"  Volatility: {latest['Volatility']:.2f}%")
        print(f"  Force Index: {latest['Force_Index']:.0f}")
        print(f"  VCP Signal: {'Yes' if latest['VCP_Signal'] else 'No'}")
        print(f"  Breakout Signal: {'Yes' if latest['Signal'] else 'No'}")
        
        from chart_plotter import MarketSmithChart
        chart = MarketSmithChart(figsize=(16, 10))
        save_path = f"{symbol}_analysis.png"
        chart.plot(df_with_signals, symbol, save_path)
