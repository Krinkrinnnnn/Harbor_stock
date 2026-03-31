"""
Risk Appetite Pro — Institutional Sentiment Engine
===================================================
4 indicators measuring institutional risk appetite via price ratios
and FRED credit data. Returns a 0-4 score and Risk-On / Risk-Off signal.

Indicators:
  1. QQQ/XLP vs SMA50   — Growth vs Defensive rotation
  2. HYG/IEF vs SMA50   — Credit risk appetite
  3. High Yield OAS      — Credit stress (FRED: BAMLH0A0HYM2)
  4. Yield Curve 10Y-2Y  — Recession signal (FRED: DGS10, DGS2)

Data sources (tried in order):
  1. Direct FRED API via requests (most reliable, needs FRED_API_KEY)
  2. yfinance ETF proxies (TLT/SHY for yield, HYG for credit stress)
"""

import yfinance as yf
import pandas as pd
import numpy as np
import os
import requests
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

FRED_API_KEY = os.getenv("FRED_API_KEY", "").strip()


# ==========================================
# DATA FRESHNESS HELPER
# ==========================================

def check_yf_freshness(df_or_series, label: str) -> None:
    """Log the last date in a yfinance DataFrame/Series."""
    try:
        idx = df_or_series.index[-1]
        last_date = idx.strftime("%Y-%m-%d") if hasattr(idx, 'strftime') else str(idx)
        from datetime import datetime
        age = (datetime.now() - idx).days if hasattr(idx, 'year') else -1
        if age <= 1:
            print(f"    📅 {label}: ✅ {last_date} (fresh)")
        elif age <= 3:
            print(f"    📅 {label}: ⚠️ {last_date} ({age}d old)")
        else:
            print(f"    📅 {label}: ❌ {last_date} ({age}d old — STALE)")
    except Exception:
        pass


# ==========================================
# FRED HELPER (direct API)
# ==========================================

def fred_latest(series_id: str) -> float | None:
    """Fetch the latest value of a FRED series via direct HTTP."""
    if not FRED_API_KEY:
        return None
    try:
        url = (
            f"https://api.stlouisfed.org/fred/series/observations"
            f"?series_id={series_id}"
            f"&api_key={FRED_API_KEY}"
            f"&file_type=json"
            f"&sort_order=desc"
            f"&limit=1"
        )
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        obs = data.get("observations", [])
        if obs and obs[0].get("value", ".") != ".":
            val = float(obs[0]["value"])
            obs_date = obs[0].get("date", "?")
            from datetime import datetime as dt
            try:
                age = (dt.now() - dt.strptime(obs_date, "%Y-%m-%d")).days
                if age <= 2:
                    print(f"    📅 FRED {series_id}: ✅ {obs_date} (fresh)")
                elif age <= 7:
                    print(f"    📅 FRED {series_id}: ⚠️ {obs_date} ({age}d old)")
                else:
                    print(f"    📅 FRED {series_id}: ❌ {obs_date} ({age}d old — STALE)")
            except Exception:
                pass
            return val
    except Exception as e:
        print(f"    ⚠️ FRED API error ({series_id}): {e}")
    return None


def fred_series_last_n(series_id: str, n: int = 10) -> list[float]:
    """Fetch the last N values of a FRED series."""
    if not FRED_API_KEY:
        return []
    try:
        url = (
            f"https://api.stlouisfed.org/fred/series/observations"
            f"?series_id={series_id}"
            f"&api_key={FRED_API_KEY}"
            f"&file_type=json"
            f"&sort_order=desc"
            f"&limit={n}"
        )
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        obs = data.get("observations", [])
        return [float(o["value"]) for o in obs if o.get("value", ".") != "."]
    except Exception as e:
        print(f"    ⚠️ FRED API error ({series_id}): {e}")
    return []


# ==========================================
# INDICATOR 1: QQQ/XLP (Growth vs Defensive)
# ==========================================

