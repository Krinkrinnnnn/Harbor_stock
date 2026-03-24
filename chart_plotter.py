import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle, FancyBboxPatch
from matplotlib.lines import Line2D
from matplotlib.widgets import CheckButtons
from diagram_indicators import MovingAverages, IndicatorPlotter


class MarketSmithChart:
    """
    MarketSmith / TradingView / StockPlot 風格圖表繪製類
    - 蠟燭圖 (綠/紅) - 更美觀的樣式，沒有週末空隙 (StockPlot 風格)
    - 支援交互式十字線 (Crosshair)
    - RS 線
    - VCP 收縮波 (T1, T2, T3)
    - 移動平均線 (MA20, MA50, EMA13, EMA120)
    - 成交量柱狀圖
    """
    
    COLORS = {
        'bullish': '#07BF7D',      # StockPlot default Up color
        'bearish': '#FF4500',      # StockPlot default Down color (OrangeRed)
        'wick': '#000000',         # StockPlot default Wick color (Black)
        'background': '#FFFFFF',   # White background
        'grid': '#E5E5E5',
        'text': '#333333',
        'ma20': '#FFA500',         # Orange
        'ma50': '#1E90FF',         # DodgerBlue
        'ema13': '#FF1493',        # DeepPink
        'ema120': '#8A2BE2',       # BlueViolet
        'rs_line': '#0066CC',
        'rs_fill_up': '#00AA00',
        'rs_fill_down': '#CC0000',
        'volume_up': '#07BF7D',
        'volume_down': '#FF4500',
        'crosshair': '#757575'
    }
    
    def __init__(self, figsize=(18, 12)):
        self.figsize = figsize
        self.fig = None
        self.ax_price = None
        self.ax_volume = None
        self.ax_rs = None
        self.ma = MovingAverages()
        
        # 儲存 X 軸的日期映射 (消除週末空隙用)
        self.date_mapping = {}
        self.inv_date_mapping = {}
        self.dates = []
    
    def _prepare_continuous_x_axis(self, df):
        """
        準備連續的 X 軸 (跳過週末，類似 StockPlot 的處理方式)
        """
        df = df.copy()
        df = df.dropna(subset=['Open', 'Close'])
        
        self.dates = df.index.tolist()
        
        for i, date in enumerate(self.dates):
            self.date_mapping[date] = i
            self.inv_date_mapping[i] = date
            
        return df
    
    def _format_x_axis(self, ax, num_ticks=10):
        """
        格式化 X 軸標籤 (將連續索引轉換回日期)
        """
        if not self.dates:
            return
            
        total_dates = len(self.dates)
        step = max(1, total_dates // num_ticks)
        
        tick_positions = list(range(0, total_dates, step))
        tick_labels = [self.dates[i].strftime('%Y-%m-%d') for i in tick_positions]
        
        ax.set_xticks(tick_positions)
        ax.set_xticklabels(tick_labels, rotation=45, ha='right')
    
    def _draw_candlestick(self, ax, df):
        """
        繪製美觀的蠟燭圖 (StockPlot 風格)，使用連續的 X 軸索引
        空心綠色蠟燭 = 上漲 (Close >= Open)
        實心紅色蠟燭 = 下跌 (Close < Open)
        """
        width = 0.6
        
        for i, (idx, row) in enumerate(df.iterrows()):
            x_pos = self.date_mapping[idx]
            
            open_price = row['Open']
            close_price = row['Close']
            high_price = row['High']
            low_price = row['Low']
            
            is_bullish = close_price >= open_price
            
            body_color = '#FFFFFF' if is_bullish else self.COLORS['bearish']
            edge_color = self.COLORS['bullish'] if is_bullish else self.COLORS['bearish']
            wick_color = self.COLORS['bullish'] if is_bullish else self.COLORS['bearish']
            
            body_bottom = min(open_price, close_price)
            body_height = abs(close_price - open_price)
            
            # 繪製上下影線
            ax.plot([x_pos, x_pos], [low_price, high_price],
                    color=wick_color, linewidth=1.5, zorder=1)
            
            # 繪製實體
            if body_height > 0:
                rect = Rectangle(
                    (x_pos - width/2, body_bottom),
                    width,
                    body_height,
                    facecolor=body_color,
                    edgecolor=edge_color,
                    linewidth=1.2,
                    zorder=2
                )
                ax.add_patch(rect)
            else:
                # 十字線 (Doji)
                ax.plot([x_pos - width/2, x_pos + width/2], 
                        [close_price, close_price],
                        color=edge_color, linewidth=1.5, zorder=2)
    
    def _draw_volume(self, ax, df):
        """
        繪製成交量柱狀圖
        """
        width = 0.6
        
        for i, (idx, row) in enumerate(df.iterrows()):
            if pd.isna(row['Volume']) or row['Volume'] == 0:
                continue
            
            x_pos = self.date_mapping[idx]
            volume = row['Volume']
            
            is_bullish = row['Close'] >= row['Open']
            color = self.COLORS['volume_up'] if is_bullish else self.COLORS['volume_down']
            
            rect = Rectangle(
                (x_pos - width/2, 0),
                width,
                volume,
                facecolor=color,
                edgecolor=self.COLORS['wick'],
                linewidth=0.5,
                alpha=0.7
            )
            ax.add_patch(rect)
    
    def _draw_vcp_pattern(self, ax, df):
        """
        繪製 VCP 收縮波
        """
        if 'VCP_Contractions' not in df.columns:
            return
        
        contractions = df['VCP_Contractions'].iloc[-1]
        
        if not contractions:
            return
        
        colors = ['#FF6B6B', '#4ECDC4', '#45B7D1']
        
        for i, c in enumerate(contractions):
            wave = c['wave']
            date = c['date']
            price = c['price']
            contraction_pct = c.get('contraction_pct', 0)
            
            if date not in self.date_mapping:
                continue
                
            x_pos = self.date_mapping[date]
            color = colors[i % len(colors)]
            
            ax.hlines(y=price, xmin=0, xmax=x_pos,
                      colors=color, linestyles='--', linewidth=1.5, alpha=0.7)
            
            ax.plot(x_pos, price, 'o', color=color, markersize=8, zorder=7)
            
            bbox_props = dict(boxstyle="round,pad=0.3", facecolor='white', 
                              edgecolor=color, alpha=0.9, linewidth=1.5)
            ax.annotate(f'{wave}\n-{contraction_pct:.1f}%',
                        xy=(x_pos, price),
                        xytext=(10, 15),
                        textcoords='offset points',
                        fontsize=9,
                        fontweight='bold',
                        color=color,
                        ha='left',
                        va='bottom',
                        bbox=bbox_props,
                        zorder=10)
        
        if len(contractions) >= 2:
            wave_x = [self.date_mapping[c['date']] for c in contractions if c['date'] in self.date_mapping]
            wave_prices = [c['price'] for c in contractions if c['date'] in self.date_mapping]
            
            if len(wave_x) >= 2:
                ax.plot(wave_x, wave_prices, '-', color='#9B59B6', 
                        linewidth=2, alpha=0.7, zorder=4)
    
    def _draw_signals(self, ax, df):
        """
        繪製信號標記
        """
        vcp_signals = df[df['VCP_Signal']]
        for idx, row in vcp_signals.iterrows():
            if idx in self.date_mapping:
                x_pos = self.date_mapping[idx]
                ax.scatter(x_pos, row['Close'] * 1.02,
                           color='#FFA726', marker='^', s=100, label='VCP Signal' if idx == vcp_signals.index[0] else "",
                           zorder=8, alpha=0.9, edgecolors='#E65100', linewidths=1)
        
        breakout_signals = df[df['Signal']]
        for idx, row in breakout_signals.iterrows():
            if idx in self.date_mapping:
                x_pos = self.date_mapping[idx]
                ax.scatter(x_pos, row['Close'] * 1.02,
                           color='#66BB6A', marker='*', s=200, label='Buy Signal' if idx == breakout_signals.index[0] else "",
                           zorder=9, edgecolors='#1B5E20', linewidths=1)
                print(f"[{idx.strftime('%Y-%m-%d')}] BUY SIGNAL DETECTED at ${row['Close']:.2f}!")
    
    def _draw_rs_line(self, ax, df):
        """
        繪製 RS 線 (使用連續的 X 軸)
        """
        x_values = [self.date_mapping[idx] for idx in df.index if idx in self.date_mapping]
        rs_values = [df.loc[idx, 'RS_Line'] for idx in df.index if idx in self.date_mapping]
        
        ax.fill_between(x_values, 100, rs_values,
                        where=np.array(rs_values) >= 100,
                        alpha=0.3, color=self.COLORS['rs_fill_up'])
        ax.fill_between(x_values, 100, rs_values,
                        where=np.array(rs_values) < 100,
                        alpha=0.3, color=self.COLORS['rs_fill_down'])
        
        ax.plot(x_values, rs_values, color=self.COLORS['rs_line'], 
                linewidth=1.5, label='RS Line')
        
        ax.axhline(y=100, color='#666666', linestyle='-', linewidth=1, alpha=0.7)
        
        # RS MA20
        rs_ma20 = df['RS_Line'].rolling(window=20).mean()
        rs_ma20_values = [rs_ma20[idx] for idx in df.index if idx in self.date_mapping]
        ax.plot(x_values, rs_ma20_values,
                color='#FF6600', linewidth=1, linestyle='--', alpha=0.6, 
                label='RS 20-day MA')
                
    def _draw_moving_averages(self, ax, df):
        """
        繪製移動平均線
        """
        x_values = [self.date_mapping[idx] for idx in df.index if idx in self.date_mapping]
        lines = {}
        
        for ma_name, color, style, width in [
            ('MA20', self.COLORS['ma20'], '-', 1.5),
            ('MA50', self.COLORS['ma50'], '-', 1.5),
            ('EMA13', self.COLORS['ema13'], ':', 1.5),
            ('EMA120', self.COLORS['ema120'], ':', 1.5)
        ]:
            if ma_name in df.columns:
                ma_values = [df.loc[idx, ma_name] for idx in df.index if idx in self.date_mapping]
                line, = ax.plot(x_values, ma_values, color=color, linestyle=style,
                                linewidth=width, label=ma_name, alpha=0.85)
                lines[ma_name] = line
                
        return lines

    def plot(self, df, symbol, save_path=None):
        """
        繪製完整圖表
        """
        df = self.ma.calculate(df)
        df = self.ma.get_crossovers(df)
        
        # 準備連續的 X 軸 (跳過週末空隙)
        df_clean = self._prepare_continuous_x_axis(df)
        
        self.fig = plt.figure(figsize=self.figsize, facecolor=self.COLORS['background'], layout="constrained")
        
        # 使用 GridSpec 分配空間，類似 StockPlot 的佈局
        gs = self.fig.add_gridspec(5, 1, height_ratios=[3, 0.8, 1, 0.2, 0.2], 
                                   hspace=0.05)
        
        self.ax_price = self.fig.add_subplot(gs[0])
        self.ax_volume = self.fig.add_subplot(gs[1], sharex=self.ax_price)
        self.ax_rs = self.fig.add_subplot(gs[2], sharex=self.ax_price)
        
        self.ax_price.set_facecolor(self.COLORS['background'])
        self.ax_volume.set_facecolor(self.COLORS['background'])
        self.ax_rs.set_facecolor(self.COLORS['background'])
        
        # 繪製各個組件
        self._draw_candlestick(self.ax_price, df_clean)
        self._draw_vcp_pattern(self.ax_price, df_clean)
        ma_lines = self._draw_moving_averages(self.ax_price, df_clean)
        self._draw_signals(self.ax_price, df_clean)
        
        self._draw_volume(self.ax_volume, df_clean)
        self._draw_rs_line(self.ax_rs, df_clean)
        
        # 設置標題和標籤
        self.ax_price.set_ylabel('Price', fontsize=10)
        self.ax_price.set_title(f'{symbol} - Technical Analysis (StockPlot Style)', 
                                fontsize=14, fontweight='bold', loc='left')
        
        # 網格線設定 (StockPlot 風格)
        for ax in [self.ax_price, self.ax_volume, self.ax_rs]:
            ax.grid(True, alpha=0.2, color='#000000', linestyle='-')
            # 隱藏右側和上方的邊框
            ax.spines['right'].set_visible(False)
            ax.spines['top'].set_visible(False)
            ax.spines['left'].set_visible(False)
            ax.spines['bottom'].set_visible(False)
        
        # Add CheckButtons for toggling indicators
        if ma_lines:
            rax = self.fig.add_axes([0.02, 0.8, 0.08, 0.12])
            rax.set_facecolor(self.COLORS['background'])
            rax.set_title("Indicators", fontsize=9, fontweight='bold')
            labels = list(ma_lines.keys())
            visibility = [True] * len(labels)
            self.check = CheckButtons(rax, labels, visibility)
            
            for label in self.check.labels:
                label.set_fontsize(8)
                
            def toggle_lines(label):
                line = ma_lines[label]
                line.set_visible(not line.get_visible())
                self.fig.canvas.draw_idle()
                
            self.check.on_clicked(toggle_lines)
        
        # 設定 X 軸限制和格式
        max_x = len(self.dates) - 1
        self.ax_price.set_xlim(-1, max_x + 2)
        
        # 隱藏上半部圖表的 X 軸標籤 (ShareX 效果)
        plt.setp(self.ax_price.get_xticklabels(), visible=False)
        plt.setp(self.ax_volume.get_xticklabels(), visible=False)
        
        # 格式化最下方圖表的 X 軸
        self._format_x_axis(self.ax_rs)
        
        # Y 軸限制
        price_min = df_clean['Low'].min()
        price_max = df_clean['High'].max()
        price_range = price_max - price_min
        self.ax_price.set_ylim(price_min - price_range * 0.05, price_max + price_range * 0.1)
        
        vol_max = df_clean['Volume'].max()
        self.ax_volume.set_ylim(0, vol_max * 1.05)
        
        # 圖例設定
        legend_elements = [
            Line2D([0], [0], color=self.COLORS['bullish'], linewidth=2, label='Up'),
            Line2D([0], [0], color=self.COLORS['bearish'], linewidth=2, label='Down'),
            Line2D([0], [0], color=self.COLORS['ma20'], linewidth=1.5, label='MA20'),
            Line2D([0], [0], color=self.COLORS['ma50'], linewidth=1.5, label='MA50'),
            Line2D([0], [0], color=self.COLORS['ema13'], linewidth=1.5, linestyle=':', label='EMA13'),
            Line2D([0], [0], color=self.COLORS['ema120'], linewidth=1.5, linestyle=':', label='EMA120'),
        ]
        self.ax_price.legend(handles=legend_elements, loc='upper left', fontsize=8, 
                             ncol=3, framealpha=0.8, edgecolor='#DDDDDD')
        
        # 標示最新價格
        latest_price = df_clean['Close'].iloc[-1]
        self.ax_price.axhline(y=latest_price, color=self.COLORS['crosshair'], 
                              linestyle=':', linewidth=1, alpha=0.5)
        self.ax_price.annotate(f'{latest_price:.2f}',
                               xy=(max_x + 0.5, latest_price),
                               xytext=(5, 0), textcoords='offset points',
                               va='center', ha='left',
                               bbox=dict(boxstyle='square,pad=0.2', 
                                         fc=self.COLORS['crosshair'], ec='none', alpha=0.8),
                               color='white', fontsize=9, fontweight='bold')
        
        plt.show()
        
        return self.fig
