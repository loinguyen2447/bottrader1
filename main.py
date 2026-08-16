"""
main.py
Vòng lặp chính: mỗi khi có nến mới đóng trên MT5, chương trình chạy ĐÚNG 1 lần
để lấy dữ liệu và kiểm tra ZigZag + RSI + Trendline (breakout), in kết quả ra console.

Cách chạy:
    python main.py        (terminal MT5 phải đang mở và đã đăng nhập)

Dừng: nhấn Ctrl+C.
"""

import json
import time
import MetaTrader5 as mt5

from data_feed import DataFeed
from rsi import RSI
from trendline import BreakoutMonitor
from chart_render import build_state, write_chart_state, write_chart_page

# ----------------------- Cấu hình (đọc từ config.json) -----------------------
TF_MAP = {
    "M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4,
    "D1": mt5.TIMEFRAME_D1, "W1": mt5.TIMEFRAME_W1, "MN1": mt5.TIMEFRAME_MN1,
}

DEFAULT_CONFIG = {
    "symbol": "XAUUSD",
    "timeframe": "D1",
    "bars": 300,
    "rsi_period": 14,
    "check_interval": 2,
    "deviation_by_timeframe": {"D1": 6.0},   # deviation riêng cho từng khung thời gian
    "deviation_default": 0.5,                  # khung chưa khai báo sẽ dùng mức này
}


def _load_config() -> dict:
    """Đọc config.json; nếu thiếu file hoặc lỗi thì dùng giá trị mặc định."""
    try:
        with open("config.json", encoding="utf-8") as f:
            cfg = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        cfg = {}
    return {**DEFAULT_CONFIG, **cfg}


CFG = _load_config()
SYMBOL = CFG["symbol"]
TF_NAME = CFG["timeframe"]                     # tên khung, vd "D1"
TIMEFRAME = TF_MAP.get(TF_NAME, mt5.TIMEFRAME_D1)
BARS = CFG["bars"]
RSI_PERIOD = CFG["rsi_period"]
CHECK_INTERVAL = CFG["check_interval"]
# Deviation theo khung thời gian hiện tại; khung chưa khai báo thì dùng mặc định
DEVIATION = CFG["deviation_by_timeframe"].get(TF_NAME, CFG["deviation_default"])
CHART_HTML_PATH = "chart.html"         # trang biểu đồ trendline (mở trình duyệt là xem được)
CHART_STATE_PATH = "chart_state.json"  # dữ liệu JSON (dùng khi chạy qua http.server)
# ------------------------------------------------------------------------------


def _format_structure(trend: str) -> str:
    return {"up": "TANG (HH + HL)", "down": "GIAM (LH + LL)", "none": "chua ro"}[trend]


def _format_rsi(value) -> str:
    if value is None:
        return "chua du du lieu"
    txt = f"{value:.1f}"
    if value > 70:
        txt += " [QUA MUA]"
    elif value < 30:
        txt += " [QUA BAN]"
    return txt


def _format_trendline(result: dict) -> str:
    line = result.get("trendline")
    if line is None:
        return "khong co"
    return f"{line.p1[1]:.2f} -> {line.p2[1]:.2f} (slope {line.slope:+.4f}/nen)"


def _write_chart(df, mon, rsi, result: dict):
    """Ghi biểu đồ trendline (HTML + JSON) từ trạng thái hiện tại."""
    state = build_state(df, mon, rsi, result)
    write_chart_state(CHART_STATE_PATH, state)
    write_chart_page(CHART_HTML_PATH, state)