def score_growth_vs_defensive() -> dict:
    """
    QQQ (growth) / XLP (consumer staples) ratio vs 50-day SMA.
    +1 if current ratio > SMA50 (institutions rotating into growth).
    """
    print("  📊 [1/4] QQQ/XLP Growth vs Defensive...")
    try:
        data = yf.download(["QQQ", "XLP"], period="120d", progress=False)["Close"]
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)

        check_yf_freshness(data, "QQQ/XLP")

        ratio = data["QQQ"] / data["XLP"]
        sma50 = ratio.rolling(50).mean()

        df = pd.DataFrame({"QQQ_XLP": ratio, "SMA50": sma50}).dropna()
        latest = df.iloc[-1]
        ratio_val = round(float(latest["QQQ_XLP"]), 4)
        sma_val = round(float(latest["SMA50"]), 4)

        score = 1 if ratio_val > sma_val else 0
        trend = "Growth Leading" if score else "Defensive Leading"
        print(f"    Ratio: {ratio_val} | SMA50: {sma_val}  →  {'✅ +1' if score else '❌ 0'}")
        return {"score": score, "ratio": ratio_val, "sma": sma_val, "trend": trend, "df": df}

    except Exception as e:
        print(f"    ⚠️ Failed: {e}")
        return {"score": 0, "ratio": None, "sma": None, "trend": "N/A", "df": pd.DataFrame()}


# ==========================================
# INDICATOR 2: HYG/IEF (Credit Risk Appetite)
# ==========================================

def score_credit_appetite() -> dict:
    """
    HYG (high yield bonds) / IEF (treasuries) ratio vs 50-day SMA.
    +1 if current ratio > SMA50 (institutions buying credit risk).
    """
    print("  📊 [2/4] HYG/IEF Credit Appetite...")
    try:
        data = yf.download(["HYG", "IEF"], period="120d", progress=False)["Close"]
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)

        check_yf_freshness(data, "HYG/IEF")

        ratio = data["HYG"] / data["IEF"]
        sma50 = ratio.rolling(50).mean()

        df = pd.DataFrame({"HYG_IEF": ratio, "SMA50": sma50}).dropna()
        latest = df.iloc[-1]
        ratio_val = round(float(latest["HYG_IEF"]), 4)
        sma_val = round(float(latest["SMA50"]), 4)

        score = 1 if ratio_val > sma_val else 0
        trend = "Risk-On (Credit)" if score else "Risk-Off (Credit)"
        print(f"    Ratio: {ratio_val} | SMA50: {sma_val}  →  {'✅ +1' if score else '❌ 0'}")
        return {"score": score, "ratio": ratio_val, "sma": sma_val, "trend": trend, "df": df}

    except Exception as e:
        print(f"    ⚠️ Failed: {e}")
        return {"score": 0, "ratio": None, "sma": None, "trend": "N/A", "df": pd.DataFrame()}


# ==========================================
# INDICATOR 3: HIGH YIELD OAS SPREAD
# ==========================================

def score_high_yield_spread() -> dict:
    """
    ICE BofA US High Yield OAS Spread (BAMLH0A0HYM2).
    +1 if spread < 4.0% (tight = low stress).
    Fallback: HYG price change proxy.
    """
    print("  📊 [3/4] High Yield OAS Spread...")

    # Method 1: Direct FRED API
    spread = fred_latest("BAMLH0A0HYM2")
    if spread is not None:
        score = 1 if spread < 4.0 else 0
        trend = f"Low Stress ({spread:.2f}%)" if score else f"High Stress ({spread:.2f}%)"
        print(f"    OAS: {spread:.2f}% (FRED)  →  {'✅ +1' if score else '❌ 0'}")
        return {"score": score, "spread": round(spread, 2), "trend": trend, "source": "FRED"}

    # Method 2: HYG 20-day return proxy (rising = spreads tightening)
    print("    ⚠️ FRED unavailable, using HYG proxy...")
    try:
        hyg = yf.download("HYG", period="60d", progress=False)["Close"]
        if isinstance(hyg.columns, pd.MultiIndex):
            hyg.columns = hyg.columns.get_level_values(0)
        hyg_ret = round(float((hyg.iloc[-1] / hyg.iloc[-20] - 1) * 100), 2)
        score = 1 if hyg_ret > 0 else 0
        trend = f"HYG +{hyg_ret}% (proxy)" if score else f"HYG {hyg_ret}% (proxy)"
        print(f"    HYG 20d return: {hyg_ret}% (proxy)  →  {'✅ +1' if score else '❌ 0'}")
        return {"score": score, "spread": None, "trend": trend, "source": "yfinance proxy"}
    except Exception as e:
        print(f"    ⚠️ Proxy failed: {e}")

    return {"score": 0, "spread": None, "trend": "N/A (no data)", "source": "none"}


# ==========================================
# INDICATOR 4: YIELD CURVE 10Y - 2Y
# ==========================================

