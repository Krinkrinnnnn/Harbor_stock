"""
US Stock Ticker Fetcher
=======================
Fetches all US stock tickers from NASDAQ FTP and saves to tickers.txt.
Run this daily to keep the ticker list updated.

Usage:
    python3 tickers.py              # Fetch and save tickers
    python3 tickers.py --load      # Load tickers from file

Schedule (macOS):
    crontab -e
    0 6 * * * /opt/anaconda3/bin/python3 /Users/krin-mac/Documents/Stock_python/screen/tickers.py
"""

import ftplib
import pandas as pd
import io
import os
import argparse

TICKERS_FILE = os.path.join(os.path.dirname(__file__), "tickers.txt")


def fetch_us_tickers():
    """Fetch all US stock tickers from NASDAQ FTP."""
    print("Connecting to NASDAQ FTP...")
    
    ftp = ftplib.FTP("ftp.nasdaqtrader.com")
    ftp.login("anonymous", "")
    ftp.cwd("SymbolDirectory")

    # 1. Fetch NASDAQ listed stocks
    nasdaq_data = io.BytesIO()
    ftp.retrbinary("RETR nasdaqlisted.txt", nasdaq_data.write)
    nasdaq_df = pd.read_csv(io.StringIO(nasdaq_data.getvalue().decode('utf-8')), sep="|")
    
    # 2. Fetch other listed stocks (NYSE, AMEX, etc.)
    other_data = io.BytesIO()
    ftp.retrbinary("RETR otherlisted.txt", other_data.write)
    other_df = pd.read_csv(io.StringIO(other_data.getvalue().decode('utf-8')), sep="|")
    
    ftp.quit()
    print("Connected and downloaded data.")

    # Get NASDAQ symbols
    nasdaq_symbols = nasdaq_df['Symbol'].tolist() if 'Symbol' in nasdaq_df.columns else []
    
    # Get other exchange symbols - check for 'ACT Symbol' column
    other_symbols = other_df['ACT Symbol'].tolist() if 'ACT Symbol' in other_df.columns else []
    
    # Combine
    tickers = nasdaq_symbols + other_symbols
    
    # Clean: remove invalid entries
    tickers = [str(t).strip() for t in tickers if isinstance(t, str) and len(str(t).strip()) > 0]
    tickers = [t for t in tickers if 'File Creation Time' not in t and t != 'nan']
    
    # Filter: exclude test issues and ETFs (optional - keep for now)
    nasdaq_test = set(nasdaq_df[nasdaq_df['Test Issue'] == 'Y']['Symbol'].tolist()) if 'Test Issue' in nasdaq_df.columns else set()
    nasdaq_etf = set(nasdaq_df[nasdaq_df['ETF'] == 'Y']['Symbol'].tolist()) if 'ETF' in nasdaq_df.columns else set()
    other_test = set(other_df[other_df['Test Issue'] == 'Y']['ACT Symbol'].tolist()) if 'Test Issue' in other_df.columns else set()
    other_etf = set(other_df[other_df['ETF'] == 'Y']['ACT Symbol'].tolist()) if 'ETF' in other_df.columns else set()
    
    exclude = nasdaq_test | nasdaq_etf | other_test | other_etf
    tickers = [t for t in tickers if t not in exclude]
    
    # Deduplicate and sort
    tickers = sorted(list(set(tickers)))
    
    print(f"Fetched {len(tickers)} US stock tickers (excluding ETFs and test issues)")
    
    return tickers


def save_tickers(tickers, filepath=TICKERS_FILE):
    """Save tickers to file."""
    with open(filepath, "w") as f:
        for ticker in tickers:
            f.write(f"{ticker}\n")
    print(f"Saved to {filepath}")


def load_tickers(filepath=TICKERS_FILE):
    """Load tickers from file."""
    if not os.path.exists(filepath):
        print(f"Error: {filepath} not found. Run with no args first.")
        return []
    
    with open(filepath, "r") as f:
        tickers = [line.strip() for line in f if line.strip()]
    
    print(f"Loaded {len(tickers)} tickers from {filepath}")
    return tickers


def update_tickers():
    """Fetch and save latest tickers."""
    tickers = fetch_us_tickers()
    save_tickers(tickers)
    return tickers


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="US Stock Ticker Fetcher")
    parser.add_argument("--load", action="store_true", help="Load tickers from file (skip fetch)")
    parser.add_argument("--fetch", action="store_true", help="Fetch fresh tickers from NASDAQ")
    parser.add_argument("--output", type=str, help="Custom output file path")
    args = parser.parse_args()
    
    if args.output:
        TICKERS_FILE = args.output
    
    if args.load:
        load_tickers()
    else:
        update_tickers()
