"""
trendline.py
Module vẽ đường xu hướng (trendline) từ các điểm đảo chiều của ZigZag
và phát hiện breakout (giá phá vỡ trendline).

Logic (theo yêu cầu):
- Mô hình TĂNG khi ZigZag xác định đỉnh sau cao hơn đỉnh trước (HH)
  và đáy sau cao hơn đáy trước (HL).
- Khi có mô hình tăng: lấy 2 điểm ĐÁY gần nhất để kẻ trendline hỗ trợ.
- Khi giá ĐÓNG CỬA phá xuống dưới trendline -> thông báo "BREAKOUT".
- Ngược lại (mô hình giảm LH + LL): kẻ trendline qua 2 ĐỈNH gần nhất,
  giá đóng cửa phá lên trên -> thông báo "BREAKOUT".
- Xác nhận "cú phá vỡ THẬT" bằng phân kỳ RSI tại 2 điểm "thuộc về" 2 điểm kẻ trend
  (đáy sau mỗi đỉnh / đỉnh sau mỗi đáy trong chuỗi xen kẽ của ZigZag):
  - Mô hình GIẢM (trendline qua 2 ĐỈNH): 2 đáy giá THẤP dần nhưng đường nối các ĐÁY RSI
    (tính từ đáy RSI sâu nhất, từ điểm đầu trendline đến lúc phá vỡ) DỐC LÊN → phân kỳ
    DƯƠNG → cú phá vỡ thật. Đáy RSI phải xuất hiện TRƯỚC đáy giá cuối L2.
  - Mô hình TĂNG (trendline qua 2 ĐÁY): 2 đỉnh giá CAO dần nhưng RSI tại đỉnh sau (H_c)
    THẤP HƠN RSI tại đỉnh trước (H_b) → phân kỳ ÂM → cú phá vỡ thật.

Dùng chung với data_feed.py (lấy dữ liệu) và zigzag.py (tìm điểm đảo chiều).
"""

from zigzag import ZigZag


class Trendline:
    """Đường xu hướng đi qua 2 điểm. Mỗi điểm là tuple (index, price)."""

    def __init__(self, p1, p2):
        self.p1 = p1  # (index, price) - điểm trước
        self.p2 = p2  # (index, price) - điểm sau
        dx = p2[0] - p1[0]
        self.slope = (p2[1] - p1[1]) / dx if dx != 0 else 0.0

    def value_at(self, index: int) -> float:
        """Giá trị của trendline tại một bar index bất kỳ."""
        return self.p1[1] + self.slope * (index - self.p1[0])

    def __repr__(self):
        return (f"Trendline({self.p1[1]:.2f} -> {self.p2[1]:.2f}, "
                f"slope={self.slope:+.4f}/bar)")


def detect_structure(pivots: list) -> str:
    """Nhận diện mô hình từ các điểm đảo chiều của ZigZag.

    Trả về "up" (HH + HL), "down" (LH + LL) hoặc "none" (chưa rõ).
    """
    highs = [p for p in pivots if p["type"] == "high"]
    lows = [p for p in pivots if p["type"] == "low"]
    if len(highs) < 2 or len(lows) < 2:
        return "none"

    hh = highs[-1]["price"] > highs[-2]["price"]   # đỉnh sau cao hơn đỉnh trước
    hl = lows[-1]["price"] > lows[-2]["price"]     # đáy sau cao hơn đáy trước
    lh = highs[-1]["price"] < highs[-2]["price"]   # đỉnh sau thấp hơn đỉnh trước
    ll = lows[-1]["price"] < lows[-2]["price"]     # đáy sau thấp hơn đáy trước

    if hh and hl:
        return "up"
    if lh and ll:
        return "down"
    return "none"


def check_breakout(df, deviation: float = 0.5) -> dict:
    """Kiểm tra breakout trên toàn bộ DataFrame (cần cột time/high/low/close).

    Trả về dict: trend, trendline, breakout (bool), message.
    """
    zz = ZigZag.compute(df, deviation=deviation)
    times = df["time"].tolist()
    closes = df["close"].tolist()

    result = {"trend": detect_structure(zz.pivots),
              "trendline": None, "breakout": False, "message": None}

    if result["trend"] not in ("up", "down"):
        return result

    # 2 điểm gần nhất: đáy (mô hình tăng) hoặc đỉnh (mô hình giảm)
    ptype = "low" if result["trend"] == "up" else "high"
    pts = [p for p in zz.pivots if p["type"] == ptype][-2:]
    if len(pts) < 2:
        return result

    idx1 = times.index(pts[0]["time"])
    idx2 = times.index(pts[1]["time"])
    line = Trendline((idx1, pts[0]["price"]), (idx2, pts[1]["price"]))
    result["trendline"] = line

    # Duyệt từ điểm cuối của trendline: giá đóng cửa phá qua đường -> breakout
    for i in range(idx2, len(closes)):
        if result["trend"] == "up" and closes[i] < line.value_at(i):
            result["breakout"] = True
            result["message"] = f"BREAKOUT! Gia pha trendline ho tro luc {times[i]}"
            break
        if result["trend"] == "down" and closes[i] > line.value_at(i):
            result["breakout"] = True
            result["message"] = f"BREAKOUT! Gia pha trendline khang cu luc {times[i]}"
            break

    return result


