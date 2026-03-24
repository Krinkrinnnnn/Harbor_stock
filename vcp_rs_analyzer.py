import pandas as pd
import numpy as np


def calculate_rs_line(df, benchmark_df):
    """
    計算每日 RS 曲線 (相對強度線)
    RS = 股價 / 標竿價格 * 基準值
    """
    if benchmark_df is None or benchmark_df.empty:
        return pd.Series(index=df.index, data=100.0)
    
    aligned_benchmark = benchmark_df.reindex(df.index, method='ffill')
    
    base_stock = df['Close'].iloc[0]
    base_benchmark = aligned_benchmark['Close'].iloc[0]
    
    if base_benchmark == 0 or pd.isna(base_benchmark):
        return pd.Series(index=df.index, data=100.0)
    
    rs_line = (df['Close'] / base_stock) / (aligned_benchmark['Close'] / base_benchmark) * 100
    
    return rs_line


def detect_vcp_pattern(df, lookback=60):
    """
    檢測 VCP (Volatility Contraction Pattern) - MarketSmith 風格
    返回收縮波信息: T1, T2, T3 等
    """
    df = df.copy()
    
    highs = df['High'].values
    dates = df.index.values
    
    pivot_highs = []
    for i in range(2, len(highs) - 2):
        if highs[i] > highs[i-1] and highs[i] > highs[i-2] and \
           highs[i] > highs[i+1] and highs[i] > highs[i+2]:
            pivot_highs.append({
                'date': df.index[i],
                'price': highs[i],
                'idx': i
            })
    
    contractions = []
    wave_num = 0
    prev_high = None
    
    for pivot in pivot_highs[-6:]:
        if prev_high is not None:
            if pivot['price'] < prev_high * 0.98:
                wave_num += 1
                contraction_pct = (prev_high - pivot['price']) / prev_high * 100
                contractions.append({
                    'wave': f'T{wave_num}',
                    'date': pivot['date'],
                    'price': pivot['price'],
                    'prev_price': prev_high,
                    'contraction_pct': contraction_pct
                })
        prev_high = pivot['price']
    
    return contractions


def calculate_daily_signals(df, benchmark_df, params=None):
    """
    逐日計算 VCP 和 RS 信號
    返回包含每日信號的 DataFrame
    """
    if params is None:
        params = {
            'rs_score_threshold': 70,
            'rs_line_threshold': 100,
            'volatility_max': 12.0,
            'volatility_ma_period': 10,
            'contraction_pct': 0.85,
            'breakout_window': 20,
            'force_index_span': 13,
        }

    df = df.copy()
    
    df['RS_Line'] = calculate_rs_line(df, benchmark_df)
    
    rs_min = df['RS_Line'].rolling(window=252, min_periods=20).min()
    rs_max = df['RS_Line'].rolling(window=252, min_periods=20).max()
    df['RS_Score'] = ((df['RS_Line'] - rs_min) / (rs_max - rs_min) * 100).fillna(50)
    
    window = params.get('breakout_window', 20)
    df['High_20'] = df['High'].rolling(window=window, min_periods=1).max()
    df['Low_20'] = df['Low'].rolling(window=window, min_periods=1).min()
    df['Volatility'] = (df['High_20'] - df['Low_20']) / df['Low_20'] * 100
    
    ma_period = params.get('volatility_ma_period', 10)
    df['Volatility_MA'] = df['Volatility'].rolling(window=ma_period).mean()
    
    # Contraction: current volatility is below the MA and decreasing vs 10 days ago
    contraction_pct = params.get('contraction_pct', 0.85)
    df['Contraction_Trend'] = (
        (df['Volatility'] < df['Volatility_MA']) &
        (df['Volatility'] < df['Volatility'].shift(10) * contraction_pct)
    )
    
    force_span = params.get('force_index_span', 13)
    force_index = (df['Close'] - df['Close'].shift(1)) * df['Volume']
    df['Force_Index'] = force_index.ewm(span=force_span).mean()
    
    rs_thresh = params.get('rs_score_threshold', 70)
    vol_max = params.get('volatility_max', 12.0)
    
    df['VCP_Signal'] = (
        (df['RS_Score'] > rs_thresh) &
        (df['RS_Line'] > params.get('rs_line_threshold', 100)) &
        (df['Volatility'] < vol_max) &
        (df['Contraction_Trend']) &
        (df['Force_Index'] > 0)
    )
    
    df['Breakout'] = df['Close'] >= df['High_20']
    
    df['Signal'] = df['VCP_Signal'] & df['Breakout']
    
    df['VCP_Contractions'] = [detect_vcp_pattern(df)] * len(df)
    
    return df


def print_signal_summary(df):
    """
    打印信號摘要
    """
    signals = df[df['Signal']].copy()
    
    if signals.empty:
        print("\nNo breakout signals found.")
        return
    
    print("\n" + "="*70)
    print("SIGNAL SUMMARY - Breakout Points")
    print("="*70)
    print(f"{'Date':<12} {'Price':>10} {'RS Line':>10} {'RS Score':>10} {'Volatility':>12}")
    print("-"*70)
    
    for idx, row in signals.iterrows():
        date_str = idx.strftime('%Y-%m-%d')
        print(f"{date_str:<12} ${row['Close']:>8.2f} {row['RS_Line']:>10.1f} "
              f"{row['RS_Score']:>10.1f} {row['Volatility']:>10.2f}%")
    
    print("="*70)
    print(f"Total breakout signals: {len(signals)}")
