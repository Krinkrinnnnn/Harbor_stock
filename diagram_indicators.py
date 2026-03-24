import pandas as pd
import numpy as np
import warnings


class MovingAverages:
    """
    移動平均線指標類
    - MA20: 20日簡單移動平均線
    - MA50: 50日簡單移動平均線
    - EMA13: 13日指數移動平均線
    - EMA120: 120日指數移動平均線
    """
    
    def __init__(self):
        self.ma20 = None
        self.ma50 = None
        self.ema13 = None
        self.ema120 = None
    
    def calculate(self, df):
        """
        計算所有移動平均線
        """
        df = df.copy()
        
        df['MA20'] = df['Close'].rolling(window=20).mean()
        df['MA50'] = df['Close'].rolling(window=50).mean()
        df['EMA13'] = df['Close'].ewm(span=13, adjust=False).mean()
        df['EMA120'] = df['Close'].ewm(span=120, adjust=False).mean()
        
        self.ma20 = df['MA20']
        self.ma50 = df['MA50']
        self.ema13 = df['EMA13']
        self.ema120 = df['EMA120']
        
        return df
    
    def get_crossovers(self, df):
        """
        檢測均線交叉信號
        - 黃金交叉: 短期均線上穿長期均線
        - 死亡交叉: 短期均線下穿長期均線
        """
        df = df.copy()
        
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FutureWarning)
            
            df['MA20_Above_MA50'] = (df['MA20'] > df['MA50']).astype(bool)
            prev_ma20_above = df['MA20_Above_MA50'].shift(1).fillna(False).infer_objects(copy=False)
            df['Golden_Cross'] = (df['MA20_Above_MA50']) & (~prev_ma20_above)
            df['Death_Cross'] = (~df['MA20_Above_MA50']) & (prev_ma20_above)
            
            df['EMA13_Above_MA20'] = (df['EMA13'] > df['MA20']).astype(bool)
            prev_ema13_above = df['EMA13_Above_MA20'].shift(1).fillna(False).infer_objects(copy=False)
            df['Short_Golden_Cross'] = (df['EMA13_Above_MA20']) & (~prev_ema13_above)
            df['Short_Death_Cross'] = (~df['EMA13_Above_MA20']) & (prev_ema13_above)
        
        return df
    
    def get_trend(self, df):
        """
        判斷趨勢狀態
        """
        latest = df.iloc[-1]
        
        trend = {
            'ma20': latest['MA20'] if pd.notna(latest['MA20']) else None,
            'ma50': latest['MA50'] if pd.notna(latest['MA50']) else None,
            'ema13': latest['EMA13'] if pd.notna(latest['EMA13']) else None,
            'ema120': latest['EMA120'] if pd.notna(latest['EMA120']) else None,
        }
        
        if trend['ma20'] and trend['ma50']:
            if latest['Close'] > trend['ma20'] > trend['ma50']:
                trend['status'] = 'Strong Uptrend'
            elif latest['Close'] > trend['ma20']:
                trend['status'] = 'Uptrend'
            elif latest['Close'] < trend['ma20'] < trend['ma50']:
                trend['status'] = 'Strong Downtrend'
            elif latest['Close'] < trend['ma20']:
                trend['status'] = 'Downtrend'
            else:
                trend['status'] = 'Sideways'
        else:
            trend['status'] = 'Insufficient Data'
        
        return trend


class IndicatorPlotter:
    """
    指標繪圖類
    """
    
    COLORS = {
        'MA20': '#FF9800',
        'MA50': '#2196F3',
        'EMA13': '#E91E63',
        'EMA120': '#9C27B0'
    }
    
    LABELS = {
        'MA20': 'MA20 (Short-term)',
        'MA50': 'MA50 (Medium-term)',
        'EMA13': 'EMA13 (Fast)',
        'EMA120': 'EMA120 (Long-term)'
    }
    
    @staticmethod
    def draw_moving_averages(ax, df):
        """
        繪製移動平均線
        """
        if 'MA20' in df.columns:
            ax.plot(df.index, df['MA20'], color=IndicatorPlotter.COLORS['MA20'],
                    linewidth=1.5, label=IndicatorPlotter.LABELS['MA20'], alpha=0.8)
        
        if 'MA50' in df.columns:
            ax.plot(df.index, df['MA50'], color=IndicatorPlotter.COLORS['MA50'],
                    linewidth=1.5, label=IndicatorPlotter.LABELS['MA50'], alpha=0.8)
        
        if 'EMA13' in df.columns:
            ax.plot(df.index, df['EMA13'], color=IndicatorPlotter.COLORS['EMA13'],
                    linewidth=1.2, label=IndicatorPlotter.LABELS['EMA13'], alpha=0.8,
                    linestyle='--')
        
        if 'EMA120' in df.columns:
            ax.plot(df.index, df['EMA120'], color=IndicatorPlotter.COLORS['EMA120'],
                    linewidth=1.5, label=IndicatorPlotter.LABELS['EMA120'], alpha=0.8)
    
    @staticmethod
    def draw_crossovers(ax, df):
        """
        繪製交叉信號
        """
        golden_cross = df[df['Golden_Cross']]
        if not golden_cross.empty:
            ax.scatter(golden_cross.index, golden_cross['MA20'] * 0.99,
                       color='gold', marker='^', s=100, label='Golden Cross',
                       zorder=7, edgecolors='orange', linewidths=1)
        
        death_cross = df[df['Death_Cross']]
        if not death_cross.empty:
            ax.scatter(death_cross.index, death_cross['MA20'] * 1.01,
                       color='black', marker='v', s=100, label='Death Cross',
                       zorder=7, edgecolors='red', linewidths=1)