class BreakoutMonitor:
    """Theo dõi live: mỗi nến mới đóng gọi on_new_bar(), báo breakout đúng 1 lần.

    Cách dùng (kết hợp DataFeed.next_closed — 1 fetch duy nhất mỗi chu kỳ):
        mon = BreakoutMonitor(deviation=0.5)
        while True:
            df = feed.next_closed()   # None nếu chưa có nến mới đóng
            if df is None:
                continue
            bar = df.iloc[-1]
            rsi.update(bar["close"])
            r = mon.on_new_bar(bar["time"], bar["high"], bar["low"], bar["close"], rsi.value)
            if r["new_alert"]:
                print(r["message"])
    """

    def __init__(self, deviation: float = 0.5):
        self.deviation = deviation
        self.zz = ZigZag(deviation=deviation)
        self.times = []
        self.closes = []
        self.rsi_values = []   # RSI tại từng nến (None nếu chưa đủ dữ liệu)
        self.trend = "none"
        self.line = None
        self._signaled = None  # (time_p1, time_p2) của trendline đã báo rồi

    def on_new_bar(self, time, high: float, low: float, close: float,
                   rsi_value=None) -> dict:
        """Đưa 1 nến mới (đã đóng) vào, trả về kết quả kiểm tra.

        rsi_value: RSI hiện tại của nến này (nên gọi rsi.update(close) TRƯỚC rồi
        truyền rsi.value) — dùng để xác nhận "cú phá vỡ thật" bằng phân kỳ RSI.
        """
        self.zz.update(time, high, low)
        self.times.append(time)
        self.closes.append(close)
        self.rsi_values.append(rsi_value)
        self.trend = detect_structure(self.zz.pivots)

        result = {"trend": self.trend, "trendline": None,
                  "breakout": False, "new_alert": False, "message": None,
                  "real_breakout": False, "rsi_divergence": None}

        if self.trend not in ("up", "down"):
            return result

        line, key = self._build_line()
        if line is None:
            return result
        result["trendline"] = line

        idx, break_time = self._first_break(line)
        if idx is not None:
            result["breakout"] = True
            div = self._rsi_divergence(idx)
            result["rsi_divergence"] = div
            # real_breakout phản ánh trạng thái phân tích HIỆN TẠI (không phụ thuộc
            # alert-once) — nến nào cũng tính lại được
            if div and div["divergence"]:
                result["real_breakout"] = True
            if key != self._signaled:
                self._signaled = key
                result["new_alert"] = True
                target = "ho tro" if self.trend == "up" else "khang cu"
                if div and div["divergence"]:
                    if div.get("method") == "rsi_point_compare":
                        # Mô hình TĂNG: so sánh RSI tại 2 đỉnh (H_b vs H_c)
                        result["message"] = (
                            f"PHA VO THAT! Gia pha trendline {target} luc {break_time} "
                            f"(2 dinh {div['p1']['price']:.1f}->{div['p2']['price']:.1f} di nguoc RSI: "
                            f"RSI {div['p1']['rsi']:.1f}->{div['p2']['rsi']:.1f})")
                    else:
                        # Mô hình GIẢM: đường nối các đáy RSI
                        w = div["window"]
                        dp = w.get("deepest") or {}
                        le = w.get("last_extreme") or {}
                        result["message"] = (
                            f"PHA VO THAT! Gia pha trendline {target} luc {break_time} "
                            f"(2 diem {div['p1']['price']:.1f}->{div['p2']['price']:.1f} di nguoc RSI: "
                            f"cuc tri RSI {dp.get('rsi', 0):.1f}->{le.get('rsi', 0):.1f}, "
                            f"slope {w['rsi_slope']:+.3f}/nen)")
                else:
                    result["message"] = f"BREAKOUT! Gia pha trendline {target} luc {break_time}"
        return result

    def _build_line(self):
        ptype = "low" if self.trend == "up" else "high"
        pts = [p for p in self.zz.pivots if p["type"] == ptype][-2:]
        if len(pts) < 2:
            return None, None
        idxs = [self._index_of(p["time"]) for p in pts]
        if any(i is None for i in idxs):
            return None, None
        line = Trendline((idxs[0], pts[0]["price"]), (idxs[1], pts[1]["price"]))
        return line, (pts[0]["time"], pts[1]["time"])

    def _index_of(self, t):
        for i, x in enumerate(self.times):
            if x == t:
                return i
        return None

    def _first_break(self, line):
        """Tìm bar đầu tiên (từ điểm cuối trendline) mà giá đóng cửa phá qua đường."""
        start = line.p2[0]
        for i in range(start, len(self.closes)):
            v = line.value_at(i)
            if self.trend == "up" and self.closes[i] < v:
                return i, self.times[i]
            if self.trend == "down" and self.closes[i] > v:
                return i, self.times[i]
        return None, None

    def _rsi_at(self, t):
        """RSI tại nến có thời gian t (None nếu chưa có)."""
        i = self._index_of(t)
        if i is None or i >= len(self.rsi_values):
            return None
        return self.rsi_values[i]

    def _rsi_extremes(self, a: int, b: int, want_min: bool):
        """Các điểm cực trị RSI (đáy nếu want_min=True, đỉnh nếu False) trong [a, b].

        Trả về list [(bar_index, rsi_value), ...].
        """
        out = []
        for i in range(a + 1, b):
            v = self.rsi_values[i]
            if v is None or self.rsi_values[i - 1] is None or self.rsi_values[i + 1] is None:
                continue
            if want_min and v <= self.rsi_values[i - 1] and v < self.rsi_values[i + 1]:
                out.append((i, v))
            if not want_min and v >= self.rsi_values[i - 1] and v > self.rsi_values[i + 1]:
                out.append((i, v))
        return out

    @staticmethod
    def _slope(pts) -> float:
        """Độ dốc (hồi quy tuyến tính) của các điểm (bar_index, rsi_value)."""
        n = len(pts)
        if n < 2:
            return None
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        mx = sum(xs) / n
        my = sum(ys) / n
        den = sum((x - mx) ** 2 for x in xs)
        if den == 0:
            return None
        return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den

    def _rsi_divergence(self, break_idx):
        """Xác nhận "cú phá vỡ thật" bằng cách vẽ đường nối các điểm cực trị RSI
        (đáy RSI — mô hình giảm / đỉnh RSI — mô hình tăng) từ điểm đầu tiên của
        trendline đến lúc phá vỡ — đúng như đường xu hướng vẽ tay trên bảng RSI.

        - Mô hình GIẢM: trendline qua 2 ĐỈNH; mỗi đỉnh có 1 ĐÁY tạo ngay sau nó
          (pivot kế tiếp trong chuỗi xen kẽ). 2 đáy giá THẤP dần mà đường nối các
          ĐÁY RSI (tính từ đáy RSI sâu nhất, cửa sổ từ điểm đầu trendline đến lúc
          phá vỡ) DỐC LÊN → phân kỳ DƯƠNG → cú phá vỡ thật. Đáy RSI phải xuất hiện
          TRƯỚC đáy giá cuối L2 (nếu RSI vẫn đang giảm tại mức đáy mới thì không
          phải phân kỳ).
        - Mô hình TĂNG: so sánh trực tiếp RSI tại 2 đỉnh — đỉnh sau CAO hơn (HH) mà
          RSI tại đỉnh sau THẤP HƠN → phân kỳ ÂM → cú phá vỡ thật (cách này ổn định hơn
          đo cửa sổ vì sau đỉnh RSI cao nhất thì các đỉnh RSI tiếp theo luôn thấp hơn).

        Trả về dict hoặc None (chưa đủ dữ liệu / chưa xác minh được).
        """
        pivots = self.zz.pivots
        ptype = "high" if self.trend == "down" else "low"   # điểm kẻ trendline
        opp = "low" if self.trend == "down" else "high"     # điểm 'thuộc về' sau nó

        pts = [p for p in pivots if p["type"] == ptype][-2:]
        if len(pts) < 2:
            return None

        times = [p["time"] for p in pivots]
        follow = []
        for p in pts:
            idx = times.index(p["time"])
            if idx + 1 >= len(pivots) or pivots[idx + 1]["type"] != opp:
                return None  # điểm 'thuộc về' chưa được xác nhận
            follow.append(pivots[idx + 1])

        r1 = self._rsi_at(follow[0]["time"])
        r2 = self._rsi_at(follow[1]["time"])
        if r1 is None or r2 is None:
            return None

        # Cửa sổ quan sát: từ điểm ĐẦU TIÊN của trendline đến lúc phá vỡ
        start_idx = self._index_of(pts[0]["time"])
        if start_idx is None:
            return None

        want_min = self.trend == "down"

        # ============ MÔ HÌNH TĂNG: so sánh RSI tại 2 đỉnh (phân kỳ Âm kinh điển) ============
        # Đỉnh giá sau CAO hơn (HH) nhưng RSI tại đỉnh sau THẤP HƠN -> đà tăng yếu đi
        # -> phá vỡ thật. (Đo cửa sổ không ổn định cho mô hình tăng vì sau đỉnh RSI
        # cao nhất thì các đỉnh RSI tiếp theo luôn thấp hơn.)
        if not want_min:
            divergence = follow[1]["price"] > follow[0]["price"] and r2 < r1
            return {
                "divergence": divergence,
                "kind": "bearish" if divergence else "none",
                "method": "rsi_point_compare",
                "window": {
                    "from": str(pts[0]["time"]),
                    "to": str(self.times[break_idx]),
                    "rsi_slope": None,
                    "note": "so sanh RSI tai 2 dinh (H_b vs H_c)",
                },
                "p1": {"time": str(follow[0]["time"]), "price": follow[0]["price"], "rsi": r1},
                "p2": {"time": str(follow[1]["time"]), "price": follow[1]["price"], "rsi": r2},
            }

        # ============ MÔ HÌNH GIẢM: đường nối các ĐÁY RSI (như đường vẽ tay) ============
        extremes = self._rsi_extremes(start_idx, break_idx, want_min=True)
        if not extremes:
            return None

        # Đáy RSI sâu nhất làm điểm xuất phát của đường nối
        deepest = min(extremes, key=lambda e: e[1])
        i_deep = deepest[0]
        after = [e for e in extremes if e[0] >= i_deep]

        # Độ dốc đường nối các đáy RSI (từ đáy sâu nhất đến lúc phá vỡ).
        # Nếu chưa có đáy RSI thứ 2 thì tạm dùng RSI lúc phá vỡ làm điểm cuối.
        slope = self._slope(after) if len(after) >= 2 else None
        if slope is None:
            r_break = self.rsi_values[break_idx]
            if r_break is not None and break_idx != i_deep:
                slope = (r_break - deepest[1]) / (break_idx - i_deep)

        # Đáy RSI phải xuất hiện TRƯỚC đáy giá cuối L2 — nếu RSI vẫn đang giảm tại
        # mức đáy mới thì không phải phân kỳ (tránh báo nhầm khi RSI xác nhận xu hướng).
        i_follow2 = self._index_of(follow[1]["time"])
        guard_ok = i_follow2 is not None and i_deep < i_follow2

        divergence = False
        if guard_ok:
            if len(after) >= 2 and slope is not None:
                divergence = follow[1]["price"] < follow[0]["price"] and slope > 0
            else:
                # Chưa đủ 2 đáy RSI sau điểm sâu nhất: so RSI lúc phá vỡ với đáy đó
                r_break = self.rsi_values[break_idx]
                if r_break is not None:
                    divergence = follow[1]["price"] < follow[0]["price"] and r_break > deepest[1]

        kind = "bullish" if divergence else "none"
        last_e = after[-1] if after else deepest
        return {
            "divergence": divergence,
            "kind": kind,
            "method": "rsi_extreme_line",
            "window": {
                "from": str(pts[0]["time"]),
                "to": str(self.times[break_idx]),
                "rsi_slope": slope,
                "deepest": {"time": str(self.times[i_deep]), "rsi": deepest[1]},
                "last_extreme": {"time": str(self.times[last_e[0]]), "rsi": last_e[1]},
                "note": None if guard_ok else "RSI dat day tai/sau day gia cuoi - khong phan ky",
            },
            "p1": {"time": str(follow[0]["time"]), "price": follow[0]["price"], "rsi": r1},
            "p2": {"time": str(follow[1]["time"]), "price": follow[1]["price"], "rsi": r2},
        }


if __name__ == "__main__":
    # Ví dụ: lấy dữ liệu từ DataFeed (MT5) và kiểm tra breakout
    from data_feed import DataFeed
    import MetaTrader5 as mt5

    feed = DataFeed(symbol="XAUUSD", timeframe=mt5.TIMEFRAME_H1, bars=300)
    df = feed.get_closed_rates()

    result = check_breakout(df, deviation=0.5)
    ten = {"up": "TANG (HH + HL)", "down": "GIAM (LH + LL)", "none": "chua ro"}
    print("Mo hinh:", ten[result["trend"]])
    if result["trendline"] is not None:
        print("Trendline:", result["trendline"])
    print("Breakout:", "CO" if result["breakout"] else "chua")
    if result["message"]:
        print(">>", result["message"])

    # Mô phỏng live: nạp từng nến, in thông báo breakout khi xuất hiện
    print("\n--- Mo phong live (tung nen) ---")
    mon = BreakoutMonitor(deviation=0.5)
    for _, bar in df.iterrows():
        r = mon.on_new_bar(bar["time"], bar["high"], bar["low"], bar["close"])
        if r["new_alert"]:
            print(">>", r["message"])

    feed.shutdown()
