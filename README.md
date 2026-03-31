# Harbor Stock Analysis System

End-to-end stock analysis pipeline: Market Regime → Screener → Backtest → Notification.

## Quick Start

```bash
# Build Docker image
docker compose build

# Run full pipeline (regime-based auto mode)
docker compose run --rm harbor-engine python run_pipeline.py

# Backtest a specific stock
docker compose run --rm harbor-engine python run_backtest.py --strategy vcp --symbol AAPL --years 3 --capital 100000
docker compose run --rm harbor-engine python run_backtest.py --strategy oversold --symbol MU --years 1

# Run screeners
docker compose run --rm harbor-engine python screen/screen_main.py --screener all
docker compose run --rm harbor-engine python screen/screen_main.py --screener oversold

# Interactive shell
docker compose run --rm harbor-engine bash
```

## Project Structure

```
Harbor_stock/
├── run_backtest.py              # CLI: backtest VCP or Oversold strategy
├── backtest_oversold.py         # Oversold Spring Trap backtest engine
├── backtester.py                # VCP + RS backtest engine (backtrader)
├── fetch_data.py                # Central data fetching (yfinance)
├── run_pipeline.py              # Full pipeline orchestrator
├── vcp_rs_analyzer.py           # VCP pattern + RS signal calculator
├── notifier.py                  # Discord webhook notifier
├── Dockerfile                   # Docker build config
├── docker-compose.yml           # Docker Compose services
├── requirements.txt             # Python dependencies
├── screen/
│   ├── screen_main.py           # Screener entry point (runs all screeners)
│   ├── filters.py               # Shared filters (liquidity, ADR, earnings)
│   ├── tickers.py               # US stock ticker fetcher
│   ├── correlation.py           # Correlation risk analysis
│   ├── backtest_runner.py       # Screener → Backtest pipeline
│   └── screener_list/           # All screener modules
│       ├── stage2_screener.py   # Minervini Stage 2
│       ├── momentum_screener.py # Momentum screener
│       ├── week10_momentum.py   # Week 10% momentum
│       └── oversold_screener.py # Spring Trap oversold
├── market_health/
│   ├── market_regime.py         # Market Health Scoring (0-4)
│   ├── risk_appetite_pro.py     # Institutional Sentiment (0-4)
│   ├── decision_engine.py       # Unified decision matrix
│   └── macro_openbb.py          # OpenBB macro data fetcher
├── positioning/
│   └── position_sizer.py        # Risk-based position sizing
└── back_test_result/            # Backtest output directory
```

---

## Modules

### 1. Data Fetching — `fetch_data.py`

Central data fetching module using yfinance.

#### `fetch_stock_data(symbol, years=1, benchmark_symbol="^GSPC")`

| Param | Type | Default | Description |
|---|---|---|---|
| `symbol` | str | required | Stock ticker (e.g. `AAPL`) |
| `years` | int | `1` | Number of years of historical data |
| `benchmark_symbol` | str | `"^GSPC"` | Benchmark ticker for RS comparison |

Returns `(stock_df, benchmark_df)` tuple. Columns are capitalized (`Open`, `High`, `Low`, `Close`, `Volume`).

---

### 2. Backtesting

Two backtest engines are available via `run_backtest.py`.

#### CLI — `run_backtest.py`

| Argument | Type | Default | Description |
|---|---|---|---|
| `--strategy` | str | `vcp` | `vcp` or `oversold` |
| `--symbol` | str | `NVDA` | Stock ticker |
| `--years` | int | `3` | Years of historical data |
| `--capital` | float | `100000` | Starting capital |
| `--no-plot` | flag | `False` | Disable chart generation |

#### VCP + RS Strategy — `backtester.py`