def score_yield_curve() -> dict:
    """
    10-Year minus 2-Year Treasury yield spread.
    +1 if spread > 0 (normal/steepening).
    Fallback: TLT/SHY price ratio proxy.
    """
    print("  📊 [4/4] Yield Curve 10Y-2Y...")

    # Method 1: Direct FRED API
    y10 = fred_latest("DGS10")
    y2 = fred_latest("DGS2")

    if y10 is not None and y2 is not None:
        spread = round(y10 - y2, 3)
        score = 1 if spread > 0 else 0
        trend = f"Normal ({spread:+.3f}%)" if score else f"Inverted ({spread:+.3f}%)"
        print(f"    10Y: {y10}% | 2Y: {y2}% | Spread: {spread:+.3f}% (FRED)  →  {'✅ +1' if score else '❌ 0'}")
        return {"score": score, "spread": spread, "y10": y10, "y2": y2, "trend": trend, "source": "FRED"}

    # Method 2: TLT/SHY ratio proxy (inverse — TLT up = yields down)
    print("    ⚠️ FRED unavailable, using TLT/SHY proxy...")
    try:
        data = yf.download(["TLT", "SHY"], period="60d", progress=False)["Close"]
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        ratio = data["TLT"] / data["SHY"]
        ratio_now = round(float(ratio.iloc[-1]), 4)
        ratio_20d = round(float(ratio.iloc[-20]), 4)
        change = round(ratio_now - ratio_20d, 4)
        # Rising TLT/SHY = yields falling, curve steepening from short end
        score = 1 if change > 0 else 0
        trend = f"TLT/SHY +{change} (proxy)" if score else f"TLT/SHY {change} (proxy)"
        print(f"    TLT/SHY change(20d): {change} (proxy)  →  {'✅ +1' if score else '❌ 0'}")
        return {"score": score, "spread": None, "y10": None, "y2": None, "trend": trend, "source": "yfinance proxy"}
    except Exception as e:
        print(f"    ⚠️ Proxy failed: {e}")

    return {"score": 0, "spread": None, "y10": None, "y2": None, "trend": "N/A (no data)", "source": "none"}


# ==========================================
# COMPOSITE: Run All 4
# ==========================================

def calculate_risk_appetite_pro() -> dict:
    """
    Run all 4 risk appetite indicators.

    Returns:
        {
            "score": int (0-4),
            "signal": "Risk-On" | "Risk-Off",
            "indicator_scores": { ... },
            "metrics": { ... },
            "details": { ... }
        }
    """
    print(f"\n  {'─'*50}")
    print(f"  🧬 RISK APPETITE PRO (Institutional Sentiment)")
    print(f"  {'─'*50}")

    g_vs_d = score_growth_vs_defensive()
    credit = score_credit_appetite()
    hy_spread = score_high_yield_spread()
    yc = score_yield_curve()

    total = g_vs_d["score"] + credit["score"] + hy_spread["score"] + yc["score"]
    signal = "Risk-On" if total >= 2 else "Risk-Off"

    print(f"  {'─'*50}")
    print(f"  🧬 RISK APPETITE SCORE: {total} / 4  →  {signal}")
    print(f"  {'─'*50}")

    return {
        "score": total,
        "signal": signal,
        "indicator_scores": {
            "Growth_vs_Defensive": g_vs_d["score"],
            "Credit_Appetite": credit["score"],
            "High_Yield_Spread": hy_spread["score"],
            "Yield_Curve": yc["score"],
        },
        "metrics": {
            "QQQ_XLP_Trend": g_vs_d["trend"],
            "HYG_IEF_Trend": credit["trend"],
            "HY_OAS_Spread": hy_spread.get("trend", "N/A"),
            "Yield_Curve_Trend": yc.get("trend", "N/A"),
        },
        "details": {
            "qqq_xlp_ratio": g_vs_d.get("ratio"),
            "hyg_ief_ratio": credit.get("ratio"),
            "hy_spread_pct": hy_spread.get("spread"),
            "hy_source": hy_spread.get("source", "none"),
            "yield_spread_pct": yc.get("spread"),
            "yield_10y": yc.get("y10"),
            "yield_2y": yc.get("y2"),
            "yield_source": yc.get("source", "none"),
        },
    }


if __name__ == "__main__":
    result = calculate_risk_appetite_pro()
    print(f"\n  Result: {result['signal']} ({result['score']}/4)")
    print(f"  HY Source: {result['details']['hy_source']}")
    print(f"  Yield Source: {result['details']['yield_source']}")
