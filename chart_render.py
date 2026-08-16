"""
chart_render.py
Xuất biểu đồ trendline ra file HTML tự chứa (self-contained) để nhìn thấy
trendline THẬT từ dữ liệu MT5 — không cần server, không cần CDN.

main.py gọi hàm này sau mỗi lần phân tích (khởi động + mỗi nến mới đóng):
    state = build_state(df, mon, rsi, result)
    write_chart_state("chart_state.json", state)   # dữ liệu dạng JSON (tùy chọn)
    write_chart_page("chart.html", state)          # trang HTML vẽ biểu đồ

Trang HTML chứa sẵn dữ liệu (nhúng trong thẻ <script>) nên mở trực tiếp bằng
trình duyệt là xem được ngay. Nếu sau này chạy qua http.server, trang cũng
thử đọc chart_state.json mỗi 2 giây để tự cập nhật live.
"""

import json
import math
from datetime import datetime

import pandas as pd
import rsi as rsi_mod


def build_state(df, mon, rsi, result: dict) -> dict:
    """Gom trạng thái hiện tại (nến + ZigZag + trendline + breakout + RSI).

    df      : DataFrame đã đóng (cột time/open/high/low/close) — các nến để vẽ
    mon     : BreakoutMonitor (có .zz.pivots và phương thức _first_break)
    rsi     : đối tượng RSI (có .value)
    result  : dict trả về từ mon.on_new_bar(...) — chứa trend, trendline, message
    """
    idx_of = {t: i for i, t in enumerate(df["time"])}

    bars = [
        {"t": str(t), "o": round(o, 2), "h": round(h, 2),
         "l": round(l, 2), "c": round(c, 2)}
        for t, o, h, l, c in zip(df["time"], df["open"], df["high"], df["low"], df["close"])
    ]

    pivots = []
    for p in mon.zz.pivots:
        i = idx_of.get(p["time"])
        if i is None:
            continue
        pivots.append({"i": i, "p": round(p["price"], 2), "type": p["type"]})

    line = result.get("trendline")
    line_json = None
    if line is not None:
        line_json = {
            "p1": [line.p1[0], round(line.p1[1], 2)],
            "p2": [line.p2[0], round(line.p2[1], 2)],
            "slope": round(line.slope, 6),
        }

    breakout = None
    if line is not None:
        idx, btime = mon._first_break(line)
        if idx is not None:
            breakout = {"idx": idx, "time": str(btime)}

    # Chuỗi RSI (Wilder) cho toàn bộ nến — để chart.html vẽ bảng RSI bên dưới
    period = getattr(rsi, "period", 14)
    rsi_series = [
        None if math.isnan(v) else round(float(v), 2)
        for v in rsi_mod.rsi(df["close"], period)
    ]

    return {
        "updated": datetime.now().isoformat(timespec="seconds"),
        "bars": bars,
        "pivots": pivots,
        "trend": result.get("trend", "none"),
        "trendline": line_json,
        "breakout": breakout,
        "real_breakout": result.get("real_breakout", False),
        "rsi_divergence": result.get("rsi_divergence"),
        "rsi": round(rsi.value, 2) if rsi.value is not None else None,
        "rsi_period": period,
        "rsi_series": rsi_series,
        "message": result.get("message"),
    }


