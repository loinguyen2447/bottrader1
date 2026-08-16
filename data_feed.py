"""
data_feed.py
Module lấy dữ liệu OHLCV từ MetaTrader 5 terminal, dùng làm nền cho
các module tiếp theo (ZigZag, Trendline, Volume Profile).

Yêu cầu: pip install MetaTrader5 pandas
Terminal MT5 phải đang mở và đăng nhập sẵn trên máy.
"""

import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime


class DataFeed:
    def __init__(self, symbol: str, timeframe=mt5.TIMEFRAME_H1, bars: int = 500):
        """
        symbol: ví dụ "EURUSD", "XAUUSD"
        timeframe: mt5.TIMEFRAME_M1, M5, M15, H1, H4, D1 ...
        bars: số nến muốn lấy mỗi lần
        """
        self.symbol = symbol
        self.timeframe = timeframe
        self.bars = bars
        self.last_bar_time = None  # dùng để phát hiện nến mới

        if not mt5.initialize():
            raise RuntimeError(f"Không thể kết nối MT5: {mt5.last_error()}")

        if not mt5.symbol_select(symbol, True):
            raise RuntimeError(f"Không tìm thấy symbol: {symbol}")

    def get_rates(self) -> pd.DataFrame:
        """Lấy dữ liệu OHLCV mới nhất, trả về DataFrame đã sort theo thời gian tăng dần."""
        rates = mt5.copy_rates_from_pos(self.symbol, self.timeframe, 0, self.bars)
        if rates is None or len(rates) == 0:
            raise RuntimeError(f"Không lấy được dữ liệu: {mt5.last_error()}")

        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        df.rename(columns={"tick_volume": "volume"}, inplace=True)
        return df[["time", "open", "high", "low", "close", "volume", "spread"]]

    def get_closed_rates(self) -> pd.DataFrame:
        """
        Trả về dữ liệu CHỈ gồm các nến đã đóng (bỏ nến cuối cùng đang chạy).
        Nên dùng hàm này cho ZigZag/Trendline để tránh repaint/lookahead bias.
        """
        df = self.get_rates()
        return df.iloc[:-1].reset_index(drop=True)

    def has_new_bar(self) -> bool:
        """
        Kiểm tra xem đã có nến mới đóng hay chưa (so với lần gọi trước).
        Dùng trong vòng lặp chính để tránh tính lại ZigZag/trendline mỗi tick.
        """
        df = self.get_closed_rates()
        latest_time = df["time"].iloc[-1]

        if self.last_bar_time is None:
            self.last_bar_time = latest_time
            return True  # lần đầu chạy, coi như có dữ liệu mới

        if latest_time != self.last_bar_time:
            self.last_bar_time = latest_time
            return True

        return False

    def shutdown(self):
        mt5.shutdown()


if __name__ == "__main__":
    # Ví dụ sử dụng
    feed = DataFeed(symbol="XAUUSD", timeframe=mt5.TIMEFRAME_H1, bars=500)

    df = feed.get_closed_rates()
    print(df.tail())

    print("Có nến mới không?", feed.has_new_bar())

    feed.shutdown()
