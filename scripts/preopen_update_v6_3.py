#@title 開市前快速更新 v6.3（格子 2）｜開市前約 30 分鐘執行（香港冬令 22:00、夏令 21:00）
#@markdown 要先跑過格子 1（完整簡報）。這格只讀格子 1 存下的 latest_plan.json，再取期指、VIX、名單股和持倉的盤前價，大約一分鐘完成。
#@markdown **存檔位置**：要和格子 1 一樣。勾選就從 Google Drive 讀計劃檔，並把結果存回同一個資料夾。
SAVE_TO_DRIVE = True  #@param {type:"boolean"}
#@markdown **持倉有變**：留空就用格子 1 的持倉；填了就取代（格式同格子 1：`代號:股數:止蝕價:入場價:入場日`）
POSITIONS_OVERRIDE = ""  #@param {type:"string"}
# ======================================================================
# 美股盤前簡報 v6.3・格子 2：開市前快速更新
# 做的事：
#   1. 期指、VIX、QQQ 盤前缺口 → 開市情景（和格子 1 同一套規則）。
#   2. 持倉：盤前價有沒有跌穿止蝕、低開幾多；連同格子 1 標示的要處理事項。
#   3. 富途下單清單：逐張單按盤前價判斷「可以落單／開市後再決定／不落單／取消」，今日名額按次序重新分配。
#   4. B 級：盤前已越過或接近觸發價的，提醒設提示價。
#   5. 今晚時間表（香港時間），標示已過和還有幾多分鐘。
# 盤前報價來自 Yahoo 的 5 分鐘線，可能有延誤；落單前最後一眼以富途的報價為準。
# 研究輔助用途｜資料需查證｜不保證獲利
# ======================================================================
import os, sys, re, json, time, subprocess, warnings
import html as _html
import datetime as _dt

if os.environ.get("PMB_SKIP_INSTALL") != "1":
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-U", "yfinance"], check=False)

import numpy as np
import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")

ET, HKT = "America/New_York", "Asia/Hong_Kong"
DRIVE_DIR, LOCAL_DIR = "/content/drive/MyDrive/premarket_brief", "premarket_out"
FUT = {"NQ=F": "Nasdaq 100 期貨", "ES=F": "S&P 500 期貨", "RTY=F": "Russell 2000 期貨"}

# ---------- 以下函數直接取自格子 1（v6.3），確保兩格的規則和寫法一致 ----------
def _easter(y):
    a, b, c = y % 19, y // 100, y % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month, day = (h + l - 7 * m + 114) // 31, (h + l - 7 * m + 114) % 31 + 1
    return _dt.date(y, month, day)

def _nth_wd(y, m, wd, n):
    first = _dt.date(y, m, 1)
    return first + _dt.timedelta(days=(wd - first.weekday()) % 7 + 7 * (n - 1))

def _last_wd(y, m, wd):
    nxt = _dt.date(y + (m == 12), m % 12 + 1, 1) - _dt.timedelta(days=1)
    return nxt - _dt.timedelta(days=(nxt.weekday() - wd) % 7)

def _observed(d):
    return d - _dt.timedelta(days=1) if d.weekday() == 5 else d + _dt.timedelta(days=1) if d.weekday() == 6 else d

def nyse_holidays(y):
    hol = {}
    ny = _dt.date(y, 1, 1)
    if ny.weekday() != 5:                                  # 元旦在星期六時不補假
        hol[_observed(ny)] = "元旦"
    hol[_nth_wd(y, 1, 0, 3)] = "馬丁路德金日"
    hol[_nth_wd(y, 2, 0, 3)] = "總統日"
    hol[_easter(y) - _dt.timedelta(days=2)] = "耶穌受難日"
    hol[_last_wd(y, 5, 0)] = "陣亡將士紀念日"
    hol[_observed(_dt.date(y, 6, 19))] = "六月節"
    hol[_observed(_dt.date(y, 7, 4))] = "獨立日"
    hol[_nth_wd(y, 9, 0, 1)] = "勞動節"
    hol[_nth_wd(y, 11, 3, 4)] = "感恩節"
    hol[_observed(_dt.date(y, 12, 25))] = "聖誕節"
    return hol

def nyse_early_closes(y, hol):
    out = {}
    for d, name in [(_nth_wd(y, 11, 3, 4) + _dt.timedelta(days=1), "感恩節翌日"), (_dt.date(y, 12, 24), "聖誕前夕"),
                    (_dt.date(y, 7, 3), "獨立日前夕")]:
        if d.weekday() < 5 and d not in hol:
            out[d] = name
    return out

def is_session(d):
    return d.weekday() < 5 and d not in HOLIDAYS

def next_session(d):
    d = d + _dt.timedelta(days=1)
    while not is_session(d):
        d += _dt.timedelta(days=1)
    return d

def sessions_until(a, b):
    """由 a（不計）到 b（計）之間有幾個交易日；b 早於或等於 a 回傳 0。"""
    n, d = 0, a
    while d < b and n < 400:
        d += _dt.timedelta(days=1)
        n += is_session(d)
    return n

def now_et():
    return pd.Timestamp.now(tz=ET)

def isnan(v):
    try:
        return v is None or (isinstance(v, (float, np.floating)) and np.isnan(v))
    except Exception:
        return False

