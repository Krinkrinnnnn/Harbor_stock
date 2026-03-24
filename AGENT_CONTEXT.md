# Stock_python Agent Context & Documentation

This document serves as context for LLM agents or developers working within the `Stock_python` directory. It explains the architecture, the purpose of each file, and the overall domain logic implemented in this project.

## Domain Overview
This project is a stock market technical analysis tool built in Python. Its primary goals are to:
1. Fetch historical stock data and benchmark data (S&P 500).
2. Perform technical analysis based on Mark Minervini's **Volatility Contraction Pattern (VCP)**.
3. Calculate **Relative Strength (RS)** compared to a benchmark to ensure the stock is outperforming the broader market.
4. Plot a highly customized, visually appealing financial chart that draws inspiration from **MarketSmith**, **TradingView**, and the **StockPlot** repository (ScottPlot/AvaloniaUI style).

## File Structure & Responsibilities

### 1. `main.py` (Entry Point & Config)
- **Role**: The main executable script and configuration hub.
- **Functionality**:
  - Centralizes all parameter settings (stock symbol, years of data, plotting flags, etc.) in a `CONFIG` dictionary.
  - Serves as the main pipeline runner, tying together data fetching, analysis, and plotting.
  - Accepts optional CLI arguments to override configuration on the fly.

### 2. `fetch_data.py` (Data Layer)
- **Role**: Data retrieval script.
- **Functionality**:
  - Uses the `yfinance` library to download historical OHLCV data for the target stock and the S&P 500 benchmark (`^GSPC`).
  - Contains the core `fetch_stock_data` function used by the main pipeline.

### 2. `vcp_rs_analyzer.py` (Core Logic & Analysis)
- **Role**: The analytical brain of the application.
- **Functionality**:
  - **Relative Strength (`calculate_rs_line`)**: Calculates the daily RS line by comparing the stock's price performance against the benchmark.
  - **VCP Detection (`detect_vcp_pattern`)**: Identifies pivot highs and calculates volatility contractions (e.g., T1, T2, T3 waves). It measures the percentage drop from previous pivot highs to validate tightening price action.
  - **Signal Generation (`calculate_daily_signals`)**: 
    - Standardizes the RS score to a 0-100 scale.
    - Calculates 20-day high/low volatility.
    - Calculates the 13-day Elder Force Index to gauge buying pressure.
    - Generates `VCP_Signal` (when RS > 70, volatility < 8%, contraction is trending, and Force Index is positive).
    - Generates `Breakout` signals (when price closes above the 20-day high).

### 3. `diagram_indicators.py` (Technical Indicators)
- **Role**: Calculation and plotting of standard technical indicators.
- **Functionality**:
  - `MovingAverages` class: Computes MA20, MA50, EMA13, and EMA120. Also detects Golden Crosses and Death Crosses. Evaluates the current trend (Strong Uptrend, Downtrend, etc.) based on moving average stacking.
  - `IndicatorPlotter` class: Contains static methods to draw these moving averages and crossover signals onto a matplotlib `Axes` object.

### 4. `chart_plotter.py` (Visualization Engine)
- **Role**: Advanced rendering of financial charts using `matplotlib`.
- **Functionality**:
  - Implements the `MarketSmithChart` class.
  - **Continuous X-Axis (`_prepare_continuous_x_axis`)**: Crucial feature that maps date indices to continuous integers to eliminate weekend and holiday gaps on the chart (inspired by StockPlot).
  - **Candlesticks (`_draw_candlestick`)**: Custom rendering of candlesticks using StockPlot color schemes (Green: `#07BF7D`, Red: `#FF4500`).
  - **VCP Annotations (`_draw_vcp_pattern`)**: Draws horizontal dashed lines at pivot highs and labels the contraction waves (e.g., T1 -10%).
  - **Multi-pane Layout**: Uses `GridSpec` to stack the Price chart, Volume bars, and Relative Strength (RS) line.
  - **UI/UX Polishes**: Clean gridlines, right-axis current price trackers, and customized legends.

### 5. `backtester.py` (Backtesting Engine)
- **Role**: Backtests the VCP + RS breakout strategy using the `backtrader` library.
- **Functionality**:
  - `VCP_STRATEGY_PARAMS`: A comprehensive parameter table with recommended defaults for entry, exit, and risk management.
  - `VCPStrategy` class: Implements the strategy using backtrader's event-driven framework with:
    - Entry: EMA13 > EMA120, price > SMA50, ATR/volatility below threshold, Force Index positive, breakout above N-day high
    - Exit: Stop-loss, trailing stop, profit target, max holding days, EMA13 break
  - `run_backtest()`: Runs the full backtest and prints performance metrics (Sharpe ratio, max drawdown, win rate, profit factor, etc.)

### 6. `run_backtest.py` (Standalone Backtest Runner)
- **Role**: A simple standalone script to run backtests without the full analysis pipeline.
- **Usage**: `python3 run_backtest.py --symbol AAPL --years 3 --capital 100000`

### 7. `enums.py` (Constants & Definitions)
- **Role**: Data structures and enums.
- **Functionality**: Defines enumerated types like `DisplayPrice` (Candlestick, OHLC, Line), `DrawType`, `IndicatorType`, and `SignalType` to keep configuration standardized.

## Design Philosophy & Guidelines for AI Agents
When modifying or extending this codebase, adhere to the following principles:
1. **Data Alignment**: Because stock data skips weekends, operations involving plotting must rely on the continuous mapping logic found in `chart_plotter.py` (`date_mapping`). Do not plot directly using Pandas DateTimeIndex if it introduces gaps.
2. **Separation of Concerns**: Keep math/calculations in `vcp_rs_analyzer.py` or `diagram_indicators.py`. Keep rendering logic strictly in `chart_plotter.py` or `diagram_indicators.py`'s plotter class.
3. **No External APIs for Data**: Data fetching currently relies solely on `yfinance` to remain free and accessible without API keys.
4. **Style Consistency**: If adding new visual elements, reference the `COLORS` dictionary in `chart_plotter.py` to maintain the StockPlot/AvaloniaUI aesthetic.

## Dependencies
- `pandas`: Data manipulation.
- `numpy`: Numerical calculations.
- `matplotlib`: Chart rendering.
- `yfinance`: Market data fetching.
