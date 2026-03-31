# Usage Guide - Stock Analysis & Backtesting

## Docker Setup (Recommended)

### Build

```bash
docker compose build
```

### Run Any Script

```bash
# Stock analysis
docker compose run --rm harbor-engine python main.py --symbol AAPL
docker compose run --rm harbor-engine python main.py --symbol NVDA --backtest

# Market regime
docker compose run --rm harbor-engine python market_health/market_regime.py

# Screeners
docker compose run --rm harbor-engine python screen/screen_main.py
docker compose run --rm harbor-engine python screen/screen_main.py --screener stage2

# Full pipeline
docker compose run --rm harbor-engine python run_pipeline.py

# Interactive shell
docker compose run --rm harbor-engine bash
```

All output files (`output/`, `back_test_result/`, `screen/screen_result/`, `market_health/screen_result/`) are mounted as volumes and persist on the host.

---

## Daily Development Flow

Copy & paste in order:

```bash
# 1. Pull latest code
git pull

# 2. Rebuild if requirements or Dockerfile changed
docker compose build

# 3. Check market regime
docker compose run --rm harbor-engine python market_health/market_regime.py

# 4. Run full pipeline (screen → backtest → summary)
docker compose run --rm harbor-engine python run_pipeline.py

# 5. Or analyze a specific stock
docker compose run --rm harbor-engine python main.py --symbol AAPL

# 6. Review outputs
ls -la output/
ls -la back_test_result/
ls -la screen/screen_result/

# 7. Stage, commit, push
git add -A && git commit -m "daily update" && git push
```

---

## Stock Analysis

### Analyze a Single Stock

```bash
# Analyze with default settings (2 years, chart)
python3 main.py --symbol AAPL

# Analyze with custom years
python3 main.py --symbol TSLA --years 3

# Disable chart output
python3 main.py --symbol NVDA --no-plot
```

### Run Backtest

```bash
# Backtest with default capital ($100k)
python3 main.py --symbol NVDA --backtest

# Custom capital
python3 main.py --symbol AAPL --backtest --capital 500000

# Backtest requires at least 3 years of data
python3 main.py --symbol MSFT --backtest --years 5
```

### Standalone Backtest Runner

```bash
python3 run_backtest.py --symbol NVDA --years 3 --capital 100000
```

## Stock Screeners

See [screen/USAGE.md](screen/USAGE.md) for detailed screener instructions.

### Quick Start

```bash
cd screen

# Update ticker list (run once or daily)
python3 tickers.py

# Run all screeners
python3 screen_main.py

# Run specific screener
python3 screen_main.py --screener stage2
python3 screen_main.py --screener momentum
python3 screen_main.py --screener week10_momentum
```

## Common Commands

| Task | Command |
|---|---|
| Analyze stock | `python3 main.py --symbol AAPL` |
| Analyze + backtest | `python3 main.py --symbol NVDA --backtest` |
| Run screeners | `cd screen && python3 screen_main.py` |
| Update tickers | `cd screen && python3 tickers.py` |

## Parameter Reference

### main.py (Analysis)

| Flag | Description | Default |
|---|---|---|
| `--symbol` | Stock symbol | AAPL |
| `--years` | Years of data | 2 |
| `--no-plot` | Disable chart | False |
| `--backtest` | Run backtest | False |
| `--capital` | Initial capital | 100000 |

### screen_main.py (Screeners)

| Flag | Description | Default |
|---|---|---|
| `--screener` | Which screener | all |
| `--no-liquidity` | Disable liquidity filter | - |
| `--no-rs-flag` | Disable new high RS | - |
| `--liquidity-min` | Min market cap ($) | 2B |
| `--volume-min` | Min avg volume ($) | 50M |
| `--rs-threshold` | RS score (0-100) | 60-70 |
| `--config` | Config YAML file | - |