def fnum(v, nd=2, suffix="", plus=False):
    if isnan(v):
        return "—"
    return f"{v:+,.{nd}f}{suffix}" if plus else f"{v:,.{nd}f}{suffix}"

def esc(x):
    return _html.escape(str(x))

def parse_entry_date(x):
    """入場日：2026-11-03、2026/11/03 或 11-03（不寫年份就當今年；日子在將來就當去年）。"""
    x = str(x).strip().replace("/", "-")
    today = now_et().date()
    if re.fullmatch(r"\d{1,2}-\d{1,2}", x):
        m_, d_ = (int(v) for v in x.split("-"))
        d = _dt.date(today.year, m_, d_)
        return d if d <= today else _dt.date(today.year - 1, m_, d_)
    return pd.Timestamp(x).date()

def parse_positions(text):
    """代號:股數:止蝕價[:入場價[:入場日]]；v6.3 起入場價和入場日用來計盈虧、R 倍數和持有日數，可以不填。"""
    pos = {}
    for item in re.split(r"[,;，；\n]+", text or ""):
        parts = [p.strip() for p in re.split(r"[:：]", item.strip()) if p.strip()]
        if not parts:
            continue
        try:
            if not 3 <= len(parts) <= 5:
                raise ValueError
            p_ = {"shares": float(parts[1]), "stop": float(parts[2]), "entry": np.nan, "entry_d": None}
            if len(parts) >= 4:
                p_["entry"] = float(parts[3])
            if len(parts) == 5:
                p_["entry_d"] = parse_entry_date(parts[4])
            pos[parts[0].upper()] = p_
        except Exception:
            print(f"  ⚠ 持倉格式看不懂，已略過：{item.strip()}（格式：代號:股數:失效位:入場價:入場日）")
    return pos

def scen_of(g):
    """QQQ 開市缺口（以 ATR 計）對應的開市情景；格子 2 也用同一個函數。"""
    if g > 1:
        return "大幅高開：規則不追開市價；條件是回調到開市區間高位或 VWAP 企穩。"
    elif g < -1:
        return "大幅低開：規則按事件日處理，首 30 分鐘區間形成前不觸發。"
    elif g > 0.25:
        return "小幅高開：規則不追開市第一口價；條件是首 30 分鐘企在開市區間上半，而且沒有跌回上日收市之下。"
    elif g >= -0.25:
        return "大致平開：條件是首 30 分鐘企在開市區間上半和上日收市之上。"
    else:
        return "小幅低開：條件是守住上日低位，並重上開市區間高位。"

def t6_order_line(o):
    """一張單的文字，照富途下單畫面的欄位次序寫，方便照抄。代號用富途的寫法（BRK-B 寫成 BRK.B）。"""
    t = o["Ticker"].replace("-", ".")
    if o["Mode"] == "開市後":
        return (f"{t}｜開市後判定：首 30 分鐘企在 pivot {o['Pivot']:,.2f} 之上，限價買入，價格不高於 {o['Limit']:,.2f}，"
                f"數量 {o['Shares']:,}；成交後設賣出止損單，止損價 {o['Stop']:,.2f}")
    side = "買入" if o["Side"] == "買入" else "賣出（沽空）"
    tail = "" if o["Side"] == "買入" else "｜沽空要融資戶口，並確認有貨可借"
    return (f"{t}｜{side}｜止損限價單｜觸發價 {o['Trigger']:,.2f}｜價格 {o['Limit']:,.2f}｜數量 {o['Shares']:,}｜期限 當日有效｜"
            f"只在常規時段觸發（不選盤前盤後）｜附加訂單：止損單，止損價 {o['Stop']:,.2f}，子單期限 撤單前有效{tail}")

