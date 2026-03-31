# Position Sizing Module

## Overview

The `position_sizer.py` module calculates optimal trade size based on **Account Risk** and **Trade Risk** parameters. It is integrated with the Decision Engine's `Position_Pct` output to scale exposure based on market regime.

---

## Core Formula

```
1. Risk Amount     = Total Equity × Risk Per Trade % (default: 2%)
2. Risk Per Share  = Entry Price × Stop Loss Distance % (default: 8%)
3. Target Shares   = Risk Amount ÷ Risk Per Share
4. Final Shares    = MIN(Target, Max Position Cap, Available Cash)
```

### Example

```
Total Equity:       $100,000
Entry Price:        $150.00
Risk Per Trade:     2% ($2,000 max loss per trade)
Stop Loss:          8% below entry ($138.00)
Max Position Size:  40% of equity ($40,000)

Risk Per Share = $150 × 8% = $12.00
Target Shares  = $2,000 ÷ $12.00 = 166 shares
Cost           = 166 × $150 = $24,900 (under 40% cap ✓)
```

---

## Function Signature

```python
from positioning.position_sizer import calculate_position_size

shares = calculate_position_size(
    total_equity=100_000,
    available_cash=80_000,
    entry_price=150.00,
    risk_per_trade_pct=0.02,          # 2% of equity at risk
    max_drawdown_per_trade_pct=0.08,  # 8% stop loss
    max_position_size_pct=0.40        # 40% max position
)
# Returns: 166
```

### Parameters

| Parameter | Description | Default | Example |
|---|---|---|---|
| `total_equity` | Total portfolio value (cash + positions) | — | $100,000 |
| `available_cash` | Currently available cash to trade | — | $80,000 |
| `entry_price` | Price of the stock to buy | — | $150.00 |
| `risk_per_trade_pct` | Max % of equity to risk per trade | 0.02 | 2% |
| `max_drawdown_per_trade_pct` | Stop loss distance from entry | 0.08 | 8% |
| `max_position_size_pct` | Max % of equity for one position | 0.40 | 40% |

### Returns

`int` — Number of shares to buy (always ≥ 0)

---

## Three Safety Constraints

The function applies **three independent caps** and returns the smallest:

| Constraint | Formula | Purpose |
|---|---|---|
| **Risk-based** | `risk_amount / risk_per_share` | Limits loss to 2% of equity |
| **Position cap** | `(equity × max_position%) / price` | Prevents over-concentration |
| **Cash limit** | `available_cash / price` | Prevents over-leveraging |

---

## Integration with Decision Engine

The Decision Engine outputs a `Position_Pct` that scales the **max_position_size_pct**:

| Regime | Position_Pct | Effective Max Position |
|---|---|---|
| 🟢 EASY_MONEY_PRO | 100% | 40% × 1.0 = 40% per position |
| 🟡 DISTRIBUTION_DANGER | 50% | 40% × 0.5 = 20% per position |
| 🟠 ACCUMULATION_PHASE | 30% | 40% × 0.3 = 12% per position |
| 🔴 HARD_MONEY_PROTECT | 0% | Skip — no trades |

### Usage in Pipeline

```python
from market_health.market_regime import load_regime_state
from positioning.position_sizer import calculate_position_size

regime = load_regime_state()
position_pct = regime.get("Position_Pct", 0) / 100  # e.g., 0.5

if position_pct > 0:
    adjusted_max = 0.40 * position_pct  # Scale by regime

    shares = calculate_position_size(
        total_equity=100_000,
        available_cash=80_000,
        entry_price=150.00,
        risk_per_trade_pct=0.02 * position_pct,  # Scale risk too
        max_drawdown_per_trade_pct=0.08,
        max_position_size_pct=adjusted_max
    )
    print(f"Buy {shares} shares (regime: {regime['Final_Regime']})")
else:
    print("HARD_MONEY_PROTECT — no trades")
```

---

## Position Sizing by Regime — Cheat Sheet

### EASY_MONEY_PRO (Full Risk-On)

| Parameter | Value | Rationale |
|---|---|---|
| Risk per trade | 2% | Normal risk tolerance |
| Stop loss | 8% | Standard VCP stop |
| Max position | 40% | High conviction allowed |
| # of positions | 3-5 | Concentrated portfolio |

### DISTRIBUTION_DANGER (Half Size)

| Parameter | Value | Rationale |
|---|---|---|
| Risk per trade | 1% | Halved — market topping |
| Stop loss | 5% | Tighter stops |
| Max position | 20% | Reduce concentration |
| # of positions | 5-8 | Diversify more |

### ACCUMULATION_PHASE (Pilot Only)

| Parameter | Value | Rationale |
|---|---|---|
| Risk per trade | 0.5% | Minimal risk |
| Stop loss | 5% | Tight — unconfirmed bottom |
| Max position | 12% | Small pilot positions |
| # of positions | 1-3 | Test the waters |

### HARD_MONEY_PROTECT (Cash)

| Parameter | Value | Rationale |
|---|---|---|
| Risk per trade | 0% | No trades |
| All positions | Close | Preserve capital |

---

## Files

| File | Purpose |
|---|---|
| `position_sizer.py` | Core position sizing function |
| `__init__.py` | Package init |

---

## Related Modules

| Module | Role |
|---|---|
| `market_health/decision_engine.py` | Outputs `Position_Pct` based on regime |
| `market_health/risk_appetite_pro.py` | Feeds sentiment signal to decision engine |
| `screen/oversold_screener.py` | Identifies candidates for ACCUMULATION_PHASE |
| `backtester.py` | Uses position sizing in backtest simulations |

---

*Harbor System — Risk-first position sizing.*
