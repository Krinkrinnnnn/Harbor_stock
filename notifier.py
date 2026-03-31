"""
Harbor Market Health — Discord Notifier (Embed Edition)
========================================================
Reads market_regime.json, formats a dual-panel embed with regime-colored
border, attaches the health chart, and sends via Discord webhook.

Usage:
    python notifier.py
    docker compose run --rm harbor-engine python notifier.py
"""

import os
import json
import sys
import requests
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

# ── Paths ────────────────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parent
JSON_PATH = ROOT_DIR / "market_health" / "screen_result" / "market_regime.json"
CHART_PATH = ROOT_DIR / "market_health" / "output" / "market_health.png"

# ── Regime → Discord embed color (decimal) ───────────────────────────────────
REGIME_COLOR = {
    "EASY_MONEY_PRO":       0x00E676,   # Green
    "DISTRIBUTION_DANGER":  0xFFEB3B,   # Yellow
    "ACCUMULATION_PHASE":   0xFF9800,   # Orange
    "HARD_MONEY_PROTECT":   0xFF5252,   # Red
}

REGIME_EMOJI = {
    "EASY_MONEY_PRO":       "🟢",
    "DISTRIBUTION_DANGER":  "🟡",
    "ACCUMULATION_PHASE":   "🟠",
    "HARD_MONEY_PROTECT":   "🔴",
}


def load_env() -> str:
    load_dotenv(ROOT_DIR / ".env")
    url = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
    if not url:
        print("ERROR: DISCORD_WEBHOOK_URL not found.")
        sys.exit(1)
    return url


def load_regime() -> dict:
    if not JSON_PATH.exists():
        print(f"ERROR: {JSON_PATH} not found. Run market_regime.py first.")
        sys.exit(1)
    with open(JSON_PATH, "r") as f:
        return json.load(f)


def mark(val) -> str:
    return "✅" if val else "❌"


def build_embed(data: dict) -> dict:
    """Build a Discord embed JSON object."""
    date = data.get("Date", "N/A")
    final_regime = data.get("Final_Regime", data.get("Regime", "UNKNOWN"))
    confidence = data.get("Confidence", 0)
    position_pct = data.get("Position_Pct", 0)
    action = data.get("Recommended_Action", "N/A")
    emoji = REGIME_EMOJI.get(final_regime, "📊")
    color = REGIME_COLOR.get(final_regime, 0x808080)

    # ── Market Health ──
    mh = data.get("Market_Health", {})
    mh_score = mh.get("Score", data.get("Total_Score", 0))
    mh_ind = mh.get("Indicator_Scores", {})
    mh_met = mh.get("Metrics", {})

    # ── Risk Appetite ──
    ra = data.get("Risk_Appetite", {})
    ra_score = ra.get("Score", 0)
    ra_signal = ra.get("Signal", "N/A")
    ra_ind = ra.get("Indicator_Scores", {})
    ra_met = ra.get("Metrics", {})

    # Score bars
    mh_bar = "█" * mh_score + "░" * (4 - mh_score)
    ra_bar = "█" * ra_score + "░" * (4 - ra_score)

    embed = {
        "title": f"{emoji} Unified Market Report — {date}",
        "color": color,
        "fields": [
            # ── Decision ──
            {
                "name": "═══ Final Decision ═══",
                "value": (
                    f"**Regime:** `{final_regime}`\n"
                    f"**Confidence:** `{confidence:.0%}` | **Position:** `{position_pct}%`\n"
                    f"**Strategy:** {action}"
                ),
                "inline": False,
            },

            # ── Panel A ──
            {
                "name": "🦴 Panel A: Market Structure (Skeleton)",
                "value": f"**Score:** `{mh_bar}` **{mh_score}/4**",
                "inline": False,
            },
            {
                "name": "Breadth",
                "value": f"{mark(mh_ind.get('Breadth'))} 50MA: {mh_met.get('Breadth_50MA_Pct', 'N/A')}% | 200MA: {mh_met.get('Breadth_200MA_Pct', 'N/A')}%",
                "inline": True,
            },
            {
                "name": "Net New Highs",
                "value": f"{mark(mh_ind.get('Net_Highs'))} {mh_met.get('Net_New_Highs', 'N/A')}",
                "inline": True,
            },
            {
                "name": "Smart Money",
                "value": f"{mark(mh_ind.get('Smart_Money'))} {mh_met.get('Smart_Money_Ratio_Trend', 'N/A')}",
                "inline": True,
            },
            {
                "name": "VIX",
                "value": f"{mark(mh_ind.get('VIX'))} {mh_met.get('VIX_Level', 'N/A')}",
                "inline": True,
            },

            # ── Panel B ──
            {
                "name": "\u200b",  # spacer
                "value": f"🧬 **Panel B: Institutional Sentiment (Nerve System)**\n**Score:** `{ra_bar}` **{ra_score}/4** | **Signal:** `{ra_signal}`",
                "inline": False,
            },
            {
                "name": "Growth vs Defensive",
                "value": f"{mark(ra_ind.get('Growth_vs_Defensive'))} {ra_met.get('QQQ_XLP_Trend', 'N/A')}",
                "inline": True,
            },
            {
                "name": "Credit Appetite",
                "value": f"{mark(ra_ind.get('Credit_Appetite'))} {ra_met.get('HYG_IEF_Trend', 'N/A')}",
                "inline": True,
            },
            {
                "name": "High Yield OAS",
                "value": f"{mark(ra_ind.get('High_Yield_Spread'))} {ra_met.get('HY_OAS_Spread', 'N/A')}",
                "inline": True,
            },
            {
                "name": "Yield Curve",
                "value": f"{mark(ra_ind.get('Yield_Curve'))} {ra_met.get('Yield_Curve_Trend', 'N/A')}",
                "inline": True,
            },
        ],
        "footer": {
            "text": f"Harbor Engine • {data.get('Timestamp', 'N/A')}",
        },
    }

    return embed


def send_discord(webhook_url: str, embed: dict, chart_path: Path) -> None:
    """Send embed + chart attachment directly via Discord webhook."""
    payload = {
        "embeds": [embed],
    }

    if chart_path.exists():
        print(f"  📎 Attaching chart: {chart_path}")
        with open(chart_path, "rb") as f:
            files = {
                "file": (chart_path.name, f, "image/png"),
            }
            # payload_json must be a string when sending files
            resp = requests.post(
                webhook_url,
                data={"payload_json": json.dumps(payload)},
                files=files,
                timeout=30,
            )
    else:
        print(f"  ⚠️  Chart not found at {chart_path}, sending embed only.")
        resp = requests.post(
            webhook_url,
            json=payload,
            timeout=30,
        )

    if resp.status_code in (200, 204):
        print("  ✅ Notification sent successfully.")
    else:
        print(f"  ❌ Failed: HTTP {resp.status_code} — {resp.text[:200]}")
        sys.exit(1)


def main():
    print("\n📬 Harbor Discord Notifier (Embed)")
    print("-" * 40)

    webhook_url = load_env()
    data = load_regime()
    embed = build_embed(data)

    # Print preview
    print(f"\n  Regime: {data.get('Final_Regime', 'UNKNOWN')}")
    print(f"  Confidence: {data.get('Confidence', 0):.0%}")
    print(f"  Position: {data.get('Position_Pct', 0)}%")
    print(f"  MH: {data.get('Market_Health', {}).get('Score', 0)}/4")
    print(f"  RA: {data.get('Risk_Appetite', {}).get('Score', 0)}/4")
    print("-" * 40)

    send_discord(webhook_url, embed, CHART_PATH)


if __name__ == "__main__":
    main()
