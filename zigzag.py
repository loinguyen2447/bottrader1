"""
zigzag.py
Module ZigZag xác định các điểm đảo chiều (swing high / swing low)
từ dữ liệu OHLCV lấy từ data_feed.py.

Có 2 cách dùng:
1. Tính một lần trên toàn bộ DataFrame:
       zz = ZigZag.compute(df, deviation=0.5)
2. Cập nhật từng nến (dùng cho live, mỗi lần có nến mới đóng):
       zz = ZigZag(deviation=0.5)
       zz.update(timestamp, high, low)

Lưu ý: nên dùng get_closed_rates() từ DataFeed để tránh repaint/lookahead bias
(chỉ tính trên các nến đã đóng, không dùng nến đang chạy).
"""

import pandas as pd


class ZigZag:
    """ZigZag tăng dần: mỗi lần gọi update() với 1 nến mới đã đóng.

    deviation: ngưỡng đảo chiều tính theo % giá, ví dụ 0.5 nghĩa là 0.5%.
    """

    def __init__(self, deviation: float = 0.5):
        self.deviation = deviation
        self.pivots = []          # list dict: {"time", "price", "type"} ("high"/"low")
        self._state = "init"      # "init" -> "up" | "down"
        self._last_pivot = None   # điểm đảo chiều đã xác nhận gần nhất
        self._extreme = None      # đỉnh/đáy đang chạy (chưa xác nhận)

    def update(self, time, high: float, low: float):
        """Đưa 1 nến mới (đã đóng) vào. time: datetime/timestamp, high/low: float."""
        bar = {"time": time, "high": high, "low": low}

        # Nến đầu tiên: chỉ ghi nhận, chưa xác định được hướng
        if self._extreme is None:
            self._extreme = bar
            return

        # Nến thứ 2: quyết định hướng ban đầu
        if self._state == "init":
            if high >= self._extreme["high"]:
                self._state = "up"
                self._last_pivot = {"time": self._extreme["time"],
                                    "price": self._extreme["low"], "type": "low"}
            else:
                self._state = "down"
                self._last_pivot = {"time": self._extreme["time"],
                                    "price": self._extreme["high"], "type": "high"}
            self.pivots.append(self._last_pivot)
            self._extreme = bar
            return

        if self._state == "up":
            # Đang tìm đỉnh: mở rộng đỉnh nếu có high mới
            if high > self._extreme["high"]:
                self._extreme = bar
            else:
                # Đảo chiều khi giá thụt lùi khỏi đỉnh >= deviation%
                retrace = (self._extreme["high"] - low) / self._extreme["high"] * 100
                if retrace >= self.deviation:
                    self._last_pivot = {"time": self._extreme["time"],
                                        "price": self._extreme["high"], "type": "high"}
                    self.pivots.append(self._last_pivot)
                    self._state = "down"
                    self._extreme = bar
        else:  # "down"
            # Đang tìm đáy: mở rộng đáy nếu có low mới
            if low < self._extreme["low"]:
                self._extreme = bar
            else:
                # Đảo chiều khi giá vọt lên khỏi đáy >= deviation%
                retrace = (high - self._extreme["low"]) / self._extreme["low"] * 100
                if retrace >= self.deviation:
                    self._last_pivot = {"time": self._extreme["time"],
                                        "price": self._extreme["low"], "type": "low"}
                    self.pivots.append(self._last_pivot)
                    self._state = "up"
                    self._extreme = bar

    @classmethod
    def compute(cls, df: pd.DataFrame, deviation: float = 0.5) -> "ZigZag":
        """Tính ZigZag một lần trên toàn bộ DataFrame (cần cột time/high/low)."""
        zz = cls(deviation=deviation)
        for t, high, low in zip(df["time"], df["high"], df["low"]):
            zz.update(t, high, low)
        return zz

    def pivots_df(self) -> pd.DataFrame:
        """Trả về các điểm đảo chiều đã xác nhận dạng DataFrame."""
        return pd.DataFrame(self.pivots)

    @property
    def last_pivot(self):
        """Điểm đảo chiều đã xác nhận gần nhất (hoặc None nếu chưa có)."""
        return self._last_pivot

    @property
    def current_extreme(self):
        """Đỉnh/đáy đang chạy (chưa xác nhận) — dùng để vẽ đoạn ZigZag cuối."""
        return self._extreme


if __name__ == "__main__":
    # Ví dụ: lấy dữ liệu từ DataFeed (MT5) và tính ZigZag
    from data_feed import DataFeed
    import MetaTrader5 as mt5

    feed = DataFeed(symbol="XAUUSD", timeframe=mt5.TIMEFRAME_H1, bars=500)
    df = feed.get_closed_rates()  # chỉ dùng nến đã đóng

    zz = ZigZag.compute(df, deviation=0.5)
    print("Số điểm đảo chiều:", len(zz.pivots))
    print(zz.pivots_df().tail(10))

    feed.shutdown()