def write_chart_state(path: str, state: dict):
    """Ghi trạng thái ra JSON (dùng khi chạy qua http.server để trang tự cập nhật)."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False)


def write_chart_page(path: str, state: dict):
    """Ghi trang HTML biểu đồ với dữ liệu nhúng sẵn — mở trình duyệt là xem được."""
    html = CHART_TEMPLATE.replace("__CHART_STATE__", json.dumps(state, ensure_ascii=False))
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)


# ---------------------------------------------------------------------------
# Mẫu trang HTML biểu đồ. Dấu hiệu __CHART_STATE__ được thay bằng JSON dữ liệu.
# ---------------------------------------------------------------------------
CHART_TEMPLATE = r"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Biểu đồ live — Trendline XAUUSD (D1)</title>
<style>
  :root { color-scheme: light dark; }
  body {
    font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
    max-width: 1080px;
    margin: 0 auto;
    padding: 20px 20px 60px;
    line-height: 1.5;
    background: #fafafa;
    color: #1f2328;
  }
  @media (prefers-color-scheme: dark) {
    body { background: #0d1117; color: #e6edf3; }
    .card { background: #161b22; border-color: #30363d; }
    header { border-color: #30363d; }
  }
  header {
    border-bottom: 2px solid #d0d7de;
    padding-bottom: 10px;
    margin-bottom: 16px;
  }
  header h1 { margin: 0 0 4px; font-size: 22px; }
  header p { margin: 0; color: #57606a; font-size: 14px; }
  @media (prefers-color-scheme: dark) { header p { color: #8b949e; } }
  .badge {
    display: inline-block;
    background: #ddf4ff; color: #0550ae;
    border-radius: 999px; padding: 2px 10px; font-size: 12px; font-weight: 600;
    margin-left: 8px; vertical-align: middle;
  }
  @media (prefers-color-scheme: dark) { .badge { background: #0c2d6b; color: #79c0ff; } }
  .card {
    background: #fff;
    border: 1px solid #d0d7de;
    border-radius: 10px;
    padding: 14px 16px;
  }
  #info {
    font-size: 14px;
    margin-bottom: 12px;
    padding: 10px 14px;
    border-radius: 8px;
    background: rgba(127,127,127,0.08);
  }
  #info b { font-weight: 650; }
  #status { font-size: 12px; color: #57606a; margin-top: 8px; }
  @media (prefers-color-scheme: dark) { #status { color: #8b949e; } }
  #status.err { color: #ef4444; }
  #chart { width: 100%; height: auto; display: block; }
  .hint { font-size: 13px; color: #57606a; margin-top: 10px; }
  @media (prefers-color-scheme: dark) { .hint { color: #8b949e; } }
  svg text { user-select: none; }
</style>
</head>
<body>

<header>
  <h1>📈 Biểu đồ live — Trendline XAUUSD (D1) <span class="badge">dữ liệu MT5 thật</span></h1>
  <p>Nến đã đóng + ZigZag + trendline (hỗ trợ / kháng cự) + điểm breakout</p>
</header>

<div class="card">
  <div id="info">Đang tải dữ liệu...</div>
  <svg id="chart" viewBox="0 0 920 670" role="img" aria-label="Biểu đồ nến XAUUSD với trendline"></svg>
  <p id="status"></p>
  <p class="hint">
    🔺 đỉnh (pivot high) · 🔻 đáy (pivot low) · đường đứt nét = trendline (nâu = hỗ trợ, tím = kháng cự)
    · ⭐ = điểm giá đóng cửa phá trendline (breakout) · nếu từ mốc đầu trendline đến lúc phá vỡ,
    2 đáy/2 đỉnh đi ngược với RSI (đường nối các đáy RSI dốc lên khi giá giảm dần) → báo <b>PHA VỠ THẬT</b>
  </p>
</div>

<script>
const EMBEDDED_STATE = __CHART_STATE__;

(function () {
  const svg = document.getElementById('chart');
  const infoEl = document.getElementById('info');
  const statusEl = document.getElementById('status');
  const W = 920, H = 500, ML = 58, MR = 22, MT = 18, MB = 32;
  const css = getComputedStyle(document.body);
  const theme = {
    text: css.color,
    up: '#22c55e', down: '#ef4444',
    lineUp: '#f59e0b', lineDown: '#a855f7'
  };

  function fmtPrice(p) {
    return p >= 1000 ? p.toFixed(1) : p.toFixed(2);
  }

  function draw(state) {
    const bars = state.bars || [];
    if (bars.length < 2) {
      svg.innerHTML = '';
      infoEl.innerHTML = 'Chưa đủ dữ liệu nến.';
      return;
    }
    const n = bars.length;
    const x = i => ML + (i / (n - 1)) * (W - ML - MR);

    const pivots = state.pivots || [];
    const line = state.trendline;
    const brk = state.breakout;

    let lo = Infinity, hi = -Infinity;
    for (const b of bars) { lo = Math.min(lo, b.l); hi = Math.max(hi, b.h); }
    if (line) {
      // Chi tinh khoang gia tren doan thuc cua trendline (p1->p2),
      // khong ngoai suy nguoc ve trai — tranh bop meo truc gia khi slope doc
      for (let i = line.p1[0]; i <= line.p2[0]; i++) {
        const v = line.p1[1] + line.slope * (i - line.p1[0]);
        lo = Math.min(lo, v); hi = Math.max(hi, v);
      }
    }
    const pad = (hi - lo) * 0.07 + 0.5;
    lo -= pad; hi += pad;
    const y = p => MT + (hi - p) / (hi - lo) * (H - MT - MB);

    let s = '';
    for (let g = 0; g <= 5; g++) {
      const py = MT + (g / 5) * (H - MT - MB);
      const pr = hi - (g / 5) * (hi - lo);
      s += '<line x1="' + ML + '" y1="' + py + '" x2="' + (W - MR) + '" y2="' + py +
           '" stroke="currentColor" stroke-opacity="0.10"/>';
      s += '<text x="' + (ML - 7) + '" y="' + (py + 4) + '" text-anchor="end" font-size="11" ' +
           'fill="currentColor" fill-opacity="0.55">' + fmtPrice(pr) + '</text>';
    }
    const step = Math.max(1, Math.ceil(n / 9));
    for (let i = 0; i < n; i += step) {
      const raw = bars[i].t || '';
      // Khung lớn (D1/W1/MN1): nến bắt đầu lúc 00:00:00 -> hiện ngày tháng; khung nhỏ: hiện giờ
      const t = raw.includes('00:00:00') ? raw.slice(0, 10) : (raw.slice(11, 16) || String(i));
      s += '<text x="' + x(i) + '" y="' + (H - 10) + '" text-anchor="middle" font-size="10" ' +
           'fill="currentColor" fill-opacity="0.5">' + t + '</text>';
    }

    const bw = Math.max(2, (W - ML - MR) / n * 0.66);
    for (const b of bars) {
      const cx = x(b.i !== undefined ? b.i : bars.indexOf(b));
      const up = b.c >= b.o;
      const col = up ? theme.up : theme.down;
      s += '<line x1="' + cx + '" y1="' + y(b.h) + '" x2="' + cx + '" y2="' + y(b.l) +
           '" stroke="' + col + '" stroke-width="1" opacity="0.85"/>';
      const top = y(Math.max(b.o, b.c)), bot = y(Math.min(b.o, b.c));
      s += '<rect x="' + (cx - bw / 2) + '" y="' + top + '" width="' + bw + '" height="' +
           Math.max(1.5, bot - top) + '" fill="' + col + '" rx="0.5"/>';
    }

    if (pivots.length >= 2) {
      const pts = pivots.map(p => x(p.i) + ',' + y(p.p)).join(' ');
      s += '<polyline points="' + pts + '" fill="none" stroke="#3b82f6" stroke-width="1.2" ' +
           'stroke-opacity="0.45" stroke-linejoin="round" stroke-dasharray="2 3"/>';
    }
    for (const p of pivots) {
      const px = x(p.i), py = y(p.p);
      if (p.type === 'high') {
        s += '<path d="M ' + (px - 5) + ' ' + (py - 4) + ' L ' + (px + 5) + ' ' + (py - 4) +
             ' L ' + px + ' ' + (py + 5) + ' Z" fill="' + theme.down + '"/>';
      } else {
        s += '<path d="M ' + (px - 5) + ' ' + (py + 4) + ' L ' + (px + 5) + ' ' + (py + 4) +
             ' L ' + px + ' ' + (py - 5) + ' Z" fill="' + theme.up + '"/>';
      }
    }

    if (line) {
      const color = state.trend === 'up' ? theme.lineUp : theme.lineDown;
      const x1 = x(line.p1[0]), y1 = y(line.p1[1]);
      const x2 = x(line.p2[0]), y2 = y(line.p2[1]);
      const xE = W - MR;
      const idxE = (xE - ML) / (W - ML - MR) * (n - 1);
      const vE = line.p1[1] + line.slope * (idxE - line.p1[0]);
      const yE = y(vE);
      s += '<line x1="' + x1 + '" y1="' + y1 + '" x2="' + xE + '" y2="' + yE + '" stroke="' + color +
           '" stroke-width="2.2" stroke-dasharray="7 5" opacity="0.95"/>';
      s += '<circle cx="' + x2 + '" cy="' + y2 + '" r="4" fill="' + color + '"/>';
      const label = state.trend === 'up' ? 'HỖ TRỢ' : 'KHÁNG CỰ';
      s += '<text x="' + (x1 - 6) + '" y="' + (y1 - 7) + '" text-anchor="end" font-size="11" ' +
           'font-weight="700" fill="' + color + '">' + label + '</text>';
    }

    if (brk && brk.idx < n) {
      const bx = x(brk.idx), by = y(bars[brk.idx].c);
      s += '<line x1="' + bx + '" y1="' + MT + '" x2="' + bx + '" y2="' + (H - MB) + '" ' +
           'stroke="' + theme.down + '" stroke-opacity="0.18" stroke-width="1"/>';
      s += '<circle cx="' + bx + '" cy="' + by + '" r="8" fill="none" stroke="' + theme.down +
           '" stroke-width="2"/>';
      s += '<path d="M ' + bx + ' ' + (by - 10) + ' l 2.6 5.2 l 5.8 0.7 l -4.2 4 l 1 5.8 l -5.2 -2.9 ' +
           'l -5.2 2.9 l 1 -5.8 l -4.2 -4 l 5.8 -0.7 Z" fill="' + theme.down + '"/>';
    }

    const lb = bars[n - 1];
    s += '<circle cx="' + x(n - 1) + '" cy="' + y(lb.c) + '" r="3.5" fill="#3b82f6" ' +
         'stroke="#fff" stroke-width="1.2"/>';

    // ---- Bang RSI (duoi bieu do nen) ----
    const rTop = 512, rBot = 652;
    const rY = v => rTop + (100 - v) / 100 * (rBot - rTop);
    s += '<line x1="' + ML + '" y1="492" x2="' + (W - MR) + '" y2="492" stroke="currentColor" stroke-opacity="0.15"/>';
    s += '<text x="' + ML + '" y="504" font-size="11" fill="currentColor" fill-opacity="0.7">RSI(' +
         (state.rsi_period || 14) + ')</text>';
    for (const [lv, lbl] of [[70, '70 - QUÁ MUA'], [30, '30 - QUÁ BÁN']]) {
      const ry = rY(lv);
      s += '<line x1="' + ML + '" y1="' + ry + '" x2="' + (W - MR) + '" y2="' + ry +
           '" stroke="currentColor" stroke-opacity="0.25" stroke-dasharray="4 4"/>';
      s += '<text x="' + (W - MR) + '" y="' + (ry + 4) + '" text-anchor="end" font-size="10" ' +
           'fill="currentColor" fill-opacity="0.55">' + lbl + '</text>';
    }
    const series = state.rsi_series || [];
    const rpts = [];
    for (let i = 0; i < series.length; i++) {
      if (series[i] == null) continue;
      rpts.push(x(i) + ',' + rY(series[i]));
    }
    if (rpts.length > 1) {
      s += '<polyline points="' + rpts.join(' ') + '" fill="none" stroke="#3b82f6" stroke-width="1.6"/>';
    }
    const lastR = series.length ? series[series.length - 1] : null;
    if (lastR != null) {
      const lx = x(series.length - 1), ly = rY(lastR);
      s += '<circle cx="' + lx + '" cy="' + ly + '" r="3.5" fill="#3b82f6"/>';
      s += '<text x="' + (lx - 8) + '" y="' + (ly - 8) + '" text-anchor="end" font-size="11" ' +
           'font-weight="700" fill="' + (lastR > 70 ? theme.down : lastR < 30 ? theme.up : '#3b82f6') +
           '">' + lastR.toFixed(1) + '</text>';
    }
    svg.innerHTML = s;

    const trendTxt = state.trend === 'up' ? 'TANG (HH + HL)' : state.trend === 'down' ? 'GIAM (LH + LL)' : 'chua ro';
    let info = 'Mô hình: <b>' + trendTxt + '</b>';
    if (line) {
      info += ' &nbsp;|&nbsp; Trendline: <b>' + fmtPrice(line.p1[1]) + ' → ' + fmtPrice(line.p2[1]) +
              '</b> (slope ' + (line.slope >= 0 ? '+' : '') + line.slope.toFixed(3) + '/nến)';
    } else if (state.trend === 'none') {
      info += ' &nbsp;|&nbsp; Trendline: chưa có mô hình rõ ràng (chờ HH+HL hoặc LH+LL)';
    } else {
      info += ' &nbsp;|&nbsp; Trendline: chưa đủ 2 điểm pivot';
    }
    const r = state.rsi;
    info += ' &nbsp;|&nbsp; RSI(14): <b>' + (r == null ? 'chưa đủ dữ liệu' : r.toFixed(1) +
            (r > 70 ? ' [QUÁ MUA]' : r < 30 ? ' [QUÁ BÁN]' : '')) + '</b>';
    if (brk) {
      const real = state.real_breakout;
      info += ' &nbsp;|&nbsp; Breakout: <b style="color:' + (real ? '#ef4444' : '#f59e0b') + '">ĐÃ PHÁ VỠ ' +
              (real ? 'THẬT (phân kỳ RSI)' : '(chưa xác nhận phân kỳ)') + ' @ ' + (brk.time || '') + '</b>';
    } else {
      info += ' &nbsp;|&nbsp; Breakout: chưa phá';
    }
    if (state.rsi_divergence) {
      const d = state.rsi_divergence;
      const kind = d.kind === 'bullish' ? 'DƯƠNG' : d.kind === 'bearish' ? 'ÂM' : 'không';
      const w = d.window || {};
      const dp = w.deepest || {};
      const le = w.last_extreme || {};
      const slope = (w.rsi_slope == null) ? '' : ' · nối cực trị RSI ' +
              Number(dp.rsi).toFixed(1) + ' (' + (dp.time || '').slice(0, 10) + ') → ' +
              Number(le.rsi).toFixed(1) + ' (' + (le.time || '').slice(0, 10) + '), dốc ' +
              (w.rsi_slope >= 0 ? '+' : '') + Number(w.rsi_slope).toFixed(3) + '/nến';
      info += '<br>Quan sát RSI ' + (w.from || '').slice(0, 10) + ' → ' +
              (w.to || '').slice(0, 10) + ': ' + kind + ' — 2 điểm ' +
              (d.p1.time || '').slice(0, 10) + ' giá ' + d.p1.price + ' (RSI ' +
              Number(d.p1.rsi).toFixed(1) + ') → ' + (d.p2.time || '').slice(0, 10) +
              ' giá ' + d.p2.price + ' (RSI ' + Number(d.p2.rsi).toFixed(1) + ')' + slope;
    }
    if (state.message) info += ' &nbsp;|&nbsp; ' + state.message;
    infoEl.innerHTML = info;
  }

  // Hiển thị dữ liệu nhúng ngay lập tức (mở file trực tiếp vẫn xem được)
  draw(EMBEDDED_STATE);
  statusEl.textContent = 'Dữ liệu lúc ' + EMBEDDED_STATE.updated + ' · ' +
                         EMBEDDED_STATE.bars.length + ' nến ngày';


  // Nếu chạy qua http.server: thử đọc chart_state.json để tự cập nhật live
  let lastUpdated = EMBEDDED_STATE.updated;
  async function poll() {
    try {
      const r = await fetch('chart_state.json?t=' + Date.now());
      if (!r.ok) throw new Error('HTTP ' + r.status);
      const state = await r.json();
      if (state.updated !== lastUpdated) {
        lastUpdated = state.updated;
        draw(state);
      }
      statusEl.className = '';
      statusEl.textContent = 'Cập nhật lúc ' + state.updated + ' · tự làm mới mỗi 2 giây · ' +
                             state.bars.length + ' nến ngày';
    } catch (e) {
      // Chế độ tĩnh (không có chart_state.json): dừng poll để tránh lỗi lặp lại
      const hasData = EMBEDDED_STATE && EMBEDDED_STATE.bars && EMBEDDED_STATE.bars.length > 0;
      if (hasData) {
        statusEl.className = '';
        statusEl.textContent = 'Chế độ tĩnh — dữ liệu lúc ' + lastUpdated +
                               '. Chạy main.py (mỗi nến mới đóng) rồi làm mới trang để cập nhật.';
      } else {
        statusEl.className = 'err';
        statusEl.textContent = 'Chưa có dữ liệu: chạy main.py để bot ghi chart.html.';
      }
      return; // không lên lịch poll tiếp
    }
    setTimeout(poll, 2000); // chế độ live (http.server): tiếp tục tự làm mới
  }
  poll();
})();
</script>

<footer style="margin-top:36px; font-size:13px; color:#57606a;">
  Dữ liệu: MT5 (nến đã đóng) · Tự động ghi bởi main.py qua chart_render.py · Vẽ bằng SVG thuần, không cần CDN
</footer>
</body>
</html>
"""
