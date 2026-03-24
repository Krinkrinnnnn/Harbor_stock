from enum import Enum


class DisplayPrice(Enum):
    Candlestick = 0
    OHLC = 1
    Line = 2


class DrawType(Enum):
    HorizontalLine = 0
    VerticalLine = 1
    TrendLine = 2
    Fibonacci = 3
    Rectangle = 4
    Text = 5


class IndicatorType(Enum):
    Price = 0
    Sub = 1


class SignalType(Enum):
    Buy = 0
    Sell = 1
    Neutral = 2
