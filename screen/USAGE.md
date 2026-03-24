# Usage Guide - Stock Screeners

## Quick Start

```bash
cd screen

# 1. Update ticker list (run once or daily)
python3 tickers.py

# 2. Run screeners
python3 main.py
```

## Ticker Management

### Fetch Latest US Stock Tickers

```bash
python3 tickers.py
```

This connects to NASDAQ FTP and fetches all US stock symbols (7,000+), excluding ETFs and test issues. Saves to `tickers.txt`.

### Load Tickers from File

```bash
python3 tickers.py --load
```

## Running Screeners

### Using main.py (Recommended)

```bash
# Run all screeners
python3 main.py

# Run specific screener
python3 main.py --screener minervini
python3 main.py --screener vcp
python3 main.py --screener momentum
```

### Using Individual Screeners

```bash
# Minervini Trend Template
python3 minervini_screener.py
python3 minervini_screener.py --no-liquidity --no-rs-flag

# VCP + RS
python3 vcp_screener.py

# Momentum
python3 momentum_screener.py
```

## Configuration Options

### Filters

| Flag | Description |
|---|---|
| `--no-liquidity` | Disable liquidity filter (market cap > $2B, vol > $50M) |
| `--no-rs-flag` | Disable "new high RS" flag |

### Parameters

| Flag | Description | Example |
|---|---|---|
| `--liquidity-min` | Min market cap in $ | `5000000000` = $5B |
| `--volume-min` | Min avg volume in $ | `100000000` = $100M |
| `--rs-threshold` | RS score threshold | `80` |
| `--volatility-max` | Max volatility ratio | `0.10` = 10% |

### Config File

```bash
python3 main.py --config config.yaml
```

Create `config.yaml`:

```yaml
screener: all

enable_liquidity_filter: true
enable_new_high_rs: true

liquidity:
  min_market_cap: 2000000000    # $2B
  min_avg_volume: 50000000      # $50M

vcp:
  rs_score_threshold: 60
  volatility_max: 0.12

momentum:
  min_rs_score: 70
```

## Screener Details

### 1. Minervini Trend Template

Marks stocks passing 8 conditions:
1. Price > 150MA and Price > 200MA
2. 150MA > 200MA
3. 200MA trending UP (past 20 days)
4. 50MA > 150MA and 50MA > 200MA
5. Price > 50MA
6. Price >= 30% above 52-week low
7. Price within 25% of 52-week high
8. Positive 1-year return

### 2. VCP + RS

Finds stocks with:
- RS Score >= 60
- RS Line >= 1.0 (outperforms S&P 500)
- Price above SMA 50
- EMA13 > EMA120 (bullish)
- ATR/Price <= 12%
- Volatility contracting
- Breaking out to 20-day high
- Positive Force Index

### 3. Momentum

Finds stocks with:
- Within 15% of 52-week high
- 1-month change >= 5%
- 3-month change >= 10%
- RS Score >= 70
- Above SMA 50 and SMA 200

## Scheduling

### Daily Ticker Update (macOS)

```bash
crontab -e
```

Add line:
```
0 6 * * * /opt/anaconda3/bin/python3 /Users/krin-mac/Documents/Stock_python/screen/tickers.py
```

This fetches the latest US stock tickers every day at 6 AM.

## Troubleshooting

### No tickers found
Run `python3 tickers.py` to fetch the latest ticker list.

### Slow screening
- Screeners process thousands of stocks
- Use `--no-liquidity` to skip market cap checks (faster)
- Use `--rs-threshold 80` for fewer but stronger signals

### Memory issues
The full US market (~7,000 stocks) requires significant memory. Consider:
- Running specific indices: `--index nq100`
- Limiting to top liquid stocks via `--liquidity-min`
