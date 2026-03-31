"""
Portfolio Manager
=================
Portfolio-level risk management: sector exposure limits and correlation defense.

Prevents extreme sector concentration and highly correlated bets among
screened candidate stocks before they enter the portfolio.

Usage:
    from positioning.portfolio_manager import PortfolioManager

    pm = PortfolioManager()
    approved, rejected = pm.filter_candidates(
        candidates=["NVDA", "AMD", "AVGO", "AAPL", "JPM"],
        current_portfolio=current_holdings
    )
"""

import os
import json
import time
import yfinance as yf
import pandas as pd
import numpy as np

# Paths
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_CACHE_DIR = os.path.join(_PROJECT_ROOT, "market_health", "screen_result")
_CACHE_PATH = os.path.join(_CACHE_DIR, "sector_cache.json")


class PortfolioManager:
    """
    Filters screener candidates against portfolio-level risk constraints.

    Checks:
      1. Sector exposure limits  — no single sector exceeds max_sector_weight
      2. Correlation defense     — no new position correlates > max_corr with existing

    Attributes:
        max_sector_weight (float): Max portfolio weight per sector (default 0.25 = 25%).
        max_corr (float): Max Pearson correlation with any single holding (default 0.80).
        lookback_days (int): Days of price history for correlation (default 60).
        default_alloc_pct (float): Assumed allocation % for new candidate (default 0.10 = 10%).
        cache_path (str): Path to sector/industry JSON cache file.
    """

    def __init__(
        self,
        max_sector_weight=0.25,
        max_corr=0.80,
        lookback_days=60,
        default_alloc_pct=0.10,
        cache_path=None,
    ):
        self.max_sector_weight = max_sector_weight
        self.max_corr = max_corr
        self.lookback_days = lookback_days
        self.default_alloc_pct = default_alloc_pct
        self.cache_path = cache_path or _CACHE_PATH

        os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
        self._cache = self._load_cache()

    # ── Cache ─────────────────────────────────────────────────────────

    def _load_cache(self):
        """Load sector/industry cache from JSON file."""
        if os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    def _save_cache(self):
        """Persist cache to disk."""
        try:
            with open(self.cache_path, "w") as f:
                json.dump(self._cache, f, indent=2)
        except IOError as e:
            print(f"  Warning: Could not save sector cache: {e}")

    def _get_stock_metadata(self, ticker):
        """
        Fetch sector and industry for a ticker.

        Uses a local JSON cache to avoid repeated yfinance .info calls.

        Args:
            ticker (str): Stock symbol.

        Returns:
            dict: {"sector": str|None, "industry": str|None}
                  sector/industry will be None if yfinance returns no data.
        """
        ticker = ticker.upper()

        # Cache hit
        if ticker in self._cache:
            return self._cache[ticker]

        # Fetch from yfinance
        metadata = {"sector": None, "industry": None}
        try:
            info = yf.Ticker(ticker).info
            if info:
                metadata["sector"] = info.get("sector") or None
                metadata["industry"] = info.get("industry") or None
        except Exception:
            pass

        # Fallback: try fast_info if .info failed
        if metadata["sector"] is None:
            try:
                fast = yf.Ticker(ticker).fast_info
                # fast_info doesn't have sector, but we tried
            except Exception:
                pass

        self._cache[ticker] = metadata
        self._save_cache()
        return metadata

    # ── Sector Exposure Check ──────────────────────────────────────────

    def check_sector_limit(self, candidate_ticker, current_portfolio, candidate_weight=None):
        """
        Check if adding a candidate would breach the sector exposure limit.

        Args:
            candidate_ticker (str): Ticker to evaluate.
            current_portfolio (list[dict]): Current holdings, each dict has:
                {"ticker": str, "weight": float}
                weight = position value / total equity (e.g. 0.15 = 15%).
            candidate_weight (float|None): Assumed weight for candidate.
                If None, uses self.default_alloc_pct.

        Returns:
            tuple: (passes: bool, details: dict)
                details includes: sector, current_sector_weight, projected_weight, max_allowed
        """
        candidate_ticker = candidate_ticker.upper()
        weight = candidate_weight if candidate_weight is not None else self.default_alloc_pct

        meta = self._get_stock_metadata(candidate_ticker)
        sector = meta["sector"]

        # If we can't determine the sector, allow it (fail-open)
        if sector is None:
            return True, {
                "ticker": candidate_ticker,
                "sector": "Unknown",
                "current_sector_weight": 0.0,
                "candidate_weight": weight,
                "projected_weight": weight,
                "max_allowed": self.max_sector_weight,
                "passes": True,
                "reason": "sector_unknown_pass_through",
            }

        # Sum current weight of this sector
        current_sector_weight = 0.0
        for h in current_portfolio:
            h_meta = self._get_stock_metadata(h["ticker"])
            if h_meta["sector"] == sector:
                current_sector_weight += h.get("weight", 0.0)

        projected = current_sector_weight + weight

        passes = projected <= self.max_sector_weight

        details = {
            "ticker": candidate_ticker,
            "sector": sector,
            "current_sector_weight": round(current_sector_weight, 4),
            "candidate_weight": round(weight, 4),
            "projected_weight": round(projected, 4),
            "max_allowed": self.max_sector_weight,
            "passes": passes,
        }

        if not passes:
            details["reason"] = f"sector '{sector}' projected {projected:.1%} > max {self.max_sector_weight:.0%}"

        return passes, details

    # ── Correlation Defense ────────────────────────────────────────────

    def check_correlation(
        self, candidate_ticker, current_portfolio_tickers, max_corr=None, lookback_days=None
    ):
        """
        Check if a candidate is too correlated with any existing holding.

        Args:
            candidate_ticker (str): Ticker to evaluate.
            current_portfolio_tickers (list[str]): Tickers currently held.
            max_corr (float|None): Override max correlation threshold.
            lookback_days (int|None): Override lookback period.

        Returns:
            tuple: (passes: bool, details: dict)
                details includes: max_correlation, correlated_with, lookback_days
        """
        candidate_ticker = candidate_ticker.upper()
        threshold = max_corr if max_corr is not None else self.max_corr
        days = lookback_days if lookback_days is not None else self.lookback_days

        # Normalize tickers
        existing = [t.upper() for t in current_portfolio_tickers]

        # Nothing to compare against
        if not existing:
            return True, {
                "ticker": candidate_ticker,
                "max_correlation": None,
                "correlated_with": None,
                "lookback_days": days,
                "passes": True,
                "reason": "empty_portfolio_pass_through",
            }

        all_tickers = list(set([candidate_ticker] + existing))

        # Need at least 2 tickers
        if len(all_tickers) < 2:
            return True, {
                "ticker": candidate_ticker,
                "max_correlation": None,
                "correlated_with": None,
                "lookback_days": days,
                "passes": True,
            }

        try:
            data = yf.download(all_tickers, period=f"{days}d", progress=False)

            # Handle multi-index columns from yfinance
            if isinstance(data.columns, pd.MultiIndex):
                if "Close" in data.columns.levels[0]:
                    data = data["Close"]
                elif "Adj Close" in data.columns.levels[0]:
                    data = data["Adj Close"]
                else:
                    return True, {
                        "ticker": candidate_ticker,
                        "max_correlation": None,
                        "correlated_with": None,
                        "lookback_days": days,
                        "passes": True,
                        "reason": "price_data_unavailable",
                    }
            else:
                # Single-column fallback
                if "Close" in data.columns:
                    data = data[["Close"]]
                    data.columns = [candidate_ticker]

            # Drop rows with too many NaNs, then fill remaining
            data = data.dropna(thresh=max(2, len(data.columns) // 2))
            if data.empty or len(data) < 10:
                return True, {
                    "ticker": candidate_ticker,
                    "max_correlation": None,
                    "correlated_with": None,
                    "lookback_days": days,
                    "passes": True,
                    "reason": "insufficient_price_history",
                }

            returns = data.pct_change().dropna()

            if len(returns) < 5:
                return True, {
                    "ticker": candidate_ticker,
                    "max_correlation": None,
                    "correlated_with": None,
                    "lookback_days": days,
                    "passes": True,
                    "reason": "insufficient_return_history",
                }

            corr_matrix = returns.corr()

            # Extract candidate's correlations with existing holdings
            if candidate_ticker not in corr_matrix.columns:
                return True, {
                    "ticker": candidate_ticker,
                    "max_correlation": None,
                    "correlated_with": None,
                    "lookback_days": days,
                    "passes": True,
                    "reason": "ticker_not_in_correlation_matrix",
                }

            candidate_corr = corr_matrix[candidate_ticker]

            max_r = -np.inf
            worst_pair = None

            for existing_ticker in existing:
                if existing_ticker == candidate_ticker:
                    continue
                if existing_ticker in candidate_corr.index:
                    r = abs(candidate_corr[existing_ticker])
                    if np.isnan(r):
                        continue
                    if r > max_r:
                        max_r = r
                        worst_pair = existing_ticker

            if max_r == -np.inf:
                return True, {
                    "ticker": candidate_ticker,
                    "max_correlation": None,
                    "correlated_with": None,
                    "lookback_days": days,
                    "passes": True,
                    "reason": "no_comparable_pairs",
                }

            passes = max_r <= threshold

            details = {
                "ticker": candidate_ticker,
                "max_correlation": round(max_r, 4),
                "correlated_with": worst_pair,
                "lookback_days": days,
                "passes": passes,
            }

            if not passes:
                details["reason"] = (
                    f"correlation {max_r:.2f} with {worst_pair} > max {threshold:.2f}"
                )

            return passes, details

        except Exception as e:
            # Fail-open: allow the trade if correlation calculation fails
            return True, {
                "ticker": candidate_ticker,
                "max_correlation": None,
                "correlated_with": None,
                "lookback_days": days,
                "passes": True,
                "reason": f"correlation_error: {e}",
            }

    # ── Orchestrator ───────────────────────────────────────────────────

    def filter_candidates(self, candidates, current_portfolio, verbose=True):
        """
        Run sector + correlation checks on a list of screener candidates.

        Approved candidates are added to a simulated portfolio so that
        sequential checks account for previously approved candidates.

        Args:
            candidates (list[str]): Ticker symbols from screener output.
            current_portfolio (list[dict]): Current holdings:
                [{"ticker": "AAPL", "weight": 0.15}, ...]
            verbose (bool): Print results to console.

        Returns:
            tuple: (approved: list[dict], rejected: list[dict])
                Each dict: {"ticker": str, "reason": str|None,
                            "sector_check": dict, "correlation_check": dict}
        """
        approved = []
        rejected = []

        # Working copy of portfolio — grows as candidates pass
        simulated_portfolio = list(current_portfolio)
        simulated_tickers = [h["ticker"].upper() for h in simulated_portfolio]

        if verbose:
            print("\n" + "=" * 70)
            print("  PORTFOLIO RISK FILTER")
            print("=" * 70)
            print(f"  Candidates:       {len(candidates)}")
            print(f"  Current Holdings: {len(current_portfolio)}")
            print(f"  Sector Max:       {self.max_sector_weight:.0%}")
            print(f"  Correlation Max:  {self.max_corr:.2f}")
            print(f"  Lookback:         {self.lookback_days} days")
            print(f"  Default Alloc:    {self.default_alloc_pct:.0%}")
            print("=" * 70)

        for ticker in candidates:
            ticker = ticker.upper()

            # 1. Correlation check
            corr_pass, corr_details = self.check_correlation(
                ticker, simulated_tickers
            )

            # 2. Sector check
            sector_pass, sector_details = self.check_sector_limit(
                ticker, simulated_portfolio
            )

            passed = corr_pass and sector_pass

            result = {
                "ticker": ticker,
                "sector_check": sector_details,
                "correlation_check": corr_details,
            }

            if passed:
                result["reason"] = None
                approved.append(result)

                # Add to simulated portfolio for subsequent checks
                simulated_portfolio.append(
                    {"ticker": ticker, "weight": self.default_alloc_pct}
                )
                simulated_tickers.append(ticker)

                if verbose:
                    sector = sector_details.get("sector", "Unknown")
                    r = corr_details.get("max_correlation")
                    r_str = f"{r:.2f}" if r is not None else "N/A"
                    proj = sector_details.get("projected_weight", 0)
                    print(
                        f"  [PASS] {ticker:<6}  Sector: {sector:<20} "
                        f"Projected: {proj:>5.1%}  MaxCorr: {r_str}"
                    )
            else:
                # Build rejection reason
                reasons = []
                if not corr_pass:
                    reasons.append(
                        f"correlation {corr_details['max_correlation']:.2f} "
                        f"with {corr_details['correlated_with']}"
                    )
                if not sector_pass:
                    reasons.append(
                        f"sector '{sector_details['sector']}' "
                        f"projected {sector_details['projected_weight']:.1%}"
                    )
                result["reason"] = "; ".join(reasons)
                rejected.append(result)

                if verbose:
                    print(f"  [REJECT] {ticker:<6}  Reason: {result['reason']}")

        if verbose:
            print("\n" + "-" * 70)
            print(f"  Approved: {len(approved)}  |  Rejected: {len(rejected)}")
            print("=" * 70 + "\n")

        return approved, rejected


# ── CLI / Demo ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Example: current portfolio with 3 positions
    current_portfolio = [
        {"ticker": "AAPL", "weight": 0.20},
        {"ticker": "MSFT", "weight": 0.15},
        {"ticker": "JPM",  "weight": 0.10},
    ]

    # Candidates from screener
    candidates = ["NVDA", "AMD", "AVGO", "TSLA", "CRM", "META", "GOOG"]

    pm = PortfolioManager(
        max_sector_weight=0.25,
        max_corr=0.80,
        lookback_days=60,
        default_alloc_pct=0.10,
    )

    approved, rejected = pm.filter_candidates(candidates, current_portfolio)

    print("\n--- Approved List ---")
    for a in approved:
        print(f"  {a['ticker']}: {a['reason'] or 'OK'}")

    print("\n--- Rejected List ---")
    for r in rejected:
        print(f"  {r['ticker']}: {r['reason']}")