CSS = """
<style>
.pmb{font-family:-apple-system,"Segoe UI","Noto Sans TC","PingFang TC","Microsoft JhengHei",sans-serif;background:#fff;color:#1a1a1a;
padding:18px 20px;max-width:1180px;border-radius:10px;line-height:1.5;font-size:13.5px}
.pmb h1{font-size:19px;margin:0}.pmb .sub{color:#666;font-size:12px;margin:2px 0 10px}
.pmb .hero{border:1px solid #e3e3e3;border-left-width:8px;border-radius:10px;padding:14px 16px;margin:8px 0}
.pmb .big{font-size:22px;font-weight:700}.pmb .mid{font-size:14px;margin:4px 0 8px}
.pmb .pill{display:inline-block;padding:2px 10px;border-radius:999px;font-size:12px;font-weight:600;margin:2px 6px 2px 0}
.pmb .on{background:#e3f4e8;color:#0a7d33}.pmb .off{background:#efefef;color:#777}
.pmb .wrn{background:#fdf0d5;color:#9a6700}.pmb .bad{background:#fde3e1;color:#b42318}
.pmb .kv{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:8px;margin:10px 0}
.pmb .kv div{background:rgba(255,255,255,.7);border:1px solid #e6e6e6;border-radius:8px;padding:6px 10px}
.pmb .kv small{display:block;color:#666;font-size:11.5px}.pmb .kv b{font-size:14px}
.pmb ul{margin:6px 0 4px 18px;padding:0}.pmb li{margin:3px 0}
.pmb table{border-collapse:collapse;width:100%;font-size:12.5px;margin:6px 0}
.pmb th{text-align:left;border-bottom:2px solid #ddd;padding:5px 8px;color:#555;font-weight:600;white-space:nowrap}
.pmb td{border-bottom:1px solid #eee;padding:4px 8px;white-space:nowrap}
.pmb td.num,.pmb th.num{text-align:right;font-variant-numeric:tabular-nums}
.pmb .g{color:#0a7d33}.pmb .r{color:#c0392b}.pmb .a{color:#b7791f}.pmb .m{color:#999}
.pmb .tw{overflow-x:auto}
.pmb details{border:1px solid #e3e3e3;border-radius:10px;margin:8px 0;padding:0 14px;background:#fff}
.pmb summary{cursor:pointer;font-weight:700;font-size:14.5px;padding:10px 0}
.pmb .cnt{font-weight:400;color:#666;font-size:12.5px;margin-left:6px}
.pmb .sec{padding-bottom:10px}.pmb h3{font-size:13.5px;margin:14px 0 2px}
.pmb .note{color:#666;font-size:12px;margin:2px 0 6px}
.pmb .bar{height:9px;border-radius:5px;background:#eee;overflow:hidden;min-width:120px}.pmb .bar>i{display:block;height:100%}
.pmb .two{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:14px}
.pmb .opp{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:8px;margin:8px 0}
.pmb .opp div{border:1px solid #e6e6e6;border-radius:8px;padding:7px 10px}
.pmb .opp b{font-size:13px}.pmb .opp span{float:right;font-weight:700}.pmb .opp small{display:block;color:#555;font-size:12px}
.pmb .warnbox{background:#fff8e1;border:1px solid #f0d58a;border-radius:8px;padding:6px 10px;margin:6px 0;font-size:12.5px}
.pmb pre{white-space:pre-wrap;font-size:12px;background:#f7f7f7;padding:10px;border-radius:8px}
.pmb .dq{margin:6px 0 8px;font-size:12.5px}
.pmb .dq.ok{display:inline-block;padding:2px 10px;border:1px solid #9bc5a6;border-radius:999px;color:#1d5a2c;background:#eef7ef}
.pmb details.dq{border:0;padding:0;background:none;box-shadow:none}
.pmb details.dq summary{display:inline-block;padding:2px 10px;border:1px solid #e0c27a;border-radius:999px;background:#fdf6e3;color:#7a5a12;cursor:pointer}
.pmb details.dq ul{margin:6px 0 0;padding-left:20px;color:#444}
.pmb .disc{margin:20px 0 4px;padding:12px 0 0;border-top:1px solid #e3e3e3;color:#666;font-size:12px;line-height:1.6}
</style>
"""

T6_CSS = """
<style>
.pmb .q{font-size:16px;font-weight:700;margin:18px 0 6px;padding-top:12px;border-top:2px solid #e3e3e3}
.pmb .q small{font-weight:400;color:#666;font-size:12.5px;margin-left:8px}
.pmb .ans{font-size:14.5px;margin:2px 0 8px}
.pmb td.ck,.pmb th.ck{text-align:center;padding:4px 4px}.pmb th.ck{font-size:11.5px}
.pmb td.wrap{white-space:normal;min-width:190px;max-width:340px}
.pmb .cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(430px,100%),1fr));gap:12px;margin:8px 0}
.pmb .card{border:1px solid #d9d9d9;border-radius:10px;padding:10px 12px;background:#fff;min-width:0}
.pmb .card h4{margin:0 0 2px;font-size:16px}.pmb .card h4 small{font-weight:400;color:#666;font-size:12px;margin-left:6px}
.pmb .card .why{font-size:12.5px;margin:6px 0}
.pmb .card table{font-size:12.5px;margin:4px 0}.pmb .card td{white-space:normal;vertical-align:top;padding:3px 6px}
.pmb .card td:first-child{white-space:nowrap;color:#555;width:1%}
.pmb .card ul,.pmb .card ol{margin:2px 0 2px 18px;padding:0}.pmb .card li{margin:2px 0}
.pmb .chip{display:inline-block;padding:1px 7px;border-radius:999px;font-size:11.5px;margin:2px 4px 2px 0;background:#f1f1f1;color:#444}
.pmb .chip.ok{background:#e3f4e8;color:#0a7d33}.pmb .chip.no{background:#fde3e1;color:#b42318}.pmb .chip.na{background:#f1f1f1;color:#999}
.pmb .chip.t{background:#1a1a1a;color:#fff;font-weight:600}
.pmb .thumbs{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(235px,100%),1fr));gap:8px;margin:8px 0}
.pmb .thumb{border:1px solid #e6e6e6;border-radius:8px;padding:6px 8px;min-width:0}
.pmb .thumb b{font-size:13px}.pmb .thumb small{display:block;color:#555;font-size:11.5px;white-space:normal}
.pmb .more{color:#666;font-size:12.5px;margin:18px 0 4px;padding-top:10px;border-top:2px solid #e3e3e3}
.pmb table.cmp td,.pmb table.cmp th{padding:4px 5px}
.pmb table.cmp .s{color:#888;font-size:11px;white-space:normal}
.pmb table.cmp td.w{white-space:normal}
</style>
"""

HOLIDAYS, EARLY_CLOSES = {}, {}
for _y in range(now_et().year - 1, now_et().year + 2):
    HOLIDAYS.update(nyse_holidays(_y))
