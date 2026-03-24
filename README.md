# Stock Backtest

VCP (Volatility Contraction Pattern) + RS (Relative Strength) strategy backtesting and analysis tool.

## Features

- **VCP Pattern Detection**: Identifies Mark Minervini's Volatility Contraction Pattern with T1, T2, T3 wave labels
- **Relative Strength Analysis**: Calculates RS line vs S&P 500 benchmark
- **MarketSmith-style Charts**: Candlestick charts with moving averages, volume, and RS line
- **Backtesting Engine**: Event-driven backtesting using backtrader library
- **Interactive Checkboxes**: Toggle MA20, MA50, EMA13, EMA120 visibility on chart

## Installation

```bash
pip install pandas numpy matplotlib yfinance backtrader
```

## Usage

### Run Analysis (Chart)
```bash
python3 main.py --symbol AAPL --years 2
```

### Run Backtest
```bash
python3 run_backtest.py --symbol NVDA --years 3 --capital 100000
```

### Run Analysis + Backtest
```bash
python3 main.py --symbol TSLA --backtest --years 3
```

## Strategy Parameters

| Parameter | Default | Description |
|---|---|---|
| EMA Short | 13 | Short-term EMA period |
| EMA Long | 120 | Long-term EMA period |
| SMA | 50 | Trend filter SMA |
| Breakout Period | 20 | N-day high for breakout |
| ATR Period | 20 | Volatility measurement |
| Stop Loss | 7% | Hard stop-loss |
| Trailing Stop | 10% | Trailing stop from peak |
| Profit Target | 25% | Take profit target |
| Max Holding | 60 bars | Maximum holding period |

## Files

- `main.py` — Entry point and configuration
- `run_backtest.py` — Standalone backtest runner
- `backtester.py` — Backtrader-based backtesting engine
- `vcp_rs_analyzer.py` — VCP and RS signal calculation
- `chart_plotter.py` — MarketSmith-style chart rendering
- `diagram_indicators.py` — Moving averages and indicators
- `fetch_data.py` — Yahoo Finance data fetching
- `enums.py` — Enumerations and constants
