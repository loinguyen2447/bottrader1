# CLAUDE.md — Hướng dẫn làm việc với dự án

Dự án: **Bot giao dịch MT5 (XAUUSD)** — phát hiện breakout bằng ZigZag + Trendline + RSI.
Ngôn ngữ: Python 3, giao tiếp với terminal MetaTrader 5 qua package `MetaTrader5`.

## Chạy & kiểm tra

```bash
# Chạy bot chính (bắt buộc terminal MT5 đang mở và đã đăng nhập)
python main.py          # dừng: Ctrl+C

# Tự kiểm tra từng module (đều kết nối MT5, cần terminal đang mở)
python data_feed.py     # lấy nến XAUUSD H1, in tail
python zigzag.py        # tính ZigZag 500 nến, in các điểm đảo chiều
python trendline.py     # check_breakout + mô phỏng live từng nến
python rsi.py           # RSI Wilder 100 nến
```

- Cài đặt: `pip install MetaTrader5 pandas`
- Lưu ý Windows console: khi chạy script in tiếng Việt có dấu, dùng
  `PYTHONIOENCODING=utf-8 python ...` để tránh `UnicodeEncodeError` (console mặc định cp1258).

## Kiến trúc & vai trò từng file

| File | Vai trò |
|---|---|
| `main.py` | Vòng lặp chính: kết nối MT5 → warm-up 300 nến → poll mỗi 2s → khi có nến mới đóng thì phân tích 1 lần, in kết quả, ghi biểu đồ |
| `data_feed.py` | `DataFeed`: kết nối MT5, `get_rates()` (OHLCV), `get_closed_rates()` (**chỉ nến đã đóng**), `has_new_bar()` phát hiện nến mới |
| `zigzag.py` | `ZigZag`: swing high/low theo `deviation%`. Dùng tăng dần `update(time, high, low)` hoặc 1 lần `ZigZag.compute(df, deviation)` |
| `trendline.py` | `Trendline` (p1→p2, slope, value_at), `detect_structure()` (HH+HL / LH+LL), `check_breakout()` (1 lần trên df), `BreakoutMonitor` (live từng nến) |
| `rsi.py` | RSI công thức Wilder: class `RSI` (tăng dần, có `.value`) + hàm vector `rsi()`/`add_rsi()` |
| `chart_render.py` | `build_state()` gom trạng thái hiện tại → `write_chart_state()` ghi `chart_state.json` → `write_chart_page()` ghi `chart.html` (tự chứa, nhúng dữ liệu) |
| `chart.html` | **File sinh tự động** — biểu đồ nến + ZigZag + trendline + breakout + RSI (SVG thuần, không CDN, mở trình duyệt là xem được) |
| `chart_state.json` | **File sinh tự động** — dữ liệu JSON để cập nhật live khi chạy qua `python -m http.server` |
| `preview.html` | Tài liệu trực quan: sơ đồ Mermaid + mô phỏng trendline tương tác (dữ liệu giả lập) |
| `so_do_hoat_dong.md` | Tài liệu sơ đồ hoạt động (bản Markdown/Mermaid) |
| `thunhiem.py`, `import MetaTrader5 as mt5.py` | File rời, không thuộc pipeline chính |

## Cấu hình (`config.json` — main.py tự đọc khi khởi động)

Sửa file `config.json`, không cần đụng code:

```json
{
  "symbol": "XAUUSD",
  "timeframe": "D1",            // đổi khung: M1/M5/M15/M30/H1/H4/D1/W1/MN1
  "bars": 300,
  "rsi_period": 14,
  "check_interval": 2,          // giây giữa 2 lần poll — quyết định độ chễ phát hiện nến mới
  "deviation_by_timeframe": { "D1": 6.0 },   // deviation riêng theo từng khung
  "deviation_default": 0.5      // khung chưa khai báo sẽ dùng mức này
}
```

- `deviation` = % ngưỡng đảo chiều ZigZag: càng lớn càng lọc nhiễu (chỉ nhận đỉnh/đáy lớn), càng nhỏ càng nhạy.
- Muốn dùng khung khác: sửa `timeframe` + thêm mục deviation cho khung đó trong `deviation_by_timeframe`.
- Đầu ra: `chart.html` (biểu đồ tự chứa), `chart_state.json` (dữ liệu JSON).

## Quy ước & logic quan trọng

1. **Chỉ dùng nến đã đóng** (`get_closed_rates()`) cho mọi tính toán — tránh repaint/lookahead bias. Không dùng nến đang chạy.
2. **Trendline chỉ được kẻ khi có mô hình rõ ràng**:
   - Mô hình TĂNG = đỉnh sau cao hơn (HH) **và** đáy sau cao hơn (HL) → trendline qua **2 đáy** gần nhất (hỗ trợ).
   - Mô hình GIẢM = LH + LL → trendline qua **2 đỉnh** gần nhất (kháng cự).
   - Cấu trúc hỗn hợp (vd HH nhưng LL) → `none` → **không kẻ trendline** (cố ý, tránh đường sai lệch).
3. **Breakout**: giá **đóng cửa** phá qua trendline (tăng: phá dưới hỗ trợ; giảm: phá trên kháng cự). Mỗi trendline chỉ báo alert **1 lần** (`_signaled` lưu cặp thời gian 2 điểm).
4. **Xác nhận "phá vỡ thật" bằng phân kỳ RSI**: khi phá trendline, bot lấy 2 điểm "thuộc về" 2 mốc kẻ trend (mô hình giảm: 2 đáy tạo ngay sau 2 đỉnh kẻ trend; mô hình tăng: 2 đỉnh sau 2 đáy kẻ trend) rồi kiểm tra phân kỳ RSI — mô hình giảm: đáy sau thấp hơn nhưng RSI cao hơn (phân kỳ DƯƠNG); mô hình tăng: đỉnh sau cao hơn nhưng RSI thấp hơn (phân kỳ ÂM). Có phân kỳ → `real_breakout=True`, báo `PHA VO THAT`; không → báo breakout thường (chưa xác nhận). Gọi `on_new_bar(..., rsi_value)` với RSI của nến (phải `rsi.update(close)` TRƯỚC).
4. `has_new_bar()`: lần gọi đầu luôn trả `True` và bị "nuốt" trong main.py (tránh chạy lại nến vừa nạp ở warm-up).
5. MT5 Python package (bản 5.0.x) **không có API vẽ object lên biểu đồ terminal** (`chart_object_create` không tồn tại) → mọi hiển thị trendline đều qua `chart_render.py` → `chart.html`.
6. `chart.html`/`chart_state.json` là đầu ra sinh bởi `main.py` — nếu sửa logic phân tích hoặc giao diện, nhớ chạy lại main (hoặc script warm-up tương đương) để cập nhật 2 file này.
7. Dữ liệu thật hiện tại (08-2026): XAUUSD D1 — cập nhật trạng thái mô hình theo lần chạy mới nhất; `none` (chưa có HH+HL hoặc LH+LL) thì chưa có trendline — đây là hành vi đúng, không phải lỗi.

## Độ trễ đã đo (máy thật)

- Lấy 300 nến: ~1.5 ms · `has_new_bar()`: ~1.4 ms · phân tích 1 nến: ~0 ms · ghi biểu đồ: ~5.6 ms (số đo trên nến H1)
- Trọn 1 lượt có nến mới: ~7 ms. Độ chễ phát hiện nến mới: 0–2 s (trung bình ~1 s, do `CHECK_INTERVAL`).
