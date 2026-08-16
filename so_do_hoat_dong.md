# Sơ đồ hoạt động — Bot giao dịch MT5 (XAUUSD)

Tài liệu mô tả chương trình **đang chạy như thế nào**, từ lúc khởi động đến vòng lặp theo dõi nến mới.
Các sơ đồ viết bằng [Mermaid](https://mermaid.js.org/) — mở file này trong VSCode/GitHub/GitLab để xem dạng đồ họa.

---

## 1. Kiến trúc tổng quan

```
┌────────────────────────────────────────────────────────────────────┐
│                             main.py                                │
│  Vòng lặp chính: chờ nến mới đóng → kiểm tra → in kết quả         │
│  → ghi biểu đồ (chart_render.py)                                   │
└───┬───────────────┬─────────────────┬───────────────┬─────────┬────┘
    │               │                 │               │         │
    ▼               ▼                 ▼               ▼         ▼
┌──────────┐  ┌───────────┐   ┌──────────────┐  ┌─────────┐  ┌─────────────┐
│ data_feed│  │  zigzag   │   │  trendline   │  │   rsi   │  │chart_render │
│  (MT5)   │  │ ZigZag    │   │ Trendline +  │  │ RSI     │  │ Xuất chart  │
│          │  │ (điểm đảo │   │ BreakoutMonitor│ │ (Wilder)│  │ .html + .json│
│ Lấy nến  │  │ chiều)    │   │              │  │         │  │             │
└────┬─────┘  └───────────┘   └──────────────┘  └─────────┘  └─────────────┘
     │
     ▼
┌────────────┐
│ Terminal   │
│ MetaTrader5│
└────────────┘
```

- **data_feed.py** — kết nối MT5, lấy nến OHLCV, chỉ trả về **nến đã đóng** (tránh repaint/lookahead bias).
- **zigzag.py** — nhận diện swing high / swing low theo ngưỡng `deviation%`.
- **trendline.py** — kẻ đường xu hướng qua 2 điểm ZigZag, phát hiện giá **phá vỡ** (breakout).
- **rsi.py** — RSI công thức Wilder, cập nhật từng nến.
- **chart_render.py** — gom trạng thái hiện tại (nến + ZigZag + trendline + breakout + RSI) thành JSON, ghi ra `chart.html` (biểu đồ nến tự chứa — mở trình duyệt là thấy trendline được vẽ) và `chart_state.json`.

---

## 2. Sơ đồ hoạt động chính (main.py)

```mermaid
flowchart TD
    Start(["BẮT ĐẦU<br/>python main.py"]) --> Connect["Kết nối MT5<br/>mt5.initialize() + symbol_select('XAUUSD')"]
    Connect --> OK{"Kết nối +<br/>chọn symbol<br/>thành công?"}
    OK -- "Lỗi" --> Err(["KẾT THÚC<br/>RuntimeError: kiểm tra terminal MT5"])
    OK -- "OK" --> Init["Khởi tạo:<br/>DataFeed(D1, 300 nến)<br/>BreakoutMonitor(deviation=6.0%)<br/>RSI(period=14)"]
    Init --> Warmup["Khởi động (warm-up):<br/>lặp từng nến lịch sử đã đóng:<br/>• mon.on_new_bar(...) → ZigZag + trendline<br/>• rsi.update(close)<br/><i>(làm cho chỉ báo 'sẵn sàng' từ nến hiện tại)</i>"]
    Warmup --> Mark["Đánh dấu nến đã xử lý:<br/>feed.has_new_bar()<br/><i>(lần gọi đầu luôn trả True và bị 'nuốt'</i><br/><i>→ vòng lặp không chạy lại nến vừa nạp)</i>"]
    Mark --> PrintInit["In trạng thái hiện tại:<br/>mô hình + trendline + RSI + breakout"]
    PrintInit --> Loop["VÒNG LẶP CHÍNH"]

    Loop --> Sleep["Chờ CHECK_INTERVAL = 2 giây"]
    Sleep --> HasNew{"feed.has_new_bar()?<br/>có nến mới đóng<br/>so với lần kiểm tra trước?"}
    HasNew -- "Không" --> Sleep
    HasNew -- "Có" --> GetBar["Lấy nến đóng mới nhất:<br/>get_closed_rates().iloc[-1]"]
    GetBar --> Analyze["Phân tích:<br/>• mon.on_new_bar(time, high, low, close)<br/>• rsi.update(close)"]
    Analyze --> Print["In summary:<br/>mô hình (TANG/GIAM)<br/>trendline (giá trị + slope)<br/>RSI (quá mua/quá bán)<br/>trạng thái breakout"]
    Print --> Alert{"Có alert mới?<br/>(new_alert = True)"}
    Alert -- "Có" --> ShowAlert["In *** BREAKOUT! ***"]
    Alert -- "Không" --> Continue
    ShowAlert --> Continue
    Continue --> Stop{"Người dùng nhấn<br/>Ctrl+C?"}
    Stop -- "Chưa" --> Sleep
    Stop -- "Có" --> Shutdown["Đóng kết nối MT5<br/>feed.shutdown()"]
    Shutdown --> End(["KẾT THÚC"])
```

> Điểm mấu chốt: chương trình chỉ chạy **đúng 1 lần kiểm tra** khi có nến mới đóng trên D1 — không tính lại theo từng tick giá.

---

## 3. Chi tiết từng bước

### 3.1 DataFeed.has_new_bar() — phát hiện nến mới

```mermaid
flowchart TD
    S(["has_new_bar()"]) --> A["get_closed_rates()<br/>lấy dữ liệu, bỏ nến cuối đang chạy"]
    A --> B{"last_bar_time<br/>chưa có?<br/>(lần đầu)"}
    B -- "Có" --> C["Ghi nhận nến mới nhất<br/>return True"]
    B -- "Không" --> D{"Nến mới nhất<br/>≠ last_bar_time?"}
    D -- "Có (có nến mới đóng)" --> E["Cập nhật last_bar_time<br/>return True"]
    D -- "Không (vẫn nến cũ)" --> F["return False<br/>→ main chờ tiếp"]
```

### 3.2 ZigZag.update() — xác định điểm đảo chiều

```mermaid
flowchart TD
    S(["update(time, high, low)"]) --> A{"Nến đầu tiên?<br/>_extreme == None"}
    A -- "Có" --> B["Ghi nhận nến làm extreme<br/>→ return"]
    A -- "Không" --> C{"Đang ở trạng thái<br/>khởi tạo (nến 2)?"}
    C -- "Có" --> D{"high ≥ extreme.high?"}
    D -- "Có" --> E["state = up<br/>xác nhận pivot LOW ở nến đầu"]
    D -- "Không" --> F["state = down<br/>xác nhận pivot HIGH ở nến đầu"]
    E --> G["extreme = nến hiện tại"]
    F --> G
    C -- "Không" --> H{"state == up?<br/>(đang tìm đỉnh)"}
    H -- "Có" --> I{"Có high mới cao hơn?"}
    I -- "Có" --> J["Mở rộng đỉnh: extreme = nến mới"]
    I -- "Không" --> K{"Giá thụt lùi khỏi đỉnh<br/>≥ deviation% ?"}
    K -- "Có" --> L["Xác nhận pivot HIGH<br/>state = down, extreme = nến mới"]
    K -- "Không" --> M["Giữ nguyên (chưa đủ để đảo chiều)"]
    H -- "Không (down, đang tìm đáy)" --> N{"Có low mới thấp hơn?"}
    N -- "Có" --> O["Mở rộng đáy: extreme = nến mới"]
    N -- "Không" --> P{"Giá vọt lên khỏi đáy<br/>≥ deviation% ?"}
    P -- "Có" --> Q["Xác nhận pivot LOW<br/>state = up, extreme = nến mới"]
    P -- "Không" --> R["Giữ nguyên"]
```

### 3.3 BreakoutMonitor.on_new_bar() — trendline + breakout

```mermaid
flowchart TD
    S(["on_new_bar(time, high, low, close)"]) --> A["zigzag.update(time, high, low)<br/>thêm time & close vào danh sách"]
    A --> B["detect_structure(pivots)<br/>→ trend: up (HH+HL) / down (LH+LL) / none"]
    B --> C{"trend là up hoặc down?"}
    C -- "Không (none)" --> D["return: chưa đủ dữ liệu<br/>breakout = False"]
    C -- "Có" --> E["Lấy 2 điểm gần nhất:<br/>• trend up  → 2 ĐÁY gần nhất<br/>• trend down → 2 ĐỈNH gần nhất"]
    E --> F["Kẻ Trendline qua 2 điểm<br/>tính slope, value_at(index)"]
    F --> G{"Giá ĐÓNG CỬA phá qua<br/>trendline (từ điểm cuối trở đi)?"}
    G -- "Không phá" --> H["return: breakout = False<br/>(trendline vẫn giữ)"]
    G -- "Có phá" --> I{"Trendline này đã<br/>báo alert chưa?"}
    I -- "Chưa" --> J["new_alert = True<br/>message = 'BREAKOUT! Gia pha<br/>trendline ho tro / khang cu'"]
    I -- "Đã báo" --> K["Chỉ ghi breakout = True<br/>KHÔNG báo lại (báo đúng 1 lần)"]
    J --> K
```

### 3.5 chart_render.py — vẽ trendline ra biểu đồ

Mỗi lần main.py phân tích xong (khởi động + mỗi nến D1 mới đóng) nó ghi đè
`chart.html` — trang HTML **tự chứa** (SVG thuần, không cần CDN/server), nhúng sẵn
dữ liệu MT5 thật: nến đã đóng, các điểm pivot ZigZag (▲ đỉnh / ▼ đáy), trendline
(đường đứt nét: nâu = hỗ trợ khi mô hình TĂNG, tím = kháng cự khi mô hình GIẢM),
điểm breakout (⭐) và RSI. Mở file bằng trình duyệt (hoặc tab Preview) là thấy
trendline được vẽ; chạy lại `main.py` mỗi khi có nến mới đóng rồi làm mới trang
trình duyệt để cập nhật. Nếu chạy qua `python -m http.server`, trang tự đọc
`chart_state.json` mỗi 2 giây để cập nhật live.

```mermaid
flowchart LR
    A["main.py phân tích xong"] --> B["build_state()<br/>gom nến + pivot + trendline"]
    B --> C["write_chart_page()<br/>ghi chart.html (nhúng dữ liệu)"]
    B --> D["write_chart_state()<br/>ghi chart_state.json"]
    C --> E["Mở chart.html → thấy trendline"]
    D -. chạy qua http.server .-> F["chart.html tự cập nhật 2s"]
```

### 3.4 RSI.update() — RSI Wilder

```mermaid
flowchart TD
    S(["update(close)"]) --> A{"Đã có nến trước?<br/>_prev_close == None"}
    A -- "Có (nến đầu)" --> B["Lưu prev_close<br/>return None (chưa đủ dữ liệu)"]
    A -- "Không" --> C["diff = close − prev_close<br/>gain = max(diff, 0)<br/>loss = max(−diff, 0)"]
    C --> D{"Đã tích lũy đủ<br/>`period` phiên làm nóng?"}
    D -- "Chưa" --> E["Thêm gain/loss vào danh sách"]
    E --> F{"Đủ `period` ngay lần này?"}
    F -- "Chưa đủ" --> G["return None"]
    F -- "Đủ" --> H["avg_gain = trung bình period đầu<br/>avg_loss = trung bình period đầu"]
    D -- "Đủ rồi" --> I["Wilder smoothing:<br/>avg = (avg × (period−1) + giá trị mới) / period"]
    H --> Calc["RSI = 100 − 100 / (1 + avg_gain / avg_loss)<br/>nếu avg_loss = 0 → RSI = 100"]
    I --> Calc
```

---

## 4. Chuỗi gọi hàm theo thời gian (một lần kiểm tra)

```mermaid
sequenceDiagram
    participant Main as main.py
    participant Feed as DataFeed
    participant Mon as BreakoutMonitor
    participant ZZ as ZigZag
    participant TL as Trendline
    participant RSI as RSI

    loop Cứ 2 giây
        Main->>Feed: has_new_bar()
        Feed-->>Main: False (chưa có nến mới)
    end

    Note over Main: Nến D1 mới đóng
    Main->>Feed: has_new_bar() → True
    Main->>Feed: get_closed_rates().iloc[-1]
    Feed-->>Main: bar (time, high, low, close)
    Main->>Mon: on_new_bar(time, high, low, close)
    Mon->>ZZ: update(time, high, low)
    ZZ-->>Mon: pivots mới (nếu có đảo chiều)
    Mon->>Mon: detect_structure() → trend
    Mon->>TL: Trendline(p1, p2) nếu có mô hình
    TL-->>Mon: slope + value_at()
    Mon-->>Main: {trend, trendline, breakout, new_alert}
    Main->>RSI: update(close)
    RSI-->>Main: rsi.value
    Main->>Main: in summary + alert (nếu có)
```

---

## 5. Tóm tắt trạng thái hiện tại

| Hạng mục | Giá trị đang dùng (main.py) |
|---|---|
| Symbol | `XAUUSD` (vàng) |
| Khung thời gian | `D1` |
| Số nến lấy mỗi lần | `300` |
| Ngưỡng đảo chiều ZigZag | `6.0%` |
| RSI | `period = 14` |
| Chu kỳ kiểm tra | `2 giây` |
| Điều kiện báo | Giá đóng cửa phá trendline (hỗ trợ nếu mô hình tăng, kháng cự nếu giảm), mỗi trendline báo 1 lần |
| Chỉ tính trên | Nến đã đóng (`get_closed_rates`) |
| Hiển thị trendline | `chart.html` — biểu đồ nến tự chứa, ghi lại sau mỗi lần phân tích (mở trình duyệt là xem được) |
