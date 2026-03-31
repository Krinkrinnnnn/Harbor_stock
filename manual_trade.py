"""
Manual Trade Assistant
======================
CLI tool for discretionary trades. Verifies a buy against portfolio constraints,
auto-calculates a technical stop-loss, and outputs the exact position size.

Usage:
    python manual_trade.py --ticker AAPL --buy 195.50 --equity 100000 --cash 80000
    python manual_trade.py --ticker NVDA                          # auto-fetch price + auto-SL
    python manual_trade.py --ticker AAPL --buy 195.50 --sl 188.00 # manual stop-loss
"""

import argparse
import os
import sys
import numpy as np
import pandas as pd
import yfinance as yf

# Add market_health to path for regime import
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT_DIR)
sys.path.insert(0, os.path.join(ROOT_DIR, "market_health"))

from positioning.position_sizer import calculate_position_size
from positioning.portfolio_manager import PortfolioManager


# ── Helpers ────────────────────────────────────────────────────────────

def _fetch_price(ticker):
    """Fetch the current market price for a ticker."""
    try:
        t = yf.Ticker(ticker)
        info = t.fast_info
        price = info.get("lastPrice") or info.get("last_price") or info.get("previousClose")
        if price is None:
            # Fallback: grab last close from history
            hist = t.history(period="5d")
            if not hist.empty:
                price = hist["Close"].iloc[-1]
        return float(price) if price else None
    except Exception:
        return None


def _calculate_auto_sl(ticker, buy_price):
    """
    Calculate a technical stop-loss using 50MA and 14-day ATR.

    Logic:
      - If price > 50MA: SL = 50MA - (1 * ATR14)
      - If price <= 50MA: SL = lowest low of last 10 days - 1%

    Returns:
        tuple: (sl_price: float, sl_method: str, atr14: float, sma50: float)
    """
    df = yf.Ticker(ticker).history(period="100d")

    if df.empty or len(df) < 50:
        # Fallback: 5% below buy price
        fallback = buy_price * 0.95
        return fallback, "fallback_5pct", 0, 0

    # 50-day SMA
    sma50 = df["Close"].rolling(50).mean().iloc[-1]

    # 14-day ATR (Wilder's method)
    high = df["High"]
    low = df["Low"]
    prev_close = df["Close"].shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    atr14 = tr.rolling(14).mean().iloc[-1]

    if pd.isna(sma50) or pd.isna(atr14):
        fallback = buy_price * 0.95
        return fallback, "fallback_5pct", 0, 0

    if buy_price > sma50:
        # Normal case: price is above 50MA
        sl = sma50 - (1 * atr14)
        method = "50MA - 1xATR"
    else:
        # Price below 50MA: use recent swing low - 1%
        recent_low = df["Low"].tail(10).min()
        sl = recent_low * 0.99
        method = "swing_low_10d - 1%"

    # Safety: SL must be below buy price
    if sl >= buy_price:
        sl = buy_price * 0.95
        method = "fallback_5pct (SL >= buy)"

    return round(sl, 2), method, round(atr14, 2), round(sma50, 2)


def _load_regime():
    """Load market regime state, returning defaults if unavailable."""
    try:
        from market_regime import load_regime_state
        regime = load_regime_state(max_hours=9999)
        if regime:
            return regime
    except (ImportError, Exception):
        pass

    # Default: assume neutral regime
    return {
        "Final_Regime": "UNKNOWN",
        "Position_Pct": 100,
        "Action": "Proceed with caution (no regime data)",
        "Confidence": 0.5,
    }


def _format_bar(label, value, width=50):
    """Format a single output line inside a box."""
    content = f"  {label:<28} {value}"
    return content


