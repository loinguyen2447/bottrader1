# Bot phân tích XAUUSD (ZigZag + Trendline + RSI)

Bot đọc dữ liệu nến từ terminal **MetaTrader 5**, nhận diện cấu trúc thị trường bằng
**ZigZag**, kẻ **trendline** qua các pivot, phát hiện **breakout** và xác nhận bằng
**phân kỳ RSI**, sau đó vẽ mọi thứ lên **biểu đồ HTML** (mở bằng trình duyệt là xem được).

> ⚠️ Đây là công cụ **phân tích/hiển thị** — bot **KHÔNG đặt lệnh** tự động.

---

## Tính năng

- Lấy nến **đã đóng** từ MT5 (không repaint / không lookahead bias)
- **ZigZag** theo % deviation — chỉ giữ các điểm đảo chiều lớn, lọc nhiễu
- **Trendline** qua 2 pivot (mô hình TĂNG: HH+HL / mô hình GIẢM: LH+LL)
- **Breakout** khi giá đóng cửa phá trendline (mỗi trendline chỉ báo 1 lần)
- **Phân kỳ RSI** tại 2 đáy/đỉnh thuộc 2 điểm kẻ trend → xác nhận **"phá vỡ thật"**
- **Biểu đồ HTML tự chứa** (SVG, không cần internet): nến + pivot + trendline + điểm breakout + bảng RSI

---

## Yêu cầu

| Thứ | Ghi chú |
|---|---|
| Windows | MetaTrader5 Python chỉ hỗ trợ Windows |
| **Terminal MT5 đang mở và đã đăng nhập** | Bot kết nối vào terminal qua `mt5.initialize()` |
| Python 3.9+ | Kiểm tra: `python --version` |
| Symbol XAUUSD | Phải có trong "Market Watch" của MT5 |

---

## Cài đặt trên máy MỚI (sau khi clone repo)

```bash
git clone <đường-dẫn-repo-của-bạn> <tên-thư-mục>
cd <tên-thư-mục>

# (Khuyến nghị) tạo môi trường ảo
python -m venv venv
venv\Scripts\activate

# Cài thư viện
pip install -r requirements.txt

# Chạy
python main.py
```

Nếu console Windows không hiện tiếng Việt có dấu, chạy bằng:
```bash
set PYTHONIOENCODING=utf-8
python main.py
```

---

## Cấu hình (`config.json`)

| Tham số | Ý nghĩa | Ví dụ |
|---|---|---|
| `symbol` | Cặp tiền | `"XAUUSD"` |
| `timeframe` | Khung nến | `"D1"` (M1/M5/M15/M30/H1/H4/D1/W1/MN1) |
| `bars` | Số nến lấy | `300` |
| `rsi_period` | Chu kỳ RSI (Wilder) | `14` |
| `check_interval` | Giây giữa 2 lần poll nến mới | `2` |
| `deviation_by_timeframe` | ZigZag deviation riêng cho từng khung | `{ "D1": 6.0 }` |
| `deviation_default` | Deviation dùng cho khung chưa khai báo | `0.5` |

**Đổi khung thời gian** chỉ cần sửa `timeframe` + thêm deviation cho khung đó trong
`deviation_by_timeframe` — không cần đụng code.

> Mẹo tìm deviation hợp lý: deviation càng lớn → ít pivot, chỉ giữ đảo chiều lớn.
> Trên D1 XAUUSD, `6.0` cho ~18 pivot trong 300 nến (chỉ các swing lớn).

---

## Cấu trúc dự án

| File | Vai trò |
|---|---|
| `main.py` | Vòng lặp chính: đọc config → phân tích mỗi nến mới → ghi biểu đồ |
| `data_feed.py` | Kết nối MT5, lấy nến OHLCV đã đóng, phát hiện nến mới |
| `zigzag.py` | Nhận diện swing high/low theo % deviation |
| `trendline.py` | Kẻ trendline, phát hiện breakout, xác nhận phá vỡ thật bằng phân kỳ RSI |
| `rsi.py` | RSI công thức Wilder |
| `chart_render.py` | Gom trạng thái → ghi `chart.html` + `chart_state.json` |
| `config.json` | Cấu hình (symbol, timeframe, deviation theo khung...) |
| `thunhiem.py` | Tham khảo: indicator ZigZag++ trên TradingView (MPL 2.0) |

**File sinh tự động** (không commit, tái tạo mỗi lần chạy): `chart.html`, `chart_state.json`, `preview.html`.

---

## Lưu ý quan trọng

1. **Chỉ dùng nến đã đóng** — `data_feed.get_closed_rates()` bỏ nến đang chạy để tránh repaint.
2. **Trendline chỉ kẻ khi có mô hình rõ ràng** (HH+HL hoặc LH+LL). Cấu trúc hỗn hợp
   (ví dụ LH + HL — giá co lại thành tam giác) thì bot báo `chua ro`, **không kẻ** trendline.
3. **"Phá vỡ thật"** = phá trendline + phân kỳ RSI tại 2 điểm thuộc 2 mốc kẻ trend:
   - Mô hình GIẢM: 2 đáy giá thấp dần nhưng đường nối các **đáy RSI dốc lên** (từ đáy RSI sâu nhất).
   - Mô hình TĂNG: 2 đỉnh giá cao dần nhưng **RSI tại đỉnh sau thấp hơn** đỉnh trước.
4. Nến D1 đóng 1 lần/ngày, W1 1 lần/tuần — bot vẫn poll mỗi `check_interval` giây nhưng
   chỉ phân tích khi có nến mới thật sự đóng.
5. MT5 Python không có API vẽ object lên terminal → biểu đồ hiển thị qua file HTML.
