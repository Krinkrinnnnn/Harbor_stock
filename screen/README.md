# Stock Screeners

A comprehensive stock screening system with multiple strategies for finding winning stocks.

## Overview

This folder contains three stock screeners:

1. **Minervini Trend Template** - Mark Minervini's 8-condition trend template
2. **VCP + RS** - Volatility Contraction Pattern with Relative Strength
3. **Momentum** - Strong momentum stocks near 52-week highs

## Quick Start

### 1. Update Ticker List (Daily)

```bash
python3 tickers.py
```

This fetches all US stock tickers from NASDAQ FTP and saves to `tickers.txt`.

### 2. Run Screeners

#### Using main.py (Recommended)

```bash
# Run all screeners
python3 main.py

# Run specific screener
python3 main.py --screener minervini
python3 main.py --screener vcp
python3 main.py --screener momentum

# With custom parameters
python3 main.py --liquidity-min 5000000000   # $5B min market cap
python3 main.py --volume-min 100000000       # $100M min volume
python3 main.py --rs-threshold 80           # RS score threshold

# Disable filters
python3 main.py --no-liquidity
python3 main.py --no-rs-flag
```

#### Using Individual Screeners

```bash
# Minervini
python3 minervini_screener.py
python3 minervini_screener.py --no-liquidity --no-rs-flag

# VCP
python3 vcp_screener.py
python3 vcp_screener.py --index all

# Momentum
python3 momentum_screener.py
```

## Filter Configuration

### Liquidity Filter (Enabled by Default)
- Market Cap > $2B
- 21-day Average Dollar Volume > $50M

### New High RS Flag
- Marks stocks where RS Line is at a new 252-day high

## File Structure

```
screen/
├── main.py              # Central screener runner
├── tickers.py           # Fetch US stock tickers
├── tickers.txt          # US stock ticker list (7,000+)
├── filters.py           # Liquidity & RS filter functions
├── minervini_screener.py
├── vcp_screener.py
├── momentum_screener.py
└── README.md
```

## Schedule Daily Updates

### macOS (crontab)

```bash
crontab -e
```

Add line to fetch tickers daily at 6 AM:
```
0 6 * * * /opt/anaconda3/bin/python3 /Users/krin-mac/Documents/Stock_python/screen/tickers.py
```

## Configuration File

Create `config.yaml` for custom settings:

```yaml
screener: all

enable_liquidity_filter: true
enable_new_high_rs: true

liquidity:
  min_market_cap: 2000000000
  min_avg_volume: 50000000

minervini:
  cond_6_pct_above_52w_low: 30
  cond_7_within_pct_of_52w_high: 25

vcp:
  rs_score_threshold: 60
  volatility_max: 0.12

momentum:
  min_rs_score: 70
  min_price_pct_52w_high: 0.85
```

Then run:
```bash
python3 main.py --config config.yaml
```
