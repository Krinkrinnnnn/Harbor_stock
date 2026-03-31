"""
OpenBB Macro Data Fetcher
=========================
Fetches options sentiment (Put/Call ratio) and treasury yield spread
using the OpenBB Platform SDK.

Gracefully degrades if OpenBB or API keys are missing — returns safe
defaults so the rest of the scoring pipeline never crashes.

Setup:
    pip install openbb
    # Add FRED_API_KEY to .env (free: https://fred.stlouisfed.org/docs/api/api_key.html)
"""

import os
import warnings

from dotenv import load_dotenv

load_dotenv()

# ── Lazy-load OpenBB (avoids hard crash if not installed) ────────────────────
try:
    from openbb import obb
    OBB_AVAILABLE = True
except ImportError:
    OBB_AVAILABLE = False

# ── Configure FRED key if present ────────────────────────────────────────────
if OBB_AVAILABLE:
    _fred_key = os.getenv("FRED_API_KEY", "").strip()
    if _fred_key:
        try:
            obb.user.credentials.fred_api_key = _fred_key
        except Exception:
            pass


# ==========================================
# PUT / CALL RATIO (CBOE)
# ==========================================

def get_put_call_ratio() -> dict:
    """
    Fetch the CBOE total equity Put/Call ratio via OpenBB.

    Returns:
        {"ratio": float, "source": str}  or  {"ratio": None, "source": str}
    """
    if not OBB_AVAILABLE:
        return {"ratio": None, "source": "openbb not installed"}

    # Attempt 1: CBOE index options totals
    try:
        result = obb.derivatives.options.chains(
            symbol="SPX", provider="cboe"
        )
        if result and result.results:
            df = result.to_df()
            if "put_call_ratio" in df.columns:
                ratio = float(df["put_call_ratio"].dropna().iloc[-1])
                return {"ratio": ratio, "source": "CBOE (SPX chains)"}
    except Exception:
        pass

    # Attempt 2: Equity options chain for SPY as proxy
    try:
        result = obb.derivatives.options.chains(
            symbol="SPY", provider="cboe"
        )
        if result and result.results:
            df = result.to_df()
            if "put_call_ratio" in df.columns:
                ratio = float(df["put_call_ratio"].dropna().iloc[-1])
                return {"ratio": ratio, "source": "CBOE (SPY chains)"}
    except Exception:
        pass

    return {"ratio": None, "source": "CBOE data unavailable"}


# ==========================================
# TREASURY YIELD SPREAD (10Y - 2Y)
# ==========================================

def get_treasury_yield_spread() -> dict:
    """
    Fetch the 10-Year minus 2-Year US Treasury yield spread from FRED.

    FRED series:
        DGS10 — 10-Year Treasury Constant Maturity Rate
        DGS2  — 2-Year Treasury Constant Maturity Rate

    Returns:
        {"spread": float, "y10": float, "y2": float, "source": str}
        or safe defaults on failure.
    """
    if not OBB_AVAILABLE:
        return {"spread": None, "y10": None, "y2": None, "source": "openbb not installed"}

    spread = None
    y10 = None
    y2 = None
    source = "FRED"

    # ── 10-Year yield ──
    try:
        r10 = obb.fixedincome.government.treasury_rates(
            provider="federal_reserve"
        )
        if r10 and r10.results:
            for item in r10.results:
                name = getattr(item, "name", "") or ""
                val = getattr(item, "rate", None) or getattr(item, "value", None)
                if val is not None and "10" in name:
                    y10 = float(val)
                    break
    except Exception:
        pass

    # Fallback: FRED series directly
    if y10 is None:
        try:
            r10 = obb.economy.fred_series(
                symbol="DGS10", provider="fred"
            )
            if r10 and r10.results:
                df = r10.to_df()
                y10 = float(df["value"].dropna().iloc[-1])
        except Exception:
            pass

    # ── 2-Year yield ──
    try:
        r2 = obb.fixedincome.government.treasury_rates(
            provider="federal_reserve"
        )
        if r2 and r2.results:
            for item in r2.results:
                name = getattr(item, "name", "") or ""
                val = getattr(item, "rate", None) or getattr(item, "value", None)
                if val is not None and "2" in name:
                    y2 = float(val)
                    break
    except Exception:
        pass

    # Fallback: FRED series directly
    if y2 is None:
        try:
            r2 = obb.economy.fred_series(
                symbol="DGS2", provider="fred"
            )
            if r2 and r2.results:
                df = r2.to_df()
                y2 = float(df["value"].dropna().iloc[-1])
        except Exception:
            pass

    # ── Calculate spread ──
    if y10 is not None and y2 is not None:
        spread = round(y10 - y2, 3)

    return {
        "spread": spread,
        "y10": y10,
        "y2": y2,
        "source": source,
    }


# ==========================================
# COMPOSITE SCORE (called by market_regime.py)
# ==========================================

def calculate_openbb_sentiment_score() -> dict:
    """
    Indicator 5 — Options / Macro Sentiment.

    Scoring logic (+1 if ANY of the following):
      • Put/Call ratio > 1.2  (extreme fear → contrarian bullish)
      • Treasury 10Y-2Y spread > 0  (normal / steepening curve)

    Returns a dict compatible with the other indicator functions.
    """
    print("  📊 Calculating OpenBB Sentiment (Options + Macro)...")

    if not OBB_AVAILABLE:
        print("    ⚠️  OpenBB not installed — skipping (score = 0)")
        return {
            "score": 0,
            "put_call_ratio": None,
            "yield_spread": None,
            "trend": "N/A (openbb not installed)",
            "details": {},
        }

    # Fetch data
    pc_data = get_put_call_ratio()
    ys_data = get_treasury_yield_spread()

    pc_ratio = pc_data["ratio"]
    spread = ys_data["spread"]

    # ── Scoring ──
    score = 0
    reasons = []

    if pc_ratio is not None:
        if pc_ratio > 1.2:
            score = 1
            reasons.append(f"P/C {pc_ratio:.2f} > 1.2 (fear)")
    if spread is not None:
        if spread > 0:
            score = 1
            reasons.append(f"10Y-2Y = {spread:+.3f}% (healthy)")

    # Build trend string
    if score:
        trend = "Bullish (" + " | ".join(reasons) + ")"
    else:
        parts = []
        if pc_ratio is not None:
            parts.append(f"P/C {pc_ratio:.2f}")
        if spread is not None:
            parts.append(f"10Y-2Y {spread:+.3f}%")
        trend = "Bearish (" + (" | ".join(parts) if parts else "no data") + ")"

    print(f"    P/C Ratio: {pc_ratio} ({pc_data['source']})")
    print(f"    10Y-2Y Spread: {spread} ({ys_data['source']})")
    print(f"    → {'✅ +1' if score else '❌ 0'}")

    return {
        "score": score,
        "put_call_ratio": pc_ratio,
        "yield_spread": spread,
        "trend": trend,
        "details": {
            "pc_source": pc_data["source"],
            "ys_source": ys_data["source"],
            "y10": ys_data.get("y10"),
            "y2": ys_data.get("y2"),
        },
    }