# ── Main ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Manual Trade Assistant — verify, calculate, and size a trade",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--ticker", type=str, required=True, help="Stock symbol (e.g. AAPL)")
    parser.add_argument("--buy", type=float, default=None, help="Entry price (default: auto-fetch)")
    parser.add_argument("--sl", type=float, default=None, help="Stop-loss price (default: auto-calculate)")
    parser.add_argument("--equity", type=float, default=100_000, help="Total account equity (default: 100000)")
    parser.add_argument("--cash", type=float, default=100_000, help="Available cash (default: 100000)")
    parser.add_argument("--override", action="store_true", help="Override portfolio manager rejection")
    args = parser.parse_args()

    ticker = args.ticker.upper()

    # ── 1. Fetch Price ──────────────────────────────────────────────────
    buy_price = args.buy
    price_source = "manual"
    if buy_price is None:
        buy_price = _fetch_price(ticker)
        price_source = "yfinance (live)"
        if buy_price is None:
            print(f"\n  [ERROR] Could not fetch price for {ticker}. Use --buy to set manually.")
            sys.exit(1)

    # ── 2. Calculate Stop-Loss ──────────────────────────────────────────
    if args.sl is not None:
        sl_price = args.sl
        sl_method = "manual"
        atr14 = 0
        sma50 = 0
    else:
        sl_price, sl_method, atr14, sma50 = _calculate_auto_sl(ticker, buy_price)

    sl_pct = (buy_price - sl_price) / buy_price

    # ── 3. Portfolio Manager Check ──────────────────────────────────────
    # Dummy current portfolio — in production this would load from a file
    current_portfolio = [
        {"ticker": "MSFT", "weight": 0.15},
    ]

    pm = PortfolioManager(
        max_sector_weight=0.25,
        max_corr=0.80,
        lookback_days=60,
        default_alloc_pct=0.10,
    )

    approved, rejected = pm.filter_candidates(
        candidates=[ticker],
        current_portfolio=current_portfolio,
        verbose=False,
    )

    portfolio_pass = len(approved) > 0
    portfolio_reason = rejected[0]["reason"] if rejected else None

    # Sector details
    sector_check = (approved[0] if approved else (rejected[0] if rejected else {})).get("sector_check", {})
    corr_check = (approved[0] if approved else (rejected[0] if rejected else {})).get("correlation_check", {})
    sector_name = sector_check.get("sector", "Unknown")
    sector_proj = sector_check.get("projected_weight", 0)
    max_corr_val = corr_check.get("max_correlation")
    corr_with = corr_check.get("correlated_with")

    # ── 4. Market Regime & Position Sizing ──────────────────────────────
    regime = _load_regime()
    regime_name = regime.get("Final_Regime", "UNKNOWN")
    position_pct = regime.get("Position_Pct", 100)

    # Check HARD_MONEY_PROTECT
    hard_stop = position_pct == 0

    # Scaled risk parameters
    risk_per_trade = 0.02 * (position_pct / 100)
    max_position = 0.40 * (position_pct / 100)

    shares = calculate_position_size(
        total_equity=args.equity,
        available_cash=args.cash,
        entry_price=buy_price,
        risk_per_trade_pct=risk_per_trade,
        max_drawdown_per_trade_pct=sl_pct,
        max_position_size_pct=max_position,
    )

    capital_required = shares * buy_price

    # ── 5. Console Output ──────────────────────────────────────────────
    W = 62
    print("\n" + "=" * W)
    print("  MANUAL TRADE ASSISTANT")
    print("=" * W)

    # Trade Setup
    print("\n" + "-" * W)
    print("  [1] TRADE SETUP")
    print("-" * W)
    print(_format_bar("Ticker:", ticker))
    print(_format_bar("Buy Price:", f"${buy_price:,.2f}  ({price_source})"))
    print(_format_bar("Stop-Loss:", f"${sl_price:,.2f}  ({sl_method})"))
    print(_format_bar("SL Distance:", f"${buy_price - sl_price:,.2f}  ({sl_pct:.2%})"))
    if sma50 > 0:
        print(_format_bar("50-Day SMA:", f"${sma50:,.2f}"))
    if atr14 > 0:
        print(_format_bar("14-Day ATR:", f"${atr14:,.2f}"))

    # Portfolio Check
    print("\n" + "-" * W)
    print("  [2] PORTFOLIO CHECK")
    print("-" * W)
    if portfolio_pass:
        print(_format_bar("Status:", "[PASS]"))
    else:
        print(_format_bar("Status:", "[REJECT]"))
    print(_format_bar("Sector:", f"{sector_name} (projected {sector_proj:.1%})"))
    if max_corr_val is not None:
        print(_format_bar("Max Correlation:", f"{max_corr_val:.2f} with {corr_with}"))
    else:
        print(_format_bar("Max Correlation:", "N/A"))
    if portfolio_reason:
        print(_format_bar("Reason:", portfolio_reason))
        if not args.override:
            print("\n  WARNING: This trade violates portfolio constraints.")
            print("  Re-run with --override to force the trade.")

    # Regime
    print("\n" + "-" * W)
    print("  [3] REGIME-ADJUSTED RISK")
    print("-" * W)
    print(_format_bar("Market Regime:", regime_name))
    print(_format_bar("Position %:", f"{position_pct}%"))
    print(_format_bar("Risk per Trade:", f"{risk_per_trade:.2%} (base 2% x {position_pct/100:.0%})"))
    print(_format_bar("Max Position:", f"{max_position:.0%} (base 40% x {position_pct/100:.0%})"))
    if hard_stop:
        print(_format_bar("WARNING:", "HARD_MONEY_PROTECT — buying discouraged"))

    # Actionable Order
    print("\n" + "-" * W)
    print("  [4] ACTIONABLE ORDER")
    print("-" * W)

    if shares > 0 and (portfolio_pass or args.override):
        print(_format_bar("Shares:", f"{shares:,}"))
        print(_format_bar("Capital Required:", f"${capital_required:,.2f}"))
        print(_format_bar("Max Loss:", f"${shares * (buy_price - sl_price):,.2f}"))
        print()
        print(f"  >>>  BUY {shares:,} SHARES OF {ticker} AT ${buy_price:,.2f}")
        print(f"       Stop-Loss: ${sl_price:,.2f}  |  Max Loss: ${shares * (buy_price - sl_price):,.2f}")
    elif shares == 0:
        print(_format_bar("Shares:", "0"))
        print(_format_bar("Reason:", "Position size too small or risk too high"))
        if hard_stop:
            print()
            print("  >>>  DO NOT BUY — Market is in HARD_MONEY_PROTECT regime")
    elif not portfolio_pass and not args.override:
        print(_format_bar("Shares:", "BLOCKED"))
        print()
        print(f"  >>>  DO NOT BUY — Portfolio check failed: {portfolio_reason}")
        print(f"       Use --override to force")

    print("\n" + "=" * W + "\n")


if __name__ == "__main__":
    main()