for _y in range(now_et().year - 1, now_et().year + 2):
    EARLY_CLOSES.update(nyse_early_closes(_y, HOLIDAYS))

def at_et(d, h, m):
    return pd.Timestamp(_dt.datetime(d.year, d.month, d.day, h, m)).tz_localize(ET)

def close_of(d):
    return at_et(d, 13, 0) if d in EARLY_CLOSES else at_et(d, 16, 0)

def fetch_bars(symbols):
    """5 分鐘線（包括盤前盤後）的收市價和成交量，索引為美東時間。取不到就回傳兩個空表。"""
    symbols = list(dict.fromkeys(s for s in symbols if s))
    try:
        raw = yf.download(symbols, period="5d", interval="5m", prepost=True, auto_adjust=False,
                          group_by="column", threads=True, progress=False)
    except Exception as e:
        print(f"  5 分鐘線取不到（{type(e).__name__}）")
        return pd.DataFrame(), pd.DataFrame()
    if raw is None or not len(raw):
        return pd.DataFrame(), pd.DataFrame()
    if not isinstance(raw.columns, pd.MultiIndex):
        raw.columns = pd.MultiIndex.from_product([list(raw.columns), symbols[:1]])
    idx = pd.to_datetime(raw.index)
    idx = (idx.tz_localize("UTC") if idx.tz is None else idx).tz_convert(ET)
    c, v = raw["Close"].copy(), raw["Volume"].copy()
    c.index = v.index = idx
    return c.sort_index(), v.sort_index()

def last_after(C, sym, cut):
    """收市之後（盤後或盤前）最新的一個報價：（價, 時間）；沒有就回傳 None。"""
    if sym not in C.columns:
        return None
    x = C[sym].dropna()
    x = x[x.index > cut + pd.Timedelta(minutes=5)]
    return (float(x.iloc[-1]), x.index[-1]) if len(x) else None

def last_before(C, sym, cut):
    if sym not in C.columns:
        return np.nan
    x = C[sym].dropna()
    x = x[x.index <= cut]
    return float(x.iloc[-1]) if len(x) else np.nan

def pm_volume(Vb, sym, day, now):
    """目標交易日由美東 4:00 到現在（最遲 9:30）的成交股數。"""
    if sym not in Vb.columns:
        return np.nan
    x = Vb[sym].dropna()
    a, b = at_et(day, 4, 0), min(now, at_et(day, 9, 30))
    x = x[(x.index >= a) & (x.index < b)]
    return float(x.sum()) if len(x) else np.nan

DISCLOSURE = ("研究聲明：本報告是自動產生的市況、市場寬度與技術篩選工具，全部內容由固定規則計算，所有讀者看到的內容相同，並不考慮任何人的財務狀況、投資目標或風險承受能力。"
              "頁內的倉位試算只按讀者自行輸入的參數計算。內容只供研究和教育用途，不構成投資建議、要約或招攬，亦不保證準確、完整或及時。"
              "過往表現（包括跟進紀錄）不代表將來表現。")

def size_attrs(o):
    """倉位試算用的屬性（與完整簡報相同）：入場價由計劃卡的股數和風險反推，風險倍數按計劃檔的戶口和風險 %。"""
    try:
        sh, risk = int(o.get("PlanShares") or 0), float(o.get("PlanRisk") or 0)
        eq, base = float(PLAN_META["equity"]), float(PLAN_META["base"])
        if sh <= 0 or risk <= 0 or eq <= 0 or base <= 0:
            return ""
        lg = o["Side"] == "買入"
        rps = risk / sh
        entry = o["Stop"] + rps if lg else o["Stop"] - rps
        mult = risk / (eq * base / 100)
        return (f' data-ticker="{esc(o["Ticker"])}" data-direction="{"long" if lg else "short"}" data-entry="{entry:.4f}" data-stop="{o["Stop"]:.4f}"'
                f' data-limit="{o["Limit"]:.4f}" data-risk-mult="{mult:.6f}" data-atr="{float(o.get("ATR") or 0):.4f}"')
    except (TypeError, ValueError, KeyError):
        return ""

PLAN_META = {"equity": 0, "base": 0}

