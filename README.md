# Stock Analysis & Backtesting System

A comprehensive stock analysis system with VCP+RS analysis, backtesting, and multiple stock screeners.

## Features

- **VCP Pattern Detection**: Identifies Mark Minervini's Volatility Contraction Pattern
- **Relative Strength Analysis**: Calculates RS line vs S&P 500 benchmark
- **MarketSmith-style Charts**: Candlestick charts with MAs, volume, and RS line
- **Backtesting Engine**: Event-driven backtesting using backtrader
- **Stock Screeners**: Minervini Trend Template, VCP+RS, Momentum strategies

## Installation

```bash
pip install pandas numpy matplotlib yfinance backtrader pyyaml
```

## Quick Start

### 1. Analyze a Stock

```bash
# Basic analysis with chart
python3 main.py --symbol AAPL

# With backtest
python3 main.py --symbol NVDA --backtest --years 3
```

### 2. Run Stock Screeners

```bash
cd screen

# Update ticker list (run daily)
python3 tickers.py

# Run all screeners
python3 main.py

# Run specific screener
python3 main.py --screener minervini
python3 main.py --screener vcp
python3 main.py --screener momentum
```

## Usage Examples

### Stock Analysis

```bash
# Analyze Apple with 2 years of data
python3 main.py --symbol AAPL --years 2

# Analyze and save chart
python3 main.py --symbol TSLA --years 2

# Run backtest
python3 main.py --symbol NVDA --backtest --capital 100000
```

### Stock Screeners

```bash
cd screen

# Run with custom parameters
python3 main.py --liquidity-min 5000000000   # $5B market cap
python3 main.py --rs-threshold 80
python3 main.py --no-liquidity              # Disable liquidity filter
python3 main.py --no-rs-flag                 # Disable new high RS flag

# Use config file
python3 main.py --config config.yaml
```

## Strategy Parameters

### VCP Strategy (Backtest)

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

### Screeners

| Screener | Key Criteria |
|---|---|
| Minervini | Price > 150MA & 200MA, 200MA trending up, price within 25% of 52w high |
| VCP + RS | RS Score > 60, volatility < 12%, breakout, positive Force Index |
| Momentum | Within 15% of 52w high, 1M change > 5%, RS Score > 70 |

## File Structure

```
Stock_python/
├── main.py                    # Stock analysis entry point
├── run_backtest.py            # Backtest runner
├── backtester.py              # Backtrader engine
├── vcp_rs_analyzer.py         # VCP + RS signals
├── chart_plotter.py           # MarketSmith-style charts
├── diagram_indicators.py      # Moving averages
├── fetch_data.py              # Yahoo Finance data
├── enums.py                   # Constants
│
├── screen/                    # Stock Screeners
│   ├── main.py                # Screener runner
│   ├── tickers.py             # Fetch US tickers
│   ├── tickers.txt            # 7,000+ US stocks
│   ├── filters.py             # Liquidity & RS filters
│   ├── minervini_screener.py  # Minervini Trend Template
│   ├── vcp_screener.py        # VCP + RS
│   └── momentum_screener.py  # Momentum
│
└── output/                    # Generated charts
```

## Scheduling

### Daily Ticker Update (macOS)

```bash
crontab -e
```

Add:
```
0 6 * * * /opt/anaconda3/bin/python3 /Users/krin-mac/Documents/Stock_python/screen/tickers.py
```

## Configuration

Create `screen/config.yaml`:

```yaml
screener: all

enable_liquidity_filter: true
enable_new_high_rs: true

liquidity:
  min_market_cap: 2000000000
  min_avg_volume: 50000000

vcp:
  rs_score_threshold: 60
  volatility_max: 0.12

momentum:
  min_rs_score: 70
```
