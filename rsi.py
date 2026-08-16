"""
rsi.py
Module tính RSI (Relative Strength Index) theo công thức Wilder,
dùng cho dữ liệu OHLCV lấy từ data_feed.py.

Có 2 cách dùng:
1. Tính một lần trên toàn bộ DataFrame:
       df = add_rsi(df, period=14)          # thêm cột "rsi" vào df
       s = rsi(df["close"], period=14)      # hoặc lấy riêng chuỗi RSI
2. Cập nhật từng nến (dùng cho live):
       r = RSI(period=14)
       r.update(close)                      # trả về giá trị RSI hiện tại

Quy ước: nếu không có lỗ (avg_loss = 0) thì RSI = 100.
"""

import pandas as pd


def _wilder_rma(values, period: int):
    """Wilder's Running Moving Average (giống rma() trong TradingView).

    Giá trị đầu = trung bình đơn giản của `period` giá trị đầu tiên,
    sau đó làm trơn: rma = (rma_prev * (period - 1) + value) / period.
    """
    if len(values) < period:
        return [float("nan")] * len(values)

    seed = sum(values[:period]) / period
    out = [float("nan")] * (period - 1) + [seed]
    prev = seed
    for v in values[period:]:
        prev = (prev * (period - 1) + v) / period
        out.append(prev)
    return out


def rsi(close, period: int = 14) -> pd.Series:
    """Tính RSI (Wilder) cho chuỗi giá đóng cửa, trả về pd.Series cùng index."""
    close = pd.Series(close)
    delta = close.diff()

    gain = delta.clip(lower=0).dropna()    # chỉ giữ phần tăng, bỏ NaN đầu
    loss = (-delta.clip(upper=0)).dropna() # chỉ giữ phần giảm (số dương)

    avg_gain = _wilder_rma(gain.tolist(), period)
    avg_loss = _wilder_rma(loss.tolist(), period)

    rs = pd.Series(avg_gain, index=gain.index) / pd.Series(avg_loss, index=loss.index)
    out = 100 - 100 / (1 + rs)
    out = out.where(pd.Series(avg_loss, index=loss.index) != 0, 100.0)
    return out.reindex(close.index)  # bar đầu tiên = NaN (chưa đủ dữ liệu)


def add_rsi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """Thêm cột "rsi" vào DataFrame (cần cột close), trả về bản sao."""
    df = df.copy()
    df["rsi"] = rsi(df["close"], period)
    return df


class RSI:
    """RSI tăng dần: mỗi lần gọi update(close) với giá đóng cửa của nến mới."""

    def __init__(self, period: int = 14):
        self.period = period
        self.value = None           # RSI hiện tại (None khi chưa đủ dữ liệu)
        self._prev_close = None
        self._gains = []
        self._losses = []
        self._avg_gain = None
        self._avg_loss = None

    def update(self, close: float):
        """Đưa 1 giá đóng cửa mới vào, trả về RSI hiện tại (hoặc None)."""
        if self._prev_close is None:
            self._prev_close = close
            return None

        diff = close - self._prev_close
        self._prev_close = close
        gain = max(diff, 0.0)
        loss = max(-diff, 0.0)

        if len(self._gains) < self.period:
            # Giai đoạn "làm nóng": tích lũy đủ `period` phiên đầu
            self._gains.append(gain)
            self._losses.append(loss)
            if len(self._gains) == self.period:
                self._avg_gain = sum(self._gains) / self.period
                self._avg_loss = sum(self._losses) / self.period
        else:
            # Wilder smoothing
            self._avg_gain = (self._avg_gain * (self.period - 1) + gain) / self.period
            self._avg_loss = (self._avg_loss * (self.period - 1) + loss) / self.period

        if self._avg_gain is not None:
            self.value = 100.0 if self._avg_loss == 0 else \
                100 - 100 / (1 + self._avg_gain / self._avg_loss)
        return self.value

    @classmethod
    def compute(cls, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Tính RSI một lần trên toàn bộ DataFrame (cần cột close)."""
        r = cls(period=period)
        values = [r.update(c) for c in df["close"]]
        return pd.Series(values, index=df.index)


if __name__ == "__main__":
    # Ví dụ: lấy dữ liệu từ DataFeed (MT5) và tính RSI
    from data_feed import DataFeed
    import MetaTrader5 as mt5

    feed = DataFeed(symbol="XAUUSD", timeframe=mt5.TIMEFRAME_H1, bars=100)
    df = feed.get_closed_rates()  # chỉ dùng nến đã đóng

    df = add_rsi(df, period=14)
    print(df[["time", "close", "rsi"]].tail())

    feed.shutdown()