def _print_summary(bar, result: dict, rsi_value):
    if result.get("real_breakout"):
        state = "PHA VO THAT (phan ky RSI xac nhan)!"
    elif result.get("breakout"):
        state = "PHA VO (chua xac nhan phan ky RSI)"
    else:
        state = "chua pha"
    div = result.get("rsi_divergence")
    print("-" * 60)
    print(f"Nen dong: {bar['time']} | close = {bar['close']:.2f}")
    print(f"Mo hinh  : {_format_structure(result['trend'])}")
    print(f"Trendline: {_format_trendline(result)}")
    print(f"RSI({RSI_PERIOD}): {_format_rsi(rsi_value)}")
    print(f"Breakout : {state}")
    if div:
        kind = "DUONG" if div["kind"] == "bullish" else "AM" if div["kind"] == "bearish" else "khong"
        w = div["window"]
        if div.get("method") == "rsi_point_compare":
            # Mô hình TĂNG: so sánh RSI tại 2 đỉnh
            print(f"Phan ky  : {kind} | 2 dinh {div['p1']['price']:.1f}->{div['p2']['price']:.1f} "
                  f"nguoc RSI ({div['p1']['rsi']:.1f}->{div['p2']['rsi']:.1f}), "
                  f"{w['from'][:10]} -> {w['to'][:10]})")
        else:
            # Mô hình GIẢM: đường nối các đáy RSI
            dp = w.get("deepest") or {}
            le = w.get("last_extreme") or {}
            slope_txt = f"{w['rsi_slope']:+.3f}" if w.get("rsi_slope") is not None else "n/a"
            print(f"Phan ky  : {kind} | 2 diem {div['p1']['price']:.1f}->{div['p2']['price']:.1f} "
                  f"nguoc RSI, cuc tri RSI {dp.get('rsi', 0):.1f}->{le.get('rsi', 0):.1f} "
                  f"(slope {slope_txt}/nen, {w['from'][:10]} -> {w['to'][:10]})")


def main():
    print(f"Dang ket noi MT5... ({SYMBOL} {TF_NAME}, deviation {DEVIATION}%)")
    feed = DataFeed(SYMBOL, TIMEFRAME, BARS)
    try:
        df = feed.get_closed_rates()
        mon = BreakoutMonitor(deviation=DEVIATION)
        rsi = RSI(period=RSI_PERIOD)

        # Khởi động: nạp lịch sử để ZigZag + RSI sẵn sàng từ nến hiện tại
        last = {"trend": "none", "trendline": None, "breakout": False, "message": None}
        for _, bar in df.iterrows():
            rsi.update(bar["close"])  # cập nhật RSI trước để monitor dùng cho xác nhận phân kỳ
            last = mon.on_new_bar(bar["time"], bar["high"], bar["low"], bar["close"], rsi.value)

        # Đánh dấu nến hiện tại đã xử lý (dùng df đã nạp, không fetch lại):
        # tránh vòng lặp chính xử lý lại nến vừa warm-up
        feed.mark_processed(df)

        print(f"[{SYMBOL}] Trang thai hien tai:")
        _print_summary(df.iloc[-1], last, rsi.value)
        _write_chart(df, mon, rsi, last)
        print(f"Da ghi {CHART_HTML_PATH} -> mo file nay de xem trendline")
        print("\nDang theo doi nến moi dong... (Ctrl+C de dung)")

        while True:
            time.sleep(CHECK_INTERVAL)
            # next_closed(): đúng 1 lần fetch duy nhất — vừa phát hiện nến mới vừa
            # lấy dữ liệu để phân tích (trước đây gọi has_new_bar() + get_closed_rates()
            # nên fetch 2 lần/chu kỳ)
            df = feed.next_closed()
            if df is None:
                continue  # chưa có nến mới đóng -> chờ tiếp

            # Có nến mới đóng: chạy đúng 1 lượt kiểm tra
            bar = df.iloc[-1]
            rsi.update(bar["close"])
            result = mon.on_new_bar(bar["time"], bar["high"], bar["low"], bar["close"], rsi.value)

            _print_summary(bar, result, rsi.value)
            _write_chart(df, mon, rsi, result)
            if result.get("new_alert") and result.get("message"):
                print("***", result["message"], "***")
    finally:
        feed.shutdown()
        print("\nDa dong ket noi MT5.")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as e:
        print(f"LOI: {e}")
        print("Kiem tra terminal MT5 da mo va dang nhap chua.")
    except KeyboardInterrupt:
        print("\nNguoi dung dung chuong trinh.")
