"""
Decision Engine — Unified Market Regime
========================================
Combines Market Health (0-4 structural) with Risk Appetite Pro (0-4 sentiment)
using a 2×2 matrix to produce a Final Regime + Confidence Score.

Matrix:
  Health >= 3  +  Risk-On  →  EASY_MONEY_PRO      (confidence 1.0)
  Health >= 3  +  Risk-Off →  DISTRIBUTION_DANGER  (confidence 0.5)
  Health <= 2  +  Risk-On  →  ACCUMULATION_PHASE   (confidence 0.3)
  Health <= 2  +  Risk-Off →  HARD_MONEY_PROTECT   (confidence 0.0)
"""


# ==========================================
# 2×2 DECISION MATRIX
# ==========================================

MATRIX = {
    # (health_on, appetite_on) → (regime, confidence, action, position_pct)
    (True,  True):  {
        "regime": "EASY_MONEY_PRO",
        "confidence": 1.0,
        "action": "Full Aggression — VCP / Stage 2 Breakouts, Max Position Size",
        "position_pct": 100,
    },
    (True,  False): {
        "regime": "DISTRIBUTION_DANGER",
        "confidence": 0.5,
        "action": "Half Size / Tight Stops — Reduce Winners, Watch for Topping",
        "position_pct": 50,
    },
    (False, True):  {
        "regime": "ACCUMULATION_PHASE",
        "confidence": 0.3,
        "action": "Mean Reversion / Bottom Fishing — Small Pilot Positions Only",
        "position_pct": 30,
    },
    (False, False): {
        "regime": "HARD_MONEY_PROTECT",
        "confidence": 0.0,
        "action": "Cash Only — Preserve Capital, Wait for Confirmation",
        "position_pct": 0,
    },
}


def compute_decision(market_health_score: int, risk_appetite_signal: str) -> dict:
    """
    Apply the 2×2 matrix.

    Args:
        market_health_score:  0-4 (structural breadth/vix/net-highs)
        risk_appetite_signal: "Risk-On" or "Risk-Off"

    Returns:
        dict with Final_Regime, Confidence, Action, Position_Pct, and inputs.
    """
    health_on = market_health_score >= 3
    appetite_on = risk_appetite_signal == "Risk-On"

    decision = MATRIX[(health_on, appetite_on)]

    return {
        "Final_Regime": decision["regime"],
        "Confidence": decision["confidence"],
        "Action": decision["action"],
        "Position_Pct": decision["position_pct"],
        "Inputs": {
            "Market_Health_Score": market_health_score,
            "Market_Health_Pass": health_on,
            "Risk_Appetite_Signal": risk_appetite_signal,
            "Risk_Appetite_Pass": appetite_on,
        },
    }


def print_decision(decision: dict) -> None:
    """Pretty-print the unified decision."""
    regime = decision["Final_Regime"]
    conf = decision["Confidence"]
    pos = decision["Position_Pct"]
    action = decision["Action"]
    inputs = decision["Inputs"]

    emoji_map = {
        "EASY_MONEY_PRO": "🟢",
        "DISTRIBUTION_DANGER": "🟡",
        "ACCUMULATION_PHASE": "🟠",
        "HARD_MONEY_PROTECT": "🔴",
    }
    emoji = emoji_map.get(regime, "📊")

    print(f"\n{'='*60}")
    print(f"  {emoji} UNIFIED DECISION ENGINE")
    print(f"{'='*60}")
    print(f"  Market Health:    {inputs['Market_Health_Score']}/4  ({'✅ Pass' if inputs['Market_Health_Pass'] else '❌ Fail'})")
    print(f"  Risk Appetite:    {inputs['Risk_Appetite_Signal']}  ({'✅ Pass' if inputs['Risk_Appetite_Pass'] else '❌ Fail'})")
    print(f"{'─'*60}")
    print(f"  Final Regime:     {emoji} {regime}")
    print(f"  Confidence:       {conf:.0%}")
    print(f"  Position Size:    {pos}%")
    print(f"  Strategy:         {action}")
    print(f"{'='*60}\n")