Event-driven backtesting using [backtrader](https://www.backtrader.com/).

**Entry conditions:** Price > SMA50, EMA13 > EMA120, Force Index positive, 20-day breakout, RS score > threshold.

**Exit conditions:** Profit target (25%), EMA13 break, stop loss (8%), trailing stop (10%), time stop (60 bars).

`run_backtest(symbol, years=3, initial_capital=100000, params=None, plot=True)`

| Param | Type | Default | Description |
|---|---|---|---|
| `symbol` | str | required | Stock ticker |
| `years` | int | `3` | Years of data |
| `initial_capital` | float | `100000` | Starting capital |
| `params` | dict | `None` | Strategy parameters (uses `VCP_STRATEGY_PARAMS` if None) |
| `plot` | bool | `True` | Generate chart + QuantStats report |

**`VCP_STRATEGY_PARAMS` defaults:**
- `rs_period`: 252, `rs_score_threshold`: 60
- `volatility_period`: 20, `volatility_max`: 0.08
- `breakout_period`: 20, `ema_short_period`: 13, `ema_long_period`: 120, `sma_period`: 50
- `risk_per_trade_pct`: 0.02, `max_drawdown_per_trade_pct`: 0.08
- `profit_target_pct`: 0.25, `trailing_stop_pct`: 0.10, `max_holding_days`: 60

#### Oversold Spring Trap — `backtest_oversold.py`

Backtests using the [backtesting](https://kernc.github.io/backtesting.py/) library.

**Entry conditions:** Close > 200 SMA, RSI(14) < 40, MACD histogram negative but improving.

**Exit conditions:** Stop loss (2% below entry low), RSI > 65, High > 50 SMA, or time stop (8 bars).

`run_backtest(tickers, period="5y", cash=10000, commission=0.002, plot=True)`

| Param | Type | Default | Description |
|---|---|---|---|
| `tickers` | list/str | required | Ticker symbol(s) |
| `period` | str | `"5y"` | yfinance period |
| `cash` | float | `10000` | Starting capital |
| `commission` | float | `0.002` | Commission rate (0.2%) |
| `plot` | bool | `True` | Generate HTML chart |

---

### 3. Pipeline — `run_pipeline.py`

Unified pipeline: Market Regime → Screener → Backtest → Summary.

#### `run_screener(screener_name, tickers=None)`

| Param | Type | Default | Description |
|---|---|---|---|
| `screener_name` | str | required | `stage2`, `momentum`, or `week10_momentum` |
| `tickers` | list | `None` | Custom ticker list (overrides file) |

#### `run_backtests(tickers, years=3, initial_capital=100000)`

| Param | Type | Default | Description |
|---|---|---|---|
| `tickers` | list | required | Ticker symbols to backtest |
| `years` | int | `3` | Years of historical data |
| `initial_capital` | float | `100000` | Starting capital |

#### `get_recommended_screener(regime)`

| Param | Type | Default | Description |
|---|---|---|---|
| `regime` | dict | required | Market regime state |

Returns `"stage2"`, `"momentum"`, or `"week10_momentum"` based on market condition.

---

### 4. VCP + RS Analyzer — `vcp_rs_analyzer.py`

Core signal calculation engine.

#### `calculate_daily_signals(df, benchmark_df, params=None)`

| Param | Type | Default | Description |
|---|---|---|---|
| `df` | DataFrame | required | Stock OHLCV data |
| `benchmark_df` | DataFrame | required | Benchmark OHLCV data |
| `params` | dict | `None` | Signal parameters |

Returns DataFrame with columns: `RS_Line`, `RS_Score`, `Volatility`, `Contraction_Trend`, `Force_Index`, `VCP_Signal`, `Breakout`, `Signal`.

#### `detect_vcp_pattern(df, lookback=60)`

| Param | Type | Default | Description |
|---|---|---|---|
| `df` | DataFrame | required | Stock OHLCV data |
| `lookback` | int | `60` | Lookback for pivot detection |

Returns list of VCP contraction wave dicts.

#### `print_signal_summary(df)`

| Param | Type | Default | Description |
|---|---|---|---|
| `df` | DataFrame | required | DataFrame with calculated signals |

Prints breakout signal dates, prices, RS scores, and volatility.

---

### 5. Screeners — `screen/`

See [screen/README.md](screen/README.md) for full screener documentation.

Quick usage:
```bash
# Run all screeners
docker compose run --rm harbor-engine python screen/screen_main.py --screener all

# Run specific screener
docker compose run --rm harbor-engine python screen/screen_main.py --screener stage2
docker compose run --rm harbor-engine python screen/screen_main.py --screener oversold

# Screener → Backtest pipeline
docker compose run --rm harbor-engine python screen/backtest_runner.py --screener momentum --top-k 5
```

---

### 6. Market Health — `market_health/`

#### `market_regime.py` — Market Health Scoring (0-4)

Calculates 4 structural indicators:
1. **Breadth:** % of S&P 500 above 50/200 MA
2. **Net New Highs:** 252-day new highs minus new lows
3. **Smart Money:** HYG/IEF ratio vs 50-day SMA
4. **VIX:** Volatility vs 20-day SMA

`run_market_health(skip_chart=False)` — Runs full scoring pipeline.

`load_regime_state(max_hours=4)` — Quick load cached regime state.

#### `risk_appetite_pro.py` — Institutional Sentiment (0-4)

Calculates 4 sentiment indicators:
1. **Growth vs Defensive:** QQQ/XLP ratio vs SMA
2. **Credit Appetite:** HYG/IEF ratio vs SMA
3. **High Yield Spread:** ICE BofA HY OAS via FRED
4. **Yield Curve:** 10Y-2Y Treasury spread via FRED

`calculate_risk_appetite_pro()` — Returns dict with `score`, `signal`, `details`.

#### `decision_engine.py` — Unified Decision Matrix

Combines Market Health + Risk Appetite via 2x2 matrix:

| Health | Appetite | Regime | Action | Position |
|---|---|---|---|---|
| On | On | EASY_MONEY_PRO | Full offense | 100% |
| On | Off | DISTRIBUTION_DANGER | Caution | 50% |
| Off | On | ACCUMULATION_PHASE | Selective | 30% |
| Off | Off | HARD_MONEY_PROTECT | Full defense | 0% |

`compute_decision(market_health_score, risk_appetite_signal)` — Returns dict with `Final_Regime`, `Confidence`, `Action`, `Position_Pct`.

---

### 7. Position Sizing — `positioning/position_sizer.py`

#### `calculate_position_size(total_equity, available_cash, entry_price, risk_per_trade_pct, max_drawdown_per_trade_pct, max_position_size_pct)`

| Param | Type | Default | Description |
|---|---|---|---|
| `total_equity` | float | required | Total portfolio value |
| `available_cash` | float | required | Available cash |
| `entry_price` | float | required | Asset price |
| `risk_per_trade_pct` | float | required | Risk per trade (e.g. 0.02 = 2%) |
| `max_drawdown_per_trade_pct` | float | required | Stop loss distance (e.g. 0.08 = 8%) |
| `max_position_size_pct` | float | required | Max position size (e.g. 0.40 = 40%) |

**Formula:**
1. Risk Amount = Equity x Risk%
2. Risk Per Share = Price x Stop%
3. Target Shares = Risk Amount / Risk Per Share
4. Capped by position limit and available cash

Returns int (shares to buy).

---

### 8. Notifier — `notifier.py`

Sends market regime report to Discord via webhook.

Requires `DISCORD_WEBHOOK_URL` in `.env`.

`main()` — Reads regime JSON, builds dual-panel embed (Panel A: Market Health, Panel B: Risk Appetite), attaches chart, sends to Discord.

---

## Environment Variables

| Variable | Description |
|---|---|
| `DISCORD_WEBHOOK_URL` | Discord webhook for notifications |
| `FRED_API_KEY` | FRED API key for treasury/credit data |
| `TZ` | Timezone (default: `Asia/Hong_Kong`) |

## Output Files

| Path | Description |
|---|---|
| `back_test_result/` | Backtest results (charts, summaries, QuantStats reports) |
| `screen/screen_result/` | Screener output files (ticker lists) |
| `market_health/screen_result/` | Market regime JSON + parquet cache |