def order_status(o, px, gate_ok, P):
    """一張單按盤前價的判斷：（代碼, 文字）。代碼：ok 可以落單、open 開市後再決定、wait 暫緩、no 不落單、dead 取消、off 閘門未開。"""
    lg = o["Side"] == "買入"
    sg = 1 if lg else -1
    trig, lim, stop, atr = o["Trigger"], o["Limit"], o["Stop"], o["ATR"]
    up, dn = ("高", "低") if lg else ("低", "高")
    if not gate_ok:
        return "off", "閘門未開：只列作觀察"
    if not o.get("Shares"):
        return "no", "按示範風險計出來的數量是 0（失效位太遠或風險額太細）：不適用"
    if px is None and o["Mode"] == "開市後":
        return "open", f"取不到盤前報價：規則要求開市後首 30 分鐘企在 pivot {o['Pivot']:,.2f} 之{'上' if lg else '下'}，限價不超過 {o['Limit']:,.2f}"
    if px is None:
        return "ok", f"取不到盤前報價（盤前未有成交，或報價延誤）：參數按上日收市計；現價是否已越過觸發位 {trig:,.2f} 未能確認"
    if sg * (px - stop) <= 0:
        return "dead", f"盤前價 {px:,.2f} 已{dn}於形態失效位 {stop:,.2f}：形態作廢"
    gap = sg * (px - o["Close"]) / atr if atr > 0 else np.nan
    if o["Mode"] == "開市後":
        if sg * (px - o["Chase"]) > 0:
            return "no", f"盤前價 {px:,.2f} 已超過規則追價上限 {o['Chase']:,.2f}：不適用"
        if sg * (px - o["Pivot"]) < 0:
            return "wait", f"盤前價 {px:,.2f} 回到 pivot {o['Pivot']:,.2f} 之{'下' if lg else '上'}：突破未企穩，規則要求開市後收復 pivot"
        return "open", f"仍在買入區（盤前 {px:,.2f}）：規則要求開市後首 30 分鐘企在 pivot 之{'上' if lg else '下'}，以限價計"
    if sg * (px - lim) >= 0:
        return "no", f"盤前價 {px:,.2f} 已越過限價 {lim:,.2f}：規則不追，今日不適用"
    if sg * (px - trig) >= 0:
        return "open", (f"盤前價 {px:,.2f} 已越過觸發位 {trig:,.2f}：止損類委託要求觸發價{up}於現價，預設參數不再適用；"
                        "規則要求開市後首 30 分鐘企穩觸發位之" + ("上" if lg else "下") + "而且成交放大，以限價計（不超過限價）")
    if not np.isnan(gap) and gap <= -P["gapdown_atr"]:
        return "wait", f"盤前逆向跳空 {abs(gap):.1f} 個 ATR（{px:,.2f}）：規則暫緩，開市後回到上日收市附近才重新判定"
    d_atr = sg * (trig - px) / atr if atr > 0 else np.nan
    if not np.isnan(d_atr) and d_atr < P["near_open_atr"]:
        return "ok", f"參數有效；盤前價 {px:,.2f} 距觸發位只有 {d_atr:.1f} 個 ATR，開市可能即時觸發"
    return "ok", f"參數有效（盤前價 {px:,.2f}，距觸發位 {d_atr:.1f} 個 ATR）"

COLOR = {"ok": "g", "open": "a", "wait": "a", "no": "m", "dead": "r", "off": "m"}
LABEL = {"ok": "參數有效", "open": "開市後判定", "wait": "暫緩", "no": "不適用", "dead": "形態作廢", "off": "閘門未開"}

def main():
    t0 = time.time()
    hist_dir = LOCAL_DIR
    if SAVE_TO_DRIVE:
        try:
            from google.colab import drive as _gdrive
            _gdrive.mount("/content/drive")
            hist_dir = DRIVE_DIR
        except Exception as e:
            print(f"Google Drive 掛載失敗（{type(e).__name__}），改讀 {LOCAL_DIR}（只有同一個工作階段跑過格子 1 才有）")
    path = os.path.join(hist_dir, "latest_plan.json")
    if not os.path.exists(path):
        print(f"找不到 {path}。請先跑格子 1（完整簡報，v6.3 或以後），而且兩格的 SAVE_TO_DRIVE 設定要一樣。")
        return
    with open(path, encoding="utf-8") as f:
        plan = json.load(f)
    P = plan.get("params", {"limit_atr": 0.2, "near_open_atr": 0.3, "gapdown_atr": 1.0})

    now = now_et()
    today = now.date()
    target = today if (is_session(today) and now < close_of(today)) else next_session(today)
    open_ = at_et(target, 9, 30)
    mins = (open_ - now).total_seconds() / 60
    phase = ("盤前" if at_et(target, 4, 0) <= now < open_ else "盤中" if open_ <= now < close_of(target)
             else "未到盤前時段")
    stale = plan.get("brief_date") != f"{target:%Y-%m-%d}"
    asof = pd.Timestamp(plan["asof"]).date()
    cut = close_of(asof)

    orders, watch = plan.get("orders", []), plan.get("watch_b", [])
    pos = plan.get("positions", [])
    if POSITIONS_OVERRIDE.strip():
        old = {p_["Ticker"]: p_ for p_ in pos}
        pos = []
        for t, p_ in parse_positions(POSITIONS_OVERRIDE).items():
            base = dict(old.get(t, {"Ticker": t, "Close": None, "ATR$": None, "Act": "", "Note": ""}))
            base.update({"Ticker": t, "Shares": p_["shares"], "Stop": p_["stop"], "Entry": p_["entry"],
                         "EntryDate": str(p_["entry_d"] or "")})
            if t not in old:
                base["Note"] = "完整簡報沒有這隻持倉的資料，只檢查形態失效位"
            pos.append(base)

    syms = [o["Ticker"] for o in orders] + [w["Ticker"] for w in watch] + [p_["Ticker"] for p_ in pos] + ["QQQ", "SPY", "IWM", "^VIX"] + list(FUT)
    print(f"取 {len(set(syms))} 個代號的 5 分鐘線（包括盤前）…")
    C, Vb = fetch_bars(syms)

    # ---- 大市 ----
    mkt = []
    for s_, name in FUT.items():
        last, ref = (C[s_].dropna().iloc[-1] if s_ in C.columns and C[s_].notna().any() else np.nan), last_before(C, s_, cut)
        if not (np.isnan(last) or np.isnan(ref)):
            mkt.append((name, f"{(last / ref - 1) * 100:+.2f}%"))
    vix = last_after(C, "^VIX", cut)
    vix_ref = last_before(C, "^VIX", cut)
    if vix and vix[1] > cut + pd.Timedelta(minutes=45):
        mkt.append(("VIX", f"{vix[0]:.2f}" + ("" if np.isnan(vix_ref) else f"（{vix[0] - vix_ref:+.2f}）")))
    else:
        mkt.append(("VIX", "未有新報價" + ("" if np.isnan(vix_ref) else f"（上日 {vix_ref:.2f}）")))
    qq, qc, qa = last_after(C, "QQQ", cut), plan["qqq"]["close"], plan["qqq"]["atr"]
    gap_atr = (qq[0] - qc) / qa if (qq and qa) else np.nan
    if qq:
        mkt.append(("QQQ " + ("盤前" if phase == "盤前" else "最新"), f"{qq[0]:,.2f}（{(qq[0] / qc - 1) * 100:+.2f}%，{gap_atr:+.2f} 個 ATR；{qq[1]:%H:%M} ET）"))
    scen = scen_of(gap_atr) if not np.isnan(gap_atr) else "未有 QQQ 盤前報價，開市後按四種情景判斷。"
    banner = []
    if not len(C.columns):
        banner.append("盤前報價今次全部暫缺：以下判斷沒有用到盤前價。")
    if stale:
        banner.append(f"計劃檔是為 {plan.get('brief_date')} 準備的，不是 {target:%Y-%m-%d}：以下價位只作參考。")
    if phase == "未到盤前時段":
        banner.append("現在未到盤前時段（美東 4:00 起），報價是上日盤後的。")
    elif phase == "盤中":
        banner.append("已經開市：以下用的是開市後的報價（可能有延誤），預設單的判斷只供參考。")
    if not np.isnan(gap_atr) and gap_atr <= -1:
        banner.append("大市大幅低開：規則把新形態的判定延至開市 30 分鐘、區間形成之後。")
    elif not np.isnan(gap_atr) and gap_atr >= 1:
        banner.append("大市大幅高開：突破股多數會開在觸發位之上；規則不追開市第一口價。")
    big = []                                        # 開市後才公佈的 ★★★ 數據：之前觸發的單注碼減半
    for x in plan.get("timeline", []):
        try:
            et_ = pd.Timestamp(x["et"]).tz_convert(ET)
        except Exception:
            continue
        if "★★★" in x["what"] and open_ <= et_ < close_of(target):
            big.append(f"{x['what'].replace('★★★', '').strip()}（香港 {et_.tz_convert(HKT):%H:%M}）")
    if big:
        banner.append("今日是事件日：" + "、".join(big) + " 公佈之前觸發的參數，規則數量減半。")
    elif plan.get("event_day"):
        banner.append("今日是事件日，但重點數據在開市前已公佈：開市後按原有的規則數量。")

    # ---- 持倉 ----
    prow = []
    for p_ in pos:
        t = p_["Ticker"]
        lp = last_after(C, t, cut)
        close = p_.get("Close") or last_before(C, t, cut)
        px = lp[0] if lp else close
        stop, atr = p_.get("Stop"), p_.get("ATR$")
        live = []
        if px is not None and stop is not None and not np.isnan(px) and px <= stop:
            live.append(f"盤前 {px:,.2f} 已低於失效位 {stop:,.2f}：已觸及形態失效位（附加的止損市價單只在常規時段觸發）")
        if lp and close and atr and not np.isnan(close) and atr > 0:
            g = (lp[0] - close) / atr
            if g <= -P["gapdown_atr"]:
                live.append(f"盤前低開 {abs(g):.1f} 個 ATR")
            elif g >= 2:
                live.append(f"盤前高開 {g:.1f} 個 ATR")
        prow.append({"t": t, "px": px, "lp": lp, "close": close, "stop": stop, "live": live, "act": p_.get("Act") or "",
                     "note": p_.get("Note") or ""})

    # ---- 下單清單 ----
    res = []
    used = {"買入": 0, "沽空": 0}
    cap = {"買入": int(plan.get("n_long", 0) or 0), "沽空": int(plan.get("n_short", 0) or 0)}
    PLAN_META.update(equity=plan.get("account_equity") or 0, base=plan.get("base_risk_pct") or 0)
    for o in sorted(orders, key=lambda x: (x["Side"] != "買入", x["Rank"])):
        gate_ok = plan.get("long_ok") if o["Side"] == "買入" else plan.get("short_ok")
        lp = last_after(C, o["Ticker"], cut)
        code, txt = order_status(o, lp[0] if lp else None, bool(gate_ok) and not stale, P)
        if stale and gate_ok:
            code, txt = "off", "計劃檔不是今日的：參數只作參考"
        slot = ""
        if code in ("ok", "open"):
            if used[o["Side"]] < cap[o["Side"]]:
                used[o["Side"]] += 1
                slot = "上限內"
            else:
                slot = "後備"
        pv = pm_volume(Vb, o["Ticker"], target, now)
        vtxt = "" if (np.isnan(pv) or not o.get("Vol50")) else f"盤前成交 {pv:,.0f} 股（50 日平均的 {pv / o['Vol50'] * 100:.1f}%）"
        res.append({**o, "code": code, "txt": txt, "slot": slot, "lp": lp, "vtxt": vtxt})

    # ---- B 級提示 ----
    walert = []
    for w in watch:
        lp = last_after(C, w["Ticker"], cut)
        if not lp or not w.get("ATR"):
            continue
        sg = 1 if w["Side"] == "買入" else -1
        d = sg * (w["Trigger"] - lp[0]) / w["ATR"]
        if d <= 0:
            walert.append(f"{w['Ticker']}：盤前 {lp[0]:,.2f} 已越過觸發價 {w['Trigger']:,.2f}（B 級只作觀察）")
        elif d < 0.5:
            walert.append(f"{w['Ticker']}：盤前 {lp[0]:,.2f}，距觸發價 {w['Trigger']:,.2f} 只有 {d:.1f} 個 ATR")

    # ---- 時間表 ----
    tl = []
    o_h = open_.tz_convert(HKT).normalize()
    for x in plan.get("timeline", []):
        try:
            et = pd.Timestamp(x["et"]).tz_convert(ET)
        except Exception:
            continue
        h = et.tz_convert(HKT)
        m_ = (et - now).total_seconds() / 60
        st = "已過" if m_ < 0 else (f"{m_:.0f} 分鐘後" if m_ < 180 else "")
        tl.append((h, et, x["what"], x["kind"], st, h.normalize() > o_h))

    # ---- 輸出：文字 ----
    nowh = now.tz_convert(HKT)
    head = (f"系統開市前更新（盤前價格重算）｜簡報日 {target:%Y-%m-%d}｜美東 {now:%H:%M}・香港 {nowh:%H:%M}｜"
            + (f"距開市 {mins:.0f} 分鐘" if mins > 0 else "已開市"))
    T = [head, f"完整簡報：{plan.get('run_et')} ET 產生；Regime {plan.get('regime')}，分數 {plan.get('score')}，{plan.get('gates')}；{plan.get('verdict')}"]
    T += [f"⚠ {b}" for b in banner]
    T.append("大市：" + "；".join(f"{a} {b}" for a, b in mkt))
    T.append("開市情景：" + scen)
    if prow:
        T.append("【持倉】")
        for r in prow:
            todo = "；".join(r["live"] + ([r["act"]] if r["act"] else [])) or "沒有需要注意的事項"
            T.append(f"  {r['t']}：{'盤前 ' + format(r['lp'][0], ',.2f') if r['lp'] else '未有盤前價'}｜失效位 {fnum(r['stop'])}｜{todo}")
    if res:
        T.append("【倉位與委託參數試算（按盤前價重算）】")
        for r in res:
            T.append(f"  {r['Ticker']}｜{LABEL[r['code']]}{('・' + r['slot']) if r['slot'] else ''}｜{r['txt']}")
            if r["code"] == "ok" and r["slot"] == "上限內":
                T.append("    " + t6_order_line(r))
    else:
        T.append("【倉位與委託參數試算（按盤前價重算）】完整簡報今日沒有首選形態。")
    if walert:
        T.append("【B 級提示】" + "；".join(walert))
    if tl:
        T.append("【今晚時間表】香港時間（美東）")
        T += [f"  {h:%H:%M}{'（翌日）' if nx else ''}（{et:%H:%M}）{w}{'｜' + st if st else ''}" for h, et, w, k, st, nx in tl]
    T.append("盤前報價為延遲數據，可能有延誤。" + DISCLOSURE)
    TXT = "\n".join(T)
    print(TXT)

    # ---- 輸出：網頁 ----
    def tb(head_, rows_):
        return ('<div class="tw"><table class="cmp"><thead><tr>' + "".join(f"<th>{esc(h)}</th>" for h in head_) + "</tr></thead><tbody>"
                + "".join(rows_) + "</tbody></table></div>")
    SM = '<div class="s">{}</div>'
    TOP = ' style="border-bottom:0"'
    H = ['<div class="pmb">', f'<div class="hero" style="border-left-color:#1a5fb4"><div class="big">系統開市前更新（盤前價格重算）</div>'
         f'<div class="mid">簡報日 <b>{target:%m-%d}</b>｜美東 {now:%H:%M}・香港 {nowh:%H:%M}｜'
         + (f"距開市 <b>{mins:.0f}</b> 分鐘" if mins > 0 else "已開市") + "</div>"
         f'<div class="sub">完整簡報於 {esc(plan.get("run_et"))} ET 產生：Regime {esc(plan.get("regime"))}，分數 {esc(plan.get("score"))}，'
         f'{esc(plan.get("gates"))}；{esc(plan.get("verdict"))}</div>'
         + ((f'<details class="dq"><summary>數據狀態：{len(banner)} 項注意</summary><ul>' + "".join(f"<li>{esc(b)}</li>" for b in banner) + "</ul></details>")
            if banner else '<div class="dq ok">數據狀態：正常</div>')
         + '<div class="kv">' + "".join(f"<div><small>{esc(a)}</small><b>{esc(b)}</b></div>" for a, b in mkt) + "</div>"
         + f'<div class="ans"><b>開市情景：</b>{esc(scen)}</div></div>']
    if prow:
        rows_ = []
        for r in prow:
            todo = r["live"] + ([r["act"]] if r["act"] else [])
            px_txt = f"{r['lp'][0]:,.2f}" if r["lp"] else "—"
            chg = "" if not (r["lp"] and r["close"] and not np.isnan(r["close"])) else f'{(r["lp"][0] / r["close"] - 1) * 100:+.1f}%'
            rows_.append(f'<tr><td{TOP}><b>{esc(r["t"])}</b></td><td class="num"{TOP}>{px_txt}{SM.format(chg)}</td>'
                         f'<td class="num"{TOP}>{fnum(r["stop"])}</td></tr><tr><td colspan="3" class="w" style="padding-top:0">'
                         + (f'<b class="r">{esc("；".join(todo))}</b>' if todo else '<span class="g">沒有需要注意的事項</span>') + "</td></tr>")
        H.append('<div class="q">一、示範持倉</div>' + tb(["代號", "盤前價", "形態失效位"], rows_))
    H.append('<div class="q">二、倉位與委託參數試算（按盤前價重算）</div>')
    if res:
        rows_ = []
        for r in res:
            sub = "　".join(x for x in (r["slot"], f"{r['Side']}・{r['Type']}") if x)
            p1 = f'{r["Pivot"]:,.2f}' if r["Mode"] == "開市後" else f'{r["Trigger"]:,.2f}'
            p2 = f'pivot・上限 {r["Limit"]:,.2f}' if r["Mode"] == "開市後" else f'限價 {r["Limit"]:,.2f}'
            rows_.append(f'<tr{size_attrs(r)}><td{TOP}><b>{esc(r["Ticker"])}</b>{SM.format(esc(sub))}</td>'
                         f'<td{TOP}><b class="{COLOR[r["code"]]}">{esc(LABEL[r["code"]])}</b></td>'
                         f'<td class="num"{TOP}>{p1}{SM.format(esc(p2))}</td>'
                         f'<td class="num"{TOP}><span data-f="shares">{r["Shares"]:,}</span>{SM.format("失效位 " + format(r["Stop"], ",.2f"))}</td></tr>'
                         f'<tr><td colspan="4" class="w" style="padding-top:0">{esc(r["txt"])}'
                         + (SM.format(esc(r["vtxt"])) if r["vtxt"] else "") + "</td></tr>")
        H.append(tb(["代號", "判定", "觸發位", "試算數量"], rows_))
        go = [r for r in res if r["code"] == "ok" and r["slot"] == "上限內"]
        if go:
            H.append('<h3>模擬參數摘要（僅供參考，非交易指令）</h3><div style="font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12px">'
                     + "".join(f'<div style="margin:3px 0" data-order{size_attrs(r)} data-mode="{"open" if r["Mode"] == "開市後" else "stop"}" '
                               f'data-trigger="{r["Trigger"]:.2f}" data-pivot="{r["Pivot"]:.2f}" data-sym="{esc(r["Ticker"])}">{esc(t6_order_line(r))}</div>'
                               for r in go) + "</div>")
        H.append(f'<div class="note">規則示範上限：多頭 {cap["買入"]} 單位、空頭 {cap["沽空"]} 單位，按完整簡報的排序分配給「參數有效」和「開市後判定」的參數；'
                 "排前的不適用時由後備遞補。「開市後判定」的參數不作預設。數量按頁頂設定的戶口和風險 % 試算。</div>")
    else:
        H.append('<div class="note">完整簡報今日沒有首選形態。</div>')
    if walert:
        H.append('<h3>B 級提示</h3><ul>' + "".join(f"<li>{esc(x)}</li>" for x in walert) + "</ul>")
    if tl:
        rows_ = [f'<tr><td>{h:%H:%M}{"（翌日）" if nx else ""}</td><td class="m">{et:%H:%M}</td>'
                 f'<td class="w">{esc(w)}{SM.format(esc(st)) if st else ""}</td></tr>'
                 for h, et, w, k, st, nx in tl]
        H.append('<div class="q">三、今晚時間表（香港時間）</div>' + tb(["香港", "美東", "事項"], rows_))
    H.append(f'<div class="note">盤前報價為延遲數據（5 分鐘線），可能有延誤。</div><div class="disc">{esc(DISCLOSURE)}</div></div>')
    H.insert(1, f'<div id="sizer-meta" hidden data-equity0="{plan.get("account_equity") or 100000:g}" data-risk0="{plan.get("base_risk_pct") or 0.75:g}" '
                f'data-mult-long="{plan.get("mult_long") or 0:.4f}" data-mult-short="{plan.get("mult_short") or 0:.4f}" data-event="{int(bool(plan.get("event_day")))}"></div>')
    PAGE = CSS + T6_CSS + "".join(H)
    try:
        from IPython.display import display, HTML
        display(HTML(PAGE))
    except Exception:
        pass
    try:
        day_dir = os.path.join(hist_dir, f"{target:%Y-%m}")
        os.makedirs(day_dir, exist_ok=True)
        stem = f"{target:%Y-%m-%d}_pre{now:%m%d-%H%M}ET"
        with open(os.path.join(day_dir, stem + "_preopen.html"), "w", encoding="utf-8") as f:
            f.write('<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
                    f"<title>開市前快速更新 {target:%Y-%m-%d}</title></head><body style='margin:0;background:#f3f3f3;padding:12px'>{PAGE}</body></html>")
        with open(os.path.join(day_dir, stem + "_preopen.txt"), "w", encoding="utf-8") as f:
            f.write(TXT)
        print(f"\n已存到 {day_dir}/{stem}_preopen.html")
    except Exception as e:
        print(f"存檔失敗（{type(e).__name__}）")

main()
