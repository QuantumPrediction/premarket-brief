#@title 美股盤前簡報 v6.3（格子 1：完整簡報）｜整段貼到 Colab 一個格子，填好右邊表單，按 ▶ 執行
#@markdown **戶口與風險**
ACCOUNT_EQUITY = 100000  #@param {type:"number"}
BASE_RISK_PCT = 0.75  #@param {type:"number"}
#@markdown **風險上限（v6）**：所有持倉同時打到止蝕時，最多可以輸掉戶口的幾多 %。填 0 = 按 Regime 自動（A 6%、B 4%、C 2%、D 和 E 1%）
MAX_HEAT_PCT = 0  #@param {type:"number"}
#@markdown **現有持倉**（格式 `代號:股數:止蝕價:入場價:入場日`，入場價和入場日可以不填；逗號分隔，例：`AAPL:100:330:352.4:2026-11-03, LLY:20:1290`；沒有就留空）
POSITIONS_TEXT = ""  #@param {type:"string"}
#@markdown **股票池**（去掉 sp400 會快一些）
UNIVERSE = "sp500+ndx100+sp400"  #@param ["sp500+ndx100+sp400", "sp500+ndx100", "sp500+ndx100+sp400+sp600"]
#@markdown **額外股票**（想加入掃描的代號，逗號分隔；沒有就留空）
EXTRA_TICKERS_TEXT = ""  #@param {type:"string"}
#@markdown **選項**：存到 Google Drive（我的雲端硬碟 → premarket_brief → 年-月；要回看之前的簡報就要勾選）／取財報日與日曆／掃描盤前異動（只在美東 4:00–9:35 有數據）
SAVE_TO_DRIVE = True  #@param {type:"boolean"}
FETCH_EVENTS = True  #@param {type:"boolean"}
SCAN_PREMARKET = True  #@param {type:"boolean"}
#@markdown **High Tight Flag 全市場掃描**：除股票池外，再掃全美上市股票（多數 HTF 出現在中小型股；會多花幾分鐘）
HTF_WIDE_SCAN = True  #@param {type:"boolean"}
#@markdown **補充數據層（v5）**：加入 Nasdaq 財報日曆和經濟日曆（含聯儲局講話）、全市場盤前／盤後異動榜、VIX 期限結構、期權引伸波幅和沽空數據。Cboe 和 FINRA 的數據經 OpenBB 取得，Nasdaq 直接連線。任何一項失敗都自動退回 v4 的做法；不勾選就等於 v4。想加信貸息差，在 Colab Secrets 加入免費的 FRED_API_KEY（選用）
USE_OPENBB = True  #@param {type:"boolean"}
#@markdown **把消息面另外用純文字印在儀表板下面**（方便複製）
PRINT_NEWS_TEXT = True  #@param {type:"boolean"}
#@markdown **AI 消息面（選用，要收費）**：勾選後由 Claude 上網搜尋當日消息，寫成一段消息面放進簡報。需要 Anthropic API key：在 Colab 左邊的鑰匙圖示（Secrets）加一個名為 `ANTHROPIC_API_KEY` 的密鑰並允許這個筆記本讀取。
AI_NEWS = False  #@param {type:"boolean"}
AI_MODEL = "claude-sonnet-5-5"  #@param ["claude-sonnet-5-5", "claude-opus-5-5", "claude-haiku-5-5"]
#@markdown **顯示數據源診斷**：在簡報內顯示數據源狀態表和日曆來源（只供開發時用；平時只印在執行紀錄）
SHOW_DEBUG_PANEL = False  #@param {type:"boolean"}

# ======================================================================
# 美股盤前簡報引擎 v6.3（格子 1：完整簡報，可直接複製貼上）
# v6.3 改動：
#   富途下單清單：每隻 A 級一行，寫明單種（止損限價單）、觸發價、限價、數量、附加止損單；數量按限價（最差成交價）計，
#                 保持每注風險不變。已升穿 pivot 的不預設單，改為開市後用限價單。今日名額以外的列作後備。
#   持倉管理：持倉可加入場價和入場日（代號:股數:止蝕價:入場價:入場日），計算盈虧、R 倍數、持有日數，
#             並按 POS_RULES 標示要處理的事項（保本、財報前利潤墊、遠離 50 日線、時間止蝕、急升持有規則）。
#   今晚時間表：開市、收市、經濟數據、名單和持倉的財報，換算成香港時間。
#   計劃檔：每次執行存一份 latest_plan.json，給格子 2「開市前快速更新」讀取。
#   格子 2（另一個檔案 preopen_update_v6_3.py）：開市前約 30 分鐘執行，只取期指、VIX 和名單、持倉的盤前價，
#             逐張單判斷可以落單、開市後再決定還是取消，約一分鐘完成。
# v6.2 改動：
#   存檔：每日的簡報放在 Google Drive 的 premarket_brief/年-月/ 資料夾，檔名以簡報日開頭，再加執行時間（美東），
#         例如 2026-11-20_run1119-2347ET_dashboard.html；同一日跑幾次都不會互相覆蓋。各個名單的 CSV 放在 年-月/data/ 之下。
#         SAVE_TO_DRIVE 預設改為勾選。daily_log.csv 改為每次執行一行，並記下簡報日和執行編號。
#   首頁加「近 10 日回顧」：每日的分數、Regime、閘門、首選名單、新入選和跌出；沒有執行紀錄的日子用今日數據回算分數。
#   修正：開市情景分開大致平開、小幅高開、小幅低開；缺數據比例不足 1% 時顯示小數；引伸波幅用 Yahoo 後備時不再顯示矛盾的註釋；
#         沒有持倉時不再寫「連持倉計」。
# v6.1 改動（按 v6 在 2026-11-19 收市後的實測結果）：
#   數據完整性：最後一個交易日沒有收市價的股票，先重新下載，再用 5 分鐘線補；補不到的在頁頂講明，並從寬度的分母剔除。
#               （今次實測有約 190 隻股票沒有收市價，掃描在不知情下只用了八成股票池。）最新一日數據未到也會提示。
#   分級：波幅異常地小的股票（疑似收購後鎖價）不再入選；QQQ 在破位邊緣時不開新空倉；首頁加一句結論。
#   名單跟進與成績表：每次執行把全部候選存入 tier_history.csv（要勾選 SAVE_TO_DRIVE），下次列出新入選、跌出、已觸發、已止蝕，
#                     並用「全部候選」作對照。Google Drive 改為一開始就掛載。
#   自選名單體檢：表單「額外股票」內的代號用同一套清單檢查。
#   Cboe 取不到時（今次是 403），波動指數和期權引伸波幅改用 Yahoo 作後備；異動榜剔除與日線相差逾 60% 的報價（疑似拆股）。
#   其他：沒有板塊資料的股票用 nasdaq.com 補上；盤前參考價已越過的觸發位會標示；財報反應沒有價格時不再寫「待開市」。
# v6 改動：首頁改為只答三條問題 —— 今日可否交易、看哪幾隻、每隻怎樣做；其餘章節全部摺疊。
#   分級：六個做多名單合併去重，逐隻做八項清單（趨勢、RS、板塊、收縮、成交、資金、距離、事件）。
#         A 級要形態完成、距觸發價 3% 以內、5 個交易日內沒有財報、形態低位距入場價不超過 8%、同板塊最多 2 隻、閘門容許；
#         閘門未開時 A 級改稱「預備」。B 級寫明尚欠哪一項；其餘列出未入選原因。做空（回抽阻力）同樣分級，並用上沽空回補日數。
#   計劃卡：每隻首選一張，內嵌日線縮圖（均線、觸發價、止蝕、2R）、觸發價、追價上限、止蝕、股數、2R／3R 的算式、
#           開市三種情況、事件和放棄條件。B 級有縮圖總覽。
#   風險預算：按 Regime、未平倉風險和多倉上限，計出今日最多開幾注；分散檢查：板塊分佈和 60 日相關係數。
#   門檻全部是經驗值，未經回測，集中放在 PLAN 這個表。新功能任何一步出錯，首頁自動退回 v5.2 的版面。
#   掃描引擎、健康分數、閘門和補充數據層沒有改動。
# v5.2 改動（按 v5.1 的實測結果）：
#   財報反應：Nasdaq 剛公佈時沒有盈利驚喜，改用 Yahoo 的補上；Nasdaq 財報日曆改為四線同時取（原來要 39 秒）。
#   財報日：Yahoo 逐隻查詢照做，再用 Nasdaq 日曆核對；兩邊相差超過一日的取較早一日並加「？」。
#   經濟日曆：Nasdaq 的時間確認是美東；與 Yahoo 合併，補上聯儲局講話、FOMC 會議紀錄和市場預期。官員講話只有主席算三星。
#   異動榜：股票池成員按上日收市價計算延長時段的升跌，剔除 ETF 和沒有異動的大型股。
#   引伸波幅：加一行比較隔夜缺口與期權為今日定價的波幅。
#   FRED 的公開下載在 Colab 逾時，改為選用：在 Colab Secrets 加 FRED_API_KEY 才取信貸息差和 NFCI。
#   標題：公司名稱只是代號本身的（例如 TJX），標題要有代號才保留。
# v5.1 改動（按 2026-11-19 的實測結果）：
#   Nasdaq 的財報日曆、經濟日曆、異動榜改為直接連線（OpenBB 的請求在 Colab 被 Nasdaq 拒絕）；OpenBB 只保留 Cboe 和 FINRA。
#   芝加哥聯儲的 NFCI 來源停在 4 月，改由 FRED 的公開 CSV 取 NFCI 和高收益債息差，並加入過期檢查。
#   引伸波幅改用上日收市價附近的同一個行使價計算；VIX 期貨曲線剔除未開始交易的遠月；期限結構的判讀放寬。
#   修正 v4 的問題：U/D 量比在下跌日少於 20 日的強勢股上變成空白；盈利驚喜在 ±2% 以內改為「符合預期」；
#   High Tight Flag 加一條「單日升 40% 以上而之後橫行」的疑似收購規則；標題剔除與該股無關的文章。
# v5 改動：在 v4 之上加一層補充數據，只供參考，不計入健康分數和四個閘門；USE_OPENBB 不勾選時行為與 v4 相同。
#   價格下載和掃描引擎沒有改動，仍然用 yfinance。
# v4 改動：
#   修正：FTD 的第 1 日按 O'Neil 定義計算；派發日加入「指數升 5% 即失效」；下一個交易日和交易日數改用
#         紐約交易所假期表；財報日加入重試並標示取不到的股票；分數歷史內的龍頭比例改為按當日名單計算；
#         High Tight Flag 標示單日跳升（疑似收購）；墮落龍頭要 3 個月回報為負。
#   新增：消息面（昨日市場回顧、財報反應、今日事件時間表、名單財報風險、標題；可選 AI 撰寫）、
#         焦點名單與提示價、指數對照、預期波幅、派發日明細、板塊排名變化、各指數寬度、U/D 量比。
# ---- 以下是 v3 的說明 ----
# 分數與閘門的規則與 v1、v2、Playbook 相同。
# v3 改動：(1) 新增 High Tight Flag 掃描（股票池 + 全美上市股票）；
#          (2) RS 評級改為「各期回報先排名、再加權」並加入 1 個月回報，
#              舊的 12 個月加權 RS 保留為「12 個月 RS」作對照；
#          (3) 抗跌強勢、收窄名單收緊；龍頭股加 RS 分解表。
# ======================================================================
import os, sys, subprocess, time, io, re, base64, warnings
import html as _html

if os.environ.get("PMB_SKIP_INSTALL") != "1":
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-U",
                    "yfinance", "lxml", "html5lib", "beautifulsoup4"], check=False)
    if USE_OPENBB:                                           # 只裝用得著的三個套件，不裝整套 openbb
        print("安裝 OpenBB（只裝 Cboe 和 FINRA 兩個數據源；出現版本衝突的紅字提示可以不理）…")
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "openbb-core[pandas]", "openbb-cboe", "openbb-finra"], check=False)

import numpy as np
import pandas as pd
import requests
import yfinance as yf

warnings.filterwarnings("ignore")

# ---------- 補充數據層（v5.2）：Cboe、FINRA 經 OpenBB；Nasdaq 直接連線；FRED 要免費密鑰（選用）。任何一項失敗，簡報照 v4 的做法運作 ----------
OBB, OBB_LOG, OBB_ERR = None, [], []
if USE_OPENBB:
    try:
        from openbb import obb as OBB
        _miss = [n for n in ("cboe", "finra") if not hasattr(OBB, n)]
        if _miss:
            OBB_ERR.append("OpenBB 已載入，但找不到這些數據源：" + "、".join(_miss)
                           + "；相關項目會略過。重新啟動工作階段後再執行一次，通常可以解決。")
    except Exception as e:
        OBB = None
        OBB_ERR.append(f"OpenBB 載入失敗（{type(e).__name__}: {' '.join(str(e).split())[:160]}），Cboe 和 FINRA 的項目會略過，其餘照常。"
                       "如果是第一次安裝，請在 Colab 選「執行階段 → 重新啟動工作階段」，然後再執行一次。")
    warnings.filterwarnings("ignore")

def obb_ok(*names):
    """OpenBB 已載入，而且有齊所需的數據源。"""
    return OBB is not None and all(hasattr(OBB, n) for n in names)

def _obb_raw(fn, timeout=60, **kw):
    """執行一個 OpenBB 指令。回傳（DataFrame 或 None、狀態、備註、秒數）；任何錯誤都不會向外拋，逾時就放棄。"""
    import concurrent.futures as _cf
    t0 = time.time()
    def _run():
        res = fn(**kw)
        try:
            df = res.to_dataframe(index=None)
        except Exception:
            rows = getattr(res, "results", None) or []
            df = pd.DataFrame([r.model_dump() if hasattr(r, "model_dump") else r for r in rows])
        return df.reset_index(drop=True)
    ex = _cf.ThreadPoolExecutor(max_workers=1)
    try:
        df = ex.submit(_run).result(timeout=timeout)
        return df, ("成功" if len(df) else "空白"), "", time.time() - t0
    except _cf.TimeoutError:
        return None, "逾時", f"超過 {timeout} 秒沒有回應", time.time() - t0
    except Exception as e:
        if type(e).__name__ == "EmptyDataError" or "[Empty]" in str(e):
            return pd.DataFrame(), "空白", "", time.time() - t0
        return None, "失敗", f"{type(e).__name__}: {' '.join(str(e).split())[:150]}", time.time() - t0
    finally:
        ex.shutdown(wait=False)

def obb_call(feed, fn, timeout=60, **kw):
    """執行一個 OpenBB 指令並記入狀態表。成功或空白回傳 DataFrame，失敗回傳 None。"""
    df, st, note, sec = _obb_raw(fn, timeout, **kw)
    OBB_LOG.append({"Feed": feed, "Status": st, "Rows": 0 if df is None else len(df), "Sec": sec, "Note": note})
    return df

def _direct(feed, fn, log=True):
    """執行一個直接連線的取數函數（要回傳 DataFrame）。回傳（DataFrame 或 None、狀態、備註）；log=True 時記入狀態表。"""
    t0 = time.time()
    try:
        df = fn()
        st, note = ("成功" if len(df) else "空白"), ""
    except Exception as e:
        df, st, note = None, "失敗", f"{type(e).__name__}: {' '.join(str(e).split())[:150]}"
    if log:
        OBB_LOG.append({"Feed": feed, "Status": st, "Rows": 0 if df is None else len(df), "Sec": time.time() - t0, "Note": note})
    return df, st, note

def nq_get(path, timeout=20):
    """直接向 api.nasdaq.com 取數，做法與取 Nasdaq 100 名單和篩選器相同。回傳回應內的 data；被拒絕或格式不符就拋出例外。"""
    r = requests.get("https://api.nasdaq.com/api/" + path.lstrip("/"),
                     headers={**UA, "Accept": "application/json, text/plain, */*"}, timeout=timeout)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}")
    j = r.json()
    code = (j.get("status") or {}).get("rCode")
    if code not in (None, 200):
        raise RuntimeError(f"Nasdaq 回應代碼 {code}")
    return j.get("data")

def fred_key():
    """FRED 的免費密鑰：放在 Colab Secrets，名稱 FRED_API_KEY。沒有就回傳 None，相關項目會略過。"""
    try:
        from google.colab import userdata
        k = userdata.get("FRED_API_KEY")
    except Exception:
        k = None
    return k or os.environ.get("FRED_API_KEY") or None

def fred_api(sid, key, n=80):
    """由 FRED 官方 API 取一條數列最近 n 筆。回傳 date、v 兩欄。錯誤訊息不帶網址，免得把密鑰寫進簡報。"""
    try:
        r = requests.get("https://api.stlouisfed.org/fred/series/observations", timeout=12,
                         params={"series_id": sid, "api_key": key, "file_type": "json", "sort_order": "desc", "limit": n})
    except requests.RequestException as e:
        raise RuntimeError(type(e).__name__) from None
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}")
    d = pd.DataFrame(r.json().get("observations") or [])
    if not len(d) or "value" not in d.columns:
        return pd.DataFrame(columns=["date", "v"])
    d["date"], d["v"] = pd.to_datetime(d["date"], errors="coerce"), pd.to_numeric(d["value"], errors="coerce")
    return d.dropna(subset=["date", "v"]).sort_values("date").reset_index(drop=True)[["date", "v"]]

def _num(s):
    """把「$1,234.5」「+3.5%」「N/A」這類字串欄轉成數字。"""
    return pd.to_numeric(s.astype(str).str.replace(r"[^0-9.\-]", "", regex=True), errors="coerce")

def _need(df, cols):
    """補回要用的欄位，免得之後取欄位時出錯。"""
    return df.reindex(columns=list(dict.fromkeys(list(df.columns) + list(cols))))

# ---------- 進階設定 ----------
MAX_STOP_PCT   = 8.0          # 止蝕距離上限 %
LEADERS        = "auto"       # "auto" = 成交金額最高的 N_LEADERS 隻；或手動名單 ["NVDA","MSFT",...]
N_LEADERS      = 20
HISTORY_PERIOD = "5y"
MIN_PRICE      = 10.0
MIN_DOLLAR_VOL = 20e6
FETCH_ATH      = True
MAX_ATH_CHECK  = 150
DRIVE_DIR      = "/content/drive/MyDrive/premarket_brief"
LOCAL_DIR      = "premarket_out"
DUP_CLASS      = {"GOOG", "FOX", "NWS"}          # 同一公司的第二類股份，不在名單重複出現

TH = dict(
    weights       = {"trend": 30, "breadth": 25, "risk": 20, "vol": 15, "rates": 10},
    regime_bands  = [70, 55, 40, 25],
    risk_mult     = {"A": 1.00, "B": 0.75, "pilot": 0.25, "short": 0.50},
    long_cap      = {"A": "80–100%", "B": "50–75%", "C": "0–30%", "D": "0–10%", "E": "0–10%"},
    short_cap     = {"A": "不做", "B": "不做", "C": "不做", "D": "上限 30%", "E": "上限 50%"},
    dist_days_ok  = 3, dist_days_warn = 5, near_high_pct = 5.0,
    breadth_bands = [(65, 3), (50, 2), (35, 1)],
    vix_bands     = [(16, 3), (20, 2), (25, 1)],
    term_bands    = [(0.90, 2), (1.00, 1)],
    tnx_bands_bp  = [(10, 2), (25, 1)],
    dxy_max_20d   = 2.0,
    leaders_bands = [(60, 2), (40, 1)],
    ftd_min_corr  = 8.0, ftd_gain = 1.25, ftd_lookback = 60,
    oversold_pct50 = 15.0, oversold_vix = 35.0,
    vol_confirm   = 1.4,
    bo_follow_ok  = 60.0, bo_follow_bad = 40.0,
    tt_rs_min     = 70, tt_above_low = 30.0, tt_within_high = 25.0,
    vcp_lookback  = 130, vcp_first_max = 35.0, vcp_last_max = 12.0,
    vcp_vol_dry   = 0.80, vcp_near_pivot = 5.0, vcp_min_base = 15,
    extended_pct  = 5.0, earnings_warn_days = 7,
    # v2 掃描
    tight_pctile  = 0.25, tight_vol = 0.85, tight_from_high = 15.0, tight_r10_max = 10.0, tight_dist_min = -6.0,
    resilient_rs  = 80, resilient_from_high = 8.0, resilient_max_ext = 20.0,
    # RS 評級：各期回報的百分位，按以下權重加權（日數: 權重）
    rs_legs       = {21: 0.20, 63: 0.30, 126: 0.20, 189: 0.15, 252: 0.15},
    # High Tight Flag
    htf_pole_gain = 90.0, htf_pole_max = 40, htf_top_window = 30, htf_flag_min = 3, htf_flag_max = 25,
    htf_flag_depth = 25.0, htf_wide_min_price = 5.0, htf_wide_min_mcap = 300e6, htf_wide_min_dv = 10e6, htf_wide_max = 2000,
    pullback_rs   = 80,
    gap_pct       = 4.0, gap_vol = 2.0,
    short_rs_max  = 30, short_ext_pct50 = 15.0, short_ext_atr = 3.0,
    fallen_rs     = 80, fallen_from_high = 25.0,
    premarket_gap = 3.0, premarket_top_n = 400,
)

# ---------- v6.1：存檔位置。要讀回之前幾日的名單，所以一開始就決定；勾選 SAVE_TO_DRIVE 時在這裡掛載 Google Drive ----------
HIST_DIR = LOCAL_DIR
if SAVE_TO_DRIVE:
    try:
        from google.colab import drive as _gdrive
        _gdrive.mount("/content/drive")
        HIST_DIR = DRIVE_DIR
    except Exception as e:
        print(f"Google Drive 掛載失敗（{type(e).__name__}），改存到 {LOCAL_DIR}")
try:
    os.makedirs(HIST_DIR, exist_ok=True)
except Exception:
    HIST_DIR = LOCAL_DIR
    os.makedirs(HIST_DIR, exist_ok=True)

# ---------- 工具 ----------
ET = "America/New_York"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}

def now_et():
    return pd.Timestamp.now(tz=ET)

# ---- 紐約交易所假期表（休市日、提早收市日、期權結算日）----
import datetime as _dt

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

HOLIDAYS, EARLY_CLOSES = {}, {}
for _y in range(now_et().year - 1, now_et().year + 2):
    HOLIDAYS.update(nyse_holidays(_y))
for _y in range(now_et().year - 1, now_et().year + 2):
    EARLY_CLOSES.update(nyse_early_closes(_y, HOLIDAYS))

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

def opex_date(y, m):
    d = _nth_wd(y, m, 4, 3)                                # 每月第三個星期五
    return d if is_session(d) else d - _dt.timedelta(days=1)

def _norm_daily_index(df):
    idx = pd.to_datetime(df.index)
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_localize(None)
    df = df.copy()
    df.index = idx.normalize()
    return df[~df.index.duplicated(keep="last")].sort_index()

def drop_partial(df):
    t = now_et()
    today = t.tz_localize(None).normalize()
    cut = (13, 15) if t.date() in EARLY_CLOSES else (16, 15)     # 提早收市日 13:00 收市
    if len(df) and df.index[-1] >= today and (t.hour, t.minute) < cut:
        return df.loc[df.index < today]
    return df

def dl(tickers, period=None, chunk=120, pause=1.0, label=""):
    """分批下載日線，回傳 {欄位: DataFrame(日期 x 代號)}；Close 為除權後、未經股息調整的價格。"""
    tickers = list(dict.fromkeys([t for t in tickers if isinstance(t, str) and t]))
    frames = []
    for i in range(0, len(tickers), chunk):
        part = tickers[i:i + chunk]
        df = None
        for attempt in range(3):
            try:
                df = yf.download(part, period=period, interval="1d", auto_adjust=False,
                                 group_by="column", threads=True, progress=False)
            except Exception as e:
                print(f"  下載出錯（第 {attempt + 1} 次）：{type(e).__name__}: {str(e)[:120]}")
                df = None
            if df is not None and len(df):
                break
            time.sleep(4 * (attempt + 1))
        if df is None or not len(df):
            print(f"  ⚠ 這一批下載失敗，略過 {len(part)} 隻：{part[:5]}…")
            continue
        if not isinstance(df.columns, pd.MultiIndex):
            df.columns = pd.MultiIndex.from_product([list(df.columns), part[:1]])
        frames.append(_norm_daily_index(df))
        if label:
            print(f"  {label}: {min(i + chunk, len(tickers))}/{len(tickers)}")
        time.sleep(pause)
    if not frames:
        return {}
    big = pd.concat(frames, axis=1)
    big = big.loc[:, ~big.columns.duplicated()]
    return {str(f): drop_partial(big[f]).dropna(axis=1, how="all") for f in big.columns.get_level_values(0).unique()}

def intraday_close(symbols, interval="5m", chunk=100):
    """盤前盤後也包括在內的分鐘線收市價，索引為美東時間；取不到回傳空表。"""
    symbols = list(dict.fromkeys(str(x).upper() for x in symbols if x))
    out = []
    for i in range(0, len(symbols), chunk):
        part = symbols[i:i + chunk]
        try:
            raw = yf.download(part, period="5d", interval=interval, prepost=True, auto_adjust=False,
                              group_by="column", threads=True, progress=False)
            if raw is None or not len(raw):
                continue
            if not isinstance(raw.columns, pd.MultiIndex):
                raw.columns = pd.MultiIndex.from_product([list(raw.columns), part[:1]])
            px = raw["Close"].copy()
            idx = pd.to_datetime(px.index)
            idx = idx.tz_localize("UTC") if idx.tz is None else idx
            px.index = idx.tz_convert(ET)
            out.append(px)
        except Exception as e:
            print(f"  分鐘線取不到（{type(e).__name__}）")
        time.sleep(0.5)
    if not out:
        return pd.DataFrame()
    big = pd.concat(out, axis=1)
    return big.loc[:, ~big.columns.duplicated()].sort_index()

def band_ge(x, levels):
    out = pd.Series(0.0, index=x.index)
    for thr, p in sorted(levels):
        out = out.mask(x >= thr, float(p))
    return out.where(x.notna())

def band_lt(x, levels):
    out = pd.Series(0.0, index=x.index)
    for thr, p in sorted(levels, reverse=True):
        out = out.mask(x < thr, float(p))
    return out.where(x.notna())

def band_le(x, levels):
    out = pd.Series(0.0, index=x.index)
    for thr, p in sorted(levels, reverse=True):
        out = out.mask(x <= thr, float(p))
    return out.where(x.notna())

def flag(cond, like, pts=1.0):
    return (cond.astype(float) * pts).where(like.notna())

def isnan(v):
    try:
        return v is None or (isinstance(v, (float, np.floating)) and np.isnan(v))
    except Exception:
        return False

def fnum(v, nd=2, suffix="", plus=False):
    if isnan(v):
        return "—"
    return f"{v:+,.{nd}f}{suffix}" if plus else f"{v:,.{nd}f}{suffix}"

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
            print(f"  ⚠ 持倉格式看不懂，已略過：{item.strip()}（格式：代號:股數:止蝕價:入場價:入場日）")
    return pos

POSITIONS = parse_positions(POSITIONS_TEXT)
EXTRA_TICKERS = [t.strip().upper() for t in re.split(r"[,;，；\s]+", EXTRA_TICKERS_TEXT or "") if t.strip()]
UNIVERSE_SOURCES = UNIVERSE.split("+")

# ---------- 股票池 ----------
WIKI = {
    "sp500": ("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies", 480, 520),
    "sp400": ("https://en.wikipedia.org/wiki/List_of_S%26P_400_companies", 380, 420),
    "sp600": ("https://en.wikipedia.org/wiki/List_of_S%26P_600_companies", 570, 620),
}
SECTOR_ETF_OF = {
    "information technology": "XLK", "technology": "XLK",
    "communication services": "XLC", "telecommunications": "XLC",
    "consumer discretionary": "XLY", "consumer staples": "XLP",
    "financials": "XLF", "industrials": "XLI", "energy": "XLE",
    "materials": "XLB", "basic materials": "XLB",
    "health care": "XLV", "utilities": "XLU", "real estate": "XLRE",
}
# Nasdaq 100 之中多數已在 S&P 500；以下是可能不在 S&P 的成份，只在網上名單取不到時作後備（未必是最新成份）
NDX_SUPPLEMENT = "ASML AZN ARM PDD MELI CCEP TEAM GFS SHOP TRI MSTR ZS MDB OKTA DDOG APP MRVL".split()
FALLBACK_UNIVERSE = ("NVDA MSFT AAPL GOOGL AMZN META AVGO TSLA NFLX AMD PLTR COST JPM LLY V MA UNH XOM HD PG "
                     "ORCL CRM ADBE QCOM TXN INTC MU AMAT LRCX KLAC ASML PANW CRWD SNOW NOW SHOP UBER ABNB BKNG "
                     "GS MS BAC WFC C CAT DE BA GE HON LMT RTX UNP UPS WMT TGT NKE SBUX MCD DIS CMCSA T VZ PFE MRK "
                     "ABBV JNJ TMO ISRG VRTX REGN CVX COP SLB LIN FCX NEM").split()

def _clean_ticker(s):
    return s.astype(str).str.strip().str.upper().str.replace(".", "-", regex=False)

def _wiki_constituents(url, lo, hi):
    page = requests.get(url, headers=UA, timeout=30).text
    for t in pd.read_html(io.StringIO(page)):
        cols = [" ".join(str(x) for x in c).strip() if isinstance(c, tuple) else str(c).strip() for c in t.columns]
        t.columns = cols
        tcol = next((c for c in cols if c.lower() in ("symbol", "ticker", "ticker symbol")), None)
        if tcol is None or not (lo <= len(t) <= hi):
            continue
        scol = (next((c for c in cols if "gics sector" in c.lower()), None)
                or next((c for c in cols if c.lower() == "sector"), None))
        gcol = next((c for c in cols if "sub-industry" in c.lower() or "sub industry" in c.lower()), None)
        return pd.DataFrame({"Ticker": _clean_ticker(t[tcol]).values,
                             "Sector": t[scol].astype(str).values if scol else "",
                             "SubInd": t[gcol].astype(str).values if gcol else ""})
    raise ValueError("找不到成份股表格")

def _ndx_constituents():
    """Wikipedia 的 Nasdaq-100 頁已沒有成份表，改用其他來源，逐個試。"""
    try:
        page = requests.get("https://www.slickcharts.com/nasdaq100", headers=UA, timeout=30).text
        for t in pd.read_html(io.StringIO(page)):
            cols = [str(c).strip() for c in t.columns]
            if "Symbol" in cols and 90 <= len(t) <= 115:
                return _clean_ticker(t["Symbol"]).tolist(), "slickcharts"
    except Exception:
        pass
    try:
        j = requests.get("https://api.nasdaq.com/api/quote/list-type/nasdaq100",
                         headers={**UA, "Accept": "application/json, text/plain, */*"}, timeout=30).json()
        syms = [str(r["symbol"]).upper().replace(".", "-") for r in j["data"]["data"]["rows"]]
        if len(syms) >= 90:
            return syms, "nasdaq.com"
    except Exception:
        pass
    return NDX_SUPPLEMENT, "後備補充名單"

NDX_LIST = []
def get_universe():
    parts, notes = [], []
    for src in UNIVERSE_SOURCES:
        if src == "ndx100":
            syms, where = _ndx_constituents()
            NDX_LIST.extend(syms)
            parts.append(pd.DataFrame({"Ticker": syms, "Sector": "", "SubInd": "", "Source": "ndx100"}))
            print(f"  ndx100: {len(syms)} 隻（來源：{where}）")
            if where == "後備補充名單":
                notes.append("Nasdaq 100 成份名單取不到，只補入了一份可能過時的後備名單；絕大部分成份已在 S&P 500 內，影響有限。")
            continue
        url, lo, hi = WIKI[src]
        try:
            d = _wiki_constituents(url, lo, hi)
            d["Source"] = src
            parts.append(d)
            print(f"  {src}: {len(d)} 隻")
        except Exception as e:
            print(f"  ⚠ {src} 成份股取不到（{type(e).__name__}: {str(e)[:80]}）")
            if src == "sp500":
                try:
                    g = pd.read_csv("https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv")
                    parts.append(pd.DataFrame({"Ticker": _clean_ticker(g["Symbol"]).values,
                                               "Sector": g["GICS Sector"].astype(str).values,
                                               "SubInd": g["GICS Sub-Industry"].astype(str).values if "GICS Sub-Industry" in g.columns else "",
                                               "Source": "sp500"}))
                    print(f"  sp500（GitHub 後備）: {len(g)} 隻")
                except Exception as e2:
                    print(f"  ⚠ sp500 後備來源亦失敗（{type(e2).__name__}）")
    fallback = not any(len(p) > 300 for p in parts)
    if fallback:
        parts.append(pd.DataFrame({"Ticker": FALLBACK_UNIVERSE, "Sector": "", "SubInd": "", "Source": "fallback"}))
    extra = list(EXTRA_TICKERS) + list(POSITIONS.keys())
    if isinstance(LEADERS, (list, tuple)):
        extra += [str(x).upper() for x in LEADERS]
    if extra:
        parts.append(pd.DataFrame({"Ticker": extra, "Sector": "", "SubInd": "", "Source": "extra"}))
    u = pd.concat(parts, ignore_index=True)
    u = u[u["Ticker"].str.len() > 0]
    # 同一代號在多個來源出現時，保留有板塊資料的一行
    u["_has"] = (u["Sector"].astype(str).str.len() > 0).astype(int)
    u = u.sort_values("_has", ascending=False, kind="stable").drop_duplicates("Ticker", keep="first").drop(columns="_has").reset_index(drop=True)
    u["SecETF"] = u["Sector"].astype(str).str.strip().str.lower().map(SECTOR_ETF_OF).fillna("")
    u["SubInd"] = u["SubInd"].astype(str).replace({"nan": ""})
    return u, fallback, notes

print("讀取股票池…")
UNI, UNIVERSE_FALLBACK, UNI_NOTES = get_universe()
print(f"股票池共 {len(UNI)} 隻")

def fill_missing_sectors():
    """沒有 GICS 板塊的股票（主要是不屬於 S&P 的 Nasdaq 100 成份），用 nasdaq.com 篩選器的板塊補上。分類方法與 GICS 略有不同。"""
    need = [i for i in UNI.index if not UNI.at[i, "SecETF"]]
    if not need:
        return 0
    j = requests.get("https://api.nasdaq.com/api/screener/stocks?tableonly=true&limit=25&offset=0&download=true",
                     headers={**UA, "Accept": "application/json, text/plain, */*"}, timeout=30).json()
    data = j.get("data") or {}
    rows = data.get("rows") or (data.get("table") or {}).get("rows") or []
    sec = {str(r.get("symbol", "")).strip().upper().replace(".", "-").replace("/", "-"): str(r.get("sector", "")).strip().lower() for r in rows}
    etf_of = {**SECTOR_ETF_OF, "finance": "XLF"}
    n = 0
    for i in need:
        etf = etf_of.get(sec.get(UNI.at[i, "Ticker"], ""), "")
        if etf:
            UNI.at[i, "SecETF"] = etf
            n += 1
    return n
try:
    _nfill = fill_missing_sectors()
    if _nfill:
        print(f"  為 {_nfill} 隻沒有板塊資料的股票補上板塊（來源：nasdaq.com）")
except Exception as e:
    print(f"  板塊補充資料取不到（{type(e).__name__}），這些股票的板塊留空")

# ---------- 下載 ----------
SECTOR_ETFS = {"XLK": "科技", "XLC": "通訊", "XLY": "非必需消費", "XLF": "金融", "XLI": "工業", "XLE": "能源",
               "XLB": "原材料", "XLV": "醫療", "XLP": "必需消費", "XLU": "公用", "XLRE": "房地產"}
INDUSTRY_ETFS = {"SMH": "半導體", "IGV": "軟件", "XBI": "生物科技", "ITB": "建築", "KRE": "地區銀行",
                 "XRT": "零售", "ITA": "國防航天", "XME": "金屬礦業", "GDX": "金礦", "ARKK": "投機成長"}
DEFENSIVE = ["XLU", "XLP", "XLV"]
MACRO_SYMS = (["QQQ", "SPY", "IWM", "RSP", "DIA", "^IXIC", "^NDX", "^GSPC", "HYG", "IEF", "LQD", "TLT", "SPHB", "SPLV",
               "^VIX", "^VXN", "^VIX3M", "^VVIX", "^TNX", "^IRX", "^FVX", "^TYX", "DX-Y.NYB"]
              + list(SECTOR_ETFS) + list(INDUSTRY_ETFS))
OVERNIGHT = {"NQ=F": "Nasdaq 100 期貨", "ES=F": "S&P 500 期貨", "RTY=F": "Russell 2000 期貨", "^VIX": "VIX",
             "^TNX": "10 年期孳息", "DX-Y.NYB": "美元指數", "CL=F": "原油", "GC=F": "黃金", "BTC-USD": "Bitcoin"}

RUN_TS = now_et()
print(f"執行時間（美東）：{RUN_TS:%Y-%m-%d %H:%M}")
print("下載宏觀與 ETF…")
M = dl(MACRO_SYMS, period=HISTORY_PERIOD, chunk=60)
if "Close" not in M or "QQQ" not in M["Close"].columns:
    raise RuntimeError("QQQ 下載失敗，無法繼續。請隔幾分鐘重跑（Yahoo 可能限流）。")
CAL = M["Close"]["QQQ"].dropna().index
ASOF, N = CAL[-1], len(CAL)
SESS_D = next_session(ASOF.date())                       # 這份簡報所準備的交易日（已扣除休市日）
SESS = pd.Timestamp(SESS_D)
print(f"數據截至 {ASOF:%Y-%m-%d} 收市，共 {N} 個交易日")
if N < 320:
    raise RuntimeError("歷史數據少於 320 個交易日，分數無法計算。")

def mser(sym, field="Close"):
    f = M.get(field)
    if f is None and field == "Adj Close":
        f = M.get("Close")
    if f is None or sym not in f.columns:
        return None
    s = f[sym].reindex(CAL).ffill(limit=3)
    return None if s.notna().sum() < 60 else s

print("下載股票池日線（需時數分鐘）…")
U = dl(UNI["Ticker"].tolist(), period=HISTORY_PERIOD, chunk=120, label="股票池")
if "Close" not in U:
    raise RuntimeError("股票池下載失敗，請隔幾分鐘重跑。")
C = U["Close"].reindex(CAL)
C = C.loc[:, C.iloc[-5:].notna().any()]
H = U["High"].reindex(CAL).reindex(columns=C.columns)
L = U["Low"].reindex(CAL).reindex(columns=C.columns)
O = U["Open"].reindex(CAL).reindex(columns=C.columns)
V = U["Volume"].reindex(CAL).reindex(columns=C.columns)

# ---------- v6.1：數據完整性。最後一個交易日沒有收市價的股票：先重新下載，再用 5 分鐘線補；補不到的要講明 ----------
DATA_HOLE, DATA_FIX = [], {"n0": 0, "daily": 0, "intraday": 0}
def _holes():
    lastc = C.iloc[-1]
    return [t for t in C.columns[lastc.isna().values] if C[t].iloc[-6:-1].notna().any()]

def fix_last_day():
    miss = _holes()
    DATA_FIX["n0"] = len(miss)
    if not miss:
        return
    print(f"  ⚠ {len(miss)} 隻股票在 {ASOF:%m-%d} 沒有收市價（Yahoo 未提供），重新下載這些股票…")
    win = CAL[-10:]
    redo = dl(miss, period="1mo", chunk=60, pause=1.0)
    if "Close" in redo:
        for fld, pan in (("Close", C), ("High", H), ("Low", L), ("Open", O), ("Volume", V)):
            if fld not in redo:
                continue
            new = redo[fld].reindex(win)
            for t in miss:
                if t in new.columns:
                    old = pan.loc[win, t]
                    pan.loc[win, t] = old.where(old.notna(), new[t]).values
    left = _holes()
    DATA_FIX["daily"] = len(miss) - len(left)
    if left:
        print(f"  ⚠ 仍有 {len(left)} 隻沒有收市價，改用 5 分鐘線補上…")
        day, n_i = ASOF.date(), 0
        for i in range(0, len(left), 100):
            part = left[i:i + 100]
            try:
                raw = yf.download(part, period="5d", interval="5m", prepost=False, auto_adjust=False,
                                  group_by="column", threads=True, progress=False)
                if raw is None or not len(raw):
                    continue
                if not isinstance(raw.columns, pd.MultiIndex):
                    raw.columns = pd.MultiIndex.from_product([list(raw.columns), part[:1]])
                idx = pd.to_datetime(raw.index)
                raw.index = (idx.tz_localize("UTC") if idx.tz is None else idx).tz_convert(ET)
                d1 = raw[raw.index.date == day]
                if not len(d1):
                    continue
                for t in part:
                    try:
                        c1 = d1["Close"][t].dropna()
                        if not len(c1):
                            continue
                        C.loc[ASOF, t] = float(c1.iloc[-1])
                        if isnan(H.loc[ASOF, t]):
                            H.loc[ASOF, t] = float(d1["High"][t].max())
                        if isnan(L.loc[ASOF, t]):
                            L.loc[ASOF, t] = float(d1["Low"][t].min())
                        if isnan(O.loc[ASOF, t]):
                            O.loc[ASOF, t] = float(d1["Open"][t].dropna().iloc[0])
                        if isnan(V.loc[ASOF, t]):
                            V.loc[ASOF, t] = float(d1["Volume"][t].sum())
                        n_i += 1
                    except Exception:
                        pass
            except Exception as e:
                print(f"  5 分鐘線取不到（{type(e).__name__}）")
            time.sleep(0.5)
        DATA_FIX["intraday"] = n_i

try:
    fix_last_day()
except Exception as e:
    print(f"  ⚠ 補數據時出錯（{type(e).__name__}: {str(e)[:100]}），照原有數據繼續")
try:
    DATA_HOLE = _holes()
    DATA_HOLE = sorted(DATA_HOLE, key=lambda t: -float(np.nan_to_num((C[t].iloc[-6:-1] * V[t].iloc[-6:-1]).mean())))   # 成交金額大的排前
except Exception:
    DATA_HOLE = []
if DATA_FIX["n0"]:
    print(f"  數據完整性：最初 {DATA_FIX['n0']} 隻沒有 {ASOF:%m-%d} 的收市價；重新下載補回 {DATA_FIX['daily']} 隻，"
          f"5 分鐘線補回 {DATA_FIX['intraday']} 隻，仍然缺 {len(DATA_HOLE)} 隻")
TICKS = list(C.columns)
LOAD_RATIO = len(TICKS) / max(len(UNI), 1) * 100
print(f"成功載入 {len(TICKS)}/{len(UNI)} 隻（{LOAD_RATIO:.0f}%）")
SEC_OF = UNI.set_index("Ticker")["SecETF"].to_dict()
SUB_OF = UNI.set_index("Ticker")["SubInd"].to_dict()

# ---------- 指數技術面 ----------
def tech(sym):
    c, h, l, v = mser(sym, "Close"), mser(sym, "High"), mser(sym, "Low"), mser(sym, "Volume")
    if c is None:
        return None
    h = c if h is None else h
    l = c if l is None else l
    v = pd.Series(np.nan, index=CAL) if v is None else v
    d = pd.DataFrame({"c": c, "h": h, "l": l, "v": v})
    pc = c.shift(1)
    d["ema21"] = c.ewm(span=21, adjust=False).mean()
    d["s50"] = c.rolling(50).mean()
    d["s200"] = c.rolling(200).mean()
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    d["atr"] = tr.rolling(14).mean()
    delta = c.diff()
    up = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    dn = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    d["rsi"] = 100 - 100 / (1 + up / dn)
    d["hi252"] = h.rolling(252).max()
    d["hi20"] = h.rolling(20).max()
    d["lo20"] = l.rolling(20).min()
    d["ret"] = c / pc - 1
    d["distday"] = ((d["ret"] <= -0.002) & (v > v.shift(1))).astype(float)
    d["dist25"] = dist_count(d["c"].values, d["distday"].values)
    return d

def dist_count(cv, isd, win=25, expire=0.05):
    """近 25 個交易日的派發日數目；其後指數收市較該日高出 5% 的派發日視為失效（O'Neil 的做法）。"""
    n = len(cv)
    out = np.full(n, np.nan)
    for t in range(win, n):
        cnt = 0
        for i in range(t - win + 1, t + 1):
            if isd[i] == 1 and not (i < t and np.nanmax(cv[i + 1:t + 1]) >= cv[i] * (1 + expire)):
                cnt += 1
        out[t] = cnt
    return out

def dist_days_active(d, win=25, expire=0.05):
    """列出目前仍然有效的派發日：日期、當日跌幅、何時自動失效。"""
    n, rows = len(d), []
    cv = d["c"].values
    for i in range(max(n - win, 1), n):
        if d["distday"].iloc[i] == 1 and not (i < n - 1 and np.nanmax(cv[i + 1:]) >= cv[i] * (1 + expire)):
            rows.append({"Date": f"{d.index[i]:%m-%d}", "Chg%": d["ret"].iloc[i] * 100,
                         "Left": win - (n - 1 - i), "Kill": cv[i] * (1 + expire)})
    return pd.DataFrame(rows)

Q = tech("QQQ")
SPYT, IWMT = tech("SPY"), tech("IWM")
q = Q.iloc[-1]

def rally_status(d):
    look = min(TH["ftd_lookback"], len(d) - 1)
    lows = d["l"].iloc[-look:]
    low_pos = len(d) - look + int(np.nanargmin(lows.values))
    low_val = d["l"].iloc[low_pos]
    prior_high = d["h"].iloc[max(0, low_pos - 252):low_pos + 1].max()
    depth = (low_val / prior_high - 1) * 100
    # 第 1 日：創低位當日若收升、或收在當日波幅上半，當日就是第 1 日；否則是其後第一個收升的交易日。
    c, h, l = d["c"].values, d["h"].values, d["l"].values
    def _closes_well(i):
        rng = h[i] - l[i]
        return (i > 0 and c[i] > c[i - 1]) or (rng > 0 and (c[i] - l[i]) / rng >= 0.5)
    d1 = low_pos if _closes_well(low_pos) else next((i for i in range(low_pos + 1, len(d)) if c[i] > c[i - 1]), None)
    res = dict(low_date=d.index[low_pos], low=low_val, depth=depth, day=(len(d) - d1) if d1 is not None else 0,
               day1_date=d.index[d1] if d1 is not None else None,
               in_correction=depth <= -TH["ftd_min_corr"], ftd_date=None, ftd_valid=False)
    if res["in_correction"] and d1 is not None:
        for i in range(d1 + 3, len(d)):                    # 第 4 日起才算
            if d["ret"].iloc[i] * 100 >= TH["ftd_gain"] and d["v"].iloc[i] > d["v"].iloc[i - 1]:
                if bool((d["c"].iloc[i:] >= d["l"].iloc[i]).all()):
                    res["ftd_date"], res["ftd_valid"] = d.index[i], True
    return res

RALLY = rally_status(Q)
wk = Q["c"].resample("W-FRI").last().dropna()
WK10, WK40 = wk.rolling(10).mean().iloc[-1], wk.rolling(40).mean().iloc[-1]
WEEKLY_UP = bool(wk.iloc[-1] > WK10 > WK40) if len(wk) >= 40 else None

# ---------- 市場健康分數（規則與 v1 相同）----------
class Pillar:
    def __init__(self, key, name):
        self.key, self.name, self.items = key, name, []
    def add(self, label, pts, mx, value=""):
        if pts is not None:
            pts = pd.Series(pts, index=CAL).astype(float)
            if pts.notna().sum() == 0:
                pts = None
        self.items.append((label, pts, float(mx), value if pts is not None else "缺數據"))
    def series(self):
        ok = [(p, m) for _, p, m, _ in self.items if p is not None]
        if not ok:
            return pd.Series(np.nan, index=CAL)
        return sum(p.fillna(0) for p, _ in ok) / sum(m for _, m in ok) * 100

def above50(t):
    return None if t is None else flag(t["c"] > t["s50"], t["s50"], 0.5)

P_TREND = Pillar("trend", "趨勢")
c_, e21, s50, s200 = Q["c"], Q["ema21"], Q["s50"], Q["s200"]
P_TREND.add("收市 > 21EMA", flag(c_ > e21, e21), 1, f"{q.c:.2f} vs {q.ema21:.2f}")
P_TREND.add("收市 > 50 日線", flag(c_ > s50, s50), 1, f"{q.c:.2f} vs {q.s50:.2f}")
P_TREND.add("收市 > 200 日線", flag(c_ > s200, s200), 1, f"{q.c:.2f} vs {q.s200:.2f}")
P_TREND.add("21EMA > 50 日線", flag(e21 > s50, s50), 1)
P_TREND.add("50 日線 > 200 日線", flag(s50 > s200, s200), 1)
P_TREND.add("50 日線高於 10 日前", flag(s50 > s50.shift(10), s50.shift(10)), 1)
P_TREND.add("200 日線高於 20 日前", flag(s200 > s200.shift(20), s200.shift(20)), 1)
near_hi = (c_ / Q["hi252"] - 1) * 100
P_TREND.add(f"距 52 週高位 {TH['near_high_pct']:g}% 以內", flag(near_hi >= -TH["near_high_pct"], Q["hi252"]), 1, f"{near_hi.iloc[-1]:.1f}%")
P_TREND.add("20 日高位高於前一個 20 日", flag(Q["hi20"] > Q["hi20"].shift(20), Q["hi20"].shift(20)), 1)
P_TREND.add("20 日低位高於前一個 20 日", flag(Q["lo20"] > Q["lo20"].shift(20), Q["lo20"].shift(20)), 1)
dd = Q["dist25"]
dd_pts = pd.Series(0.0, index=CAL).mask(dd <= TH["dist_days_warn"], 0.5).mask(dd <= TH["dist_days_ok"], 1.0).where(dd.notna())
DIST_N = 0 if np.isnan(q.dist25) else int(q.dist25)
P_TREND.add("近 25 日派發日數目", dd_pts, 1, f"{DIST_N} 個")
P_TREND.add("SPY > 50 日線", above50(SPYT), 0.5)
P_TREND.add("IWM > 50 日線", above50(IWMT), 0.5)

def pct_above(n):
    ma = C.rolling(n).mean()
    valid = ma.notna() & C.notna()
    return (C.gt(ma) & valid).sum(axis=1) / valid.sum(axis=1).replace(0, np.nan) * 100

PCT20, PCT50, PCT200 = pct_above(20), pct_above(50), pct_above(200)
HI252, LO252 = H.rolling(252).max(), L.rolling(252).min()
NH = (H.ge(HI252) & HI252.notna()).sum(axis=1).astype(float)
NL = (L.le(LO252) & LO252.notna()).sum(axis=1).astype(float)
has252 = HI252.notna().sum(axis=1)
NH, NL = NH.where(has252 > 0), NL.where(has252 > 0)
chg = C - C.shift(1)
ADV, DEC = (chg > 0).sum(axis=1).astype(float), (chg < 0).sum(axis=1).astype(float)
NET = ADV - DEC
RANA = (NET / (ADV + DEC).replace(0, np.nan) * 1000).fillna(0)
MCO = RANA.ewm(span=19, adjust=False).mean() - RANA.ewm(span=39, adjust=False).mean()
ADL = NET.cumsum()
NHNL10 = (NH - NL).rolling(10).mean()

P_BREADTH = Pillar("breadth", "寬度")
P_BREADTH.add("高於 50 日線的股票比例", band_ge(PCT50, TH["breadth_bands"]), 3, f"{PCT50.iloc[-1]:.0f}%")
P_BREADTH.add("高於 200 日線的股票比例", band_ge(PCT200, TH["breadth_bands"]), 3, f"{PCT200.iloc[-1]:.0f}%")
P_BREADTH.add("高於 20 日線的比例高於 5 日前", flag(PCT20 > PCT20.shift(5), PCT20.shift(5)), 1,
              f"{PCT20.iloc[-1]:.0f}%（5 日前 {PCT20.iloc[-6]:.0f}%）")
P_BREADTH.add("52 週新高數 > 新低數", flag(NH > NL, NH), 1, f"{fnum(NH.iloc[-1], 0)} vs {fnum(NL.iloc[-1], 0)}")
P_BREADTH.add("（新高 − 新低）10 日平均 > 0", flag(NHNL10 > 0, NHNL10), 1, fnum(NHNL10.iloc[-1], 1))
P_BREADTH.add("McClellan Oscillator > 0", flag(MCO > 0, PCT50), 1, fnum(MCO.iloc[-1], 1))
P_BREADTH.add("騰落線 > 其 20 日均線", flag(ADL > ADL.rolling(20).mean(), ADL.rolling(20).mean()), 1)

DV50 = (C * V).rolling(50).mean().iloc[-1]
if isinstance(LEADERS, (list, tuple)):
    LEAD = [t for t in [str(x).upper() for x in LEADERS] if t in TICKS]
else:
    LEAD = [t for t in DV50.dropna().sort_values(ascending=False).index if t not in DUP_CLASS][:N_LEADERS]
S50_ALL = C.rolling(50).mean()
if isinstance(LEADERS, (list, tuple)):
    lead_mask = pd.DataFrame(False, index=CAL, columns=C.columns)
    lead_mask[LEAD] = True
else:
    # 分數歷史用「當日」成交金額最高的 N 隻，避免用今日的名單回看過去
    dv_hist = (C * V).rolling(50).mean()
    dv_hist.loc[:, [t for t in dv_hist.columns if t in DUP_CLASS]] = np.nan
    lead_mask = dv_hist.rank(axis=1, ascending=False) <= N_LEADERS
_lv = lead_mask & S50_ALL.notna() & C.notna()
LEAD_PCT50 = (C.gt(S50_ALL) & _lv).sum(axis=1) / _lv.sum(axis=1).replace(0, np.nan) * 100

P_RISK = Pillar("risk", "風險偏好")
def ratio_item(a, b):
    x, y = mser(a, "Adj Close"), mser(b, "Adj Close")
    if x is None or y is None:
        return None, ""
    r = x / y
    ma = r.rolling(50).mean()
    return flag(r > ma, ma), ("之上" if r.iloc[-1] > ma.iloc[-1] else "之下")
for a, b in [("SMH", "QQQ"), ("RSP", "SPY"), ("IWM", "SPY"), ("XLY", "XLP"), ("SPHB", "SPLV")]:
    pts, val = ratio_item(a, b)
    P_RISK.add(f"{a}/{b} > 50 日均線", pts, 1, val)
P_RISK.add("龍頭股高於 50 日線的比例", band_ge(LEAD_PCT50, TH["leaders_bands"]), 2, f"{LEAD_PCT50.iloc[-1]:.0f}%")
sec_adj = pd.DataFrame({s: mser(s, "Adj Close") for s in SECTOR_ETFS if mser(s, "Adj Close") is not None})
if sec_adj.shape[1] >= 8:
    sec_r21 = sec_adj / sec_adj.shift(21) - 1
    sec_rank = sec_r21.rank(axis=1, ascending=False)
    n_def = (sec_rank[[s for s in DEFENSIVE if s in sec_rank.columns]] <= 3).sum(axis=1)
    TOP3 = sec_r21.iloc[-1].sort_values(ascending=False).head(3).index.tolist()
    P_RISK.add("最強三個板塊中防守板塊 ≤ 1 個", flag(n_def <= 1, sec_r21.iloc[:, 0]), 1, "、".join(TOP3))
else:
    sec_r21, TOP3 = None, []
    P_RISK.add("最強三個板塊中防守板塊 ≤ 1 個", None, 1)

P_VOL = Pillar("vol", "波動率")
VIX, VXN, VIX3M = mser("^VIX"), mser("^VXN"), mser("^VIX3M")
if VIX is not None:
    P_VOL.add("VIX 水平", band_lt(VIX, TH["vix_bands"]), 3, f"{VIX.iloc[-1]:.1f}")
    P_VOL.add("VIX < 其 20 日均線", flag(VIX < VIX.rolling(20).mean(), VIX.rolling(20).mean()), 1, f"20 日均 {VIX.rolling(20).mean().iloc[-1]:.1f}")
else:
    P_VOL.add("VIX 水平", None, 3)
    P_VOL.add("VIX < 其 20 日均線", None, 1)
if VIX is not None and VIX3M is not None:
    TERM = VIX / VIX3M
    P_VOL.add("VIX/VIX3M 期限結構", band_lt(TERM, TH["term_bands"]), 2, f"{TERM.iloc[-1]:.2f}")
else:
    TERM = None
    P_VOL.add("VIX/VIX3M 期限結構", None, 2)
if VXN is not None:
    P_VOL.add("VXN < 其 20 日均線", flag(VXN < VXN.rolling(20).mean(), VXN.rolling(20).mean()), 1, f"VXN {VXN.iloc[-1]:.1f}")
else:
    P_VOL.add("VXN < 其 20 日均線", None, 1)
if VIX is not None and VXN is not None:
    SPREAD = VXN - VIX
    med = SPREAD.rolling(252).median()
    P_VOL.add("VXN − VIX 差距 ≤ 一年中位數", flag(SPREAD <= med, med), 1, f"{SPREAD.iloc[-1]:.1f}（中位 {med.iloc[-1]:.1f}）")
else:
    P_VOL.add("VXN − VIX 差距 ≤ 一年中位數", None, 1)

P_RATES = Pillar("rates", "利率與信貸")
TNX, DXY, IRX = mser("^TNX"), mser("DX-Y.NYB"), mser("^IRX")
HYG, IEF = mser("HYG", "Adj Close"), mser("IEF", "Adj Close")
if TNX is not None:
    TNX20 = (TNX - TNX.shift(20)) * 100
    P_RATES.add("10 年期孳息 20 日變動", band_le(TNX20, TH["tnx_bands_bp"]), 2, f"{TNX.iloc[-1]:.2f}%（{TNX20.iloc[-1]:+.0f}bp）")
else:
    P_RATES.add("10 年期孳息 20 日變動", None, 2)
if HYG is not None and IEF is not None:
    CR = HYG / IEF
    P_RATES.add("HYG/IEF > 50 日均線", flag(CR > CR.rolling(50).mean(), CR.rolling(50).mean(), 2), 2,
                "之上" if CR.iloc[-1] > CR.rolling(50).mean().iloc[-1] else "之下")
else:
    P_RATES.add("HYG/IEF > 50 日均線", None, 2)
if HYG is not None:
    P_RATES.add("HYG > 50 日線", flag(HYG > HYG.rolling(50).mean(), HYG.rolling(50).mean()), 1,
                "之上" if HYG.iloc[-1] > HYG.rolling(50).mean().iloc[-1] else "之下")
else:
    P_RATES.add("HYG > 50 日線", None, 1)
if DXY is not None:
    DXY20 = (DXY / DXY.shift(20) - 1) * 100
    P_RATES.add(f"美元指數 20 日升幅 < {TH['dxy_max_20d']:g}%", flag(DXY20 < TH["dxy_max_20d"], DXY20), 1, f"{DXY20.iloc[-1]:+.1f}%")
else:
    P_RATES.add(f"美元指數 20 日升幅 < {TH['dxy_max_20d']:g}%", None, 1)
# 只作顯示、不計分：短端利率 3 個月變動，反映市場對加息或減息的預期
IRX63 = None if IRX is None else float((IRX.iloc[-1] - IRX.iloc[-64]) * 100)

PILLARS = [P_TREND, P_BREADTH, P_RISK, P_VOL, P_RATES]
PS = pd.DataFrame({p.key: p.series() for p in PILLARS})
wts = pd.Series(TH["weights"], dtype=float)
SCORE = PS.fillna(0).mul(wts, axis=1).sum(axis=1) / PS.notna().mul(wts, axis=1).sum(axis=1).replace(0, np.nan)
SCORE.iloc[:min(260, N - 1)] = np.nan

REG_NAME = {4: ("A", "強勢多頭"), 3: ("B", "偏多"), 2: ("C", "震盪"), 1: ("D", "防守"), 0: ("E", "空頭")}
def band_of(s):
    b = TH["regime_bands"]
    return 4 if s >= b[0] else 3 if s >= b[1] else 2 if s >= b[2] else 1 if s >= b[3] else 0
raw = SCORE.dropna().apply(band_of)
reg, cur, prev = [], None, None
for r in raw.values:
    if cur is None or r < cur:
        cur = r
    elif r > cur and prev is not None and prev > cur:
        cur = min(r, prev)
    reg.append(cur)
    prev = r
REGIME = pd.Series(reg, index=raw.index)
score_now, score_prev, score_5 = float(SCORE.iloc[-1]), float(SCORE.iloc[-2]), float(SCORE.iloc[-6])
reg_now, reg_prev = int(REGIME.iloc[-1]), int(REGIME.iloc[-2])
REG_L, REG_T = REG_NAME[reg_now]
REG_DAYS = int((REGIME.iloc[::-1] == reg_now).cumprod().sum())      # 已在現 Regime 幾多日

pct50_now = float(PCT50.iloc[-1])
vix_now = float(VIX.iloc[-1]) if VIX is not None else np.nan
s50_down = bool(Q["s50"].iloc[-1] < Q["s50"].iloc[-11])
OVERSOLD = bool(pct50_now < TH["oversold_pct50"] or (not np.isnan(vix_now) and vix_now > TH["oversold_vix"]))
LONG_GATE = bool(reg_now >= 3 and q.c > q.s50)
PILOT_GATE = bool((not LONG_GATE) and ((score_now >= TH["regime_bands"][2] and q.c > q.ema21) or RALLY["ftd_valid"]))
SHORT_SETUP = bool(reg_now <= 1 and q.c < q.s50 and s50_down)
SHORT_GATE = bool(SHORT_SETUP and not OVERSOLD)
GATE_OPEN = bool(LONG_GATE or PILOT_GATE or SHORT_GATE)
if LONG_GATE:
    RISK_MULT, SIDE = TH["risk_mult"][REG_L], "多頭閘門開"
elif PILOT_GATE:
    RISK_MULT, SIDE = TH["risk_mult"]["pilot"], "只有試單閘門開"
elif SHORT_GATE:
    RISK_MULT, SIDE = TH["risk_mult"]["short"], "空頭閘門開"
else:
    RISK_MULT, SIDE = TH["risk_mult"]["pilot"], "所有閘門關閉"
RISK_DOLLARS = ACCOUNT_EQUITY * BASE_RISK_PCT / 100 * RISK_MULT
LONG_RISK = ACCOUNT_EQUITY * BASE_RISK_PCT / 100 * (TH["risk_mult"][REG_L] if LONG_GATE else TH["risk_mult"]["pilot"])

# ---------- 市場週期與做空時機（v2）----------
dd_from_high = (q.c / q.hi252 - 1) * 100
if RALLY["in_correction"] and q.c < q.s50:
    if RALLY["ftd_valid"]:
        CYCLE = f"調整後已出現 FTD（{RALLY['ftd_date']:%m-%d}），試單階段"
    elif RALLY["day"] == 0:
        CYCLE = "調整中，低位後未有收升日，反彈嘗試未開始"
    else:
        CYCLE = f"調整中，反彈嘗試第 {RALLY['day']} 日"
elif q.c > q.s50 and reg_now >= 3 and DIST_N <= 4:
    CYCLE = "確認升勢"
elif q.c > q.s50:
    CYCLE = "升勢受壓"
else:
    CYCLE = "回調中（未達 8%）"
NEXT_DAY = RALLY["day"] + 1                                 # 下一個交易日是反彈第幾日（未開始時，收升才算第 1 日）
d21_q = (q.c / q.ema21 - 1) * 100
if not SHORT_SETUP:
    SHORT_TIMING = "不適用"
elif OVERSOLD:
    SHORT_TIMING = "超賣：規則不開新空頭形態"
elif d21_q >= -2.0:
    SHORT_TIMING = "阻力區：QQQ 已反彈到下降中的 21EMA 附近，規則容許空反彈失敗的形態"
elif q.c <= q.lo20 * 1.01:
    SHORT_TIMING = "破位邊緣：規則不追空，已有空倉的失效位下移"
else:
    SHORT_TIMING = "中間位置：規則要求反彈到阻力才有新空頭形態"
if SHORT_GATE and not LONG_GATE and not PILOT_GATE:
    SIDE = {"阻力區": "空頭閘門開，阻力區", "中間位置": "空頭閘門開，中間位置", "破位邊緣": "空頭閘門開，破位邊緣"}.get(SHORT_TIMING.split("：")[0], SIDE)
print(f"市場健康分數 {score_now:.0f}（昨 {score_prev:.0f}，5 日前 {score_5:.0f}）→ Regime {REG_L} {REG_T}｜{SIDE}｜{CYCLE}")

# ---------- 個股特徵 ----------
last = C.iloc[-1]
S150, S200 = C.rolling(150).mean(), C.rolling(200).mean()
EMA21 = C.ewm(span=21, adjust=False).mean()
PC = C.shift(1)
TR = np.maximum(H - L, np.maximum((H - PC).abs(), (L - PC).abs()))
ATR = TR.rolling(14).mean()
AVGVOL50 = V.rolling(50).mean()

def ret_n(n):
    return last / C.shift(n).iloc[-1] - 1
# 12 個月 RS（舊算法）：回報直接加權。升幅極大的股票即使近期大跌，12 個月回報仍會把分數撐在高位。
rs12_raw = 0.4 * ret_n(63) + 0.2 * ret_n(126) + 0.2 * ret_n(189) + 0.2 * ret_n(252)
RS12 = (rs12_raw.rank(pct=True) * 98 + 1).round()
# RS（v3）：每一期回報先在股票池內排百分位，再按權重加權，最後再排一次百分位。
# 排名有上限（最高 100），所以單一期的極端升幅不能蓋過近期的弱勢；另加 1 個月一期。
RET_LEGS = pd.DataFrame({n: ret_n(n) for n in TH["rs_legs"]})
PCT_LEGS = RET_LEGS.rank(pct=True) * 100
_w = pd.Series(TH["rs_legs"], dtype=float)
rs_comp = (PCT_LEGS.mul(_w, axis=1).sum(axis=1, skipna=True) / PCT_LEGS.notna().mul(_w, axis=1).sum(axis=1).replace(0, np.nan))
rs_comp = rs_comp.where(PCT_LEGS[63].notna())                 # 最少要有 3 個月歷史
RS = (rs_comp.rank(pct=True) * 98 + 1).round()

F = pd.DataFrame(index=TICKS)
F["Close"] = last
F["Chg%"] = (last / PC.iloc[-1] - 1) * 100
F["RS"] = RS
F["RS12"] = RS12
F["RS1M"] = (ret_n(21).rank(pct=True) * 98 + 1).round()
F["R21%"], F["R63%"] = ret_n(21) * 100, ret_n(63) * 100
F["R126%"], F["R189%"], F["R252%"] = ret_n(126) * 100, ret_n(189) * 100, ret_n(252) * 100
F["Ret3D%"] = ret_n(3) * 100
F["VolX"] = V.iloc[-1] / AVGVOL50.shift(1).iloc[-1]
F["Vol3/50"] = V.rolling(3).mean().iloc[-1] / AVGVOL50.iloc[-1]
F["Vol10/50"] = V.rolling(10).mean().iloc[-1] / AVGVOL50.iloc[-1]
F["DV50"] = DV50
F["ATR%"] = ATR.iloc[-1] / last * 100
F["s50"], F["s150"], F["s200"], F["ema21"] = S50_ALL.iloc[-1], S150.iloc[-1], S200.iloc[-1], EMA21.iloc[-1]
F["hi252"], F["lo252"] = HI252.iloc[-1], LO252.iloc[-1]
F["hi20"] = H.rolling(20).max().iloc[-1]
F["FromHigh%"] = (last / F["hi252"] - 1) * 100
F["From50%"] = (last / F["s50"] - 1) * 100
F["From21%"] = (last / F["ema21"] - 1) * 100
F["ExtATR"] = (last - F["ema21"]) / ATR.iloc[-1]
F["EMA21up"] = EMA21.iloc[-1] > EMA21.iloc[-6]
F["S50up"] = S50_ALL.iloc[-1] > S50_ALL.iloc[-11]
F["Above50"] = last > F["s50"]
F["Above200"] = last > F["s200"]
F["Gap%"] = (O.iloc[-1] / PC.iloc[-1] - 1) * 100
# U/D 量比：50 日內上升日成交 ÷ 下跌日成交，> 1.2 代表有資金吸納
_vv = V.where(C.notna() & PC.notna())                       # 有價格的日子才計
_upv, _dnv = _vv.where(~(C <= PC), 0.0), _vv.where(~(C >= PC), 0.0)     # 不合條件的日子當成交為 0，而不是當缺數據
F["UD"] = (_upv.rolling(50, min_periods=40).sum().iloc[-1]
           / _dnv.rolling(50, min_periods=40).sum().iloc[-1].replace(0, np.nan))
F["H3"], F["L3"] = H.rolling(3).max().iloc[-1], L.rolling(3).min().iloc[-1]
rng = (H.iloc[-1] - L.iloc[-1]).replace(0, np.nan)
F["ClosePos"] = (last - L.iloc[-1]) / rng
F["SecETF"] = [SEC_OF.get(t, "") for t in TICKS]
F["SubInd"] = [SUB_OF.get(t, "") for t in TICKS]
F["Liquid"] = (F["Close"] >= MIN_PRICE) & (F["DV50"] >= MIN_DOLLAR_VOL) & ~F.index.isin(DUP_CLASS)

s200_up = S200.iloc[-1] > S200.shift(21).iloc[-1]
F["TT"] = ((last > F["s150"]) & (last > F["s200"]) & (F["s150"] > F["s200"]) & s200_up
           & (F["s50"] > F["s150"]) & (F["s50"] > F["s200"]) & (last > F["s50"])
           & (last >= F["lo252"] * (1 + TH["tt_above_low"] / 100))
           & (last >= F["hi252"] * (1 - TH["tt_within_high"] / 100))
           & (F["RS"] >= TH["tt_rs_min"]))
F["Stage"] = np.select(
    [(last > F["s50"]) & (F["s50"] > F["s200"]), (last < F["s50"]) & (F["s50"] > F["s200"]),
     (last < F["s50"]) & (F["s50"] < F["s200"]), (last > F["s50"]) & (F["s50"] < F["s200"])],
    ["2 上升", "3 轉弱", "4 下跌", "1 築底"], default="—")
if sec_r21 is not None:
    SEC_RANK_NOW = sec_r21.iloc[-1].rank(ascending=False)
    F["SecRank"] = F["SecETF"].map(SEC_RANK_NOW)
else:
    SEC_RANK_NOW = pd.Series(dtype=float)
    F["SecRank"] = np.nan

# RS 線（股價 ÷ SPY）是否貼近 52 週高位；指數見頂以來的表現
spy_c = mser("SPY", "Close")
if spy_c is not None:
    RSL = C.div(spy_c, axis=0)
    F["RSLHigh"] = RSL.iloc[-1] >= RSL.rolling(252).max().iloc[-1] * 0.995
else:
    F["RSLHigh"] = False
PEAK_DATE = Q["c"].iloc[-252:].idxmax()
F["SincePeak%"] = (last / C.loc[PEAK_DATE] - 1) * 100
QQQ_SINCE_PEAK = (q.c / Q["c"].loc[PEAK_DATE] - 1) * 100

# 收窄程度：10 日波幅在過去 126 日的百分位（越低越窄）
R10 = (H.rolling(10).max() - L.rolling(10).min()) / C
F["R10%"] = R10.iloc[-1] * 100
F["TightPct"] = R10.iloc[-126:].le(R10.iloc[-1], axis=1).sum() / R10.iloc[-126:].notna().sum().replace(0, np.nan)
F["Pivot10"] = H.rolling(10).max().iloc[-1]

# ---------- 突破、跌破、突破成功率 ----------
PH21, PH252 = H.rolling(21).max().shift(1), H.rolling(252).max().shift(1)
PL21, PL252 = L.rolling(21).min().shift(1), L.rolling(252).min().shift(1)
BO21, BO252 = C.gt(PH21), C.gt(PH252)
BD21, BD252 = C.lt(PL21), C.lt(PL252)
FRESH252 = BO252 & ~BO252.shift(1, fill_value=False)
FRESH21 = BO21 & ~BO21.shift(1, fill_value=False)
FRESH_BD21 = BD21 & ~BD21.shift(1, fill_value=False)
FRESH_BD252 = BD252 & ~BD252.shift(1, fill_value=False)
F["BO_1M"], F["BO_52W"] = BO21.iloc[-1], BO252.iloc[-1]
F["Fresh_1M"], F["Fresh_52W"] = FRESH21.iloc[-1], FRESH252.iloc[-1]
F["BD_1M"], F["BD_52W"] = BD21.iloc[-1], BD252.iloc[-1]
F["FreshBD_1M"], F["FreshBD_52W"] = FRESH_BD21.iloc[-1], FRESH_BD252.iloc[-1]
F["Pivot52W"] = PH252.iloc[-1]
F["VolOK"] = F["VolX"] >= TH["vol_confirm"]
F["Fallen"] = ((F["RS12"] >= TH["fallen_rs"]) & (F["FromHigh%"] <= -TH["fallen_from_high"]) & (last < F["s50"])
               & (F["R63%"] < 0))

liq = F["Liquid"].reindex(TICKS).fillna(False).values.astype(bool)
tot = succ = 0
for p in range(max(N - 16, 0), N - 5):
    m = FRESH252.iloc[p].values.astype(bool) & liq
    if m.any():
        tot += int(m.sum())
        succ += int((last.values[m] > PH252.iloc[p].values[m]).sum())
BO_FOLLOW, BO_FOLLOW_N = (succ / tot * 100 if tot >= 5 else np.nan), tot
liqF = F[F["Liquid"]]
COUNTS = {"月高突破": int(liqF["BO_1M"].sum()), "52 週高突破": int(liqF["BO_52W"].sum()),
          "月低跌破": int(liqF["BD_1M"].sum()), "52 週低跌破": int(liqF["BD_52W"].sum()),
          "通過 Trend Template": int(liqF["TT"].sum())}

# ---------- VCP（與 v1 相同）----------
def swing_points(h, l, thr):
    n = len(h)
    piv, trend, hi_i, lo_i = [], 0, 0, 0
    for i in range(1, n):
        if trend == 0:
            if h[i] > h[hi_i]:
                hi_i = i
            if l[i] < l[lo_i]:
                lo_i = i
            if hi_i < i and l[i] <= h[hi_i] * (1 - thr):
                piv.append(("H", hi_i, h[hi_i])); trend = -1; lo_i = i
            elif lo_i < i and h[i] >= l[lo_i] * (1 + thr):
                piv.append(("L", lo_i, l[lo_i])); trend = 1; hi_i = i
        elif trend == 1:
            if h[i] > h[hi_i]:
                hi_i = i
            elif l[i] <= h[hi_i] * (1 - thr):
                piv.append(("H", hi_i, h[hi_i])); trend = -1; lo_i = i
        else:
            if l[i] < l[lo_i]:
                lo_i = i
            elif h[i] >= l[lo_i] * (1 + thr):
                piv.append(("L", lo_i, l[lo_i])); trend = 1; hi_i = i
    if trend == 1:
        piv.append(("H*", hi_i, h[hi_i]))
    elif trend == -1:
        piv.append(("L*", lo_i, l[lo_i]))
    return piv

def size_for(entry, stop):
    risk_ps = entry - stop
    shares = int(LONG_RISK // risk_ps) if risk_ps > 0 else 0
    return shares, (risk_ps / entry * 100 if entry else np.nan), shares * entry / ACCOUNT_EQUITY * 100

def vcp_check(t):
    d = pd.DataFrame({"h": H[t], "l": L[t], "c": C[t], "v": V[t]}).dropna().tail(TH["vcp_lookback"])
    if len(d) < 60:
        return None
    h, l, c, v = d["h"].values, d["l"].values, d["c"].values, d["v"].values
    atrp = F.at[t, "ATR%"] / 100 if not np.isnan(F.at[t, "ATR%"]) else 0.03
    piv = swing_points(h, l, float(np.clip(1.5 * atrp, 0.03, 0.08)))
    highs = [(i, p) for ty, i, p in piv if ty == "H"]
    if not highs:
        return None
    b_i, b_p = max(highs, key=lambda x: x[1])
    seq = [x for x in piv if x[1] >= b_i]
    contr = []
    for k, (ty, i, p) in enumerate(seq):
        if ty == "H":
            nxt = next((x for x in seq[k + 1:] if x[0].startswith("L")), None)
            if nxt is not None:
                contr.append((p, nxt[2], (p - nxt[2]) / p * 100))
    if len(contr) < 2:
        return None
    depths = [x[2] for x in contr]
    tail = depths[-3:] if len(depths) >= 3 else depths
    if not all(tail[i + 1] < tail[i] for i in range(len(tail) - 1)):
        return None
    if max(depths) > TH["vcp_first_max"] or depths[-1] > TH["vcp_last_max"]:
        return None
    pivot, last_low = contr[-1][0], contr[-1][1]
    base_days = len(d) - 1 - b_i
    if pivot < 0.80 * b_p or base_days < TH["vcp_min_base"]:
        return None
    vol_dry = float(np.mean(v[-10:]) / np.mean(v[-50:])) if np.mean(v[-50:]) > 0 else np.nan
    if np.isnan(vol_dry) or vol_dry > TH["vcp_vol_dry"]:
        return None
    dist = (c[-1] / pivot - 1) * 100
    if dist < -TH["vcp_near_pivot"] or dist > TH["extended_pct"]:
        return None
    entry = pivot * 1.001
    stop = max(last_low * 0.995, entry * (1 - MAX_STOP_PCT / 100))
    shares, riskp, posp = size_for(entry, stop)
    # 質素：最後一次收縮相對第一次縮了幾多（越小越好）
    quality = depths[-1] / depths[0] if depths[0] else np.nan
    return {"Ticker": t, "Pivot": pivot, "Dist%": dist, "Contr": f"{len(depths)}T " + "→".join(f"{x:.0f}" for x in depths) + "%",
            "Quality": quality, "VolDry": vol_dry, "BaseDays": int(base_days), "Stop": stop,
            "Risk%": riskp, "Shares": shares, "Pos%": posp, "State": "待突破" if dist <= 0 else "剛突破"}

vcp_rows = []
for t in F.index[F["TT"] & F["Liquid"]]:
    try:
        r = vcp_check(t)
        if r:
            vcp_rows.append(r)
    except Exception:
        pass
VCP = pd.DataFrame(vcp_rows)

def enrich(d):
    """為名單補上個股共用欄位。"""
    if d is None or len(d) == 0:
        return pd.DataFrame()
    d = d.copy()
    for col in ["SecETF", "SecRank", "RS", "RS12", "RS1M", "R21%", "R63%", "R126%", "R189%", "R252%", "DV50", "UD", "H3", "L3", "ATR%", "Stage", "Close", "Chg%", "VolX", "FromHigh%", "From50%", "From21%",
                "ExtATR", "RSLHigh", "SincePeak%", "Ret3D%", "Gap%", "R10%", "TightPct", "Vol10/50", "Pivot10", "Pivot52W", "VolOK"]:
        if col not in d.columns:
            d[col] = d["Ticker"].map(F[col])
    return d.reset_index(drop=True)

def pick(mask, sort, asc=False, n=None):
    idx = F[mask].sort_values(sort, ascending=asc).index
    d = enrich(pd.DataFrame({"Ticker": idx}))
    return d.head(n) if n else d

VCP = enrich(VCP).sort_values(["RS", "Dist%"], ascending=[False, False]).reset_index(drop=True) if len(VCP) else pd.DataFrame()
vcp_set = set(VCP["Ticker"]) if len(VCP) else set()

# ---------- v2 掃描 ----------
L_ = F["Liquid"]
# 收窄待發
TIGHT = pick(L_ & F["TT"] & (F["FromHigh%"] >= -TH["tight_from_high"]) & (F["TightPct"] <= TH["tight_pctile"])
             & (F["R10%"] <= TH["tight_r10_max"]) & ((F["Close"] / F["Pivot10"] - 1) * 100 >= TH["tight_dist_min"])
             & (F["Vol10/50"] <= TH["tight_vol"]) & ~F.index.isin(vcp_set), "RS")
if len(TIGHT):
    TIGHT["DistPivot%"] = (TIGHT["Close"] / TIGHT["Pivot10"] - 1) * 100
    TIGHT["TightPctD"] = TIGHT["TightPct"] * 100
# 新高突破（52 週高首日）
BO52 = pick(L_ & F["Fresh_52W"], ["VolOK", "RS"], asc=[False, False])
if len(BO52):
    BO52["Ext%"] = (BO52["Close"] / BO52["Pivot52W"] - 1) * 100
BO1M = pick(L_ & F["Fresh_1M"] & (F["Stage"] == "2 上升") & ~F["BO_52W"], "RS")
# 抗跌強勢：指數調整時仍貼近高位、RS 線創新高
RESIL = pick(L_ & (F["Stage"] == "2 上升") & (F["RS"] >= TH["resilient_rs"]) & (F["FromHigh%"] >= -TH["resilient_from_high"])
             & F["RSLHigh"] & (F["SincePeak%"] > 0) & (F["From50%"] <= TH["resilient_max_ext"]) & ~F["Fallen"],
             ["RS", "SincePeak%"], asc=[False, False])
# 回調買點：上升趨勢中回到 21EMA 或 50 日線、成交縮減
near21 = F["From21%"].between(-1.5, 2.0) & F["EMA21up"]
near50 = F["From50%"].between(-1.0, 3.0) & F["S50up"]
PULL = pick(L_ & F["TT"] & (F["RS"] >= TH["pullback_rs"]) & (near21 | near50) & (F["Close"] <= 0.97 * F["hi20"])
            & (F["Vol3/50"] <= 1.0), "RS")
if len(PULL):
    PULL["At"] = np.where(PULL["Ticker"].map(near21).fillna(False).astype(bool), "21EMA", "50 日線")
# 缺口
GAPUP = pick(L_ & (F["Gap%"] >= TH["gap_pct"]) & (F["VolX"] >= TH["gap_vol"]) & (F["ClosePos"] >= 0.5), "Gap%")
GAPDN = pick(L_ & (F["Gap%"] <= -TH["gap_pct"]) & (F["VolX"] >= TH["gap_vol"]) & (F["ClosePos"] <= 0.5), "Gap%", asc=True)
# 做空：回抽阻力（弱股反彈到下降中的均線）
S_RETEST = pick(L_ & (F["Stage"] == "4 下跌") & (F["RS"] <= TH["short_rs_max"]) & ~F["S50up"] & (F["Ret3D%"] > 0)
                & (F["From21%"].between(-3.0, 1.0) | F["From50%"].between(-4.0, 1.0)), "RS", asc=True)
# 做空：新跌破
BD = pick(L_ & (F["FreshBD_52W"] | (F["FreshBD_1M"] & (F["Stage"] == "4 下跌"))), "RS", asc=True)
if len(BD):
    ext = (BD["From50%"] <= -TH["short_ext_pct50"]) | (BD["ExtATR"] <= -TH["short_ext_atr"])
    BD["Risk"] = np.where(ext, "已超跌，不追", "初段")
    BD["New52L"] = BD["Ticker"].map(F["BD_52W"])
# 墮落龍頭：RS 仍高但已大幅跌離高位（RS 評級滯後，不要因為 RS 高而接）
FALLEN = pick(L_ & F["Fallen"], "FromHigh%", asc=True)

# ---------- 歷史新高 ----------
ATH = pd.DataFrame()
if FETCH_ATH:
    cand = F[L_ & (F["Close"] >= F["hi252"] * 0.98)].sort_values("RS", ascending=False).head(MAX_ATH_CHECK).index.tolist()
    if cand:
        print(f"確認歷史新高：下載 {len(cand)} 隻的全部歷史…")
        A = dl(cand, period="max", chunk=50)
        rows = []
        if "High" in A and "Close" in A:
            AH, AC = A["High"].loc[A["High"].index <= ASOF], A["Close"].loc[A["Close"].index <= ASOF]
            for t in [x for x in cand if x in AH.columns and x in AC.columns]:
                hs, cs = AH[t].dropna(), AC[t].dropna()
                if len(hs) < 260 or len(cs) < 3 or cs.index[-1] != ASOF:
                    continue
                ath_prior = hs.loc[hs.index < cs.index[-1]].max()
                ath_before_prev = hs.loc[hs.index < cs.index[-2]].max()
                c_now, c_prev = float(cs.iloc[-1]), float(cs.iloc[-2])
                is_ath = bool(c_now > ath_prior)
                rows.append({"Ticker": t, "ATH": hs.max(), "FromATH%": (c_now / hs.max() - 1) * 100, "IsATH": is_ath,
                             "FirstDay": bool(is_ath and not (c_prev > ath_before_prev)), "Years": f"{len(hs) / 252:.1f}"})
        ATH = pd.DataFrame(rows)
        if len(ATH):
            ATH = ATH[ATH["FromATH%"] >= -2.0]
        ATH = enrich(ATH).sort_values(["IsATH", "RS"], ascending=[False, False]).reset_index(drop=True) if len(ATH) else pd.DataFrame()
COUNTS["收市創歷史新高"] = int(ATH["IsATH"].sum()) if len(ATH) else 0
ath_set = set(ATH[ATH["IsATH"]]["Ticker"]) if len(ATH) else set()
if len(BO52):
    BO52["IsATH"] = BO52["Ticker"].isin(ath_set)

# ---------- High Tight Flag ----------
def htf_core(h, l, c, v):
    """旗桿：40 個交易日內升 ≥ 90%；旗形：其後 3–25 日橫行，回調不超過 25%。回傳 dict 或 None。"""
    n = len(c)
    if n < 30:
        return None
    look = min(n, TH["htf_top_window"])
    hi_pos = n - look + int(np.argmax(h[-look:]))
    days_since = n - 1 - hi_pos
    if days_since > TH["htf_flag_max"]:
        return None
    w0 = max(0, hi_pos - TH["htf_pole_max"])
    if hi_pos - w0 < 5:
        return None
    lo_pos = w0 + int(np.argmin(l[w0:hi_pos + 1]))
    pole_low, pole_high = l[lo_pos], h[hi_pos]
    if pole_low <= 0 or lo_pos >= hi_pos:
        return None
    gain = (pole_high / pole_low - 1) * 100
    if gain < TH["htf_pole_gain"]:
        return None
    flag_low = float(np.min(l[hi_pos:]))
    depth = (pole_high - flag_low) / pole_high * 100
    if depth > TH["htf_flag_depth"]:
        return None
    vol_pole = float(np.mean(v[lo_pos:hi_pos + 1]))
    vol_flag = float(np.mean(v[hi_pos + 1:])) if days_since >= 1 else np.nan
    # 旗桿內最大的單日升幅佔整支旗桿的比例：一日升完大半支旗桿，多數是收購或消息跳升，不是 High Tight Flag
    day_gain = c[lo_pos + 1:hi_pos + 1] / c[lo_pos:hi_pos] - 1 if hi_pos > lo_pos else np.array([0.0])
    jump = float(np.max(day_gain)) if len(day_gain) else 0.0
    jump_share = np.log1p(max(jump, 0)) / np.log(pole_high / pole_low)
    pinned = days_since >= 4 and depth < 2.5 and not np.isnan(vol_flag) and vol_pole > 0 and vol_flag / vol_pole < 0.4
    note = ("單日跳升，疑似收購或消息" if jump_share >= 0.6 else "鎖價，疑似收購" if pinned
            else "單日大升後橫行，疑似收購或消息" if (jump >= 0.40 and days_since >= 3 and depth < 6) else "")
    return {"Jump%": jump * 100, "Note": note, "Pivot": float(pole_high), "PoleGain%": gain, "PoleDays": int(hi_pos - lo_pos), "FlagDays": int(days_since),
            "FlagDepth%": depth, "FlagLow": flag_low, "VolR": (vol_flag / vol_pole if vol_pole > 0 else np.nan),
            "State": "旗桿中" if days_since < TH["htf_flag_min"] else "旗形中"}

def htf_check(h, l, c, v):
    """先看昨日是否仍在旗形而今日收市升穿旗桿高位（突破旗形），否則回傳今日的狀態。"""
    prev = htf_core(h[:-1], l[:-1], c[:-1], v[:-1]) if len(c) > 31 else None
    if prev is not None and prev["State"] == "旗形中" and c[-1] > prev["Pivot"]:
        prev["State"] = "突破旗形"
        prev["FlagDays"] += 1
        res = prev
    else:
        res = htf_core(h, l, c, v)
    if res is None:
        return None
    res["Close"] = float(c[-1])
    res["Dist%"] = (c[-1] / res["Pivot"] - 1) * 100
    entry = res["Pivot"] * 1.001 if res["State"] != "突破旗形" else float(c[-1])
    stop = max(res["FlagLow"] * 0.995, entry * (1 - MAX_STOP_PCT / 100))
    if res["State"] == "旗桿中":                       # 旗形未形成，未有入場計劃
        res["Stop"], res["Shares"], res["Risk%"], res["Pos%"] = np.nan, np.nan, np.nan, np.nan
    else:
        res["Stop"] = stop
        res["Shares"], res["Risk%"], res["Pos%"] = size_for(entry, stop)
    return res

def htf_scan(Hx, Lx, Cx, Vx, tickers, src):
    rows = []
    for t in tickers:
        try:
            d = pd.DataFrame({"h": Hx[t], "l": Lx[t], "c": Cx[t], "v": Vx[t]}).dropna().tail(90)
            if len(d) < 30 or d.index[-1] != ASOF:
                continue
            r = htf_check(d["h"].values, d["l"].values, d["c"].values, d["v"].values)
            if r:
                r["Ticker"], r["Src"] = t, src
                r["DV20M"] = float((d["c"] * d["v"]).tail(20).mean() / 1e6)
                rows.append(r)
        except Exception:
            pass
    return rows

HTF, HTF_NOTE = pd.DataFrame(), ""
NAME_OF = {}                                                 # 代號 → 公司名稱（來自 nasdaq.com 篩選器）
HTF_PX = {}                                                  # v6：池外 High Tight Flag 股票的日線（畫縮圖用）

def nasdaq_screener():
    """全美上市股票名單（nasdaq.com 篩選器）。回傳 DataFrame：symbol, price, mcap, dv, industry。"""
    j = requests.get("https://api.nasdaq.com/api/screener/stocks?tableonly=true&limit=25&offset=0&download=true",
                     headers={**UA, "Accept": "application/json, text/plain, */*"}, timeout=45).json()
    data = j.get("data") or {}
    rows = data.get("rows") or (data.get("table") or {}).get("rows") or []
    d = pd.DataFrame(rows)
    num = lambda x: pd.to_numeric(x.astype(str).str.replace(r"[$,%]", "", regex=True), errors="coerce")
    out = pd.DataFrame({"symbol": d["symbol"].astype(str).str.strip().str.upper(),
                        "price": num(d["lastsale"]), "mcap": num(d["marketCap"]), "vol": num(d["volume"]),
                        "industry": d["industry"].astype(str) if "industry" in d.columns else "",
                        "name": d["name"].astype(str) if "name" in d.columns else ""})
    out["dv"] = out["price"] * out["vol"]
    return out

def run_htf():
    """先掃股票池，再（可選）掃池外的全美上市股票。"""
    global HTF, HTF_NOTE
    rows = htf_scan(H, L, C, V, list(F.index[F["Liquid"] & (F["Close"] > F["s50"])]), "股票池")
    ind_of = {}
    if HTF_WIDE_SCAN:
        try:
            sc = nasdaq_screener()
            ind_of = sc.set_index("symbol")["industry"].to_dict()
            NAME_OF.update({str(k).replace(".", "-").replace("/", "-"): v for k, v in sc.set_index("symbol")["name"].to_dict().items()})
            sc = sc[sc["symbol"].str.fullmatch(r"[A-Z]{1,5}") & (sc["price"] >= TH["htf_wide_min_price"])
                    & (sc["mcap"] >= TH["htf_wide_min_mcap"]) & (sc["dv"] >= TH["htf_wide_min_dv"] / 2) & ~sc["symbol"].isin(TICKS)]
            wide = sc.sort_values("dv", ascending=False)["symbol"].head(TH["htf_wide_max"]).tolist()
            print(f"High Tight Flag 全市場掃描：下載股票池以外的 {len(wide)} 隻（6 個月日線）…")
            Wd = dl(wide, period="6mo", chunk=150, pause=0.8, label="全市場")
            if "Close" in Wd:
                wc = Wd["Close"]
                wt = [t for t in wc.columns if t in Wd["High"].columns and t in Wd["Low"].columns and t in Wd["Volume"].columns]
                wrows = htf_scan(Wd["High"], Wd["Low"], wc, Wd["Volume"], wt, "全市場")
                for _wr in wrows:                                # v6：留下這些股票的日線，畫縮圖用
                    try:
                        _wt = _wr["Ticker"]
                        HTF_PX[_wt] = pd.DataFrame({"o": Wd["Open"][_wt] if ("Open" in Wd and _wt in Wd["Open"].columns) else wc[_wt],
                                                    "h": Wd["High"][_wt], "l": Wd["Low"][_wt], "c": wc[_wt],
                                                    "v": Wd["Volume"][_wt]}).dropna(subset=["h", "l", "c"])
                    except Exception:
                        pass
                rows += [r for r in wrows if r["DV20M"] * 1e6 >= TH["htf_wide_min_dv"]]
                HTF_NOTE = f"已掃股票池內流動性合格的 {int(F['Liquid'].sum())} 隻，和池外 {len(wt)} 隻。"
            else:
                HTF_NOTE = "全市場數據下載失敗，只掃了股票池。"
        except Exception as e:
            HTF_NOTE = f"全市場名單取不到（{type(e).__name__}），只掃了股票池。"
    else:
        HTF_NOTE = "只掃了股票池。大型和中型股很少在 8 週內升近一倍。"
    d = pd.DataFrame(rows)
    if len(d):
        d["RS"] = d["Ticker"].map(F["RS"])
        _ind = lambda t: next((x for x in (SUB_OF.get(t), ind_of.get(t)) if isinstance(x, str) and x and x.lower() != "nan"), "")
        d["Ind"] = [_ind(t) for t in d["Ticker"]]
        d["_o"] = d["State"].map({"突破旗形": 0, "旗形中": 1, "旗桿中": 2}) + (d["Note"] != "") * 10    # 疑似收購的排到最後
        d = d.sort_values(["_o", "PoleGain%"], ascending=[True, False]).drop(columns="_o").reset_index(drop=True)
    HTF = d
    n_ok = int((d["Note"] == "").sum()) if len(d) else 0
    print(f"High Tight Flag：{n_ok} 隻" + (f"（另有 {len(d) - n_ok} 隻疑似收購或消息跳升）" if len(d) > n_ok else ""))

# ---------- 板塊與行業組別 ----------
def etf_table(symbols):
    rows = []
    spy = mser("SPY", "Adj Close")
    for s, name in symbols.items():
        a, c, hi = mser(s, "Adj Close"), mser(s, "Close"), mser(s, "High")
        if a is None or c is None:
            continue
        r21, r63 = (a.iloc[-1] / a.iloc[-22] - 1) * 100, (a.iloc[-1] / a.iloc[-64] - 1) * 100
        spy21 = (spy.iloc[-1] / spy.iloc[-22] - 1) * 100 if spy is not None else np.nan
        rows.append({"ETF": s, "Name": name, "R21": r21, "R63": r63, "Ex21": r21 - spy21,
                     "Above50": bool(c.iloc[-1] > c.rolling(50).mean().iloc[-1]),
                     "FromHigh": (c.iloc[-1] / (hi if hi is not None else c).rolling(252).max().iloc[-1] - 1) * 100})
    d = pd.DataFrame(rows)
    return d.sort_values("R21", ascending=False).reset_index(drop=True) if len(d) else d

SECT_TBL, IND_TBL = etf_table(SECTOR_ETFS), etf_table(INDUSTRY_ETFS)
sec_b = liqF[liqF["SecETF"] != ""].groupby("SecETF").agg(
    n=("Close", "size"), pct50=("Above50", "mean"), pct200=("Above200", "mean"),
    nh=("BO_52W", "sum"), nl=("BD_52W", "sum"))
if len(SECT_TBL):
    SECT_TBL["Pct50"] = SECT_TBL["ETF"].map(sec_b["pct50"] * 100)
    SECT_TBL["NH"] = SECT_TBL["ETF"].map(sec_b["nh"])
    SECT_TBL["NL"] = SECT_TBL["ETF"].map(sec_b["nl"])
grp = liqF[liqF["SubInd"].astype(str).str.len() > 0].groupby("SubInd").agg(
    n=("Close", "size"), r21=("R21%", "median"), r63=("R63%", "median"), pct50=("Above50", "mean"),
    rs=("RS", "median"), nh=("BO_52W", "sum"))
grp = grp[grp["n"] >= 4].copy()
if len(grp):
    grp["pct50"] *= 100
    grp["score"] = (grp["r21"].rank(pct=True) + grp["r63"].rank(pct=True) + grp["pct50"].rank(pct=True)) / 3
    grp = grp.sort_values("score", ascending=False)
    def _top_names(g):
        m = liqF[liqF["SubInd"] == g].sort_values("RS", ascending=False).head(3)
        return "、".join(m.index)
    GRP_TOP = grp.head(8).reset_index()
    GRP_BOT = grp.tail(8).iloc[::-1].reset_index()
    GRP_TOP["Names"] = GRP_TOP["SubInd"].map(_top_names)
    GRP_BOT["Names"] = GRP_BOT["SubInd"].map(_top_names)
else:
    GRP_TOP = GRP_BOT = pd.DataFrame()
LEAD_TBL = enrich(pd.DataFrame({"Ticker": LEAD}))

# ---------- 隔夜與盤前 ----------
print("取期貨與盤前數據…")
CLOSE_CUT = pd.Timestamp(ASOF.date()).tz_localize(ET) + pd.Timedelta(hours=13 if ASOF.date() in EARLY_CLOSES else 16)
def since_close_table():
    px = intraday_close(list(OVERNIGHT), interval="15m")
    rows, nq = [], np.nan
    for s, name in OVERNIGHT.items():
        if s not in px.columns:
            continue
        x = px[s].dropna()
        ref = x[x.index < CLOSE_CUT]
        if not len(x) or not len(ref):
            continue
        # 指數類（VIX、孳息）收市後只多印一兩個報價，不算隔夜變動
        fresh = x.index[-1] > CLOSE_CUT + pd.Timedelta(minutes=45 if s.startswith("^") else 0)
        if s == "^TNX":
            ch = (x.iloc[-1] - ref.iloc[-1]) * 100 if fresh else np.nan
            txt = "—" if np.isnan(ch) else f"{ch:+.1f}bp"
        else:
            ch = (x.iloc[-1] / ref.iloc[-1] - 1) * 100 if fresh else np.nan
            txt = "—" if np.isnan(ch) else f"{ch:+.2f}%"
        if s == "NQ=F":
            nq = ch
        rows.append({"Name": name, "Last": x.iloc[-1], "Chg": txt, "ChgV": ch,
                     "Time": f"{x.index[-1]:%m-%d %H:%M}" if fresh else "收市後未有新報價"})
    return pd.DataFrame(rows), nq
try:
    OVN, NQ_CHG = since_close_table()
except Exception as e:
    print(f"  期貨數據取不到（{type(e).__name__}）")
    OVN, NQ_CHG = pd.DataFrame(), np.nan

def latest_after_close(symbols):
    """收市後或盤前的最新報價：{代號: (價, 時間)}；只接受晚於數據日收市的報價。"""
    px = intraday_close(symbols, interval="5m")
    out = {}
    for s in px.columns:
        x = px[s].dropna()
        if len(x) and x.index[-1] > CLOSE_CUT + pd.Timedelta(minutes=5):
            out[s] = (float(x.iloc[-1]), x.index[-1])
    return out

watch_all = []
for d_, n_ in [(VCP, 10), (TIGHT, 8), (BO52, 8), (RESIL, 10), (PULL, 8), (GAPUP, 5), (S_RETEST, 8), (BD, 6)]:
    if len(d_):
        watch_all += list(d_["Ticker"].head(n_))
WATCH = list(dict.fromkeys(watch_all))

# ---------- 事件：財報日曆與反應、經濟日曆、日曆因素 ----------
ECON = EARN_REACT = EARN_NEXT = pd.DataFrame()
NEWS, ECON_NOTE, EARN_NOTE, CAL_FLAGS = [], "", "", []
TIER1 = ["cpi", "payroll", "fomc", "fed funds", "pce price", "core pce", "interest rate decision"]
TIER2 = ["ppi", "unemployment rate", "initial jobless", "ism", "retail sales", "gdp", "u mich", "consumer confidence",
         "philly fed business", "jolts", "adp", "durable", "empire", "ny fed manufacturing"]
TIER3 = ["housing starts", "build permits", "existing home", "new home sales", "leading index", "cont jobless", "jobless clm 4wk"]
def econ_tier(name):
    s = str(name).lower()
    return "★★★" if any(k in s for k in TIER1) else "★★" if any(k in s for k in TIER2) else "★" if any(k in s for k in TIER3) else ""

# 日曆因素：提早收市、休市、期權結算
_next2 = next_session(SESS_D)
_opex = opex_date(SESS_D.year, SESS_D.month)
if SESS_D in EARLY_CLOSES:
    CAL_FLAGS.append(f"{SESS_D:%m-%d} 是{EARLY_CLOSES[SESS_D]}，美東 13:00 提早收市，成交偏低。")
if SESS_D == _opex:
    CAL_FLAGS.append(f"{SESS_D:%m-%d} 是{'季度四巫日' if SESS_D.month % 3 == 0 else '月度期權結算日'}，成交量失真，突破和 FTD 的成交確認要打折。")
elif _next2 == _opex:
    CAL_FLAGS.append(f"下一個交易日（{_opex:%m-%d}）是{'季度四巫日' if _opex.month % 3 == 0 else '月度期權結算日'}。")
for _k in range(1, 8):
    _d = SESS_D + _dt.timedelta(days=_k)
    if _d in HOLIDAYS:
        CAL_FLAGS.append(f"{_d:%m-%d} {HOLIDAYS[_d]}休市。")
    elif _d in EARLY_CLOSES:
        CAL_FLAGS.append(f"{_d:%m-%d} {EARLY_CLOSES[_d]}，13:00 提早收市。")

PEND = []                                                    # 已公佈、但股價反應要到下一個交易日才出現的公司
if FETCH_EVENTS:
    print("取財報日曆、經濟日曆…")
    d_prev, d_end = f"{CAL[-2]:%Y-%m-%d}", f"{_next2:%Y-%m-%d}"
    try:
        frames = []
        cal = yf.Calendars(start=d_prev, end=d_end)
        for off in (0, 100, 200, 300, 400):
            part = cal.get_earnings_calendar(filter_most_active=False, limit=100, offset=off, force=True).reset_index()
            frames.append(part)
            if len(part) < 100:
                break
        ea = pd.concat(frames, ignore_index=True).drop_duplicates("Symbol") if frames else pd.DataFrame()
        if len(ea):
            ea = ea[ea["Symbol"].isin(TICKS)].copy()            # 只留股票池內的公司
        if len(ea) and "Event Start Date" in ea.columns:
            ea["_t"] = pd.to_datetime(ea["Event Start Date"], errors="coerce", utc=True).dt.tz_convert(ET)
            ea = ea[ea["_t"].notna()]
            ea["_d"] = ea["_t"].dt.date
            hr = ea["_t"].dt.hour + ea["_t"].dt.minute / 60
            tm = ea["Timing"].astype(str).str.upper() if "Timing" in ea.columns else pd.Series("", index=ea.index)
            # BMO 開市前；AMC 收市後；TAS 表示時間已列明，按鐘點判斷；TNS 沒有時間
            ea["Slot"] = np.select([tm.eq("BMO"), tm.eq("AMC"), tm.eq("TAS") & (hr < 9.5), tm.eq("TAS") & (hr >= 16), tm.eq("TAS")],
                                   ["開市前", "收市後", "開市前", "收市後", "盤中"], default="時間不明")
            ea["ReactDay"] = [d if sl in ("開市前", "盤中") else next_session(d) if sl == "收市後" else None
                              for d, sl in zip(ea["_d"], ea["Slot"])]
            ea["When"] = ea["_t"].dt.strftime("%m-%d") + " " + ea["Slot"]
            for col in ["DV50", "RS", "Stage", "Chg%", "VolX", "Gap%"]:
                ea[col] = ea["Symbol"].map(F[col])
            ea["Surp"] = pd.to_numeric(ea["Surprise(%)"], errors="coerce") if "Surprise(%)" in ea.columns else np.nan
            ea = ea.sort_values("DV50", ascending=False)
            done = ea[ea["ReactDay"] == ASOF.date()].copy()                       # 反應已在數據日出現
            pend = ea[(ea["ReactDay"] == SESS_D) & (ea["_d"] <= ASOF.date())].copy()   # 上日收市後公佈，今日才反應
            unk = ea[ea["ReactDay"].isna() & (ea["_d"] == ASOF.date())].copy()    # 時間不明：有明顯異動才當作已反應
            unk = unk[(unk["Chg%"].abs() >= 3) | (unk["VolX"] >= 1.8)]
            done = pd.concat([done, unk], ignore_index=True)
            done["Move"], done["Src"] = done["Chg%"], "數據日全日"
            pend["Move"], pend["Src"] = np.nan, "待開市"
            PEND = pend["Symbol"].tolist()
            EARN_REACT = pd.concat([done, pend], ignore_index=True)
            EARN_NEXT = ea[ea["_d"] >= SESS_D].copy()
        if not len(EARN_REACT) and not len(EARN_NEXT):
            EARN_NOTE = "財報日曆在這幾日沒有列出股票池內的公司。"
    except Exception as e:
        EARN_NOTE = "財報日曆暫時未能提供。"
        print(f"  財報日曆出錯：{type(e).__name__}")
    try:
        ec = yf.Calendars(start=f"{SESS_D:%Y-%m-%d}", end=d_end).get_economic_events_calendar(limit=100).reset_index()
        if "Region" in ec.columns:
            ec = ec[ec["Region"].astype(str).str.upper().isin(["US", "USA", "UNITED STATES"])]
        if "Event Time" in ec.columns:
            tt = pd.to_datetime(ec["Event Time"], errors="coerce", utc=True).dt.tz_convert(ET)
            ec = ec.assign(_t=tt).sort_values("_t")
            ec["When"] = ec["_t"].dt.strftime("%m-%d %H:%M")
            ec["_d"] = ec["_t"].dt.date
        ec["Tier"] = (ec["Event"] if "Event" in ec.columns else pd.Series("", index=ec.index)).map(econ_tier)
        ECON = ec[ec["Tier"] != ""]
        if not len(ECON):
            ECON_NOTE = "這兩日沒有列出重點數據。"
    except Exception as e:
        ECON_NOTE = "經濟日曆暫時未能提供。"
        print(f"  經濟日曆出錯：{type(e).__name__}")
# ---------- 補充數據層・事件（v5.2）：Nasdaq 財報日曆覆蓋整個股票池；Nasdaq 經濟日曆補上聯儲局講話和市場預期 ----------
OBB_EARN_WINDOW = 15                                         # 財報日曆向前取多少個交易日
OBB_EARN, OBB_EARN_FULL, OBB_WIN_END = {}, False, None       # 代號 →（財報日、時段）；整段期間是否都取到；期間最後一日
EARN_SRC, ECON_SRC, OBB_TZ_NOTE = "Yahoo", "Yahoo", ""
OBB_ECON, OBB_ONLY_N, OBB_ONLY_Y = pd.DataFrame(), [], []

def _nq_sym(s):
    return str(s).strip().upper().replace(".", "-").replace("/", "-")

def nq_earnings_day(dd):
    """Nasdaq 財報日曆的一日。回傳原始欄位，另加 report_date。"""
    data = nq_get(f"calendar/earnings?date={dd:%Y-%m-%d}") or {}
    df = pd.DataFrame(data.get("rows") or [])
    if len(df):
        asof = pd.to_datetime(data.get("asOf"), errors="coerce")
        df["report_date"] = asof.date() if pd.notna(asof) else dd
    return df

def obb_earnings():
    """取 Nasdaq 財報日曆（上一個收市日至未來 OBB_EARN_WINDOW 個交易日），整理成與 Yahoo 版本相同的表。"""
    t0 = time.time()
    days, d = [CAL[-2].date(), ASOF.date()], SESS_D
    for _ in range(OBB_EARN_WINDOW + 1):
        days.append(d)
        d = next_session(d)
    days = list(dict.fromkeys(days))
    import concurrent.futures as _cf
    frames, okdays, note = [], set(), ""
    def one(dd):
        return dd, _direct("", lambda: nq_earnings_day(dd), log=False)
    with _cf.ThreadPoolExecutor(max_workers=4) as ex:        # 四條線同時取，18 日約需十秒
        res = list(ex.map(one, days))
    failed = [dd for dd, (dfi, _, _) in res if dfi is None]
    if 0 < len(failed) <= 6:                                 # 少數幾日失敗：逐日再試一次
        redo = {dd: _direct("", lambda dd=dd: nq_earnings_day(dd), log=False) for dd in failed}
        res = [(dd, redo.get(dd, r)) for dd, r in res]
    for dd, (dfi, _, notei) in res:
        if dfi is None:
            note = notei or note
        else:
            okdays.add(dd)
            if len(dfi):
                frames.append(dfi)
    df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    full = len(okdays) == len(days) and len(df) > 0
    OBB_LOG.append({"Feed": "財報日曆（Nasdaq 直連）", "Status": "成功" if full else "部分成功" if (okdays and len(df)) else "失敗",
                    "Rows": len(df), "Sec": time.time() - t0,
                    "Note": f"{len(okdays)}/{len(days)} 日" + ("" if full or not note else f"；{note}")})
    if not len(df):
        return None
    nq = _need(df, ["report_date", "symbol", "name", "time", "surprise"])
    nq["Symbol"] = nq["symbol"].map(_nq_sym)
    nq["_d"] = pd.to_datetime(nq["report_date"], errors="coerce").dt.date
    nq = nq[pd.notna(nq["_d"])].drop_duplicates(["Symbol", "_d"]).copy()
    rt = nq["time"].astype(str).str.lower()                  # time-pre-market／time-after-hours／time-not-supplied
    nq["Slot"] = np.where(rt.str.contains("pre"), "開市前", np.where(rt.str.contains("after"), "收市後", "時間不明"))
    fut = nq[nq["_d"] >= ASOF.date()].sort_values("_d").drop_duplicates("Symbol")
    earn_map = {s: (dd, sl) for s, dd, sl in zip(fut["Symbol"], fut["_d"], fut["Slot"])}
    ea = nq[nq["Symbol"].isin(TICKS)].copy()                 # 只留股票池內的公司
    ea["Company"] = ea["name"].astype(str)
    ea["ReactDay"] = [dd if sl == "開市前" else next_session(dd) if sl == "收市後" else None for dd, sl in zip(ea["_d"], ea["Slot"])]
    ea["When"] = [f"{dd:%m-%d} {sl}" for dd, sl in zip(ea["_d"], ea["Slot"])]
    for col in ["DV50", "RS", "Stage", "Chg%", "VolX", "Gap%"]:
        ea[col] = ea["Symbol"].map(F[col])
    ea["Surp"] = _num(ea["surprise"])                        # Nasdaq 的盈利驚喜本身是百分比
    ea = ea.sort_values("DV50", ascending=False)
    done = ea[ea["ReactDay"] == ASOF.date()].copy()                                # 反應已在數據日出現
    pend = ea[(ea["ReactDay"] == SESS_D) & (ea["_d"] <= ASOF.date())].copy()       # 上日收市後公佈，今日才反應
    unk = ea[ea["ReactDay"].isna() & (ea["_d"] == ASOF.date())].copy()             # 時間不明：有明顯異動才當作已反應
    unk = unk[(unk["Chg%"].abs() >= 3) | (unk["VolX"] >= 1.8)]
    done = pd.concat([done, unk], ignore_index=True)
    done["Move"], done["Src"] = done["Chg%"], "數據日全日"
    pend["Move"], pend["Src"] = np.nan, "待開市"
    react = pd.concat([done, pend], ignore_index=True)
    nxt = ea[(ea["_d"] >= SESS_D) & (ea["_d"] <= _next2)].copy()
    key_ok = all(x in okdays for x in (CAL[-2].date(), ASOF.date(), SESS_D, _next2))
    return {"react": react, "next": nxt, "pend": pend["Symbol"].tolist(), "map": earn_map, "full": full,
            "key_ok": key_ok, "win_end": days[-1]}

def nq_econ_days(days):
    """Nasdaq 經濟日曆的美國項目。回傳 date（字串，含鐘點）、event、consensus、previous、actual。"""
    rows = []
    for dd in days:
        data = nq_get(f"calendar/economicevents?date={dd:%Y-%m-%d}") or {}
        for it in (data.get("rows") or []):
            g = str(it.get("gmt") or "").strip()
            hhmm = g if re.fullmatch(r"\d{1,2}:\d{2}", g) else "00:00"       # 全日或時間待定的項目沒有鐘點
            rows.append({"date": f"{dd:%Y-%m-%d} {hhmm}", "country": str(it.get("country") or ""), "event": it.get("eventName"),
                         "consensus": it.get("consensus"), "previous": it.get("previous"), "actual": it.get("actual")})
        time.sleep(0.1)
    df = pd.DataFrame(rows)
    return df[df["country"].str.strip().str.lower() == "united states"].reset_index(drop=True) if len(df) else df

def econ_tier_n(name):
    """Nasdaq 日曆的事件名稱與 Yahoo 不同，另外分級。官員講話只有主席算三星，否則幾乎每日都是事件日。"""
    s = str(name).lower()
    if any(k in s for k in ("speak", "speech", "testif", "remarks")):
        return "★★★" if (("chair" in s and "vice" not in s) or "powell" in s) else "★★"
    if "gdpnow" in s or "continuing jobless" in s or "building permits" in s:
        return "★"
    if any(k in s for k in ("non farm", "nonfarm", "fed interest rate", "fomc", "core pce", "pce price")):
        return "★★★"
    if any(k in s for k in ("jobless claims", "philly fed", "philadelphia fed", "michigan")):
        return "★★"
    return econ_tier(name)

def obb_econ():
    """取 Nasdaq 經濟日曆（美國）。Nasdaq 不提供重要性，仍用關鍵字分級；時區由數據本身核對。"""
    ec, _, _ = _direct("經濟日曆（Nasdaq 直連）", lambda: nq_econ_days(list(dict.fromkeys([SESS_D, _next2]))))
    if ec is None or not len(ec):
        return None
    ec = _need(ec, ["date", "event", "consensus", "previous", "actual"])
    raw = pd.to_datetime(ec["date"], errors="coerce")
    keep = raw.notna()
    ec, raw = ec[keep].copy(), raw[keep]
    if not len(ec):
        return None
    hm = raw.dt.strftime("%H:%M")
    off = int(round(-pd.Timestamp(SESS_D).tz_localize(ET).utcoffset().total_seconds() / 3600))   # 美東比 GMT 慢 4 或 5 小時
    n_et, n_gmt = int((hm == "08:30").sum()), int((hm == f"{8 + off:02d}:30").sum())            # 美國數據多數在美東 08:30 公佈
    is_gmt = n_gmt >= n_et
    tz_note = ("Nasdaq 日曆的時間按 GMT 換算成美東。" if n_gmt > n_et else "Nasdaq 日曆的時間本身已是美東。" if n_et > n_gmt
               else "未能從數據確認 Nasdaq 日曆的時區，暫按 GMT 換算，時間只供參考。")
    t = raw.dt.tz_localize("UTC").dt.tz_convert(ET) if is_gmt else raw.dt.tz_localize(ET, ambiguous="NaT", nonexistent="NaT")
    allday = (hm == "00:00").to_numpy()                      # 全日或時間待定的項目不換算時區
    ec["_d"] = np.where(allday, raw.dt.date.to_numpy(), t.dt.date.to_numpy())
    ec["When"] = np.where(allday, (raw.dt.strftime("%m-%d") + " 待定").to_numpy(), t.dt.strftime("%m-%d %H:%M").to_numpy())
    ec["Event"] = ec["event"].astype(str)
    for src, dst in (("consensus", "Expected"), ("previous", "Last"), ("actual", "Actual")):
        ec[dst] = [None if (isnan(v) or str(v).replace("&nbsp;", "").strip() in ("", "-")) else str(v).replace("&nbsp;", "").strip() for v in ec[src]]
    ec["For"] = ""
    ec["Tier"] = ec["Event"].map(econ_tier_n)
    out = ec[ec["Tier"] != ""].sort_values("When")[["Tier", "When", "Event", "For", "Expected", "Last", "Actual", "_d"]]
    return out.reset_index(drop=True), tz_note

if FETCH_EVENTS and USE_OPENBB:
    print("補充數據層：直接向 Nasdaq 取財報日曆和經濟日曆…")
    try:
        _oe = obb_earnings()
        if _oe:
            OBB_EARN, OBB_EARN_FULL, OBB_WIN_END = _oe["map"], _oe["full"], _oe["win_end"]
            if _oe["key_ok"]:                                # 關鍵的四日都取到，才以 Nasdaq 為主；Yahoo 多列出的公司補在後面
                _ys = (set(EARN_REACT["Symbol"]) if len(EARN_REACT) else set()) | (set(EARN_NEXT["Symbol"]) if len(EARN_NEXT) else set())
                _ns = set(_oe["react"]["Symbol"]) | set(_oe["next"]["Symbol"])
                _yr = EARN_REACT[~EARN_REACT["Symbol"].isin(_ns)] if len(EARN_REACT) else pd.DataFrame()
                _yn = EARN_NEXT[~EARN_NEXT["Symbol"].isin(_ns)] if len(EARN_NEXT) else pd.DataFrame()
                _ysurp = ({s_: v_ for s_, v_ in zip(EARN_REACT["Symbol"], EARN_REACT["Surp"]) if not isnan(v_)}
                          if (len(EARN_REACT) and "Surp" in EARN_REACT.columns) else {})
                if len(_oe["react"]):                        # Nasdaq 剛公佈時多數未有盈利驚喜，用 Yahoo 的補上
                    _oe["react"]["Surp"] = [v_ if not isnan(v_) else _ysurp.get(s_, np.nan)
                                            for s_, v_ in zip(_oe["react"]["Symbol"], _oe["react"]["Surp"])]
                _react = pd.concat([_oe["react"], _yr], ignore_index=True) if len(_yr) else _oe["react"]
                _nextt = pd.concat([_oe["next"], _yn], ignore_index=True).sort_values("DV50", ascending=False) if len(_yn) else _oe["next"]
                _pend = _oe["pend"] + [t for t in PEND if t not in _ns]
                if _ys:
                    OBB_ONLY_N, OBB_ONLY_Y = sorted(_ns - _ys), sorted(_ys - _ns)
                EARN_REACT, EARN_NEXT, PEND = _react, _nextt, _pend
                EARN_SRC = "Nasdaq，Yahoo 補充" if (len(_yr) or len(_yn)) else "Nasdaq"
                EARN_NOTE = "" if (len(EARN_REACT) or len(EARN_NEXT)) else "財報日曆在這幾日沒有列出股票池內的公司。"
    except Exception as e:
        OBB_ERR.append(f"Nasdaq 財報日曆處理出錯（{type(e).__name__}: {' '.join(str(e).split())[:160]}），已沿用 Yahoo 的結果。")
    try:
        _oc = obb_econ()
        if _oc:
            OBB_ECON, OBB_TZ_NOTE = _oc
            _ecols = ["Tier", "When", "Event", "For", "Expected", "Last", "_d"]
            if len(OBB_ECON) and not len(ECON):
                ECON, ECON_SRC, ECON_NOTE = OBB_ECON, "Nasdaq", ""
            elif len(OBB_ECON) and all(c_ in ECON.columns for c_ in ("When", "_d", "Event", "Tier")):
                # 兩個日曆合併：同一日同一鐘點而名稱有共同字眼的，當作同一項，保留 Yahoo 的一行
                _tok = lambda x: {("philly" if w_ == "philadelphia" else w_) for w_ in re.findall(r"[a-z]{5,}", str(x).lower())}
                _yk = [(d_, str(w_)[-5:], _tok(e_)) for d_, w_, e_ in zip(ECON["_d"], ECON["When"], ECON["Event"])]
                _new = [not any(d_ == yd and str(w_)[-5:] == yt and (_tok(e_) & ytok) for yd, yt, ytok in _yk)
                        for d_, w_, e_ in zip(OBB_ECON["_d"], OBB_ECON["When"], OBB_ECON["Event"])]
                _add = OBB_ECON[_new]
                if len(_add):
                    ECON = pd.concat([ECON, _add[_ecols]], ignore_index=True).sort_values("When").reset_index(drop=True)
                    ECON_SRC, ECON_NOTE = "Yahoo＋Nasdaq", ""
    except Exception as e:
        OBB_ERR.append(f"Nasdaq 經濟日曆處理出錯（{type(e).__name__}: {' '.join(str(e).split())[:160]}），已沿用 Yahoo 的結果。")

EVENT_DAY = bool(len(ECON) and "_d" in ECON.columns and ((ECON["Tier"] == "★★★") & (ECON["_d"] == SESS_D)).any())
if EVENT_DAY:
    _ev = ECON[(ECON["Tier"] == "★★★") & (ECON["_d"] == SESS_D)]
    CAL_FLAGS.insert(0, "今日是事件日：" + "、".join(f"{r.When[-5:]} {r.Event}" for r in _ev.itertuples()) + "。規則把公佈前的示範注碼減半。")

PM = latest_after_close(["QQQ", "SPY", "IWM"] + WATCH + list(POSITIONS) + PEND[:25])
if len(EARN_REACT):
    m_ = EARN_REACT["Src"] == "待開市"
    EARN_REACT.loc[m_, "Move"] = [(PM[t][0] / F.at[t, "Close"] - 1) * 100 if t in PM else np.nan for t in EARN_REACT.loc[m_, "Symbol"]]
    EARN_REACT.loc[m_ & EARN_REACT["Move"].notna(), "Src"] = "盤後／盤前"
    def _verdict(r):
        mv, sp = r["Move"], r["Surp"]
        if isnan(mv):
            return "沒有價格數據" if r.get("Src") == "數據日全日" else "待開市"
        beat, miss = (not isnan(sp) and sp >= 2), (not isnan(sp) and sp <= -2)      # 驚喜在 ±2% 以內當作符合預期
        if beat and mv <= -1:
            return "勝預期但跌：弱"
        if miss and mv >= 1:
            return "遜預期但升：強"
        if beat and mv >= 1:
            return "勝預期，升"
        if miss and mv <= -1:
            return "遜預期，跌"
        if not isnan(sp) and abs(sp) < 2 and abs(mv) >= 3:
            return "符合預期，" + ("大升" if mv > 0 else "大跌")
        return "大升" if mv >= 3 else "大跌" if mv <= -3 else "反應平淡"
    EARN_REACT["Verdict"] = EARN_REACT.apply(_verdict, axis=1)
    EARN_REACT["IsLead"] = EARN_REACT["Symbol"].isin(LEAD)

# 盤前異動（只在美東 4:00–9:35 的交易日執行才有數據）
PMG = pd.DataFrame()
t_ = now_et()
IN_PREMARKET = is_session(t_.date()) and (4, 0) <= (t_.hour, t_.minute) < (9, 35)
if SCAN_PREMARKET and IN_PREMARKET:
    print("掃描盤前異動…")
    top_liq = liqF.sort_values("DV50", ascending=False).head(TH["premarket_top_n"]).index.tolist()
    pmq = latest_after_close(top_liq)
    rows = [{"Ticker": t, "PM": v[0], "PMGap%": (v[0] / F.at[t, "Close"] - 1) * 100} for t, v in pmq.items() if t in F.index]
    PMG = pd.DataFrame(rows)
    if len(PMG):
        PMG = PMG[PMG["PMGap%"].abs() >= TH["premarket_gap"]].sort_values("PMGap%", ascending=False)
    if len(PMG):
        PMG = enrich(PMG)
        PMG["InList"] = PMG["Ticker"].isin(WATCH)

# ---------- 個股財報日（重試；取不到的另外標示，不當作「沒有財報」）----------
EARN, EARN_FAIL = {}, set()
def next_earnings(t, tries=2):
    for k in range(tries):
        try:
            cal = yf.Ticker(t).calendar
            if isinstance(cal, dict) and len(cal):               # 空字典代表 Yahoo 沒有回應，不是沒有財報
                ds = cal.get("Earnings Date") or []
                fut = sorted(d for d in ds if d >= ASOF.date())
                return (fut[0] if fut else None), True
        except Exception:
            pass
        time.sleep(1.5 * (k + 1))
    return None, False

def fetch_earnings(tickers):
    streak = 0
    for t in tickers:
        if t in EARN or t in EARN_FAIL:
            continue
        if streak >= 6:                                      # 連續 6 隻取不到：Yahoo 正在限流，其餘直接標示取不到
            EARN_FAIL.add(t)
            continue
        d, ok = next_earnings(t)
        if ok:
            EARN[t], streak = d, 0
        else:
            EARN_FAIL.add(t)
            streak += 1
        time.sleep(0.15)

def earn_sessions(t):
    """距下一次財報還有幾個交易日（今日 = 0）；不知道回傳 None。"""
    d = EARN.get(t)
    return None if d is None else (-1 if d <= ASOF.date() else sessions_until(SESS_D, d) if d > SESS_D else 0)

def earn_str(t):
    if t in EARN_FAIL:
        return "取不到"
    d, n = EARN.get(t), earn_sessions(t)
    if d is None:
        return "—"
    if n == -1:
        return f"{d:%m-%d} 剛公佈"
    if n == 0:
        return f"{d:%m-%d} ⚠今日"
    return f"{d:%m-%d}" + (f" ⚠{n}日" if n <= TH["earnings_warn_days"] else "")

EARN_MM = set()                                              # 兩個來源的財報日不一致的股票，表內加「？」
def _with_mark(fn):
    def inner(t):
        s_ = fn(t)
        return s_ + "？" if (t in EARN_MM and s_ not in ("—", "取不到")) else s_
    return inner
earn_str = _with_mark(earn_str)

if FETCH_EVENTS:
    print("取個股財報日…")
    fetch_earnings(list(dict.fromkeys(WATCH + LEAD + list(POSITIONS)))[:80])

# ---------- High Tight Flag（放在最後才下載，免得 Yahoo 限流影響上面的財報日）----------
run_htf()
if FETCH_EVENTS and len(HTF):
    fetch_earnings(list(HTF["Ticker"].head(12)))
EARN_CONFLICT, EARN_MISMATCH = [], []
for t, (dn_, _sl) in OBB_EARN.items():                       # 用 Nasdaq 日曆核對 Yahoo 逐隻查到的財報日
    dy_ = EARN.get(t)
    if dy_ is not None and dn_ > ASOF.date() and abs((dy_ - dn_).days) > 1:
        EARN_MISMATCH.append((t, dn_, dy_))                  # 相差超過一日：取較早的一日，並在表內加「？」
        EARN_MM.add(t)
        EARN[t] = min(dn_, dy_)
    else:
        EARN[t] = dn_
    EARN_FAIL.discard(t)
if OBB_EARN_FULL:                                            # Nasdaq 日曆已覆蓋整段期間
    for t in list(EARN_FAIL):                                # Yahoo 取不到的，當作期間內沒有財報，不再標示「取不到」
        EARN[t] = None
    EARN_FAIL.clear()
    EARN_CONFLICT = sorted(t for t, d in EARN.items()
                           if d is not None and t not in OBB_EARN and ASOF.date() <= d <= OBB_WIN_END)
for d_ in (VCP, HTF, TIGHT, BO52, RESIL, PULL, GAPUP, S_RETEST, BD, LEAD_TBL):
    if len(d_):
        d_["Earn"] = d_["Ticker"].map(earn_str)

# 名單與持倉內 3 個交易日內有財報的股票
EARN_SOON = []
for nm, d_ in [("VCP", VCP), ("HTF", HTF), ("收窄", TIGHT), ("新高突破", BO52), ("抗跌強勢", RESIL), ("回調", PULL), ("回抽阻力", S_RETEST), ("新跌破", BD)]:
    if len(d_):
        for t in d_["Ticker"].head(12):
            n_ = earn_sessions(t)
            if n_ is not None and 0 <= n_ <= 3 and t not in [x[0] for x in EARN_SOON]:
                EARN_SOON.append((t, nm, earn_str(t)))
for t in POSITIONS:
    n_ = earn_sessions(t)
    if n_ is not None and 0 <= n_ <= 3 and t not in [x[0] for x in EARN_SOON]:
        EARN_SOON.append((t, "持倉", earn_str(t)))

# ---------- 標題（Yahoo）：大市、異動最大的龍頭、財報反應最大的公司、名單首幾隻 ----------
THEMES = {"Fed／利率": ["fed", "fomc", "rate hike", "rate cut", "inflation", "cpi", "yield", "treasury"],
          "AI／晶片": ["nvidia", "chip", "semiconductor", "anthropic", "openai", "data center", " ai ", "ai-"],
          "財報": ["earnings", "results", "guidance", "quarter", "outlook", "beats", "misses"],
          "IPO／集資": ["ipo", "offering", "debut"],
          "政策／監管": ["tariff", "regulat", "antitrust", "congress", "export", "white house"],
          "商品／美元": ["oil", "gold", "dollar", "crude", "bitcoin", "copper"]}
THEME_N = {}
_NAME_STOP = {"the", "inc", "corp", "corporation", "company", "companies", "holdings", "group", "common", "stock", "class",
              "ltd", "plc", "com", "new", "technologies", "international", "incorporated", "limited", "trust", "shares"}
_NAME_ALIAS = {"GOOGL": ["Google"], "GOOG": ["Google"], "META": ["Facebook", "Instagram"], "BRK-B": ["Berkshire"]}
def news_relevant(n, extra_names):
    """標題要提到該股的代號或公司名稱才保留；指數和不知道名稱的股票不篩。"""
    t = n["t"]
    if t.startswith("^") or t in ("QQQ", "SPY", "IWM"):
        return True
    title = n["title"]
    if re.search(r"(?<![A-Za-z0-9&])" + re.escape(t) + r"(?![A-Za-z0-9])", title):
        return True
    nm = NAME_OF.get(t) or extra_names.get(t)
    if not nm:
        return True
    words = [w for w in re.sub(r"[^A-Za-z]", " ", str(nm)).split()
             if len(w) >= 4 and w.lower() not in _NAME_STOP and w.upper() != t][:2] + _NAME_ALIAS.get(t, [])
    return any(re.search(r"\b" + re.escape(w) + r"\b", title, re.I) for w in words)

if FETCH_EVENTS:
    print("取標題…")
    movers = F.loc[[t for t in LEAD if t in F.index], "Chg%"].abs().sort_values(ascending=False).head(3).index.tolist()
    reps = EARN_REACT.reindex(EARN_REACT["Move"].abs().sort_values(ascending=False).index)["Symbol"].head(3).tolist() if len(EARN_REACT) else []
    seen = set()
    for t in list(dict.fromkeys(["^GSPC", "^IXIC", "QQQ"] + movers + reps + WATCH[:3])):
        try:
            for it in (yf.Ticker(t).get_news(count=6) or [])[:6]:
                c = it.get("content", it) if isinstance(it, dict) else {}
                title = str(c.get("title") or "").strip()
                if not title or title in seen:
                    continue
                seen.add(title)
                prov = (c.get("provider") or {}).get("displayName") if isinstance(c.get("provider"), dict) else c.get("publisher")
                url = ""
                for key in ("canonicalUrl", "clickThroughUrl"):
                    if isinstance(c.get(key), dict) and c[key].get("url"):
                        url = c[key]["url"]
                        break
                ts = pd.to_datetime(c.get("pubDate") or c.get("displayTime"), errors="coerce", utc=True)
                if pd.notna(ts) and ts.tz_convert(ET) < CLOSE_CUT - pd.Timedelta(days=2):
                    continue                                 # 兩日前的舊標題不要
                prov = "" if "yahoo" in str(prov or "").lower() else str(prov or "")   # 不在公開頁面顯示數據商名稱
                NEWS.append({"t": t, "title": title, "prov": prov,
                             "when": f"{ts.tz_convert(ET):%Y-%m-%d %H:%M}" if pd.notna(ts) else "", "url": url})
        except Exception:
            pass
        time.sleep(0.15)
    try:                                                     # Yahoo 會把無關的文章掛在個股名下，先剔除
        _co = dict(zip(EARN_REACT["Symbol"], EARN_REACT["Company"])) if (len(EARN_REACT) and "Company" in EARN_REACT.columns) else {}
        NEWS = [n for n in NEWS if news_relevant(n, _co)]
    except Exception:
        pass
    NEWS = sorted(NEWS, key=lambda x: x["when"], reverse=True)[:24]
    for n_ in NEWS:
        low = " " + n_["title"].lower() + " "
        for th, keys in THEMES.items():
            if any(k in low for k in keys):
                THEME_N[th] = THEME_N.get(th, 0) + 1

POS_TBL, OPEN_RISK_PCT, LONG_EXPO = pd.DataFrame(), 0.0, 0.0
CAP_MAX = {"A": 100, "B": 75, "C": 30, "D": 10, "E": 10}
# v6.3 持倉管理的提醒。全部是常見的經驗值，未經回測；按你自己的規則改。
POS_RULES = dict(
    be_atr=3.0,                 # 浮盈有 3 個 ATR 而止蝕仍在成本之下：提醒可以上移到成本
    earn_days=5,                # 5 個交易日內公佈業績：檢查利潤墊
    earn_cushion_atr=2.0,       # 利潤墊少於 2 個 ATR：提醒財報前減倉或平倉
    fast_gain=20.0, fast_days=15, hold_weeks=8,   # 入場 15 個交易日內升 20%：O'Neil 的做法是持有至少 8 週，除非跌穿止蝕
    ext50=25.0,                 # 收市高於 50 日線 25% 以上：提醒可以分段鎖定利潤
    stall_days=15, stall_atr=1.0,                 # 持有 15 個交易日仍未走出 1 個 ATR：提醒可以考慮時間止蝕
)
if POSITIONS:
    rows, open_risk = [], 0.0
    for t, p in POSITIONS.items():
        if t not in F.index:
            rows.append({"Ticker": t, "Note": "無數據"})
            continue
        px = PM[t][0] if t in PM else F.at[t, "Close"]
        risk = max(px - p["stop"], 0) * p["shares"]
        open_risk += risk
        note, act = [], []                                   # v6.3：act 是要處理的事項，note 是狀態
        _fv = lambda col: np.nan if isnan(F.at[t, col]) else float(F.at[t, col])
        cl, e21, s50, stop = _fv("Close"), _fv("ema21"), _fv("s50"), p["stop"]
        atr_d = _fv("ATR%") * cl / 100
        ent, ed = p.get("entry", np.nan), p.get("entry_d")
        low10 = float(L[t].dropna().iloc[-10:].min()) if t in L.columns else np.nan
        gain = (px / ent - 1) * 100 if (not isnan(ent) and ent > 0) else np.nan
        g_atr = (px - ent) / atr_d if not (isnan(gain) or isnan(atr_d) or atr_d <= 0) else np.nan
        r_now = (px - ent) / (ent - stop) if (not isnan(gain) and ent > stop) else np.nan
        days = sessions_until(ed, ASOF.date()) if ed else np.nan
        n_e, R_ = earn_sessions(t), POS_RULES
        if px <= stop:
            act.append(f"已到止蝕位 {stop:,.2f}：開市按計劃止蝕")
        if cl < s50:
            note.append("收市跌穿 50 日線")
        elif cl < e21:
            note.append("收市跌穿 21EMA")
        if F.at[t, "Fallen"]:
            note.append("墮落龍頭")
        if not isnan(gain) and stop >= ent:
            note.append(f"止蝕已在成本之上，鎖定 {(stop / ent - 1) * 100:+.1f}%")
        if not isnan(g_atr) and stop < ent and g_atr >= R_["be_atr"]:
            act.append(f"浮盈 {g_atr:.1f} 個 ATR，止蝕仍在成本之下：可考慮上移到成本 {ent:,.2f}")
        if n_e is not None and 0 <= n_e <= R_["earn_days"]:
            when = "今日" if n_e == 0 else f"{n_e} 個交易日後"
            if isnan(g_atr):
                act.append(f"{when}公佈業績：先決定財報前減倉還是持有（未填入場價，算不到利潤墊）")
            elif g_atr < R_["earn_cushion_atr"]:
                act.append(f"{when}公佈業績，利潤墊只有 {g_atr:.1f} 個 ATR（少於 {R_['earn_cushion_atr']:g}）：可考慮財報前減倉或平倉")
            else:
                note.append(f"{when}公佈業績，利潤墊 {g_atr:.1f} 個 ATR")
        if ed and not isnan(gain) and days <= R_["fast_days"] and gain >= R_["fast_gain"]:
            note.append(f"入場 {days} 個交易日升 {gain:.0f}%：O'Neil 的做法是持有至少 {R_['hold_weeks']} 週，除非跌穿止蝕")
        ext = (cl / s50 - 1) * 100 if (not isnan(s50) and s50 > 0) else np.nan
        if not isnan(ext) and ext >= R_["ext50"]:
            act.append(f"高於 50 日線 {ext:.0f}%：可考慮分段鎖定利潤")
        if ed and not isnan(g_atr) and days >= R_["stall_days"] and abs(g_atr) < R_["stall_atr"]:
            act.append(f"持有 {days} 個交易日，仍未走出 {R_['stall_atr']:g} 個 ATR：可考慮時間止蝕")
        trail = "；".join(x for x in (f"21EMA {e21:,.2f}" if not isnan(e21) else "", f"10 日低位 {low10:,.2f}" if not isnan(low10) else "") if x)
        rows.append({"Ticker": t, "Px": px, "Entry": ent, "PnL%": gain, "R": r_now, "Days": days, "Stop": stop,
                     "ToStop%": (px / stop - 1) * 100, "Stage": F.at[t, "Stage"], "RS": F.at[t, "RS"], "Risk$": risk,
                     "Earn": earn_str(t), "Trail": trail, "ATR$": atr_d, "Close": cl, "EMA21": e21, "S50": s50, "Low10": low10,
                     "Act": "；".join(act), "Note": "；".join(act + note) or "—"})
    POS_TBL = pd.DataFrame(rows)
    OPEN_RISK_PCT = open_risk / ACCOUNT_EQUITY * 100
    LONG_EXPO = sum((PM[t][0] if t in PM else F.at[t, "Close"]) * p["shares"] for t, p in POSITIONS.items() if t in F.index) / ACCOUNT_EQUITY * 100

# ---------- 缺口、關鍵位、觸發位、今日劇本 ----------
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

qqq_pm = PM.get("QQQ")
if qqq_pm and not np.isnan(NQ_CHG) and (RUN_TS - qqq_pm[1]) > pd.Timedelta(minutes=45):
    qqq_pm = None                                   # QQQ 的報價已舊（例如盤後時段已完），改用期貨推算
if qqq_pm:
    _hm = (qqq_pm[1].hour, qqq_pm[1].minute)
    _lab = "盤前價" if (4, 0) <= _hm < (9, 30) else "現價" if (9, 30) <= _hm < (16, 0) else "盤後價"
    GAP_PX, GAP_SRC = qqq_pm[0], f"QQQ {_lab}（{qqq_pm[1]:%m-%d %H:%M} ET）"
elif not np.isnan(NQ_CHG):
    GAP_PX, GAP_SRC = q.c * (1 + NQ_CHG / 100), "按 Nasdaq 100 期貨自收市以來的變動推算"
else:
    GAP_PX, GAP_SRC = np.nan, ""
if not np.isnan(GAP_PX):
    GAP_PCT, GAP_ATR = (GAP_PX / q.c - 1) * 100, (GAP_PX - q.c) / q.atr
    SCEN = scen_of(GAP_ATR)
else:
    GAP_PCT = GAP_ATR = np.nan
    SCEN = "未有期貨或盤前數據，開市後按四種情景判斷。"
REF_PX = GAP_PX if not np.isnan(GAP_PX) else q.c

lv = {"52 週高位": q.hi252, "20 日高位": q.hi20, "50 日線": q.s50, "21EMA": q.ema21, "200 日線": q.s200,
      "上日高位": q.h, "上日收市": q.c, "上日低位": q.l, "20 日低位": q.lo20}
if RALLY["in_correction"]:
    lv["調整低位"] = RALLY["low"]
LEVELS = pd.DataFrame([{"Level": k, "Px": v, "Dist%": (v / REF_PX - 1) * 100} for k, v in lv.items() if not isnan(v)]
                      ).sort_values("Px", ascending=False).reset_index(drop=True)

TRIG = []
if q.c < q.ema21:
    TRIG.append(("↑", f"收市重上 21EMA {q.ema21:.2f}", (q.ema21 / REF_PX - 1) * 100,
                 "試單閘門的價格條件（另需分數 ≥ 40，現 " + f"{score_now:.0f}" + "）"))
if q.c < q.s50:
    TRIG.append(("↑", f"收市重上 50 日線 {q.s50:.2f}", (q.s50 / REF_PX - 1) * 100, "多頭閘門的價格條件（另需 Regime A 或 B）"))
if q.c < q.s200:
    TRIG.append(("↑", f"收市重上 200 日線 {q.s200:.2f}", (q.s200 / REF_PX - 1) * 100, "長線分界；重上之前，反彈先當阻力看"))
if RALLY["in_correction"] and not RALLY["ftd_valid"]:
    TRIG.append(("↑", f"FTD：反彈第 4 日起，單日升 ≥ {TH['ftd_gain']}% 且成交高於上日", np.nan,
                 "試單閘門打開（標準風險的 25%）；" + ("反彈未開始，要先有收升日" if RALLY["day"] == 0 else "下一個交易日是第 " + str(NEXT_DAY) + " 日")))
    TRIG.append(("↓", f"跌穿調整低位 {RALLY['low']:.2f}", (RALLY["low"] / REF_PX - 1) * 100, "反彈嘗試作廢，重新計日"))
if q.c > q.ema21:
    TRIG.append(("↓", f"收市跌穿 21EMA {q.ema21:.2f}", (q.ema21 / REF_PX - 1) * 100, "短線轉弱，新倉減注"))
if q.c > q.s50:
    TRIG.append(("↓", f"收市跌穿 50 日線 {q.s50:.2f}", (q.s50 / REF_PX - 1) * 100, "多頭閘門關閉"))

# 向上的觸發位由近至遠排，向下的排在後面
_near = lambda x: (isnan(x[2]), abs(x[2]) if not isnan(x[2]) else 0)
TRIG = sorted([x for x in TRIG if x[0] == "↑"], key=_near) + sorted([x for x in TRIG if x[0] == "↓"], key=_near)

long_ok = LONG_GATE or PILOT_GATE
PLAY = []
if LONG_GATE:
    PLAY.append("做多：多頭閘門開。" + ("規則容許所有合格突破，示範注碼較大。" if REG_L == "A" else "規則只容許領先板塊的 A 級形態。"))
elif PILOT_GATE:
    PLAY.append("做多：只有試單閘門開，規則示範注碼為標準風險的 25%。")
else:
    PLAY.append("做多：多頭與試單閘門均關閉，做多形態只列作觀察；「抗跌強勢」名單通常是下一輪的領先股。")
if SHORT_GATE:
    PLAY.append("做空：" + SHORT_TIMING + "。規則只容許「回抽阻力」名單內的弱股，標示「已超跌」的除外。")
elif SHORT_SETUP and OVERSOLD:
    PLAY.append("做空：超賣閘門觸發，規則不開新空頭形態。")
if CAL_FLAGS:
    PLAY.append("日曆：" + " ".join(CAL_FLAGS))
if len(EARN_REACT):
    for r_ in EARN_REACT[EARN_REACT["IsLead"] & EARN_REACT["Verdict"].isin(["勝預期但跌：弱", "遜預期但升：強"])].head(3).itertuples():
        PLAY.append(f"財報反應：{r_.Symbol} {r_.Verdict.replace('：', '（' + format(r_.Move, '+.1f') + '%），')}勢訊號。")
if EARN_SOON:
    PLAY.append("財報風險：" + "、".join(f"{t}（{nm}，{es}）" for t, nm, es in EARN_SOON[:8]) + "。規則不對 3 個交易日內有財報的股票列出新形態。")
if POSITIONS and LONG_EXPO > CAP_MAX[REG_L]:
    PLAY.append(f"持倉：現有多倉佔戶口 {LONG_EXPO:.0f}%，高於 Regime {REG_L} 的上限 {CAP_MAX[REG_L]}%，規則先減最弱的持倉。")
if RALLY["in_correction"] and not RALLY["ftd_valid"]:
    if RALLY["day"] == 0:
        PLAY.append("反彈嘗試：創低位後未有收升日，反彈未開始；下一個收升的交易日才是第 1 日。")
    elif NEXT_DAY < 4:
        PLAY.append(f"反彈嘗試：下一個交易日是第 {NEXT_DAY} 日，FTD 最早在第 4 日，當日升幅再大也不算確認。")
    else:
        PLAY.append(f"反彈嘗試：下一個交易日是第 {NEXT_DAY} 日，FTD 窗口已開，留意升幅 ≥ {TH['ftd_gain']}% 且成交放大的日子。")
if not np.isnan(BO_FOLLOW):
    if BO_FOLLOW <= TH["bo_follow_bad"]:
        PLAY.append(f"突破成功率只有 {BO_FOLLOW:.0f}%：突破正在失敗，規則暫停突破形態。")
    elif BO_FOLLOW < TH["bo_follow_ok"]:
        PLAY.append(f"突破成功率 {BO_FOLLOW:.0f}%，未達 60%：即使閘門打開，突破形態只按試單規模。")
if DIST_N > TH["dist_days_warn"]:
    PLAY.append(f"近 25 日有 {DIST_N} 個派發日，機構仍在賣。")
if reg_now < reg_prev:
    PLAY.append(f"Regime 由 {REG_NAME[reg_prev][0]} 降至 {REG_L}：規則先減最弱的持倉。")
if reg_now > reg_prev:
    PLAY.append(f"Regime 由 {REG_NAME[reg_prev][0]} 升至 {REG_L}（已連續兩日確認）。")
if len(FALLEN):
    PLAY.append(f"有 {len(FALLEN)} 隻「墮落龍頭」（過去一年升幅仍大，但已跌離高位 25% 以上、失守 50 日線）：舊強勢不構成入選理由。")
if RALLY["in_correction"] and not RALLY["ftd_valid"] and not isnan(GAP_PX) and GAP_PX < RALLY["low"]:
    PLAY.append(f"盤前參考價 {GAP_PX:.2f} 已低於調整低位 {RALLY['low']:.2f}：收市仍在其下的話，反彈嘗試作廢、重新計日；規則不把今日當作反彈。")
PLAY.append("開市：" + SCEN)

ATTR = pd.DataFrame([{"Pillar": p.name, "W": TH["weights"][p.key], "Now": PS[p.key].iloc[-1], "Prev5": PS[p.key].iloc[-6],
                      "Contrib": (PS[p.key].iloc[-1] - PS[p.key].iloc[-6]) * TH["weights"][p.key] / 100} for p in PILLARS])

quality = list(UNI_NOTES)
quality += (["補充數據層暫時未能載入，該節已略過。"] if any("載入失敗" in x for x in OBB_ERR) else [])
for _x in OBB_ERR:
    print("  補充數據層：" + _x)
if DATA_HOLE:
    quality.insert(0, f"收市價缺漏：{len(DATA_HOLE)} 隻（佔股票池 {fnum(len(DATA_HOLE) / max(len(TICKS), 1) * 100, 1 if len(DATA_HOLE) < 0.01 * max(len(TICKS), 1) else 0)}%）"
                   f"沒有 {ASOF:%m-%d} 的收市價，未計入掃描、分級和寬度。成交最大的：" + "、".join(DATA_HOLE[:12]) + ("…" if len(DATA_HOLE) > 12 else ""))
if DATA_FIX["daily"] or DATA_FIX["intraday"]:
    quality.append(f"有 {DATA_FIX['n0']} 隻股票最初沒有 {ASOF:%m-%d} 的收市價：{DATA_FIX['daily']} 隻重新下載後取到"
                   + (f"，{DATA_FIX['intraday']} 隻用 5 分鐘線補上（收市價取 16:00 前最後一筆，與正式收市價可能相差幾仙）" if DATA_FIX["intraday"] else "") + "。")
_te = now_et()
_exp_d = _te.date()
if not (is_session(_exp_d) and (_te.hour, _te.minute) >= (16, 20)):
    _exp_d -= _dt.timedelta(days=1)
    while not is_session(_exp_d):
        _exp_d -= _dt.timedelta(days=1)
if ASOF.date() < _exp_d:
    quality.insert(0, f"最新一個交易日（{_exp_d:%m-%d}）的數據未到，本報告用 {ASOF:%m-%d} 的收市數據計算。")
if UNIVERSE_FALLBACK:
    quality.append("成份股名單取不到，用了後備名單，寬度與掃描結果不可靠。")
if LOAD_RATIO < 95:
    quality.append(f"只載入了 {LOAD_RATIO:.0f}% 的股票，寬度可能失真。")
missing = [it[0] for p in PILLARS for it in p.items if it[1] is None]
if missing:
    quality.append("以下檢查項目缺數據、未計入分數：" + "、".join(missing))
if (RUN_TS.tz_localize(None).normalize() - ASOF).days > 4:
    quality.append("最新數據距今超過 4 日，請確認數據源。")
if EARN_FAIL:
    quality.append(f"有 {len(EARN_FAIL)} 隻股票的財報日取不到（表內顯示「取不到」，不代表沒有財報），請自行核實："
                   + "、".join(sorted(EARN_FAIL)[:15]) + ("…" if len(EARN_FAIL) > 15 else ""))

# ---------- v4：指數對照、各指數寬度、昨日回顧、焦點名單、提示價 ----------
IDX_NAMES = {"QQQ": "Nasdaq 100", "SPY": "S&P 500", "DIA": "道指", "IWM": "Russell 2000", "RSP": "S&P 500 等權", "SMH": "半導體"}
rows = []
for s_, nm in IDX_NAMES.items():
    t_ = tech(s_)
    if t_ is None:
        continue
    r_ = t_.iloc[-1]
    rows.append({"ETF": s_, "Name": nm, "Close": r_.c, "D1": r_.ret * 100, "D5": (r_.c / t_["c"].iloc[-6] - 1) * 100,
                 "A21": bool(r_.c > r_.ema21), "A50": bool(r_.c > r_.s50), "A200": bool(r_.c > r_.s200),
                 "FromHigh": (r_.c / r_.hi252 - 1) * 100, "Dist": r_.dist25})
IDX_TBL = pd.DataFrame(rows)
DIST_TBL = dist_days_active(Q)

STAGE2 = ((C.gt(S50_ALL)) & (S50_ALL.gt(S200)) & S200.notna()).sum(axis=1) / S200.notna().sum(axis=1).replace(0, np.nan) * 100
src_of = UNI.set_index("Ticker")["Source"].to_dict()
def _breadth(name, ticks):
    ticks = [t for t in ticks if t in F.index and not isnan(F.at[t, "Close"]) and not isnan(F.at[t, "s50"])]
    if len(ticks) < 20:
        return None
    f_ = F.loc[ticks]
    return {"Grp": name, "n": len(ticks), "P50": f_["Above50"].mean() * 100, "P200": f_["Above200"].mean() * 100,
            "S2": (f_["Stage"] == "2 上升").mean() * 100, "NH": int(f_["BO_52W"].sum()), "NL": int(f_["BD_52W"].sum())}
BR_TBL = pd.DataFrame([x for x in [_breadth("Nasdaq 100", NDX_LIST), _breadth("S&P 500", [t for t in TICKS if src_of.get(t) == "sp500"]),
                                   _breadth("S&P 400 中型股", [t for t in TICKS if src_of.get(t) == "sp400"]),
                                   _breadth("全部股票池", TICKS)] if x])

# 昨日市場回顧（由數據計算）
RECAP = []
if len(IDX_TBL):
    RECAP.append("指數：" + "，".join(f"{r.Name} {r.D1:+.1f}%" for r in IDX_TBL.itertuples()) + "。")
if sec_adj.shape[1] >= 8:
    sd = ((sec_adj.iloc[-1] / sec_adj.iloc[-2] - 1) * 100).sort_values(ascending=False)
    RECAP.append("板塊：最強 " + "、".join(f"{SECTOR_ETFS[k]} {v:+.1f}%" for k, v in sd.head(3).items())
                 + "；最弱 " + "、".join(f"{SECTOR_ETFS[k]} {v:+.1f}%" for k, v in sd.tail(3).iloc[::-1].items()) + "。")
RECAP.append(f"寬度：上升 {ADV.iloc[-1]:.0f} 隻，下跌 {DEC.iloc[-1]:.0f} 隻；52 週新高 {fnum(NH.iloc[-1], 0)}，新低 {fnum(NL.iloc[-1], 0)}；"
             f"Stage 2 股票佔 {STAGE2.iloc[-1]:.0f}%（5 日前 {STAGE2.iloc[-6]:.0f}%，20 日前 {STAGE2.iloc[-21]:.0f}%）。")
_lm = F.loc[[t for t in LEAD if t in F.index], ["Chg%", "VolX"]].dropna(subset=["Chg%"]).sort_values("Chg%")
if len(_lm) >= 6:
    RECAP.append("龍頭：升幅最大 " + "、".join(f"{t} {r['Chg%']:+.1f}%" for t, r in _lm.iloc[::-1].head(3).iterrows())
                 + "；跌幅最大 " + "、".join(f"{t} {r['Chg%']:+.1f}%" + (f"（成交 {r['VolX']:.1f} 倍）" if r["VolX"] >= 1.5 else "") for t, r in _lm.head(3).iterrows()) + "。")

# 板塊排名變化（1 個月回報排名，對比 5 日前）
if sec_r21 is not None and len(SECT_TBL):
    rk_now, rk_5 = sec_r21.iloc[-1].rank(ascending=False), sec_r21.iloc[-6].rank(ascending=False)
    SECT_TBL["Rank"] = SECT_TBL["ETF"].map(rk_now)
    SECT_TBL["RankChg"] = SECT_TBL["ETF"].map(rk_5 - rk_now).map(
        lambda x: "—" if isnan(x) or x == 0 else f"↑{abs(x):.0f}" if x > 0 else f"↓{abs(x):.0f}")

# 預期波幅：VXN 引伸的單日一個標準差
VXN_NOW = float(VXN.iloc[-1]) if VXN is not None else np.nan
EM_PCT = VXN_NOW / np.sqrt(252) if not np.isnan(VXN_NOW) else np.nan
EM_TXT = ("" if np.isnan(EM_PCT) else
          f"預期波幅：VXN {VXN_NOW:.1f} 引伸單日約 ±{EM_PCT:.1f}%，即 {REF_PX * (1 - EM_PCT / 100):.2f} 至 {REF_PX * (1 + EM_PCT / 100):.2f}；"
          f"ATR 為 {q.atr:.2f}（{q.atr / q.c * 100:.1f}%）。開市後的波動在這個範圍內屬正常。")

# 焦點名單：由各做多名單按固定計分挑出最多 5 隻（閘門未開時是觀察首選）
SETUP_PTS = {"VCP": 8, "HTF": 6, "收窄": 6, "新高突破": 5, "回調": 3, "抗跌強勢": 2}
def focus_long(k=5):
    pool = {}
    def add(d, tag, pivot_col=None, stop_col=None):
        if d is None or not len(d):
            return
        for r in d.head(15).to_dict("records"):
            e = pool.setdefault(r["Ticker"], {"Tags": [], "Pivot": np.nan, "Stop": np.nan, "Close": r.get("Close", np.nan)})
            e["Tags"].append(tag)
            if pivot_col and isnan(e["Pivot"]) and not isnan(r.get(pivot_col)):
                e["Pivot"] = r[pivot_col]
            if stop_col and isnan(e["Stop"]) and not isnan(r.get(stop_col)):
                e["Stop"] = r[stop_col]
    add(VCP, "VCP", "Pivot", "Stop")
    add(HTF[(HTF["Note"] == "") & (HTF["State"] != "旗桿中")] if len(HTF) else HTF, "HTF", "Pivot", "Stop")
    add(TIGHT, "收窄", "Pivot10")
    add(BO52[BO52["Ext%"] <= TH["extended_pct"]] if len(BO52) else BO52, "新高突破", "Pivot52W")
    add(PULL, "回調", "H3")
    add(RESIL, "抗跌強勢", "Pivot10")
    out = []
    for t, e in pool.items():
        inf = t in F.index
        close = F.at[t, "Close"] if inf else e["Close"]
        piv = e["Pivot"] if not isnan(e["Pivot"]) else close
        rs = F.at[t, "RS"] if inf else np.nan
        rs_eff = rs if not isnan(rs) else (85.0 if "HTF" in e["Tags"] else 50.0)
        secr = F.at[t, "SecRank"] if inf else np.nan
        dist = (close / piv - 1) * 100
        if dist > TH["extended_pct"]:
            continue                                         # 已高出 pivot 超過買入區，不追
        n_e = earn_sessions(t)
        pts = rs_eff + SETUP_PTS[e["Tags"][0]] + 3 * (len(e["Tags"]) - 1)
        pts += 10 if (not isnan(secr) and secr <= 4) else 0
        pts += 8 if -3 <= dist <= 0 else 4 if 0 < dist <= 3 else 0
        if inf:
            pts += 5 if bool(F.at[t, "RSLHigh"]) else 0
            pts += 4 if (not isnan(F.at[t, "UD"]) and F.at[t, "UD"] >= 1.2) else 0
            pts -= 15 if F.at[t, "From50%"] > 20 else 0
        pts -= 30 if (n_e is not None and 0 <= n_e <= 3) else 0
        pts -= 5 if t in EARN_FAIL else 0
        entry = piv * 1.001 if dist <= 0 else close           # 已升穿 pivot 的，以現價計風險
        stop = e["Stop"]
        if isnan(stop) or stop >= entry:
            atrp = F.at[t, "ATR%"] if inf and not isnan(F.at[t, "ATR%"]) else 4.0
            stop = entry * (1 - min(MAX_STOP_PCT, max(3.0, 1.5 * atrp)) / 100)
        shares, riskp, posp = size_for(entry, stop)
        out.append({"Ticker": t, "Setup": "＋".join(e["Tags"]), "RS": rs, "SecETF": F.at[t, "SecETF"] if inf else "",
                    "SecRank": secr, "Close": close, "Trigger": piv * 1.001, "Dist%": dist,
                    "Status": "待升穿" if dist <= 0 else f"已升穿，買入區至 {piv * (1 + TH['extended_pct'] / 100):.2f}",
                    "Stop": stop, "Risk%": riskp,
                    "Shares": shares, "Pos%": posp, "UD": F.at[t, "UD"] if inf else np.nan, "Earn": earn_str(t), "Pts": pts})
    d = pd.DataFrame(out)
    return d.sort_values("Pts", ascending=False).head(k).reset_index(drop=True) if len(d) else d

def focus_short(k=3):
    if not len(S_RETEST):
        return pd.DataFrame()
    out = []
    short_risk = ACCOUNT_EQUITY * BASE_RISK_PCT / 100 * TH["risk_mult"]["short"]
    for r in S_RETEST.head(15).to_dict("records"):
        t = r["Ticker"]
        n_e = earn_sessions(t)
        entry, stop = r["L3"] * 0.999, r["H3"] * 1.005
        if isnan(entry) or isnan(stop) or stop <= entry:
            continue
        pts = (100 - r["RS"]) + (10 if (not isnan(r["SecRank"]) and r["SecRank"] >= 8) else 0)
        pts -= 30 if (n_e is not None and 0 <= n_e <= 3) else 0
        pts -= 5 if t in EARN_FAIL else 0
        risk_ps = stop - entry
        out.append({"Ticker": t, "Setup": "回抽阻力", "RS": r["RS"], "SecETF": r["SecETF"], "SecRank": r["SecRank"], "Close": r["Close"],
                    "Trigger": entry, "Stop": stop, "Risk%": risk_ps / entry * 100, "Shares": int(short_risk // risk_ps),
                    "Earn": earn_str(t), "Pts": pts})
    d = pd.DataFrame(out)
    return d.sort_values("Pts", ascending=False).head(k).reset_index(drop=True) if len(d) else d

FOCUS_L = focus_long()
FOCUS_S = focus_short() if SHORT_SETUP else pd.DataFrame()

ALERTS = []
for a_, what, dist, mean in TRIG:
    m_ = re.search(r"(\d+\.\d+)$", what)
    if m_:
        ALERTS.append({"Ticker": "QQQ", "Dir": "升穿" if a_ == "↑" else "跌穿", "Px": float(m_.group(1)), "Why": mean})
for r in FOCUS_L.itertuples() if len(FOCUS_L) else []:
    if r.Status == "待升穿":
        ALERTS.append({"Ticker": r.Ticker, "Dir": "升穿", "Px": round(r.Trigger, 2), "Why": f"{r.Setup} 觸發價；止蝕 {r.Stop:.2f}"})
    else:
        ALERTS.append({"Ticker": r.Ticker, "Dir": "跌穿", "Px": round(r.Stop, 2), "Why": f"{r.Setup} 已升穿 pivot；這是止蝕位"})
for r in FOCUS_S.itertuples() if len(FOCUS_S) else []:
    ALERTS.append({"Ticker": r.Ticker, "Dir": "跌穿", "Px": round(r.Trigger, 2), "Why": f"回抽阻力，跌穿 3 日低位；止蝕 {r.Stop:.2f}"})
ALERT_TBL = pd.DataFrame(ALERTS)

# ---------- v6：分級與八項清單（第一步：把各名單合併成候選，逐隻檢查）----------
# 以下門檻全部是常用的經驗值，未經回測；想改就改這個表。A 級是「先看哪幾隻圖」的次序，不是買賣訊號。
PLAN = dict(
    a_max=5, b_max=10, s_a_max=3, s_b_max=5,                    # 做多 A 級、B 級，做空 A 級、B 級各最多幾隻
    near_trigger=3.0,                                           # A 級：現價在觸發價之下不超過 3%
    earn_days=5,                                                # A 級：5 個交易日內沒有財報
    per_sector=2,                                               # A 級：同一板塊最多 2 隻（連現有持倉計）
    max_fails=2,                                                # A 級：八項清單最多 2 項不通過，而且「趨勢」一定要通過
    b_far=8.0,                                                  # B 級：現價距觸發價不可超過 8%，再遠的只列入觀察
    rs_min=80, sec_top=4, tight_pct=0.35, vol_dry=0.85, ud_min=1.2, htf_depth=20.0, htf_volr=0.8,   # 做多清單
    s_rs_max=30, s_sec_bottom=8, s_ud_max=0.9, dtc_squeeze=5.0,                                    # 做空清單
    min_stop_pct=2.0, min_stop_atr=0.75,                        # 止蝕最少要離入場價幾遠（% 與 ATR 倍數，取較大者）
    corr_max=0.75, corr_days=60,                                # 60 日回報的相關係數高於此數，當作同一注
    heat_pct={"A": 6.0, "B": 4.0, "C": 2.0, "D": 1.0, "E": 1.0},   # 所有持倉合計的風險上限（佔戶口 %），表單填了就用表單的
    new_per_day={"A": 3, "B": 2, "C": 1, "D": 1, "E": 1},          # 每日最多開幾注新倉
    chart_days=126, thumb_days=84,
    pin_atr=0.8, pin_ratio=0.4, pin_r10=3.0,                    # 波幅異常地小（疑似收購後鎖價）：ATR 低於 0.8%，或低於自己半年中位數的四成而 10 日波幅不足 3%
    follow_days=10, score_days=120,                             # 名單跟進看最近幾個名單日；成績表最多用幾個名單日
    limit_atr=0.2,                                              # v6.3 下單清單：止損限價單的限價 = 觸發價 ± 0.2 個 ATR（不超過追價上限）
    near_open_atr=0.3,                                          # v6.3 快速更新：盤前價距觸發價不足 0.3 個 ATR，開市可能即時觸發
    gapdown_atr=1.0,                                            # v6.3 快速更新：盤前逆向跳空超過 1 個 ATR，先不落單
)
T6_RULES = "6.1"                                                # 分級規則的版本。規則一改就要改這個編號，成績表不會把不同版本混在一起計
V6_OK, T6_ERR = True, []                                        # 新功能出錯就退回 v5.2 的版面，簡報其餘部分照常
T6_CK_L = ["趨勢", "RS", "板塊", "收縮", "成交", "資金", "距離", "事件"]
T6_CK_S = ["趨勢", "RS", "板塊", "未超跌", "資金", "距離", "軋空", "事件"]
T6_ORDER = {"VCP": 0, "HTF": 1, "收窄": 2, "新高突破": 3, "回調": 4, "抗跌強勢": 5, "回抽阻力": 0}
T6_L, T6_S = [], []                                             # 全部候選（做多、做空），每隻一個 dict
T6_LA, T6_LB, T6_SA, T6_SB = [], [], [], []                     # 做多首選（A 級或預備）、做多 B 級、做空首選、做空 B 級
T6_SI_L, T6_SI_S = [], []                                       # 要查沽空數據和引伸波幅的代號
T6_SGATE = bool(SHORT_GATE and not SHORT_TIMING.startswith("破位邊緣"))   # 空頭閘門開，而且不是在破位邊緣（破位邊緣不追空）
T6_WATCH, T6_WATCH_NA = [], []                                  # 自選名單體檢的結果；沒有數據的代號

def t6_warn(stage, e):
    """次要功能出錯：只記下訊息，首頁其餘部分照常。"""
    where = ""
    try:
        import traceback
        tb = traceback.extract_tb(e.__traceback__)
        own = [x for x in tb if not any(k in str(x.filename) for k in ("site-packages", "dist-packages", "lib/python"))]
        fr = (own or tb)[-1]
        where = f"；第 {fr.lineno} 行 {fr.name}"
    except Exception:
        pass
    T6_ERR.append(f"v6.1 的「{stage}」出錯（{type(e).__name__}: {' '.join(str(e).split())[:160]}{where}），這一項已略過，其餘照常。")

def t6_fail(stage, e):
    """v6 的新功能出錯：記下出錯的位置，版面退回 v5.2 的做法。"""
    global V6_OK
    V6_OK = False
    where = ""
    try:
        import traceback
        tb = traceback.extract_tb(e.__traceback__)
        own = [x for x in tb if not any(k in str(x.filename) for k in ("site-packages", "dist-packages", "lib/python"))]
        fr = (own or tb)[-1]                                     # 取腳本本身出錯的那一行，不要套件內部的
        where = f"；第 {fr.lineno} 行 {fr.name}"
    except Exception:
        pass
    T6_ERR.append(f"v6 的「{stage}」出錯（{type(e).__name__}: {' '.join(str(e).split())[:160]}{where}），首頁已退回 v5.2 的版面。")

def t6_f(v):
    """轉成數字；空白、文字或取不到就回傳 NaN。"""
    try:
        return np.nan if isnan(v) else float(v)
    except Exception:
        return np.nan

def t6_earn(t):
    """回傳（距下一次財報的交易日數，是否查得到）。日數 None = 期間內沒有財報，-1 = 剛公佈。"""
    if t in EARN_FAIL:
        return None, False
    if t in EARN:
        return earn_sessions(t), True
    return None, bool(OBB_EARN_FULL)                             # Nasdaq 日曆已覆蓋整段期間：沒有列出即沒有財報

def t6_event(t):
    """清單的「事件」：True = 期間內沒有財報，False = 有，None = 查不到。另回傳日數和寫進「尚欠」的文字。"""
    n_e, known = t6_earn(t)
    if not known:
        return None, n_e, "財報日未能確認"
    if n_e is not None and 0 <= n_e <= PLAN["earn_days"]:
        d0 = EARN.get(t)
        when = "今日" if n_e == 0 else f"{n_e} 個交易日後"
        return False, n_e, (f"{d0:%m-%d} 有財報（{when}），財報後再看" if d0 is not None else "即將有財報，財報後再看")
    return True, n_e, ""

def t6_count(c):
    """按清單重新點算通過、不通過的項數。"""
    c["NPass"] = sum(1 for v in c["Ck"].values() if v is True)
    c["NFail"] = sum(1 for v in c["Ck"].values() if v is False)
    c["Fails"] = [k for k, v in c["Ck"].items() if v is False]

def t6_pinned(t):
    """波幅異常地小的股票，多數是被收購後股價鎖在收購價附近，不是收窄形態。回傳說明文字；正常就回傳空字串。"""
    if t not in F.index:
        return ""
    a, r10 = t6_f(F.at[t, "ATR%"]), t6_f(F.at[t, "R10%"])
    if isnan(a):
        return ""
    med = np.nan
    try:
        med = t6_f((ATR[t] / C[t] * 100).iloc[-126:].median())
    except Exception:
        pass
    if a <= PLAN["pin_atr"] or (not isnan(med) and med > 0 and a <= PLAN["pin_ratio"] * med and not isnan(r10) and r10 <= PLAN["pin_r10"]):
        return f"波幅異常地小（ATR {a:.1f}%，10 日波幅 {fnum(r10, 1)}%），疑似收購後鎖價，不是收窄形態"
    return ""

def t6_long_pool():
    """把六個做多名單合併：同一隻股票只留一筆，記下它在哪幾個名單、pivot 和止蝕取自哪一個。"""
    pool = {}
    def add(d, tag, pivot_col=None, stop_col=None):
        if d is None or not len(d):
            return
        for r in d.to_dict("records"):
            e = pool.setdefault(r["Ticker"], {"Tags": [], "Pivot": np.nan, "Stop": np.nan, "PTag": "", "Rows": {}})
            e["Tags"].append(tag)
            e["Rows"][tag] = r
            if pivot_col and isnan(e["Pivot"]) and not isnan(t6_f(r.get(pivot_col))):
                e["Pivot"], e["PTag"] = t6_f(r.get(pivot_col)), tag
                if stop_col:
                    e["Stop"] = t6_f(r.get(stop_col))
    add(VCP, "VCP", "Pivot", "Stop")
    add(HTF[(HTF["Note"] == "") & (HTF["State"] != "旗桿中")] if len(HTF) else HTF, "HTF", "Pivot", "Stop")
    add(TIGHT, "收窄", "Pivot10")
    add(BO52[BO52["Ext%"] <= TH["extended_pct"]] if len(BO52) else BO52, "新高突破", "Pivot52W")
    add(PULL, "回調", "H3")
    add(RESIL, "抗跌強勢", "Pivot10")
    return pool

def t6_eval_long(t, e):
    """一隻做多候選：入場價、止蝕、股數、八項清單、未達 A 級的原因。"""
    inf = t in F.index
    fv = (lambda col: F.at[t, col]) if inf else (lambda col: np.nan)
    tags = e["Tags"]
    ptag = e["PTag"] or tags[0]
    row0 = e["Rows"][tags[0]]
    close = t6_f(fv("Close")) if inf else t6_f(row0.get("Close"))
    if isnan(close) or close <= 0:
        return None
    pivot = e["Pivot"] if not isnan(e["Pivot"]) else close
    dist = (close / pivot - 1) * 100
    through = dist > 0
    entry = close if through else pivot * 1.001              # 已升穿 pivot 的，以現價計風險
    atrp = t6_f(fv("ATR%"))
    if isnan(atrp) and t in HTF_PX and len(HTF_PX[t]) >= 5:
        hp = HTF_PX[t].tail(14)
        atrp = t6_f(((hp["h"] - hp["l"]) / hp["c"]).mean() * 100)
    atrp = 4.0 if isnan(atrp) else atrp

    # 止蝕：先用形態本身的低位；太遠（超過上限）或太近（少過一個正常波動）都要處理
    stop_nat, stop_src, clipped = e["Stop"], "形態低位", False
    if not isnan(stop_nat):
        clipped = t6_f(e["Rows"][ptag].get("Risk%")) >= MAX_STOP_PCT - 0.02      # 掃描時已被 8% 上限截短
    elif inf:
        if ptag == "收窄":
            stop_nat, stop_src = t6_f(L[t].iloc[-10:].min()) * 0.995, "10 日低位"
        elif ptag == "新高突破":
            stop_nat, stop_src = t6_f(L[t].iloc[-1]) * 0.995, "突破日低位"
        elif ptag == "回調":
            stop_nat, stop_src = t6_f(fv("L3")) * 0.995, "3 日低位"
    if isnan(stop_nat) or stop_nat >= entry:
        stop_nat, stop_src, clipped = entry * (1 - min(MAX_STOP_PCT, max(3.0, 1.5 * atrp)) / 100), "1.5 倍 ATR", False
    risk_nat = (entry - stop_nat) / entry * 100
    min_d = min(MAX_STOP_PCT, max(PLAN["min_stop_pct"], PLAN["min_stop_atr"] * atrp))
    stop, stop_ok, stop_miss = stop_nat, True, ""
    if clipped or risk_nat > MAX_STOP_PCT + 0.05:
        stop, stop_ok = entry * (1 - MAX_STOP_PCT / 100), False
        stop_miss = (f"現價距{stop_src} {risk_nat:.1f}%，超過 {MAX_STOP_PCT:g}%：等回到觸發價附近" if (through and not clipped)
                     else f"{stop_src}距入場價超過 {MAX_STOP_PCT:g}%：等形態再收窄")
        stop_src = f"暫用 {MAX_STOP_PCT:g}% 上限（{stop_src}更遠）"
    elif risk_nat < min_d:
        stop, stop_src = entry * (1 - min_d / 100), f"{stop_src}太貼近，放寬到 {min_d:.1f}%"
    shares, riskp, posp = size_for(entry, stop)

    rs, secr, ud = t6_f(fv("RS")), t6_f(fv("SecRank")), t6_f(fv("UD"))
    hr = e["Rows"].get("HTF")
    ck = {}
    ck["趨勢"] = (str(fv("Stage")) == "2 上升") if inf else None
    if not inf and t in HTF_PX and len(HTF_PX[t]) >= 50:
        ck["趨勢"] = bool(close > t6_f(HTF_PX[t]["c"].tail(50).mean()))
    ck["RS"] = None if isnan(rs) else bool(rs >= PLAN["rs_min"])
    ck["板塊"] = None if isnan(secr) else bool(secr <= PLAN["sec_top"])
    if "VCP" in tags:
        ck["收縮"] = True
    elif hr is not None:
        fd = t6_f(hr.get("FlagDepth%"))
        ck["收縮"] = None if isnan(fd) else bool(fd <= PLAN["htf_depth"])
    else:
        tp = t6_f(fv("TightPct"))
        ck["收縮"] = None if isnan(tp) else bool(tp <= PLAN["tight_pct"])
    volx, v1050 = t6_f(fv("VolX")), t6_f(fv("Vol10/50"))
    if ptag == "新高突破" or (hr is not None and hr.get("State") == "突破旗形"):
        ck["成交"] = None if isnan(volx) else bool(volx >= TH["vol_confirm"])       # 剛突破的看突破日有沒有放量
    elif hr is not None:
        vr = t6_f(hr.get("VolR"))
        ck["成交"] = None if isnan(vr) else bool(vr <= PLAN["htf_volr"])            # 旗形的成交要比旗桿少
    else:
        ck["成交"] = None if isnan(v1050) else bool(v1050 <= PLAN["vol_dry"])       # 未突破的看量縮
    ck["資金"] = None if isnan(ud) else bool(ud >= PLAN["ud_min"])
    ck["距離"] = bool(-PLAN["near_trigger"] <= dist <= TH["extended_pct"])
    ck["事件"], n_e, ev_miss = t6_event(t)

    miss = []                                                    # 未達 A 級的原因：（類別，文字）
    if tags == ["抗跌強勢"]:
        miss.append(("形態", "只在抗跌強勢名單，未有收縮或突破形態"))
    if tags == ["自選"]:
        miss.append(("形態", "不在任何掃描名單，未有系統認可的形態"))
    if ck["趨勢"] is False:
        miss.append(("趨勢", "未在 Stage 2（收市 > 50 日線 > 200 日線）"))
    if dist < -PLAN["near_trigger"]:
        miss.append(("距離", f"距觸發價還有 {abs(dist):.1f}%"))
    if ck["事件"] is not True:
        miss.append(("財報", ev_miss))
    if not stop_ok:
        miss.append(("止蝕", stop_miss))
    c = {"Ticker": t, "Side": "多", "Setup": "＋".join(tags), "Main": tags[0], "PTag": ptag, "Tags": tags, "Close": close,
         "Pivot": pivot, "Trigger": pivot * 1.001, "Entry": entry, "Dist%": dist, "Through": through,
         "Chase": pivot * (1 + TH["extended_pct"] / 100), "Stop": stop, "StopSrc": stop_src, "Risk%": riskp,
         "Shares": shares, "Pos%": posp, "RS": rs, "SecETF": (fv("SecETF") if inf else "") or "", "SecRank": secr, "UD": ud,
         "ATR%": atrp, "Earn": earn_str(t), "EarnN": n_e, "Ck": ck, "Miss": miss, "InPool": inf, "DTC": np.nan, "Imp": None,
         "Tier": "", "Reason": "", "Drop": "", "ShCap": "", "Corr": [], "Far": bool(dist < -PLAN["b_far"])}
    t6_count(c)
    if c["NFail"] > PLAN["max_fails"]:
        miss.append(("清單", f"清單有 {c['NFail']} 項不通過（{'、'.join(c['Fails'])}）"))

    why = []                                                     # 「為甚麼是它」：只寫數據，不加形容
    v_ = e["Rows"].get("VCP")
    if v_ is not None:
        why.append(f"VCP {v_.get('Contr')}，量縮比 {fnum(t6_f(v_.get('VolDry')))}，底部 {fnum(t6_f(v_.get('BaseDays')), 0)} 日")
    if hr is not None:
        why.append(f"High Tight Flag：旗桿升 {fnum(t6_f(hr.get('PoleGain%')), 0)}%（{fnum(t6_f(hr.get('PoleDays')), 0)} 日），"
                   f"旗形 {fnum(t6_f(hr.get('FlagDays')), 0)} 日、回調 {fnum(t6_f(hr.get('FlagDepth%')), 0)}%")
    if "收窄" in tags:
        why.append(f"10 日波幅收到 {fnum(t6_f(fv('R10%')), 1)}%（半年內第 {fnum(t6_f(fv('TightPct')) * 100, 0)} 百分位），量縮比 {fnum(v1050)}")
    if "新高突破" in tags:
        why.append(f"上日首次收市創 52 週高，成交 {fnum(volx, 1)} 倍")
    if "回調" in tags:
        why.append(f"回調到 {e['Rows']['回調'].get('At', '均線')}，近 3 日成交低於平均")
    if "抗跌強勢" in tags:
        why.append(f"指數見頂以來 {fnum(t6_f(fv('SincePeak%')), 1, '%', True)}，RS 線創新高")
    ex = []
    if not isnan(rs):
        ex.append(f"RS {rs:.0f}")
    if not isnan(secr) and c["SecETF"]:
        ex.append(f"{SECTOR_ETFS.get(c['SecETF'], c['SecETF'])}板塊排第 {secr:.0f}")
    if not isnan(ud):
        ex.append(f"U/D 量比 {ud:.2f}")
    c["Why"] = "；".join(why + (["，".join(ex)] if ex else []))
    return c

def t6_eval_short(r):
    """一隻做空候選（回抽阻力名單）：跌穿 3 日低位入場，止蝕放 3 日高位之上。"""
    t = r["Ticker"]
    close, l3, h3 = t6_f(r.get("Close")), t6_f(r.get("L3")), t6_f(r.get("H3"))
    if isnan(close) or isnan(l3) or isnan(h3):
        return None
    entry, stop = l3 * 0.999, h3 * 1.005
    if stop <= entry or entry <= 0:
        return None
    risk_ps = stop - entry
    riskp = risk_ps / entry * 100
    short_risk = ACCOUNT_EQUITY * BASE_RISK_PCT / 100 * TH["risk_mult"]["short"]
    shares = int(short_risk // risk_ps)
    dist = (close / entry - 1) * 100                             # 現價高於觸發價幾多
    rs, secr, ud = t6_f(r.get("RS")), t6_f(r.get("SecRank")), t6_f(r.get("UD"))
    f50, exta = t6_f(r.get("From50%")), t6_f(r.get("ExtATR"))
    over = (not isnan(f50) and f50 <= -TH["short_ext_pct50"]) or (not isnan(exta) and exta <= -TH["short_ext_atr"])
    ck = {"趨勢": str(r.get("Stage")) == "4 下跌",
          "RS": None if isnan(rs) else bool(rs <= PLAN["s_rs_max"]),
          "板塊": None if isnan(secr) else bool(secr >= PLAN["s_sec_bottom"]),
          "未超跌": None if (isnan(f50) and isnan(exta)) else (not over),
          "資金": None if isnan(ud) else bool(ud <= PLAN["s_ud_max"]),
          "距離": bool(dist <= PLAN["near_trigger"]),
          "軋空": None}
    ck["事件"], n_e, ev_miss = t6_event(t)
    miss = []
    if dist > PLAN["near_trigger"]:
        miss.append(("距離", f"現價高於觸發價 {dist:.1f}%，未到位"))
    if ck["事件"] is not True:
        miss.append(("財報", ev_miss))
    if riskp > MAX_STOP_PCT + 0.05:
        miss.append(("止蝕", f"3 日高位距觸發價 {riskp:.1f}%，超過 {MAX_STOP_PCT:g}%"))
    if over:
        miss.append(("超跌", "已超跌，不追空"))
    at = "21EMA" if (not isnan(t6_f(r.get("From21%"))) and -3.0 <= t6_f(r.get("From21%")) <= 1.0) else "50 日線"
    ex = [f"Stage 4，反彈到下降中的 {at}"]
    if not isnan(rs):
        ex.append(f"RS {rs:.0f}")
    sec = r.get("SecETF") if isinstance(r.get("SecETF"), str) else ""
    if not isnan(secr) and sec:
        ex.append(f"{SECTOR_ETFS.get(sec, sec)}板塊排第 {secr:.0f}")
    if not isnan(ud):
        ex.append(f"U/D 量比 {ud:.2f}")
    c = {"Ticker": t, "Side": "空", "Setup": "回抽阻力", "Main": "回抽阻力", "PTag": "回抽阻力", "Tags": ["回抽阻力"], "Close": close,
         "Pivot": l3, "Trigger": entry, "Entry": entry, "Dist%": dist, "Through": False, "Chase": entry * (1 - PLAN["near_trigger"] / 100),
         "Stop": stop, "StopSrc": "3 日高位之上", "Risk%": riskp, "Shares": shares, "Pos%": shares * entry / ACCOUNT_EQUITY * 100,
         "RS": rs, "SecETF": sec or "", "SecRank": secr, "UD": ud, "ATR%": t6_f(r.get("ATR%")), "Earn": earn_str(t), "EarnN": n_e,
         "Ck": ck, "Miss": miss, "InPool": True, "DTC": np.nan, "Imp": None, "Tier": "", "Reason": "", "Drop": "", "ShCap": "", "Corr": [],
         "Far": bool(over or dist > PLAN["b_far"]), "Why": "，".join(ex)}
    t6_count(c)
    return c

def t6_assign(cands, side, gate_open):
    """分級。首選（閘門開 = A 級，未開 = 預備）要沒有任何「尚欠」；欠一至兩項而且距離不太遠的是 B 級；其餘是觀察。
    排序：清單通過的項數（多者先）、不通過的項數、形態、RS。數據不齊的股票不會因為「沒有不通過」而排前。"""
    is_long = side == "多"
    a_max, b_max = (PLAN["a_max"], PLAN["b_max"]) if is_long else (PLAN["s_a_max"], PLAN["s_b_max"])
    top = "A" if gate_open else "預備"
    def rk(c):
        rs = c["RS"] if not isnan(c["RS"]) else 50.0
        return (-c["NPass"], c["NFail"], T6_ORDER.get(c["Main"], 9), -rs if is_long else rs)
    live = []
    for c in cands:
        c["Tier"], c["Reason"] = "", ""
        if c["Drop"]:
            c["Tier"], c["Reason"] = "剔除", c["Drop"]
        else:
            live.append(c)
    sec_n = {}
    if is_long:                                                  # 現有持倉也佔板塊名額
        for t in POSITIONS:
            if t in F.index and F.at[t, "SecETF"]:
                sec_n[F.at[t, "SecETF"]] = sec_n.get(F.at[t, "SecETF"], 0) + 1
    picked, spill = [], []
    for c in sorted([x for x in live if not x["Miss"]], key=rk):
        s_ = c["SecETF"]
        if s_ and sec_n.get(s_, 0) >= PLAN["per_sector"]:
            c["Reason"] = f"同板塊已有 {PLAN['per_sector']} 隻（{SECTOR_ETFS.get(s_, s_)}{'，連持倉計' if POSITIONS else ''}）"
            spill.append(c)
        elif len(picked) >= a_max:
            c["Reason"] = f"{top}名額已滿（{a_max} 隻），排序在後"
            spill.append(c)
        else:
            c["Tier"] = top
            picked.append(c)
            if s_:
                sec_n[s_] = sec_n.get(s_, 0) + 1
    bpool = spill + sorted([x for x in live if x["Miss"] and len(x["Miss"]) <= 2 and not x["Far"]], key=lambda x: (len(x["Miss"]),) + rk(x))
    for i, c in enumerate(bpool):
        if not c["Reason"]:
            c["Reason"] = "；".join(m[1] for m in c["Miss"])
        c["Tier"] = "B" if i < b_max else "觀察"
        if i >= b_max:
            c["Reason"] += "；B 級名額已滿"
    for c in live:
        if not c["Tier"]:
            c["Tier"], c["Reason"] = "觀察", "；".join(m[1] for m in c["Miss"])
    return picked, bpool[:b_max]

def t6_build():
    global T6_L, T6_S, T6_LA, T6_LB, T6_SA, T6_SB
    pool = t6_long_pool()
    if FETCH_EVENTS and not OBB_EARN_FULL:                       # Nasdaq 日曆未覆蓋時，候選之中未查過財報日的補查
        need = [t for t in pool if t in F.index and t not in EARN and t not in EARN_FAIL]
        need = sorted(need, key=lambda t: -(F.at[t, "RS"] if not isnan(F.at[t, "RS"]) else 0))[:25]
        if need:
            print(f"分級：補查 {len(need)} 隻候選的財報日…")
            fetch_earnings(need)
    T6_L = [c for c in (t6_eval_long(t, e) for t, e in pool.items()) if c]
    for c in T6_L:
        pin = t6_pinned(c["Ticker"])
        if c["Ticker"] in POSITIONS:
            c["Drop"] = "已持有，見持倉檢查"
        elif pin:
            c["Drop"] = pin
        elif c["Dist%"] > TH["extended_pct"]:
            c["Drop"] = f"已高出 pivot {c['Dist%']:.1f}%，超過買入區"
    T6_LA, T6_LB = t6_assign(T6_L, "多", long_ok)
    if SHORT_SETUP and len(S_RETEST):
        T6_S = [c for c in (t6_eval_short(r) for r in S_RETEST.to_dict("records")) if c]
        for c in T6_S:
            if c["Ticker"] in POSITIONS:
                c["Drop"] = "已持有，見持倉檢查"
    T6_SA, T6_SB = t6_assign(T6_S, "空", T6_SGATE)
    miss_px = [c["Ticker"] for c in (T6_LA + T6_SA) if c["Ticker"] not in PM]
    if miss_px:                                                  # 首選名單之中未有盤前／盤後報價的，補取一次
        try:
            PM.update(latest_after_close(miss_px[:12]))
        except Exception:
            pass

def t6_watchlist():
    """自選名單體檢：表單「額外股票」內的代號，用同一套清單檢查，並寫明系統的看法。"""
    global T6_WATCH, T6_WATCH_NA
    by = {c["Ticker"]: c for c in T6_L}
    rows, na = [], []
    for t in EXTRA_TICKERS:
        if t in by:
            rows.append(by[t])
        elif t in F.index and not isnan(F.at[t, "Close"]):
            c = t6_eval_long(t, {"Tags": ["自選"], "Pivot": t6_f(F.at[t, "Pivot10"]), "Stop": np.nan, "PTag": "自選",
                                 "Rows": {"自選": {"Close": F.at[t, "Close"]}}})
            if c is None:
                na.append(t)
                continue
            pin = t6_pinned(t)
            c["Tier"] = "自選"
            c["Reason"] = "；".join(([pin] if pin else []) + [m[1] for m in c["Miss"]])
            rows.append(c)
        else:
            na.append(t)
    T6_WATCH, T6_WATCH_NA = rows, na

try:
    print("分級：合併候選、逐隻做八項清單…")
    t6_build()
    T6_SI_L = [c["Ticker"] for c in (T6_LA + T6_LB)][:15]
    T6_SI_S = [c["Ticker"] for c in (T6_SA + T6_SB)][:8]
except Exception as e:
    t6_fail("分級", e)
if V6_OK and EXTRA_TICKERS:
    try:
        t6_watchlist()
    except Exception as e:
        t6_warn("自選名單體檢", e)



# ---------- 版面 ----------
class Raw(str):
    """已經是 HTML 的字串（不再轉義）。"""

METHOD_CK = []

def esc(x):
    return _html.escape(str(x))

NUMK = {"i", "p", "pct", "pctn", "x", "rs", "atr", "pct0"}
def cell(v, k):
    if k == "tk":
        return f"<td><b>{esc(v)}</b></td>"
    if k == "b":
        return '<td class="g">✓</td>' if (v is True or v == True) and not isnan(v) else '<td class="m">–</td>'
    if isnan(v) or (isinstance(v, str) and v in ("nan", "")):
        return '<td class="m num">—</td>' if k in NUMK else '<td class="m">—</td>'
    if k == "t":
        return f"<td>{esc(v)}</td>"
    if k in NUMK and not isinstance(v, (int, float, np.integer, np.floating)):
        return f'<td class="num">{esc(v)}</td>'
    if k == "i":
        return f'<td class="num">{v:,.0f}</td>'
    if k == "p":
        return f'<td class="num">{v:,.2f}</td>'
    if k == "x":
        return f'<td class="num">{v:,.2f}</td>'
    if k == "pctn":
        return f'<td class="num">{v:,.1f}%</td>'
    if k == "pct0":
        return f'<td class="num">{v:,.0f}%</td>'
    if k in ("pct", "atr"):
        c = "g" if v > 0 else "r" if v < 0 else "m"
        return f'<td class="num {c}">{v:+,.1f}{"%" if k == "pct" else ""}</td>'
    if k == "rs":
        c = "g" if v >= 80 else "r" if v <= 20 else ""
        return f'<td class="num {c}"><b>{v:.0f}</b></td>'
    if k == "stage":
        c = {"2": "g", "4": "r", "3": "a"}.get(str(v)[:1], "m")
        return f'<td class="{c}">{esc(v)}</td>'
    if k == "risk":
        return f'<td class="{"r" if "超跌" in str(v) else "a"}">{esc(v)}</td>'
    return f"<td>{esc(v)}</td>"

def render(df, spec, n=None, empty="沒有符合條件的股票"):
    if df is None or len(df) == 0:
        return f'<div class="note">{esc(empty)}</div>'
    d = df.head(n) if n else df
    th = "".join(f'<th class="{"num" if k in NUMK else ""}">{esc(hd)}</th>' for _, hd, k in spec)
    body = []
    for rec in d.to_dict("records"):
        body.append("<tr>" + "".join(cell(rec.get(col), k) for col, _, k in spec) + "</tr>")
    more = f'<div class="note">共 {len(df)} 隻，顯示首 {len(d)} 隻；完整名單在 CSV。</div>' if n and len(df) > n else ""
    return f'<div class="tw"><table><thead><tr>{th}</tr></thead><tbody>{"".join(body)}</tbody></table></div>{more}'

def pill(label, state):
    return f'<span class="pill {state}">{esc(label)}</span>'

def bar(v):
    col = "#0a7d33" if v >= 70 else "#b7791f" if v >= 40 else "#c0392b"
    return f'<div class="bar"><i style="width:{max(min(v, 100), 0):.0f}%;background:{col}"></i></div>'

def section(title, inner, open_=False, sub=""):
    return (f'<details{" open" if open_ else ""}><summary>{esc(title)}'
            + (f' <span class="cnt">{esc(sub)}</span>' if sub else "") + f'</summary><div class="sec">{inner}</div></details>')

def names(d, n=4):
    return "、".join(d["Ticker"].head(n)) if len(d) else "—"

COMMON = [("Ticker", "代號", "tk"), ("SecETF", "板塊", "t"), ("SecRank", "板塊排名", "i"), ("RS", "RS", "rs")]
SPEC = dict(
    vcp=COMMON + [("Close", "收市", "p"), ("Pivot", "Pivot", "p"), ("Dist%", "距 Pivot", "pct"), ("Contr", "收縮", "t"),
                  ("VolDry", "量縮比", "x"), ("BaseDays", "底部日數", "i"), ("Stop", "止蝕", "p"), ("Risk%", "風險", "pctn"),
                  ("Shares", "股數", "i"), ("Pos%", "倉位", "pctn"), ("UD", "U/D 量比", "x"), ("Earn", "財報日", "t")],
    tight=COMMON + [("Close", "收市", "p"), ("R10%", "10 日波幅", "pctn"), ("TightPctD", "收窄百分位", "pct0"),
                    ("Vol10/50", "量縮比", "x"), ("Pivot10", "Pivot（10 日高）", "p"), ("DistPivot%", "距 Pivot", "pct"),
                    ("FromHigh%", "距 52 週高", "pct"), ("UD", "U/D 量比", "x"), ("Earn", "財報日", "t")],
    bo=COMMON + [("Close", "收市", "p"), ("Chg%", "升跌", "pct"), ("VolX", "成交倍數", "x"), ("VolOK", "量確認", "b"),
                 ("Pivot52W", "突破位", "p"), ("Ext%", "高於突破位", "pct"), ("IsATH", "歷史新高", "b"),
                 ("From50%", "距 50 日線", "pct"), ("Earn", "財報日", "t")],
    ath=COMMON + [("Close", "收市", "p"), ("ATH", "歷史高位", "p"), ("FromATH%", "距歷史高位", "pct"), ("IsATH", "收市創新高", "b"),
                  ("FirstDay", "首日", "b"), ("VolX", "成交倍數", "x"), ("Years", "上市年數", "t")],
    resil=COMMON + [("Close", "收市", "p"), ("FromHigh%", "距 52 週高", "pct"), ("SincePeak%", "指數見頂以來", "pct"),
                    ("RSLHigh", "RS 線新高", "b"), ("RS1M", "1 個月 RS", "rs"), ("From50%", "距 50 日線", "pct"),
                    ("VolX", "成交倍數", "x"), ("UD", "U/D 量比", "x"), ("Earn", "財報日", "t")],
    pull=COMMON + [("Close", "收市", "p"), ("At", "回調至", "t"), ("From21%", "距 21EMA", "pct"), ("From50%", "距 50 日線", "pct"),
                   ("FromHigh%", "距 52 週高", "pct"), ("VolX", "成交倍數", "x"), ("UD", "U/D 量比", "x"), ("Earn", "財報日", "t")],
    gap=COMMON + [("Close", "收市", "p"), ("Gap%", "缺口", "pct"), ("Chg%", "全日升跌", "pct"), ("VolX", "成交倍數", "x"),
                  ("Stage", "階段", "stage"), ("FromHigh%", "距 52 週高", "pct")],
    bo1m=COMMON + [("Close", "收市", "p"), ("Chg%", "升跌", "pct"), ("VolX", "成交倍數", "x"), ("FromHigh%", "距 52 週高", "pct"),
                   ("From50%", "距 50 日線", "pct")],
    retest=COMMON + [("Close", "收市", "p"), ("From21%", "距 21EMA", "pct"), ("From50%", "距 50 日線", "pct"),
                     ("Ret3D%", "3 日升跌", "pct"), ("VolX", "成交倍數", "x"), ("FromHigh%", "距 52 週高", "pct"), ("Earn", "財報日", "t")],
    bd=COMMON + [("Close", "收市", "p"), ("Chg%", "升跌", "pct"), ("VolX", "成交倍數", "x"), ("New52L", "52 週新低", "b"),
                 ("From50%", "距 50 日線", "pct"), ("ExtATR", "距 21EMA（ATR）", "atr"), ("Risk", "追空風險", "risk"), ("Earn", "財報日", "t")],
    fallen=COMMON + [("RS12", "12 個月 RS（舊）", "rs"), ("RS1M", "1 個月 RS", "rs"), ("Close", "收市", "p"),
                     ("FromHigh%", "距 52 週高", "pct"), ("From50%", "距 50 日線", "pct"), ("R252%", "12 個月回報", "pct"),
                     ("R63%", "3 個月回報", "pct"), ("Stage", "階段", "stage")],
    htf=[("Ticker", "代號", "tk"), ("Src", "來源", "t"), ("Ind", "行業", "t"), ("State", "狀態", "t"), ("Note", "備註", "risk"), ("RS", "RS", "rs"), ("Close", "收市", "p"),
         ("Jump%", "最大單日升幅", "pct"),
         ("PoleGain%", "旗桿升幅", "pct"), ("PoleDays", "旗桿日數", "i"), ("FlagDays", "旗形日數", "i"), ("FlagDepth%", "旗形回調", "pctn"),
         ("VolR", "量比（旗形／旗桿）", "x"), ("Pivot", "Pivot（旗桿高位）", "p"), ("Dist%", "距 Pivot", "pct"),
         ("DV20M", "日均成交（百萬）", "i"), ("Stop", "止蝕", "p"), ("Shares", "股數", "i"), ("Earn", "財報日", "t")],
    rsd=[("Ticker", "代號", "tk"), ("RS", "RS（v3）", "rs"), ("RS12", "12 個月 RS（舊）", "rs"), ("R21%", "1 個月", "pct"),
         ("R63%", "3 個月", "pct"), ("R126%", "6 個月", "pct"), ("R189%", "9 個月", "pct"), ("R252%", "12 個月", "pct"),
         ("FromHigh%", "距 52 週高", "pct")],
    lead=[("Ticker", "代號", "tk"), ("SecETF", "板塊", "t"), ("Stage", "階段", "stage"), ("RS", "RS", "rs"), ("RS12", "12 個月 RS（舊）", "rs"), ("RS1M", "1 個月 RS", "rs"),
          ("Close", "收市", "p"), ("Chg%", "升跌", "pct"), ("VolX", "成交倍數", "x"), ("FromHigh%", "距 52 週高", "pct"),
          ("From50%", "距 50 日線", "pct"), ("Earn", "財報日", "t")],
    sect=[("Rank", "排名", "i"), ("RankChg", "5 日排名變化", "t"), ("ETF", "ETF", "tk"), ("Name", "板塊", "t"), ("R21", "1 個月", "pct"), ("R63", "3 個月", "pct"), ("Ex21", "1 個月超額", "pct"),
          ("Above50", "> 50 日線", "b"), ("FromHigh", "距 52 週高", "pct"), ("Pct50", "成份股 > 50 日線", "pct0"),
          ("NH", "52 週新高", "i"), ("NL", "52 週新低", "i")],
    ind=[("ETF", "ETF", "tk"), ("Name", "行業", "t"), ("R21", "1 個月", "pct"), ("R63", "3 個月", "pct"), ("Ex21", "1 個月超額", "pct"),
         ("Above50", "> 50 日線", "b"), ("FromHigh", "距 52 週高", "pct")],
    grp=[("SubInd", "行業組別（GICS）", "t"), ("n", "隻數", "i"), ("r21", "1 個月中位", "pct"), ("r63", "3 個月中位", "pct"),
         ("pct50", "> 50 日線", "pct0"), ("rs", "RS 中位", "rs"), ("nh", "新高", "i"), ("Names", "RS 最高的三隻", "t")],
    levels=[("Level", "關鍵位", "t"), ("Px", "價位", "p"), ("Dist%", "距參考價", "pct")],
    ovn=[("Name", "項目", "t"), ("Last", "最新", "p"), ("Chg", "自美股收市以來", "t"), ("Time", "報價時間（美東）", "t")],
    pmg=[("Ticker", "代號", "tk"), ("SecETF", "板塊", "t"), ("PM", "盤前價", "p"), ("PMGap%", "盤前缺口", "pct"), ("RS", "RS", "rs"),
         ("Stage", "階段", "stage"), ("FromHigh%", "距 52 週高", "pct"), ("InList", "在名單內", "b")],
    econ=[("Tier", "重要性", "t"), ("When", "時間（美東）", "t"), ("Event", "數據", "t"), ("For", "期間", "t"), ("Expected", "預期", "x"), ("Last", "前值", "x")],
    react=[("Symbol", "代號", "tk"), ("Company", "公司", "t"), ("When", "公佈", "t"), ("Surp", "盈利驚喜", "pct"), ("Move", "股價反應", "pct"),
           ("Src", "反應來源", "t"), ("VolX", "成交倍數", "x"), ("RS", "RS", "rs"), ("Stage", "階段", "stage"), ("Verdict", "判讀", "t")],
    enext=[("Symbol", "代號", "tk"), ("Company", "公司", "t"), ("When", "時間", "t"), ("RS", "RS", "rs"), ("Stage", "階段", "stage"), ("InList", "在名單／持倉", "b")],
    idx=[("ETF", "ETF", "tk"), ("Name", "指數", "t"), ("Close", "收市", "p"), ("D1", "1 日", "pct"), ("D5", "5 日", "pct"), ("A21", "> 21EMA", "b"),
         ("A50", "> 50 日線", "b"), ("A200", "> 200 日線", "b"), ("FromHigh", "距 52 週高", "pct"), ("Dist", "派發日", "i")],
    br=[("Grp", "範圍", "t"), ("n", "隻數", "i"), ("P50", "> 50 日線", "pct0"), ("P200", "> 200 日線", "pct0"), ("S2", "Stage 2", "pct0"),
        ("NH", "52 週高突破", "i"), ("NL", "52 週低跌破", "i")],
    dist=[("Date", "日期", "t"), ("Chg%", "當日跌幅", "pct"), ("Left", "尚餘交易日", "i"), ("Kill", "QQQ 收高於此即失效", "p")],
    focus_l=[("Ticker", "代號", "tk"), ("Setup", "形態", "t"), ("RS", "RS", "rs"), ("SecETF", "板塊", "t"), ("SecRank", "板塊排名", "i"),
             ("Close", "收市", "p"), ("Trigger", "觸發價", "p"), ("Dist%", "現價距觸發", "pct"), ("Status", "狀態", "t"), ("Stop", "止蝕", "p"), ("Risk%", "風險", "pctn"),
             ("UD", "U/D 量比", "x"), ("Earn", "財報日", "t")],
    focus_s=[("Ticker", "代號", "tk"), ("Setup", "形態", "t"), ("RS", "RS", "rs"), ("SecETF", "板塊", "t"), ("SecRank", "板塊排名", "i"),
             ("Close", "收市", "p"), ("Trigger", "觸發價（跌穿）", "p"), ("Stop", "止蝕", "p"), ("Risk%", "風險", "pctn"), ("Earn", "財報日", "t")],
    alerts=[("Ticker", "代號", "tk"), ("Dir", "方向", "t"), ("Px", "價位", "p"), ("Why", "原因", "t")],
    pos=[("Ticker", "代號", "tk"), ("Px", "現價", "p"), ("Entry", "入場價", "p"), ("PnL%", "盈虧", "pct"), ("R", "R 倍數", "atr"),
         ("Days", "持有日", "i"), ("Stop", "止蝕", "p"), ("ToStop%", "距止蝕", "pct"), ("Stage", "階段", "stage"),
         ("RS", "RS", "rs"), ("Risk$", "未平倉風險 $", "i"), ("Earn", "財報日", "t"), ("Trail", "參考位", "t"), ("Note", "備註", "t")],
    attr=[("Pillar", "支柱", "t"), ("W", "權重 %", "i"), ("Prev5", "5 日前", "i"), ("Now", "現在", "i"), ("Contrib", "對總分的影響", "atr")],
)

REG_COLOR = {"A": ("#0a7d33", "#eaf6ee"), "B": ("#3c8c3c", "#eef7ea"), "C": ("#b7791f", "#fdf6e3"),
             "D": ("#c05621", "#fdf0e6"), "E": ("#c0392b", "#fdecea")}[REG_L]

# 圖表（嵌入版面）
CHART_IMG = ""
try:
    import matplotlib.pyplot as plt
    w = 250
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 5.6), sharex=True, gridspec_kw={"height_ratios": [2.2, 1]})
    ax1.plot(Q["c"].iloc[-w:], color="black", lw=1.3, label="QQQ")
    ax1.plot(Q["ema21"].iloc[-w:], lw=0.9, label="21 EMA")
    ax1.plot(Q["s50"].iloc[-w:], lw=0.9, label="50 SMA")
    ax1.plot(Q["s200"].iloc[-w:], lw=0.9, label="200 SMA")
    if RALLY["in_correction"]:
        ax1.axhline(RALLY["low"], color="#c0392b", lw=0.8, ls=":")
    ax1.set_title(f"QQQ and Market Health Score (as of {ASOF:%Y-%m-%d})", fontsize=10)
    ax1.legend(loc="upper left", fontsize=8)
    ax1.grid(alpha=0.3)
    ax2.plot(SCORE.iloc[-w:], color="tab:blue", lw=1.3)
    for lvl in TH["regime_bands"]:
        ax2.axhline(lvl, color="gray", lw=0.6, ls="--")
    ax2.set_ylim(0, 100)
    ax2.set_ylabel("Health score", fontsize=8)
    ax2.grid(alpha=0.3)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100)
    plt.close(fig)
    CHART_IMG = '<img style="max-width:100%" src="data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode() + '"/>'
except Exception as e:
    print(f"圖表略過（{type(e).__name__}）")

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
.pmb details.method{margin:14px 0;border:1px solid #e3e3e3;border-radius:10px;padding:8px 12px}
.pmb details.method summary{font-weight:600;cursor:pointer}
.pmb details.method h4{margin:12px 0 4px;font-size:13.5px}
.pmb details.method p,.pmb details.method li{color:#333}
.pmb .disc{margin:20px 0 4px;padding:12px 0 0;border-top:1px solid #e3e3e3;color:#666;font-size:12px;line-height:1.6}
</style>
"""

# ---------- 補充數據層・第二層（v5.2）：波動結構、引伸波幅、異動榜、沽空、信貸 —— 只顯示，不計入分數和閘門 ----------
OBB_VOL_NAMES = [("VIX1D", "1 日"), ("VIX9D", "9 日"), ("VIX", "30 日（VIX）"), ("VIX3M", "3 個月"), ("VIX6M", "6 個月"),
                 ("VVIX", "VIX 本身的波動（VVIX）"), ("SKEW", "尾部風險（SKEW）")]
OSPEC = dict(
    log=[("Feed", "數據", "t"), ("Status", "結果", "t"), ("Rows", "筆數", "i"), ("Sec", "秒", "x"), ("Note", "備註", "t")],
    vol=[("Name", "期限", "t"), ("Sym", "代號", "t"), ("Px", "水平", "p")],
    vx=[("expiration", "到期月", "t"), ("price", "VIX 期貨", "p")],
    imp=[("Ticker", "代號", "tk"), ("Why", "用途", "t"), ("Exp", "期權到期", "t"), ("DTE", "日數", "i"), ("Px", "計算用股價", "p"),
         ("Strike", "行使價", "p"), ("Move%", "跨式成本", "pctn"), ("Dn", "下方打和", "p"), ("Up", "上方打和", "p")],
    mov=[("Ticker", "代號", "tk"), ("Name", "公司", "t"), ("List", "榜", "t"), ("Px", "最新價", "p"), ("Chg%", "相對上日收市", "pct"),
         ("RS", "RS", "rs"), ("Stage", "階段", "stage"), ("InPool", "在股票池", "b"), ("InList", "在名單／持倉", "b"), ("Earn", "財報日", "t")],
    si=[("Ticker", "代號", "tk"), ("Grp", "來自", "t"), ("Settle", "結算日", "t"), ("SIM", "沽空股數（百萬）", "x"),
        ("Chg%", "較上期", "pct"), ("DTC", "回補日數", "x"), ("Read", "判讀", "t")],
    earn=[("Ticker", "代號", "tk"), ("Date", "財報日", "t"), ("Slot", "時段", "t"), ("In", "距今交易日", "i"), ("Held", "持倉", "b")],
)

def yf_vol_snapshot():
    """Cboe 取不到時的後備：由 Yahoo 取同一批波動指數的最新收市值。"""
    d = dl(["^" + s_ for s_, _n in OBB_VOL_NAMES], period="1mo", chunk=20, pause=0.2)
    if "Close" not in d:
        raise RuntimeError("Yahoo 沒有回應")
    cl, rows = d["Close"], []
    for s_, nm in OBB_VOL_NAMES:
        if "^" + s_ in cl.columns and cl["^" + s_].notna().any():
            rows.append({"Sym": s_, "Name": nm, "Px": float(cl["^" + s_].dropna().iloc[-1])})
    return pd.DataFrame(rows)

def yf_straddles(sym, ref_px, need_from, fridays=False):
    """Cboe 取不到時的後備：由 Yahoo 的期權鏈計平價跨式成本。回傳的欄位與 Cboe 版本相同。
    用買賣中間價；沒有買賣報價（收市後常見）就用最後成交價，所以準確度比 Cboe 低。"""
    tk = yf.Ticker(sym)
    exps = sorted(pd.Timestamp(x).date() for x in (tk.options or ()))
    exps = [x for x in exps if x >= need_from]
    if not exps:
        return pd.DataFrame()
    want = [exps[0]]
    if fridays:
        fri = next((x for x in exps if x.weekday() == 4), None)
        if fri is not None and fri != exps[0]:
            want.append(fri)
    def leg(df, k):
        r_ = df[df["strike"] == k].iloc[0]
        b_, a_, l_ = (pd.to_numeric(r_.get(c_), errors="coerce") for c_ in ("bid", "ask", "lastPrice"))
        if pd.notna(b_) and pd.notna(a_) and b_ > 0 and a_ > 0:
            return float((a_ + b_) / 2)
        return float(l_) if (pd.notna(l_) and l_ > 0) else np.nan
    rows = []
    for e_ in want:
        ch = tk.option_chain(f"{e_:%Y-%m-%d}")
        ks = sorted(set(ch.calls["strike"]) & set(ch.puts["strike"]))
        if not ks:
            continue
        k = min(ks, key=lambda x: abs(x - ref_px))
        c_px, p_px = leg(ch.calls, k), leg(ch.puts, k)
        if isnan(c_px) or isnan(p_px):
            continue
        rows.append({"expiration": f"{e_:%Y-%m-%d}", "dte": (e_ - ASOF.date()).days, "underlying_price": ref_px, "cost": c_px + p_px,
                     "cost_percent": (c_px + p_px) / ref_px * 100, "strike_1": k, "strike_2": k})
        time.sleep(0.3)
    return pd.DataFrame(rows)

def nq_movers(sess_key):
    """Nasdaq 全市場異動榜（一次請求取三個榜）。回傳 symbol、name、price、chg、pct、List。"""
    data = nq_get(f"marketmovers?assetclass=STOCKS&exchangestatus={sess_key}&limit=25") or {}
    block = data.get("STOCKS") or {}
    rows = []
    for key, nm in [("MostAdvanced", "升幅榜"), ("MostDeclined", "跌幅榜"), ("MostActiveByDollarVolume", "成交額榜")]:
        tbl = (block.get(key) or {}).get("table") or {}
        lst = tbl.get("rows") if isinstance(tbl.get("rows"), list) else ((tbl.get("table") or {}).get("rows") or [])
        for r in lst:
            rows.append({"symbol": r.get("symbol"), "name": r.get("name"), "price": r.get("lastSalePrice"), "chg": r.get("lastSaleChange"),
                         "pct": r.get("percentageChange") if "MostActive" in key else r.get("change"), "List": nm})
    return pd.DataFrame(rows)

def obb_extras():
    """逐項取補充數據。每一項獨立，一項出錯不影響其他項。"""
    out = {"key": [], "vol": pd.DataFrame(), "vx": pd.DataFrame(), "imp": pd.DataFrame(), "mov": pd.DataFrame(),
           "si": pd.DataFrame(), "earn": pd.DataFrame(), "mov_label": "", "stale": [], "no_fred": False, "vol_src": "Cboe", "imp_src": "Cboe"}
    now = now_et()
    hm = (now.hour, now.minute)
    live = is_session(now.date()) and (9, 30) <= hm < (16, 15)        # 美股正在交易：期權報價是當刻的

    def _vol():
        v = {}
        snap = obb_call("波動指數快照（Cboe，經 OpenBB）", OBB.cboe.index.snapshots, 60, region="us") if obb_ok("cboe") else None
        if snap is not None and len(snap):
            snap = _need(snap, ["symbol", "price", "prev_close"])
            sym = snap["symbol"].astype(str).str.replace("^", "", regex=False).str.upper().to_numpy()
            px = pd.to_numeric(snap["price"], errors="coerce").fillna(pd.to_numeric(snap["prev_close"], errors="coerce"))
            px = pd.Series(px.to_numpy(), index=sym)
            px = px[~px.index.duplicated()].dropna()
            rows = [{"Sym": s, "Name": n, "Px": float(px[s])} for s, n in OBB_VOL_NAMES if s in px.index]
            out["vol"] = pd.DataFrame(rows)
            v = {r["Sym"]: r["Px"] for r in rows}
        if not v:                                                         # v6.1：Cboe 取不到，改用 Yahoo 的同一批指數（上日收市值）
            yv, _, _ = _direct("波動指數（Yahoo 後備）", yf_vol_snapshot)
            if yv is not None and len(yv):
                out["vol"], out["vol_src"] = yv, "Yahoo 後備，上日收市值"
                v = {r["Sym"]: r["Px"] for r in yv.to_dict("records")}
        if "VIX" in v and v.get("VIX3M", 0) > 0:
            ratio = v["VIX"] / v["VIX3M"]
            state = "逆價差" if ratio >= 1.05 else "接近持平" if ratio >= 0.95 else "正價差"
            read = {"逆價差": "短期恐慌明顯高於中期，急跌多數仍在進行。",
                    "接近持平": "市場仍然緊張，但未到恐慌定價；比率回落到 0.95 以下才算回復正常。",
                    "正價差": "期限結構正常，期權市場沒有為恐慌定價。"}[state]
            short = ""
            if "VIX9D" in v:
                short = f"；VIX9D {v['VIX9D']:.1f}，{'低於' if v['VIX9D'] < v['VIX'] else '高於'} VIX"
            out["key"].append(f"波動結構：VIX {v['VIX']:.1f}，VIX3M {v['VIX3M']:.1f}，比率 {ratio:.2f}（{state}）{short}。{read}")
        vx = obb_call("VIX 期貨曲線（Cboe，經 OpenBB）", OBB.cboe.futures.curve, 60, symbol="VX_EOD") if obb_ok("cboe") else None
        if vx is not None and len(vx):
            vx = _need(vx, ["expiration", "price"])
            vx["price"] = pd.to_numeric(vx["price"], errors="coerce")
            vx = vx.dropna(subset=["price"])[["expiration", "price"]].reset_index(drop=True)
            while len(vx) >= 3 and abs(vx["price"].iloc[-1] / vx["price"].iloc[-2] - 1) > 0.15:
                vx = vx.iloc[:-1]                                         # 最遠月與前一個月相差逾 15%：是未開始交易的舊數字，不要
            out["vx"] = vx
            if len(vx) >= 2 and vx["price"].iloc[0] > 0:
                m1, m2 = float(vx["price"].iloc[0]), float(vx["price"].iloc[1])
                txt = f"VIX 期貨（上日結算）：近月 {m1:.2f}，次月 {m2:.2f}"
                if "VIX" in v:
                    txt += (f"；現貨 VIX {v['VIX']:.2f} {'高於' if v['VIX'] > m1 else '低於'}近月期貨 {abs(v['VIX'] / m1 - 1) * 100:.0f}%"
                            + ("，期貨市場預期波動會回落" if v["VIX"] > m1 * 1.03 else ""))
                out["key"].append(txt + "。")

    def _implied():
        t0, cands = time.time(), []
        for t in (list(POSITIONS) + T6_SI_L + T6_SI_S + (list(FOCUS_L["Ticker"]) if len(FOCUS_L) else [])
                  + (list(FOCUS_S["Ticker"]) if len(FOCUS_S) else []) + list(WATCH)):
            n_e = earn_sessions(t)
            if n_e is not None and 0 <= n_e <= 5 and t not in cands:      # 5 個交易日內有財報的持倉和名單股票
                cands.append(t)
        slot_of = {t: sl for t, (_, sl) in OBB_EARN.items()}
        if len(EARN_NEXT) and "Slot" in EARN_NEXT.columns:
            for s_, sl_ in zip(EARN_NEXT["Symbol"], EARN_NEXT["Slot"]):
                slot_of.setdefault(s_, sl_)
        def close_of(sym):
            if sym == "QQQ":
                return float(Q["c"].iloc[-1])
            return float(F.at[sym, "Close"]) if (sym in F.index and not isnan(F.at[sym, "Close"])) else None
        rows, n_ok, n_try, streak, last_note = [], 0, 0, 0, ""
        use_cboe, cboe_bad, n_yahoo = obb_ok("cboe"), 0, 0
        for sym in ["QQQ"] + cands[:8]:
            if streak >= 2:                                               # 連續兩隻取不到就停，免得拖慢簡報
                break
            n_try += 1
            # 收市後和盤前，期權報價仍是上日收市的；行使價要用上日收市價，否則會把價內值當成波幅
            c0 = None if live else close_of(sym)
            kw = {"symbol": sym.replace("-", ".")}
            if c0:
                kw["strike"] = c0
            sd, st, note = None, "失敗", "Cboe 未載入"
            if use_cboe:
                sd, st, note, _ = _obb_raw(OBB.cboe.options.straddle, 45, **kw)
                if sd is None:
                    cboe_bad += 1
                    use_cboe = cboe_bad < 2                               # Cboe 連續兩次取不到，其後直接用 Yahoo
            if sd is None or not len(sd):                                 # v6.1：Cboe 取不到，改用 Yahoo 的期權鏈
                try:
                    d0_ = EARN.get(sym)
                    frm = SESS_D if sym == "QQQ" else (next_session(d0_) if (d0_ is not None and slot_of.get(sym, "") == "收市後") else d0_)
                    ref = c0 or close_of(sym)
                    sd = yf_straddles(sym, ref, frm, fridays=(sym == "QQQ")) if (ref and frm is not None) else None
                    if sd is not None and len(sd):
                        n_yahoo += 1
                except Exception as e:
                    sd, note = None, f"Yahoo 後備也取不到（{type(e).__name__}）"
            if sd is None or not len(sd):
                streak, last_note = streak + 1, (note or st)
                continue
            sd = _need(sd, ["expiration", "dte", "underlying_price", "cost", "cost_percent", "strike_1", "strike_2"])
            sd["_e"] = pd.to_datetime(sd["expiration"], errors="coerce").dt.date
            for col in ("cost", "cost_percent", "strike_1", "strike_2", "underlying_price"):
                sd[col] = pd.to_numeric(sd[col], errors="coerce")
            sd["_base"] = c0 if c0 else sd["underlying_price"]
            sd["_mv"] = sd["cost"].abs() / sd["_base"] * 100
            sd["_mv"] = sd["_mv"].fillna(sd["cost_percent"])
            sd = sd[pd.notna(sd["_e"]) & sd["_mv"].between(0.05, 60)].sort_values("_e")
            if not len(sd):
                streak, last_note = streak + 1, "期權報價不合理"
                continue
            n_ok, streak = n_ok + 1, 0
            if sym == "QQQ":
                near = sd[sd["_e"] >= SESS_D].head(1)
                picks = [("大市：最近到期", near)]
                fri = sd[(sd["_e"] >= SESS_D) & sd["_e"].map(lambda x: x.weekday() == 4)].head(1)
                if len(fri) and len(near) and fri["_e"].iloc[0] != near["_e"].iloc[0]:
                    picks.append(("大市：本週五到期", fri))
            else:
                d0, slot = EARN.get(sym), slot_of.get(sym, "")
                react = next_session(d0) if slot == "收市後" else d0      # 股價對財報作出反應的那個交易日
                picks = [(f"財報 {d0:%m-%d}" + (f" {slot}" if slot else ""), sd[sd["_e"] >= react].head(1))]
            for why, r in picks:
                if len(r):
                    r = r.iloc[0]
                    cost = abs(float(r["cost"])) if not isnan(r["cost"]) else float(r["_base"]) * float(r["_mv"]) / 100
                    k1 = r["strike_1"] if not isnan(r["strike_1"]) else r["_base"]
                    k2 = r["strike_2"] if not isnan(r["strike_2"]) else r["_base"]
                    rows.append({"Ticker": sym, "Why": why, "Exp": f"{r['_e']:%m-%d}", "DTE": r["dte"], "Px": r["_base"], "Strike": k1,
                                 "Move%": r["_mv"], "Dn": k2 - cost, "Up": k1 + cost})
        out["imp_src"] = "Yahoo 後備" if n_yahoo else "Cboe"
        OBB_LOG.append({"Feed": "期權引伸波幅（Yahoo 後備，Cboe 取不到）" if n_yahoo else "期權引伸波幅（Cboe，經 OpenBB）",
                        "Status": "成功" if (n_ok and n_ok == n_try) else "部分成功" if n_ok else "失敗",
                        "Rows": len(rows), "Sec": time.time() - t0,
                        "Note": f"{n_ok}/{n_try} 隻" + (f"；{last_note}" if (last_note and n_ok < n_try) else "")})
        out["imp"] = pd.DataFrame(rows)
        qrows = [r for r in rows if r["Ticker"] == "QQQ"]
        if qrows:
            out["key"].append(f"QQQ 引伸波幅：到 {qrows[0]['Exp']}（{fnum(qrows[0]['DTE'], 0)} 日）的平價跨式成本 {qrows[0]['Move%']:.1f}%，"
                              f"打和位 {fnum(qrows[0]['Dn'])} 至 {fnum(qrows[0]['Up'])}。")
            if (not live) and qrows[0]["Exp"] == f"{SESS_D:%m-%d}" and not isnan(GAP_PCT) and qrows[0]["Move%"] > 0:
                used = abs(GAP_PCT) / qrows[0]["Move%"] * 100
                if used >= 60:                                            # 隔夜已經走了當日預期波幅的大半
                    out["key"].append(f"隔夜缺口 {GAP_PCT:+.1f}% 已用掉期權為今日定價波幅的 {used:.0f}%："
                                      f"開市後追{'高' if GAP_PCT > 0 else '低'}的風險回報差，等回調或首 30 分鐘區間確立。")
        erows = [r for r in rows if r["Ticker"] != "QQQ"]
        if erows:
            out["key"].append("財報引伸波幅：" + "、".join(f"{r['Ticker']} ±{r['Move%']:.1f}%（{r['Why']}，期權 {r['Exp']} 到期）" for r in erows) + "。")

    def _movers():
        sess_key, lab = ((("premarket", "盤前") if (4, 0) <= hm < (9, 30) else ("currentMarket", "盤中") if (9, 30) <= hm < (16, 0)
                          else ("afterHours", "盤後")) if is_session(now.date()) else ("afterHours", "盤後"))
        mv, _, _ = _direct(f"{lab}異動榜（Nasdaq 直連）", lambda: nq_movers(sess_key))
        out["mov_label"] = lab
        if mv is None or not len(mv):
            return
        mv = _need(mv, ["symbol", "name", "price", "chg", "pct", "List"])
        mv["Ticker"] = mv["symbol"].map(_nq_sym)
        mv["Px"], chg = _num(mv["price"]), _num(mv["chg"])
        mv["Chg%"] = _num(mv["pct"]).fillna(chg / (mv["Px"] - chg) * 100)
        mv.loc[(mv["List"] == "跌幅榜") & (mv["Chg%"] > 0), "Chg%"] *= -1                 # 跌幅榜的數字如果沒有帶負號，補回
        mv["InPool"] = mv["Ticker"].isin(TICKS)
        mv["InList"] = mv["Ticker"].isin(set(WATCH) | set(POSITIONS))
        if lab != "盤中":
            # Nasdaq 的升跌是相對再上一個收市價，會把正常時段的升跌也算進去；股票池成員改用自己的上日收市價計
            ext = (mv["Px"] / mv["Ticker"].map(F["Close"]) - 1) * 100
            mv["Chg%"] = ext.where(mv["InPool"], mv["Chg%"])
            odd = mv["InPool"] & (ext.abs() > 60)                                     # v6.1：與日線相差太遠，多數是拆股或數據錯誤
            if odd.any():
                out["key"].append(f"以下股票的{lab}報價與日線收市價相差超過 60%，疑似拆股或數據錯誤，已從異動榜略過，請自行核對："
                                  + "、".join(f"{t_}（{x_:+.0f}%）" for t_, x_ in zip(mv.loc[odd, "Ticker"], ext[odd])) + "。")
                mv = mv[~odd].copy()
            mv = mv[~mv["InPool"] | mv["InList"] | (mv["Chg%"].abs() >= 1)]          # 延長時段沒有異動的大型股不列
        etf = mv["name"].astype(str).str.contains(r"\b(?:ETF|Trust|Fund|ProShares|Direxion|iShares|SPDR|Vanguard|Invesco)\b", case=False, regex=True)
        mv = mv[mv["InPool"] | (~etf & (mv["Px"] >= 5) & (mv["List"] != "成交額榜"))].copy()   # 池外：不要 ETF、仙股和成交額榜
        for col in ["RS", "Stage"]:
            mv[col] = mv["Ticker"].map(F[col])
        mv["Name"] = mv["name"].astype(str).str.slice(0, 26)
        mv["Earn"] = [earn_str(t) if (t in EARN or t in EARN_FAIL) else "" for t in mv["Ticker"]]
        mv = mv.sort_values(["InList", "InPool", "Chg%"], ascending=[False, False, False]).drop_duplicates("Ticker").reset_index(drop=True)
        out["mov"] = mv
        recs = mv.to_dict("records")
        hit = [r for r in recs if r["InList"] and not isnan(r["Chg%"]) and abs(r["Chg%"]) >= 2]
        if hit:
            out["key"].append(f"名單或持倉內的{lab}異動：" + "、".join(f"{r['Ticker']} {r['Chg%']:+.1f}%" for r in hit[:8]) + "。")
        strong = [r for r in recs if r["InPool"] and not isnan(r["RS"]) and r["RS"] >= 80 and not isnan(r["Chg%"]) and r["Chg%"] >= 3]
        if strong:
            out["key"].append(f"RS 80 以上而{lab}較上日收市再升逾 3% 的股票池成員：" + "、".join(f"{r['Ticker']} {r['Chg%']:+.1f}%" for r in strong[:8]) + "。")

    def _short():
        grp = {}
        def add(ts, g):
            for t in ts:
                grp.setdefault(t, g)
        add(list(POSITIONS), "持倉")
        add(T6_SI_S, "做空焦點")                                 # v6：分級後的做空候選和做多首選、B 級
        add(T6_SI_L, "做多焦點")
        add(list(FOCUS_L["Ticker"]) if len(FOCUS_L) else [], "做多焦點")
        add(list(FOCUS_S["Ticker"]) if len(FOCUS_S) else [], "做空焦點")
        add(list(S_RETEST["Ticker"].head(8)) if len(S_RETEST) else [], "回抽阻力")
        add(list(HTF[HTF["Note"] == ""]["Ticker"].head(5)) if len(HTF) else [], "High Tight Flag")
        syms = list(grp)[:32]
        if not syms:
            return
        alnum = lambda s: "".join(ch for ch in str(s).upper() if ch.isalnum())
        si = obb_call("沽空數據（FINRA，經 OpenBB）", OBB.finra.equity.shorts.short_interest, 90, symbol=",".join(syms))
        if si is None or not len(si):
            return
        si = _need(si, ["settlement_date", "symbol", "current_short_position", "days_to_cover", "change_pct"])
        si["_sd"] = pd.to_datetime(si["settlement_date"], errors="coerce")
        si = si[si["_sd"].notna()].sort_values("_sd").drop_duplicates("symbol", keep="last").copy()   # 每隻只留最新一期
        si["Ticker"] = si["symbol"].map(alnum).map({alnum(t): t for t in syms})
        si = si[si["Ticker"].notna()].copy()
        si["SIM"] = pd.to_numeric(si["current_short_position"], errors="coerce") / 1e6
        si["DTC"] = pd.to_numeric(si["days_to_cover"], errors="coerce")
        si["Chg%"] = pd.to_numeric(si["change_pct"], errors="coerce")
        si["Settle"] = si["_sd"].dt.strftime("%m-%d")
        si["Grp"] = si["Ticker"].map(grp)
        def read(r):
            if isnan(r["DTC"]):
                return ""
            short_side = r["Grp"] in ("做空焦點", "回抽阻力")
            if r["DTC"] >= 5:
                return "回補要 5 日以上：軋空風險高，空倉減注" if short_side else "沽空盤多：突破時有回補買盤"
            return "沽空盤偏多" if r["DTC"] >= 3 else "沽空盤不多"
        si["Read"] = [read(r) for r in si.to_dict("records")]
        out["si"] = si[["Ticker", "Grp", "Settle", "SIM", "Chg%", "DTC", "Read"]].sort_values("DTC", ascending=False).reset_index(drop=True)
        risky = [r for r in out["si"].to_dict("records") if r["Grp"] in ("做空焦點", "回抽阻力") and not isnan(r["DTC"]) and r["DTC"] >= 5]
        if risky:
            out["key"].append("做空候選中回補日數 5 日以上的：" + "、".join(f"{r['Ticker']}（{r['DTC']:.1f} 日）" for r in risky) + "，軋空風險高。")

    def _credit():
        key = fred_key()
        if not key:
            out["no_fred"] = True
            return
        for sid, nm, max_age, back in [("BAMLH0A0HYM2", "高收益債息差", 10, 20), ("NFCI", "金融狀況指數 NFCI", 21, 4)]:
            d, _, _ = _direct(f"{nm}（FRED，用你的密鑰）", lambda sid=sid: fred_api(sid, key))
            if d is None or len(d) <= back:
                continue
            last_d, last, prev = d["date"].iloc[-1], float(d["v"].iloc[-1]), float(d["v"].iloc[-1 - back])
            age = (ASOF.normalize() - last_d).days
            if age > max_age:                                             # 來源沒有更新：不拿舊數字作判斷
                OBB_LOG[-1]["Status"], OBB_LOG[-1]["Note"] = "過期", f"最新一筆是 {last_d:%Y-%m-%d}，已過期，不採用"
                out["stale"].append(nm)
                continue
            if sid == "BAMLH0A0HYM2":
                bp = (last - prev) * 100
                out["key"].append(f"高收益債息差（{last_d:%m-%d}）：{last:.2f}%，20 個交易日前 {prev:.2f}%，"
                                  f"{'擴闊' if bp > 0 else '收窄'} {abs(bp):.0f} 點子。"
                                  + ("一個月內擴闊 50 點子以上，信貸壓力正在升溫。" if bp >= 50 else "一個月內擴闊不到 50 點子，信貸市場未見明顯壓力。"))
            else:
                out["key"].append(f"金融狀況指數 NFCI（截至 {last_d:%m-%d} 當週）：{last:+.2f}，4 週前 {prev:+.2f}，"
                                  f"{'正在收緊' if last > prev + 0.02 else '正在放鬆' if last < prev - 0.02 else '大致不變'}。"
                                  "負數代表比歷史平均寬鬆，由負轉正是信貸收緊的警號。")

    def _earnlist():
        rows = []
        for t in list(dict.fromkeys(list(POSITIONS) + list(WATCH))):
            if t in OBB_EARN:
                d0, slot = OBB_EARN[t]
                n = -1 if d0 <= ASOF.date() else (sessions_until(SESS_D, d0) if d0 > SESS_D else 0)
                rows.append({"Ticker": t, "Date": f"{d0:%m-%d}", "Slot": slot, "In": n, "_d": d0, "Held": t in POSITIONS})
        if rows:
            out["earn"] = pd.DataFrame(rows).sort_values("_d").reset_index(drop=True)

    steps = []
    print("補充數據層：取波動指數、VIX 期貨和期權引伸波幅（先試 Cboe，取不到改用 Yahoo）…")
    steps += [("波動結構", _vol), ("引伸波幅", _implied)]
    print("補充數據層：取 Nasdaq 異動榜、FINRA 沽空數據…")
    steps += [("異動榜", _movers)]
    if obb_ok("finra"):
        steps += [("沽空數據", _short)]
    steps += [("信貸數據", _credit), ("財報日一覽", _earnlist)]
    for nm, fn in steps:
        try:
            fn()
        except Exception as e:
            OBB_ERR.append(f"補充數據層「{nm}」處理出錯（{type(e).__name__}: {' '.join(str(e).split())[:160]}），這一項已略過。")
    return out

def obb_section_html(x):
    """把補充數據層的結果砌成簡報內的一節。回傳（HTML、成功的項數）。"""
    log = pd.DataFrame(OBB_LOG)
    n_ok = int((log["Status"] == "成功").sum()) if len(log) else 0
    p = [f'<div class="warnbox">⚠ {esc(e)}</div>' for e in OBB_ERR] if SHOW_DEBUG_PANEL else []
    p.append('<div class="note">這一節是補充市場數據：期權引伸波幅、波動指數期限結構和沽空數據，報價有延遲。'
             "除了財報日和經濟日曆會併入第 3 節之外，其餘只供參考，不計入健康分數和四個閘門。任何一項暫缺，簡報其餘部分照常。</div>")
    if x["key"]:
        p.append("<h3>重點</h3><ul>" + "".join(f"<li>{esc(k)}</li>" for k in x["key"]) + "</ul>")
    if SHOW_DEBUG_PANEL:
        p.append("<h3>數據源狀態</h3>" + render(log, OSPEC["log"], empty="沒有執行任何取數指令"))
    elif len(log):
        print("  數據源狀態：\n" + log.to_string(index=False))
    src = [f"財報日曆和財報反應現在取自 {EARN_SRC}。"]
    if OBB_EARN:
        src.append(f"Nasdaq 日曆覆蓋到 {OBB_WIN_END:%m-%d}（未來 {OBB_EARN_WINDOW} 個交易日），共 {len(OBB_EARN)} 間公司；"
                   + ("整段期間都取到，表內的「—」代表這段期間內沒有財報。" if OBB_EARN_FULL else "有幾日取不到，其餘股票仍然逐隻問 Yahoo。"))
    if OBB_ONLY_N or OBB_ONLY_Y:
        src.append("兩個日曆在這幾日的差異（只供核對）："
                   + (f"只有 Nasdaq 列出 {'、'.join(OBB_ONLY_N[:12])}" if OBB_ONLY_N else "")
                   + ("；" if (OBB_ONLY_N and OBB_ONLY_Y) else "")
                   + (f"只有 Yahoo 列出 {'、'.join(OBB_ONLY_Y[:12])}（已補入上面的財報表）" if OBB_ONLY_Y else "") + "。")
    if EARN_MISMATCH:
        src.append("兩個來源的財報日不一致，表內已取較早的一日並加上「？」，落盤前請自行核對："
                   + "、".join(f"{t} Nasdaq {dn:%m-%d}／Yahoo {dy:%m-%d}" for t, dn, dy in EARN_MISMATCH[:12]) + "。")
    if EARN_CONFLICT:
        src.append("Yahoo 顯示以下股票在期間內有財報，但 Nasdaq 日曆沒有列出，落盤前請自行核對：" + "、".join(EARN_CONFLICT[:12]) + "。")
    src.append(f"第 3 節的經濟日曆取自 {ECON_SRC}。" + ("Nasdaq 補上了聯儲局官員講話、會議紀錄和 Yahoo 沒有的數據；" + OBB_TZ_NOTE if "Nasdaq" in ECON_SRC else ""))
    if x["no_fred"]:
        src.append("信貸息差和金融狀況指數未啟用：FRED 的公開下載在 Colab 連不上，要用它的免費密鑰。"
                   "想要這兩項，到 fred.stlouisfed.org 申請 API key，在 Colab 左邊的鑰匙圖示加入 FRED_API_KEY。")
    if x["stale"]:
        src.append("以下數據的來源沒有更新，已停用：" + "、".join(x["stale"]) + "。")
    if SHOW_DEBUG_PANEL:
        p.append("<h3>財報與經濟日曆的來源</h3><ul>" + "".join(f"<li>{esc(s)}</li>" for s in src) + "</ul>")
    else:
        print("  財報與經濟日曆的來源：" + " ".join(src))
    if len(OBB_ECON):
        p.append("<h3>經濟日曆（美國重點項目，含市場預期）</h3>" + render(OBB_ECON, SPEC["econ"], 20)
                 + f'<div class="note">{esc(OBB_TZ_NOTE)}星級按關鍵字判斷：官員講話只有主席算三星。重點項目已併入第 3 節。</div>')
    if len(x["earn"]):
        p.append(f"<h3>名單與持倉在未來 {OBB_EARN_WINDOW} 個交易日內的財報</h3>" + render(x["earn"], OSPEC["earn"], 30)
                 + '<div class="note">「距今交易日」0 代表今日，−1 代表剛公佈。</div>')
    if len(x["imp"]):
        p.append("<h3>期權引伸波幅（參考值）</h3>" + render(x["imp"], OSPEC["imp"])
                 + ('<div class="note">今次的數字按期權鏈的買賣中間價計算，沒有買賣報價時用最後成交價，準確度較低，只作參考。</div>'
                    if "Yahoo" in str(x.get("imp_src", "")) else "")
                 + '<div class="note">跨式成本＝同一到期日、同一行使價的認購加認沽期權的價錢，佔股價的百分比，是期權市場對到期前波幅的定價。'
                   "美股收市後和盤前，期權報價仍是上日收市的，所以行使價取最接近上日收市價的一個。"
                 + ("" if "Yahoo" in str(x.get("imp_src", "")) else "這裡用賣出價計算，會略為高估，流通量低的期權誤差更大。")
                 + "財報股的數字包括由現在到期權到期的所有日子，不只是財報當日。</div>")
    if len(x["vol"]) or len(x["vx"]):
        panels = []
        if len(x["vol"]):
            panels.append("<div><h3>" + ("波動指數期限結構（上日收市）" if "Yahoo" in str(x.get("vol_src", "")) else "波動指數期限結構")
                          + "</h3>" + render(x["vol"], OSPEC["vol"]) + "</div>")
        if len(x["vx"]):
            panels.append("<div><h3>VIX 期貨曲線（上日結算）</h3>" + render(x["vx"], OSPEC["vx"]) + "</div>")
        p.append(('<div class="two">' + "".join(panels) + "</div>" if len(panels) == 2 else "".join(panels))
                 + '<div class="note">正常情況下期限越長，數值越高（正價差）。VIX 明顯高於 VIX3M 是逆價差，代表市場為眼前的風險付出更高價錢，'
                   "多數出現在急跌期間；回復正價差是恐慌消退的訊號，可以配合 Follow-Through Day 一起看。"
                 + ("VIX 期貨的數字是交易所的結算參考值，與報價軟件有出入時，以報價軟件為準。" if len(x["vx"]) else "") + "</div>")
    if len(x["mov"]):
        lab = x["mov_label"]
        p.append(f"<h3>全市場{esc(lab)}異動榜</h3>" + render(x["mov"], OSPEC["mov"], 40)
                 + '<div class="note">' + ("" if lab == "盤前" else "現在不是美東的盤前時段，顯示的是" + esc(lab) + "榜；美東 4:00 至 9:30 之間執行才是盤前榜，用處最大。")
                 + "股票池成員的升跌按上日收市價計算，沒有異動的不列出；名單或持倉內的排在最前。"
                   "池外的股票只有報價數字，沒有 RS 和階段；ETF 和低於 5 元的不列出。</div>")
    if len(x["si"]):
        p.append("<h3>沽空數據（每半個月公佈一次）</h3>" + render(x["si"], OSPEC["si"])
                 + '<div class="note">回補日數＝沽空股數 ÷ 日均成交量。數據以結算日計，公佈時已滯後一至兩星期。'
                   "做空候選的回補日數高，代表好消息出現時容易被軋空。5 日這條線是常用的經驗值（見頁底「方法論與局限性」）。</div>")
    return section("補充數據層（期權引伸波幅、波動結構與沽空數據）", "".join(p), True, f"{n_ok}/{len(log)} 項成功" if SHOW_DEBUG_PANEL else ""), n_ok

OBB_SECTION, OBB_TXT, OBB_OKN = "", "", 0
OBB_MOV = OBB_IMP = OBB_SI = pd.DataFrame()
if USE_OPENBB:
    try:
        _ox = obb_extras()
        OBB_MOV, OBB_IMP, OBB_SI = _ox["mov"], _ox["imp"], _ox["si"]
        OBB_SECTION, OBB_OKN = obb_section_html(_ox)
        if _ox["key"]:
            OBB_TXT = "\n補充數據層（只供參考，不計入分數）：" + " ".join(_ox["key"])
    except Exception as e:
        print(f"  補充數據層出錯：{type(e).__name__}: {' '.join(str(e).split())[:200]}")
        OBB_SECTION = section("補充數據層（期權引伸波幅、波動結構與沽空數據）",
                              ("".join(f'<div class="warnbox">⚠ {esc(x)}</div>' for x in OBB_ERR) if SHOW_DEBUG_PANEL else "")
                              + '<div class="note">補充數據層今次未能提供，簡報其餘部分不受影響。</div>', True)

# ---------- v6：分級（第二步）：用上沽空數據，計風險預算、分散檢查、提示價和文字版 ----------
T6_BUD, T6_DIV, T6_TXT, T6_TV = {}, [], [], []
T6_FR_L = T6_FR_S = pd.DataFrame()
T6_TOP_L, T6_TOP_S = ("A 級" if long_ok else "預備"), ("A 級" if T6_SGATE else "預備")
T6_LAB_L, T6_LAB_S = ("做多 A 級" if long_ok else "做多預備"), ("做空 A 級" if T6_SGATE else "做空預備")
T6_VERDICT = ""
T6_KEYS = {"形態": "未有形態", "趨勢": "未在 Stage 2", "距離": "距離太遠", "財報": "財報在即或未確認", "止蝕": "止蝕太遠", "清單": "清單太弱", "超跌": "已超跌", "軋空": "軋空風險"}

def t6_frame(cands, cks):
    """把候選整理成一張表（存 CSV 用）。"""
    rows = []
    for c in cands:
        r = {k: c.get(k) for k in ["Ticker", "Side", "Tier", "Setup", "Reason", "NPass", "NFail", "Close", "Pivot", "Trigger", "Entry",
                                   "Dist%", "Chase", "Stop", "StopSrc", "Risk%", "Shares", "Pos%", "RS", "SecETF", "SecRank", "UD",
                                   "DTC", "Earn", "Why"]}
        for k in cks:
            v = c["Ck"].get(k)
            r["ck_" + k] = "" if v is None else ("Y" if v else "N")
        rows.append(r)
    d = pd.DataFrame(rows)
    if len(d):
        d["_o"] = d["Tier"].map({"A": 0, "預備": 0, "B": 1, "觀察": 2, "剔除": 3}).fillna(4)
        d = d.sort_values(["_o", "NPass", "NFail"], ascending=[True, False, True], kind="stable").drop(columns="_o").reset_index(drop=True)
    return d

def t6_reasons(cands):
    """觀察和剔除的候選，按第一個原因點算。"""
    cnt = {}
    for c in cands:
        if c["Tier"] not in ("觀察", "剔除"):
            continue
        if c["Drop"]:
            k = "已持有" if c["Drop"].startswith("已持有") else "疑似收購鎖價" if "鎖價" in c["Drop"] else "已走遠"
        elif c["Miss"]:
            k = T6_KEYS.get(c["Miss"][0][0], c["Miss"][0][0])
        else:
            k = "名額已滿"
        cnt[k] = cnt.get(k, 0) + 1
    return sorted(cnt.items(), key=lambda kv: -kv[1])


# ---------- v6.1：名單跟進與成績表（要勾選 SAVE_TO_DRIVE，名單才會留到下一次執行）----------
# 每次執行把全部候選連同級別、觸發價、止蝕存入 tier_history.csv；下次執行時，只用「列出之後」的日線去看每個計劃的結果。
# 假設：在觸發價成交、在止蝕價離場，不計佣金、滑價和跳空；同一日先後打到觸發價和止蝕的，當作止蝕。所以數字偏樂觀，只供描述，不是驗證。
T6_FU = {"note": "", "prev": "", "new": [], "gone": [], "stay": [], "rows": [], "score": [], "n_days": 0, "old_rules": 0}
def t6_r(x):
    """R 倍數的寫法：+1.2R；沒有就寫 —。"""
    return "—" if isnan(x) else f"{round(float(x), 1) + 0.0:+.1f}R"

def t6_side(side, tier):
    return ("做多" if side == "多" else "做空") + (" A 級" if tier == "A" else " B 級" if tier == "B" else str(tier))

T6_HIST_COLS = ["asof", "rules", "regime", "gate", "side", "ticker", "tier", "setup", "main", "close", "trigger", "entry", "chase", "stop",
                "npass", "nfail", "rs"]

def t6_hist_rows():
    """今日全部候選（做多和做空）整理成歷史檔的格式。"""
    rows = []
    for c in T6_L + T6_S:
        gate = long_ok if c["Side"] == "多" else T6_SGATE
        rows.append({"asof": f"{ASOF:%Y-%m-%d}", "rules": T6_RULES, "regime": REG_L, "gate": int(bool(gate)), "side": c["Side"],
                     "ticker": c["Ticker"], "tier": c["Tier"], "setup": c["Setup"], "main": c["Main"], "close": round(c["Close"], 4),
                     "trigger": round(c["Trigger"], 4), "entry": round(c["Entry"], 4), "chase": round(c["Chase"], 4),
                     "stop": round(c["Stop"], 4), "npass": c["NPass"], "nfail": c["NFail"], "rs": c["RS"]})
    return pd.DataFrame(rows, columns=T6_HIST_COLS)

def t6_outcome(t, side, asof, trigger, stop):
    """一個計劃在列出之後的結果。只看 asof 之後的日線。回傳（現況文字、R 倍數或 NaN、是否已觸發）。"""
    if t not in C.columns:
        return "沒有日線數據", np.nan, False
    idx = C.index[C.index > pd.Timestamp(asof)]
    risk = abs(trigger - stop)
    if not len(idx) or isnan(trigger) or isnan(stop) or not risk > 0:
        return "未有新數據", np.nan, False
    hh, ll, cc = H.loc[idx, t].values, L.loc[idx, t].values, C.loc[idx, t].values
    is_long, trig_i = side == "多", None
    for i in range(len(idx)):
        hit_t = (hh[i] >= trigger) if is_long else (ll[i] <= trigger)
        hit_s = (ll[i] <= stop) if is_long else (hh[i] >= stop)
        if trig_i is None:
            if hit_s and not hit_t:
                return f"未觸發，{idx[i]:%m-%d} 先穿止蝕，計劃作廢", np.nan, False
            if hit_t:
                trig_i = i
                if hit_s:
                    return f"{idx[i]:%m-%d} 觸發，同日打到止蝕", -1.0, True
        elif hit_s:
            return f"{idx[trig_i]:%m-%d} 觸發，{idx[i]:%m-%d} 止蝕", -1.0, True
    last = cc[-1]
    if trig_i is None:
        return ("未觸發" if isnan(last) else f"未觸發，現價距觸發價 {(last / trigger - 1) * 100:+.1f}%"), np.nan, False
    if isnan(last):
        return f"{idx[trig_i]:%m-%d} 觸發，持有中", np.nan, True
    r = (last - trigger) / risk * (1 if is_long else -1)
    return f"{idx[trig_i]:%m-%d} 觸發，持有第 {len(idx) - trig_i} 日", float(r), True

def t6_followup():
    path = os.path.join(HIST_DIR, "tier_history.csv")
    keep_hint = "今日的名單已存起來，下次執行就會有跟進。"
    if not os.path.exists(path):
        T6_FU["note"] = "未有之前的名單紀錄。" + keep_hint
        return
    h = pd.read_csv(path, dtype=str)
    if not len(h) or not set(["asof", "side", "ticker", "tier", "trigger", "stop"]).issubset(h.columns):
        T6_FU["note"] = "名單紀錄是空的或格式不符。" + keep_hint
        return
    h = h[h["asof"] < f"{ASOF:%Y-%m-%d}"].copy()
    if "rules" in h.columns:
        T6_FU["old_rules"] = int((h["rules"] != T6_RULES).sum())
        h = h[h["rules"] == T6_RULES]
    if not len(h):
        T6_FU["note"] = "未有今日之前、而且用同一版規則的名單紀錄。" + keep_hint
        return
    for col in ("trigger", "stop"):
        h[col] = pd.to_numeric(h[col], errors="coerce")
    days = sorted(h["asof"].unique())[-PLAN["score_days"]:]
    h = h[h["asof"].isin(days)]
    pos = {d: i for i, d in enumerate(days)}
    T6_FU["n_days"], T6_FU["prev"] = len(days), days[-1]

    # 1. 與上一份名單比較（做多首選）
    p_top = list(h[(h["asof"] == days[-1]) & (h["side"] == "多") & h["tier"].isin(["A", "預備"])]["ticker"])
    now_top = [c["Ticker"] for c in T6_LA]
    by = {c["Ticker"]: c for c in T6_L}
    T6_FU["new"] = [t for t in now_top if t not in p_top]
    T6_FU["stay"] = [t for t in now_top if t in p_top]
    T6_FU["gone"] = [(t, (f"現在是{by[t]['Tier']}：{by[t]['Reason']}" if t in by else "已不在任何做多名單")) for t in p_top if t not in now_top]

    # 2. 每個計劃只計一次：同一隻股票連續幾日都在同一級別，只取第一日的觸發價和止蝕
    eps = []
    for (side, tk, grp), g in h.assign(grp=h["tier"].map(lambda x: "首選" if x in ("A", "預備") else "B 級" if x == "B" else "其餘")).groupby(["side", "ticker", "grp"]):
        g = g.sort_values("asof")
        prev_i = None
        for r in g.to_dict("records"):
            i = pos[r["asof"]]
            if prev_i is None or i != prev_i + 1:
                eps.append({"side": side, "ticker": tk, "grp": grp, "asof": r["asof"], "tier": r["tier"], "setup": r.get("setup", ""),
                            "trigger": r["trigger"], "stop": r["stop"]})
            prev_i = i
    for e in eps:
        e["st"], e["R"], e["trig"] = t6_outcome(e["ticker"], e["side"], e["asof"], e["trigger"], e["stop"])
    recent = set(days[-PLAN["follow_days"]:])
    T6_FU["rows"] = sorted([e for e in eps if e["grp"] == "首選" and e["asof"] in recent], key=lambda e: (e["asof"], e["ticker"]), reverse=True)

    # 3. 成績表：首選、B 級、全部候選（對照組）。首選如果不比全部候選好，分級就沒有用處
    def stat(name, sel):
        n = len(sel)
        tr = [e for e in sel if e["trig"]]
        rr = [e["R"] for e in tr if not isnan(e["R"])]
        return {"Grp": name, "N": n, "Trig": len(tr), "Trig%": (len(tr) / n * 100 if n else np.nan),
                "Stopped": sum(1 for e in tr if e["R"] == -1.0), "Win%": (sum(1 for x in rr if x > 0) / len(rr) * 100 if rr else np.nan),
                "AvgR": (float(np.mean(rr)) if rr else np.nan)}
    lg = [e for e in eps if e["side"] == "多"]
    sc = [stat("做多首選（A 級或預備）", [e for e in lg if e["grp"] == "首選"]), stat("做多 B 級", [e for e in lg if e["grp"] == "B 級"]),
          stat("做多全部候選（對照）", lg)]
    sh = [e for e in eps if e["side"] == "空"]
    if sh:
        sc.append(stat("做空首選", [e for e in sh if e["grp"] == "首選"]))
        sc.append(stat("做空全部候選（對照）", sh))
    T6_FU["score"] = [s for s in sc if s["N"] > 0]

def t6_finalize():
    global T6_SA, T6_SB, T6_BUD, T6_DIV, T6_TXT, T6_TV, T6_FR_L, T6_FR_S, ALERT_TBL, T6_VERDICT
    # 1. 沽空數據：做空候選的回補日數高，降級
    dtc = {}
    if len(OBB_SI) and "DTC" in OBB_SI.columns:
        dtc = {r["Ticker"]: t6_f(r["DTC"]) for r in OBB_SI.to_dict("records")}
    imp = {}
    if len(OBB_IMP) and "Ticker" in OBB_IMP.columns:
        for r in OBB_IMP.to_dict("records"):
            if r["Ticker"] != "QQQ":
                imp.setdefault(r["Ticker"], r)
    for c in T6_L + T6_S:
        c["DTC"], c["Imp"] = dtc.get(c["Ticker"], np.nan), imp.get(c["Ticker"])
    redo = False
    for c in T6_S:
        if not isnan(c["DTC"]):
            c["Ck"]["軋空"] = bool(c["DTC"] < PLAN["dtc_squeeze"])
            t6_count(c)
            if c["DTC"] >= PLAN["dtc_squeeze"]:
                c["Miss"].append(("軋空", f"回補日數 {c['DTC']:.1f} 日，軋空風險高"))
                redo = True
    if redo:
        T6_SA, T6_SB = t6_assign(T6_S, "空", T6_SGATE)

    # 2. 風險預算
    heat_cap = float(MAX_HEAT_PCT) if (not isnan(MAX_HEAT_PCT) and MAX_HEAT_PCT > 0) else PLAN["heat_pct"][REG_L]
    heat_left = max(heat_cap - OPEN_RISK_PCT, 0.0)
    expo_cap = float(CAP_MAX[REG_L])
    expo_left = max(expo_cap - LONG_EXPO, 0.0)
    short_risk = ACCOUNT_EQUITY * BASE_RISK_PCT / 100 * TH["risk_mult"]["short"]
    day_cap = PLAN["new_per_day"][REG_L]
    slots_l = int((heat_left / 100 * ACCOUNT_EQUITY) // LONG_RISK) if LONG_RISK > 0 else 0
    slots_s = int((heat_left / 100 * ACCOUNT_EQUITY) // short_risk) if short_risk > 0 else 0
    n_fit, used = 0, 0.0
    for c in T6_LA:
        if c["Shares"] > 0 and c["Pos%"] > expo_left:            # 每隻獨立計：單是這一隻已超過多倉上限的餘額，股數要減
            new_sh = int((expo_left / 100 * ACCOUNT_EQUITY) // c["Entry"])
            c["ShCap"] = f"按風險計是 {c['Shares']:,} 股；多倉上限只餘 {expo_left:.1f}%，減到 {new_sh:,} 股"
            c["Shares"], c["Pos%"] = new_sh, new_sh * c["Entry"] / ACCOUNT_EQUITY * 100
        if c["Shares"] > 0 and used + c["Pos%"] <= expo_left + 1e-9:
            n_fit, used = n_fit + 1, used + c["Pos%"]
    if not long_ok:
        n_long, lim_l = 0, "多頭與試單閘門都未開"
    else:
        opts = [(len(T6_LA), f"A 級只有 {len(T6_LA)} 隻"), (day_cap, f"Regime {REG_L} 每日最多 {day_cap} 單位"),
                (slots_l, f"風險上限只餘 {heat_left:.2f}%"), (n_fit, f"多倉上限只餘 {expo_left:.0f}%")]
        n_long, lim_l = min(opts, key=lambda x: x[0])
    if not T6_SGATE:
        n_short, lim_s = 0, ("QQQ 在破位邊緣，規則不追空" if SHORT_GATE else "空頭條件成立但市場超賣" if (SHORT_SETUP and OVERSOLD) else "空頭閘門未開")
    else:
        opts = [(len(T6_SA), f"A 級只有 {len(T6_SA)} 隻"), (day_cap, f"Regime {REG_L} 每日最多 {day_cap} 單位"),
                (slots_s, f"風險上限只餘 {heat_left:.2f}%")]
        n_short, lim_s = min(opts, key=lambda x: x[0])
    T6_BUD = dict(heat_cap=heat_cap, heat_left=heat_left, expo_cap=expo_cap, expo_left=expo_left, risk_l=LONG_RISK, risk_s=short_risk,
                  n_long=max(n_long, 0), n_short=max(n_short, 0), lim_l=lim_l, lim_s=lim_s, day_cap=day_cap,
                  heat_src="自訂設定" if (not isnan(MAX_HEAT_PCT) and MAX_HEAT_PCT > 0) else f"Regime {REG_L} 預設")

    # 3. 分散檢查：板塊分佈、相關係數
    div = []
    secs = {}
    for c in T6_LA:
        secs.setdefault(c["SecETF"] or "未分類", []).append(c["Ticker"])
    for t in POSITIONS:
        if t in F.index:
            secs.setdefault(F.at[t, "SecETF"] or "未分類", []).append(t + "（持倉）")
    if secs:
        div.append(f"{T6_TOP_L}和持倉合共 {sum(len(v) for v in secs.values())} 隻，分佈在 {len(secs)} 個板塊："
                   + "；".join(f"{SECTOR_ETFS.get(k, k)} {len(v)} 隻（{'、'.join(v)}）" for k, v in sorted(secs.items(), key=lambda kv: -len(kv[1]))) + "。")
    nm = list(dict.fromkeys([c["Ticker"] for c in T6_LA if c["Ticker"] in C.columns] + [t for t in POSITIONS if t in C.columns]))
    pairs = []
    if len(nm) >= 2:
        px = C[nm]
        cm = (px / px.shift(1) - 1).iloc[-PLAN["corr_days"]:].corr(min_periods=40)
        for i, a in enumerate(nm):
            for b in nm[i + 1:]:
                v = t6_f(cm.at[a, b])
                if not isnan(v) and v >= PLAN["corr_max"]:
                    pairs.append((a, b, v))
        by = {c["Ticker"]: c for c in T6_LA}
        for a, b, v in pairs:
            for x, y in ((a, b), (b, a)):
                if x in by:
                    by[x]["Corr"].append((y, v))
        pairs.sort(key=lambda z: -z[2])
        for a, b, v in pairs[:6]:
            div.append(f"{a} 與 {b} 的 {PLAN['corr_days']} 日相關係數 {v:.2f}：兩隻一齊持有等於同一注加碼，二揀一，或各用半注。")
        if not pairs:
            div.append(f"名單和持倉之間沒有相關係數高於 {PLAN['corr_max']:g} 的組合。")
    T6_DIV = div

    # 4. 提示價：QQQ 的關鍵位，加上首選和 B 級的觸發價
    al = [a for a in ALERTS if a["Ticker"] == "QQQ"]
    for c in T6_LA:
        if c["Through"]:
            al.append({"Ticker": c["Ticker"], "Dir": "跌穿", "Px": round(c["Stop"], 2), "Why": f"{T6_TOP_L}｜{c['Setup']} 已升穿 pivot；這是止蝕位"})
        else:
            al.append({"Ticker": c["Ticker"], "Dir": "升穿", "Px": round(c["Trigger"], 2), "Why": f"{T6_TOP_L}｜{c['Setup']} 觸發價；止蝕 {c['Stop']:.2f}"})
    for c in T6_SA:
        al.append({"Ticker": c["Ticker"], "Dir": "跌穿", "Px": round(c["Trigger"], 2), "Why": f"{T6_LAB_S}｜跌穿 3 日低位；止蝕 {c['Stop']:.2f}"})
    for c in T6_LB:
        if not c["Through"]:
            al.append({"Ticker": c["Ticker"], "Dir": "升穿", "Px": round(c["Trigger"], 2), "Why": f"B 級｜{c['Setup']}；尚欠：{c['Reason']}"})
    ALERT_TBL = pd.DataFrame(al)

    # 5. 存檔用的表、TradingView 名單
    T6_FR_L, T6_FR_S = t6_frame(T6_L, T6_CK_L), t6_frame(T6_S, T6_CK_S)
    T6_TV = [("A TIER" if long_ok else "READY - GATE CLOSED", pd.DataFrame({"Ticker": [c["Ticker"] for c in T6_LA]}), 10),
             ("B TIER", pd.DataFrame({"Ticker": [c["Ticker"] for c in T6_LB]}), 15),
             ("SHORT A" if T6_SGATE else "SHORT READY", pd.DataFrame({"Ticker": [c["Ticker"] for c in T6_SA]}), 10)]

    # 6. 文字版（三條問題）
    b = T6_BUD
    if b["n_long"] == 0 and b["n_short"] == 0:
        T6_VERDICT = f"模型市況框架（{REG_L} 級）：規則示範敞口上限為零，所有形態只列作觀察，僅供研究參考。"
    else:
        T6_VERDICT = f"模型市況框架（{REG_L} 級）：規則示範敞口上限為多頭 {b['n_long']} 單位／空頭 {b['n_short']} 單位，僅供研究參考。"
    tx = ["【結論】" + T6_VERDICT,
          "【一、模型市況框架】" + f"Regime {REG_L} {REG_T}｜{SIDE}｜規則示範新倉上限：多頭 {b['n_long']} 單位（{b['lim_l']}）"
          + (f"、空頭 {b['n_short']} 單位（{b['lim_s']}）" if SHORT_SETUP else "")
          + f"｜示範每單位風險 多頭 ${b['risk_l']:,.0f}" + (f"、空頭 ${b['risk_s']:,.0f}" if SHORT_SETUP else "")
          + f"｜未平倉風險 {OPEN_RISK_PCT:.2f}%／上限 {b['heat_cap']:g}%｜多倉市值 {LONG_EXPO:.0f}%／上限 {b['expo_cap']:.0f}%"]
    n_w = sum(1 for c in T6_L if c["Tier"] == "觀察")
    n_d = sum(1 for c in T6_L if c["Tier"] == "剔除")
    rs_ = t6_reasons(T6_L)
    tx.append(f"【二、符合規則的技術形態】股票池 {len(TICKS)} 隻 → 做多候選 {len(T6_L)} 隻 → {T6_TOP_L} {len(T6_LA)}、B 級 {len(T6_LB)}、觀察 {n_w}、剔除 {n_d}"
              + ("（" + "、".join(f"{k} {v}" for k, v in rs_) + "）" if rs_ else ""))
    def ck_txt(c, cks):
        known = sum(1 for k in cks if c["Ck"].get(k) is not None)
        return f"清單 {c['NPass']}/{known}" + (f"，不通過：{'、'.join(c['Fails'])}" if c["Fails"] else "")
    tx.append(f"  {T6_LAB_L}：" + ("｜".join(f"{c['Ticker']}（{c['Setup']}，{ck_txt(c, T6_CK_L)}）" for c in T6_LA) if T6_LA else "沒有"))
    tx.append("  做多 B 級：" + ("｜".join(f"{c['Ticker']}（{c['Setup']}；尚欠：{c['Reason']}）" for c in T6_LB) if T6_LB else "沒有"))
    if SHORT_SETUP:
        tx.append(f"  {T6_LAB_S}：" + ("｜".join(f"{c['Ticker']}（{ck_txt(c, T6_CK_S)}）" for c in T6_SA) if T6_SA else "沒有")
                  + "｜B 級：" + ("｜".join(f"{c['Ticker']}（尚欠：{c['Reason']}）" for c in T6_SB) if T6_SB else "沒有"))
    for x in div:
        tx.append("  分散：" + x)
    if DATA_HOLE:
        tx.append(f"  注意：{len(DATA_HOLE)} 隻股票今日沒有收市價，未列入掃描：" + "、".join(DATA_HOLE[:12]) + ("…" if len(DATA_HOLE) > 12 else ""))
    if T6_WATCH or T6_WATCH_NA:
        tx.append("  自選名單體檢：" + "｜".join(f"{c['Ticker']}（{c['Tier']}，清單 {c['NPass']} 項通過" + (f"；{c['Reason']}" if c["Reason"] else "") + "）" for c in T6_WATCH)
                  + ("｜沒有數據：" + "、".join(T6_WATCH_NA) if T6_WATCH_NA else ""))
    fu = T6_FU
    if fu["prev"]:
        tx.append(f"  與上一份名單（{fu['prev'][5:]}）比較：新入選 " + ("、".join(fu["new"]) or "沒有") + "；留在名單 " + ("、".join(fu["stay"]) or "沒有")
                  + "；跌出 " + ("、".join(f"{t}（{why}）" for t, why in fu["gone"]) or "沒有"))
        for e in fu["rows"][:12]:
            tx.append(f"  跟進：{e['ticker']}（{e['asof'][5:]} 列出，{t6_side(e['side'], e['tier'])}，觸發 {e['trigger']:.2f}，止蝕 {e['stop']:.2f}）{e['st']}"
                      + ("" if isnan(e["R"]) else f"，{t6_r(e['R'])}"))
        for s in fu["score"]:
            tx.append(f"  成績（{fu['n_days']} 個名單日）：{s['Grp']} {s['N']} 個，已觸發 {s['Trig']} 個，其中止蝕 {s['Stopped']} 個，平均 {fnum(s['AvgR'], 2, 'R', True)}")
    elif fu["note"]:
        tx.append("  名單跟進：" + fu["note"])
    tx.append("【三、每隻怎樣做】" + ("" if (T6_LA or T6_SA) else "今日沒有首選" + ("，按 B 級的提示價等待。" if T6_LB else "，不要勉強找交易。")))
    for c in T6_LA:
        rps = c["Entry"] - c["Stop"]
        tx.append(f"  {c['Ticker']}｜" + ("已升穿，" if c["Through"] else "") + f"觸發 {c['Trigger']:.2f}｜追價上限 {c['Chase']:.2f}｜止蝕 {c['Stop']:.2f}（{c['Risk%']:.1f}%，{c['StopSrc']}）"
                  f"｜{c['Shares']:,} 股（倉位 {c['Pos%']:.1f}%）｜2R {c['Entry'] + 2 * rps:.2f}｜3R {c['Entry'] + 3 * rps:.2f}｜財報 {c['Earn']}")
    for c in T6_SA:
        rps = c["Stop"] - c["Entry"]
        tx.append(f"  做空 {c['Ticker']}｜跌穿 {c['Trigger']:.2f}｜不追空的下限 {c['Chase']:.2f}｜止蝕 {c['Stop']:.2f}（{c['Risk%']:.1f}%）"
                  f"｜{c['Shares']:,} 股｜2R {c['Entry'] - 2 * rps:.2f}｜3R {c['Entry'] - 3 * rps:.2f}"
                  + ("" if isnan(c["DTC"]) else f"｜回補日數 {c['DTC']:.1f}") + f"｜財報 {c['Earn']}")
    T6_TXT = tx

if V6_OK:
    try:
        t6_followup()
    except Exception as e:
        T6_FU["note"] = "名單跟進出錯，已略過。"
        t6_warn("名單跟進", e)
    try:
        t6_finalize()
    except Exception as e:
        t6_fail("風險預算與分散檢查", e)


# ---------- v6.2：近 10 日回顧（讀 daily_log.csv；同一個簡報日跑了幾次，只列最後一次）----------
RUN_ID = f"{SESS_D:%Y-%m-%d}_run{RUN_TS:%m%d-%H%M}ET"       # 這次執行的編號：簡報日＋執行時間（美東）
T6_HIST = []
WD_ZH = "一二三四五六日"
REG_HUE = {"A": "#0a7d33", "B": "#3c8c3c", "C": "#b7791f", "D": "#c05621", "E": "#c0392b"}

def t6_bool(v):
    return str(v).strip().lower() in ("true", "1", "yes")

def t6_gates(lg, pg, sg):
    parts = (["多頭"] if lg else ["試單"] if pg else []) + (["空頭"] if sg else [])
    return ("、".join(parts) + "開") if parts else "全關"

def t6_history_build(n=10):
    """近 n 個簡報日。有執行紀錄的用紀錄；沒有的用今日的數據回算分數和 Regime（只作參考）。"""
    global T6_HIST
    recs = []
    path = os.path.join(HIST_DIR, "daily_log.csv")
    log = pd.read_csv(path, dtype=str) if os.path.exists(path) else pd.DataFrame()
    for r in (log.to_dict("records") if (len(log) and "asof" in log.columns) else []):
        a_ = pd.to_datetime(r.get("asof"), errors="coerce")
        if pd.isna(a_) or str(r.get("run_id", "")) == RUN_ID:
            continue
        b_ = pd.to_datetime(r.get("brief_date"), errors="coerce")
        bd = b_.date() if pd.notna(b_) else next_session(a_.date())            # v6.2 之前的紀錄沒有簡報日，由數據日推算
        lab = r.get("tier_top_label")
        new_fmt = isinstance(lab, str) and lab not in ("", "nan")              # v6.1 起才有分級紀錄
        raw = r.get("tier_top") if new_fmt else r.get("focus_long")
        top = [x for x in str(raw).split(",") if x and x != "nan"] if isinstance(raw, str) else []
        recs.append({"bd": bd, "run": str(r.get("run_et", "") or ""), "score": t6_f(pd.to_numeric(r.get("score"), errors="coerce")),
                     "regime": str(r.get("regime", "") or ""),
                     "gates": t6_gates(t6_bool(r.get("long_gate")), t6_bool(r.get("pilot_gate")), t6_bool(r.get("short_gate"))),
                     "cycle": str(r.get("cycle", "") or "").replace("nan", ""), "label": lab if new_fmt else "焦點",
                     "top": top, "cmp": new_fmt, "src": "log"})
    recs.append({"bd": SESS_D, "run": f"{RUN_TS:%Y-%m-%d %H:%M}", "score": score_now, "regime": REG_L,
                 "gates": t6_gates(LONG_GATE, PILOT_GATE, SHORT_GATE), "cycle": CYCLE, "label": T6_TOP_L,
                 "top": [c["Ticker"] for c in T6_LA], "cmp": True, "src": "now"})
    by, cnt = {}, {}
    for r in sorted(recs, key=lambda x: (x["bd"], x["run"])):
        by[r["bd"]] = r
        cnt[r["bd"]] = cnt.get(r["bd"], 0) + 1
    sc = SCORE.dropna()
    for d in sc.index[-n:]:
        bd = next_session(d.date())
        if bd not in by:
            by[bd] = {"bd": bd, "run": "", "score": float(sc.loc[d]),
                      "regime": REG_NAME[int(REGIME.loc[d])][0] if (d in REGIME.index and pd.notna(REGIME.loc[d])) else "",
                      "gates": "", "cycle": "", "label": "", "top": [], "cmp": False, "src": "calc"}
    out, last = [], None
    for bd in sorted(by)[-n:]:
        r = dict(by[bd])
        r["n"] = cnt.get(bd, 0)
        r["new"] = r["gone"] = None
        if r["cmp"] and last is not None:                                       # 和上一次有分級紀錄的簡報比較
            r["new"] = [t for t in r["top"] if t not in last["top"]]
            r["gone"] = [t for t in last["top"] if t not in r["top"]]
            r["vs"] = last["bd"]
        if r["cmp"]:
            last = r
        out.append(r)
    T6_HIST = out[::-1]                                                          # 新到舊
    lines = ["【近 10 日回顧】新到舊；同一日跑了幾次只列最後一次"
             ]
    for r in T6_HIST:
        head = f"  {r['bd']:%m-%d}（{WD_ZH[r['bd'].weekday()]}）｜分數 {fnum(r['score'], 0)}｜Regime {r['regime'] or '—'}"
        if r["src"] == "calc":
            lines.append(head + "｜沒有執行紀錄（分數按今日數據回算）")
            continue
        s_ = head + f"｜閘門 {r['gates']}｜{r['label']}：{'、'.join(r['top']) or '沒有'}"
        if r["new"] is not None:
            s_ += f"｜新入選 {'、'.join(r['new']) or '沒有'}｜跌出 {'、'.join(r['gone']) or '沒有'}"
        if r["n"] > 1:
            s_ += f"｜當日跑了 {r['n']} 次"
        lines.append(s_ + ("（今次）" if r["src"] == "now" else ""))
    T6_TXT.extend(lines)

if V6_OK:
    try:
        t6_history_build()
    except Exception as e:
        t6_warn("近 10 日回顧", e)

# ---------- v6.3：富途下單清單、今晚時間表（香港時間）、給格子 2 讀取的計劃檔 ----------
HKT = "Asia/Hong_Kong"
T6_ORD, T6_ORD_TXT, T6_TL = [], [], []

def t6_atr_d(c):
    """每股一個 ATR 的金額；不知道就按 4% 估。"""
    a = t6_f(c.get("ATR%"))
    return (4.0 if isnan(a) else a) * c["Close"] / 100

def t6_vol50(t):
    """50 日平均成交股數（池外的 High Tight Flag 股票用它自己的日線）。"""
    try:
        if t in V.columns:
            return t6_f(V[t].dropna().iloc[-50:].mean())
        if t in HTF_PX and "v" in HTF_PX[t].columns:
            return t6_f(HTF_PX[t]["v"].dropna().iloc[-50:].mean())
    except Exception:
        pass
    return np.nan

def _cent_up(x):
    return float(np.ceil(round(x * 100, 6)) / 100)

def _cent_dn(x):
    return float(np.floor(round(x * 100, 6)) / 100)

def t6_order(c, rank):
    """一隻首選股票的富途下單資料。未升穿的用止損限價單預設；數量按限價（最差成交價）計，保持每注風險不變。"""
    lg = c["Side"] == "多"
    t, atr_d = c["Ticker"], t6_atr_d(c)
    risk_plan = c["Shares"] * abs(c["Entry"] - c["Stop"])           # 計劃卡的每注風險
    if lg:
        trig, stop, chase = _cent_up(c["Trigger"]), _cent_dn(c["Stop"]), _cent_dn(c["Chase"])
    else:
        trig, stop, chase = _cent_dn(c["Trigger"]), _cent_up(c["Stop"]), _cent_up(c["Chase"])
    o = {"Rank": rank, "Ticker": t, "Side": "買入" if lg else "沽空", "Setup": c["Setup"], "Name": str(NAME_OF.get(t, "") or "")[:34],
         "Close": float(c["Close"]), "Pivot": float(c["Pivot"]), "Trigger": trig, "Chase": chase, "Stop": stop,
         "ATR": float(atr_d), "ATR%": float(t6_f(c.get("ATR%"))), "Through": bool(c["Through"]), "Earn": str(c["Earn"]),
         "Vol50": float(t6_vol50(t)), "PlanShares": int(c["Shares"]), "PlanRisk": float(risk_plan)}
    if lg and c["Through"]:                                          # 已升穿 pivot：現價高過觸發價，富途不接受這張止損單
        per = abs(chase - stop)                                      # 最差是在追價上限成交
        sh = int(min(c["Shares"], risk_plan // per)) if per > 0 else 0
        o.update(Type="開市後限價單", Mode="開市後", Limit=chase, Shares=sh, Risk=float(sh * per))
    else:
        buf = PLAN["limit_atr"] * atr_d
        lim = _cent_dn(min(trig + buf, chase)) if lg else _cent_up(max(trig - buf, chase))
        lim = max(lim, trig) if lg else min(lim, trig)
        per = abs(lim - stop)
        sh = int(min(c["Shares"], risk_plan // per)) if per > 0 else 0
        o.update(Type="止損限價單", Mode="預設", Limit=lim, Shares=sh, Risk=float(sh * per))
    return o

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

def t6_orders_build():
    global T6_ORD, T6_ORD_TXT
    T6_ORD = [t6_order(c, i + 1) for i, c in enumerate(T6_LA)] + [t6_order(c, i + 1) for i, c in enumerate(T6_SA)]
    nl, ns = T6_BUD.get("n_long", 0), T6_BUD.get("n_short", 0)
    for o in T6_ORD:
        o["InSlot"] = bool(o["Rank"] <= (nl if o["Side"] == "買入" else ns))
    if not T6_ORD:
        return
    T6_ORD_TXT = [f"【模擬參數摘要（僅供參考，非交易指令）】簡報日 {SESS_D:%Y-%m-%d}；規則示範上限：多頭 {nl} 單位" + (f"、空頭 {ns} 單位" if ns else "")
                  + "；系統開市前更新（盤前價格重算）會按盤前價重新判斷每組參數"]
    if not long_ok:
        T6_ORD_TXT.append("  多頭閘門未開：以下多頭參數只作試算，規則上不適用")
    for o in T6_ORD:
        T6_ORD_TXT.append(f"  {'上限內' if o['InSlot'] else '後備　'}｜" + t6_order_line(o))
    T6_TXT.extend(T6_ORD_TXT)

def t6_timeline_build():
    """今晚要留意的時間點，按美東時間排序；顯示時換算成香港時間。"""
    global T6_TL
    d = SESS_D
    at = lambda h, m: pd.Timestamp(_dt.datetime(d.year, d.month, d.day, h, m)).tz_localize(ET)
    open_ = at(9, 30)
    close_ = at(13, 0) if d in EARLY_CLOSES else at(16, 0)
    tl = [(open_ - pd.Timedelta(minutes=43), "系統開市前更新（盤前價格重算）", "系統"),
          (open_, "美股開市", "市場"), (open_ + pd.Timedelta(minutes=30), "開市首 30 分鐘完結（開市情景判定）", "市場"),
          (close_, "美股收市" + ("（提早收市）" if d in EARLY_CLOSES else ""), "市場")]
    if len(ECON) and {"_d", "When", "Event", "Tier"} <= set(ECON.columns):
        for r in ECON[ECON["_d"] == d].itertuples():
            hm = str(r.When)[-5:]
            try:
                tl.append((at(int(hm[:2]), int(hm[3:])), f"{r.Tier} {r.Event}", "數據"))
            except ValueError:
                continue
    mine = [c["Ticker"] for c in T6_LA + T6_SA + T6_LB] + list(POSITIONS)
    if len(EARN_NEXT) and {"Symbol", "_d"} <= set(EARN_NEXT.columns):
        en = EARN_NEXT[EARN_NEXT["_d"] == d]
        pick = pd.concat([en[en["Symbol"].isin(mine)], en[~en["Symbol"].isin(mine)].head(3)])
        for r in pick.to_dict("records"):
            slot = r.get("Slot") if isinstance(r.get("Slot"), str) else (str(r.get("When", "")).split(" ", 1)[1] if " " in str(r.get("When", "")) else "時間不明")
            ts = at(9, 0) if slot == "開市前" else at(16, 5) if slot == "收市後" else close_ + pd.Timedelta(minutes=10)
            tag = "持倉" if r["Symbol"] in POSITIONS else "名單" if r["Symbol"] in mine else "大型股"
            tl.append((ts, f"{r['Symbol']} 公佈業績（{slot}；{tag}）", "財報"))
    T6_TL = [{"et": ts, "what": w, "kind": k} for ts, w, k in sorted(tl, key=lambda x: x[0])]
    o_h = open_.tz_convert(HKT)
    lines = [f"【今晚時間表】香港時間（美東）；美股開市是香港時間 {o_h:%H:%M}"]
    for x in T6_TL:
        h = x["et"].tz_convert(HKT)
        lines.append(f"  {h:%H:%M}{'（翌日）' if h.date() > o_h.date() else ''}（{x['et']:%H:%M}）{x['what']}")
    T6_TXT.extend(lines)

def _js(v):
    """轉成 JSON 可以存的值。"""
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return None if np.isnan(v) else float(v)
    if isinstance(v, float) and np.isnan(v):
        return None
    if isinstance(v, (np.bool_,)):
        return bool(v)
    if isinstance(v, dict):
        return {k: _js(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_js(x) for x in v]
    if isinstance(v, (pd.Timestamp, _dt.date)):
        return str(v)
    return v

def t6_plan_dict():
    """格子 2 要用的全部資料：名單、下單資料、持倉、時間表、QQQ 的收市價和 ATR。"""
    pos = []
    for r in (POS_TBL.to_dict("records") if len(POS_TBL) else []):
        p = POSITIONS.get(r["Ticker"], {})
        pos.append({"Ticker": r["Ticker"], "Shares": p.get("shares"), "Stop": p.get("stop"), "Entry": p.get("entry"),
                    "EntryDate": str(p.get("entry_d") or ""), **{k: r.get(k) for k in ("Close", "ATR$", "EMA21", "S50", "Low10", "Earn", "Act", "Note")}})
    watch = [{"Ticker": c["Ticker"], "Side": "買入" if c["Side"] == "多" else "沽空", "Trigger": c["Trigger"], "Stop": c["Stop"],
              "Close": c["Close"], "ATR": t6_atr_d(c), "Why": c.get("Reason", "")} for c in T6_LB + T6_SB]
    return _js({"version": "6.3", "run_id": RUN_ID, "brief_date": f"{SESS_D:%Y-%m-%d}", "asof": f"{ASOF:%Y-%m-%d}",
                "run_et": f"{RUN_TS:%Y-%m-%d %H:%M}", "account_equity": ACCOUNT_EQUITY, "base_risk_pct": BASE_RISK_PCT,
                "mult_long": LONG_RISK / (ACCOUNT_EQUITY * BASE_RISK_PCT / 100) if ACCOUNT_EQUITY and BASE_RISK_PCT else 0,
                "mult_short": TH["risk_mult"]["short"], "regime": REG_L, "score": round(score_now, 1),
                "verdict": T6_VERDICT, "gates": t6_gates(LONG_GATE, PILOT_GATE, SHORT_GATE), "long_ok": bool(long_ok),
                "short_ok": bool(T6_SGATE), "event_day": bool(EVENT_DAY), "n_long": T6_BUD.get("n_long", 0), "n_short": T6_BUD.get("n_short", 0),
                "qqq": {"close": q.c, "atr": q.atr, "high": q.h, "low": q.l},
                "params": {k: PLAN[k] for k in ("limit_atr", "near_open_atr", "gapdown_atr")},
                "orders": T6_ORD, "watch_b": watch, "positions": pos,
                "timeline": [{"et": str(x["et"]), "what": x["what"], "kind": x["kind"]} for x in T6_TL]})

if V6_OK:
    for _fn, _lab in ((t6_orders_build, "下單清單"), (t6_timeline_build, "今晚時間表")):
        try:
            _fn()
        except Exception as e:
            t6_warn(_lab, e)
# --- Hero ---
score_arrow = "▲" if score_now > score_prev + 0.5 else "▼" if score_now < score_prev - 0.5 else "■"
hero = [f'<div class="hero" style="border-left-color:{REG_COLOR[0]};background:{REG_COLOR[1]}">']
hero.append(f'<div class="big" style="color:{REG_COLOR[0]}">Regime {REG_L} {REG_T}　·　今日：{esc(SIDE)}</div>')
hero.append(f'<div class="mid">市場健康分數 <b>{score_now:.0f}</b> {score_arrow}（昨日 {score_prev:.0f}，5 日前 {score_5:.0f}；已在 {REG_L} 區 {REG_DAYS} 日）'
            f'　|　市場週期：<b>{esc(CYCLE)}</b></div>')
hero.append("<div>" + pill("多頭閘門 " + ("開" if LONG_GATE else "關"), "on" if LONG_GATE else "off")
            + pill("試單閘門 " + ("開" if PILOT_GATE else "關"), "on" if PILOT_GATE else "off")
            + pill("空頭閘門 " + ("開" if SHORT_GATE else "關"), "bad" if SHORT_GATE else "off")
            + pill("超賣 " + ("是" if OVERSOLD else "否"), "wrn" if OVERSOLD else "off")
            + (pill("空頭時機：" + SHORT_TIMING.split("：")[0], "wrn") if SHORT_SETUP else "") + "</div>")
bo_txt = "樣本不足" if np.isnan(BO_FOLLOW) else f"{BO_FOLLOW:.0f}%（{BO_FOLLOW_N} 個）"
risk_txt = f"${RISK_DOLLARS:,.0f}（標準的 {RISK_MULT * 100:.0f}%）" if GATE_OPEN else "不開新倉"
hero.append('<div class="kv">'
            f'<div><small>多倉總上限</small><b>{TH["long_cap"][REG_L]}</b></div>'
            f'<div><small>空倉</small><b>{TH["short_cap"][REG_L] if SHORT_GATE else "不做"}</b></div>'
            f'<div><small>每注風險</small><b>{risk_txt}</b></div>'
            f'<div><small>突破成功率（5–15 日前的突破）</small><b>{bo_txt}</b></div>'
            f'<div><small>52 週新高 / 新低</small><b>{fnum(NH.iloc[-1], 0)} / {fnum(NL.iloc[-1], 0)}</b></div>'
            f'<div><small>股票高於 50 日線</small><b>{pct50_now:.0f}%</b></div></div>')
hero.append("<b>今日劇本</b><ul>" + "".join(f"<li>{esc(x)}</li>" for x in PLAY) + "</ul>")
if TRIG:
    rows = "".join(f'<tr><td class="{"g" if a == "↑" else "r"}"><b>{a}</b></td><td>{esc(what)}</td>'
                   f'<td class="num">{"—" if isnan(dist) else f"{dist:+.1f}%"}</td><td>{esc(mean)}</td></tr>' for a, what, dist, mean in TRIG)
    hero.append('<b>甚麼會改變結論</b><div class="tw"><table><thead><tr><th></th><th>觸發條件（QQQ）</th><th class="num">距參考價</th>'
                f'<th>意義</th></tr></thead><tbody>{rows}</tbody></table></div>')
hero.append("</div>")

# --- 機會總覽 ---
def opp(title, d, hint):
    return f'<div><b>{esc(title)}</b><span>{len(d)}</span><small>{esc(names(d))}</small><small class="m">{esc(hint)}</small></div>'
opp_long = (opp("VCP 候選", VCP, "距 pivot 5% 以內") + opp("High Tight Flag", HTF[HTF["Note"] == ""] if len(HTF) else HTF, "8 週內升近一倍後橫行；疑似收購的不計")
            + opp("收窄待發", TIGHT, "波幅收到半年低位、量縮")
            + opp("新高突破", BO52, "上日首次收市創 52 週高") + opp("抗跌強勢", RESIL, "指數跌而它貼近高位")
            + opp("回調買點", PULL, "上升股回到 21EMA／50 日線") + opp("向上缺口", GAPUP, "缺口 ≥ 4% 且放量"))
opp_short = (opp("回抽阻力", S_RETEST, "弱股反彈到下降中的均線") + opp("新跌破", BD, "上日首次跌穿低位")
             + opp("墮落龍頭", FALLEN, "一年升幅大但趨勢已壞") + opp("向下缺口", GAPDN, "缺口 ≤ −4% 且放量"))
overview = ('<details open><summary>機會總覽 <span class="cnt">數字是符合條件的隻數，下面是 RS 最前的幾隻</span></summary><div class="sec">'
            + ("" if long_ok else '<div class="warnbox">多頭與試單閘門都未開：做多名單只作觀察、設提示，不落盤。</div>')
            + f'<h3>做多</h3><div class="opp">{opp_long}</div><h3>做空與迴避</h3><div class="opp">{opp_short}</div></div></details>')

# --- 1 市況 ---
prow = ""
for p in PILLARS:
    now_, p5 = PS[p.key].iloc[-1], PS[p.key].iloc[-6]
    dlt = now_ - p5
    prow += (f'<tr><td><b>{p.name}</b></td><td class="num">{TH["weights"][p.key]}%</td><td style="width:38%">{bar(now_)}</td>'
             f'<td class="num"><b>{now_:.0f}</b></td><td class="num {"g" if dlt > 0 else "r" if dlt < 0 else "m"}">{dlt:+.0f}</td></tr>')
pillars_html = ('<table><thead><tr><th>支柱</th><th class="num">權重</th><th>分數</th><th class="num">現在</th>'
                f'<th class="num">5 日變化</th></tr></thead><tbody>{prow}</tbody></table>')
detail_rows = ""
for p in PILLARS:
    for label, pts, mx, val in p.items:
        got = np.nan if pts is None else pts.iloc[-1]
        ok = (not isnan(got)) and got >= mx
        part = (not isnan(got)) and 0 < got < mx
        mark = '<td class="g">✓</td>' if ok else '<td class="a">◐</td>' if part else '<td class="r">✗</td>'
        detail_rows += (f"<tr><td>{p.name}</td>{mark}<td>{esc(label)}</td><td>{esc(val or '—')}</td>"
                        f'<td class="num">{"—" if isnan(got) else f"{got:g} / {mx:g}"}</td></tr>')
weekly_txt = "—" if WEEKLY_UP is None else ("週線向上（收市 > 10 週線 > 40 週線）" if WEEKLY_UP else "週線未成多頭排列")
if RALLY["in_correction"]:
    rally_txt = (f"調整低位 {RALLY['low']:.2f}（{RALLY['low_date']:%m-%d}，距之前高位 {RALLY['depth']:.1f}%）；"
                 + (f"FTD 出現於 {RALLY['ftd_date']:%m-%d}，仍然有效。" if RALLY["ftd_valid"] else f"數據日是反彈第 {RALLY['day']} 日，未有 FTD。"))
else:
    rally_txt = f"最近 60 日低位距之前高位 {RALLY['depth']:.1f}%，未達 8%，不算調整。"
irx_txt = "" if IRX63 is None else (f"　短端利率（13 週國庫券）三個月 {IRX63:+.0f}bp"
                                    + ("，市場正在消化加息。" if IRX63 >= 25 else "，市場正在消化減息。" if IRX63 <= -25 else "。"))
gap_txt = ("未有期貨或盤前數據。" if np.isnan(GAP_PX) else
           f"參考價 {GAP_PX:.2f}（{GAP_SRC}），缺口 {GAP_PCT:+.2f}%，相當於 {GAP_ATR:+.2f} ATR。")
s1 = (f'<ul><li>日線：收市 {q.c:.2f}，距 52 週高位 {dd_from_high:.1f}%，距 21EMA {d21_q:+.1f}%，距 50 日線 {(q.c / q.s50 - 1) * 100:+.1f}%，'
      f'距 200 日線 {(q.c / q.s200 - 1) * 100:+.1f}%；RSI {q.rsi:.0f}；ATR {q.atr:.2f}（{q.atr / q.c * 100:.1f}%）。</li>'
      f"<li>{esc(weekly_txt)}；近 25 日派發日 {DIST_N} 個。</li><li>{esc(rally_txt)}</li>"
      f"<li>開市參考：{esc(gap_txt)}</li><li>{esc(SCEN)}</li>" + (f"<li>{esc(EM_TXT)}</li>" if EM_TXT else "") + "</ul>"
      f'<div class="two"><div><h3>關鍵位</h3>{render(LEVELS, SPEC["levels"])}</div>'
      f"<div><h3>五大支柱</h3>{pillars_html}<div class='note'>5 日總分變動 {score_now - score_5:+.0f}；"
      + "，".join(f"{r.Pillar} {r.Contrib:+.1f}" for r in ATTR.itertuples()) + f"。{esc(irx_txt.strip())}</div></div></div>"
      + "<h3>指數對照</h3>" + render(IDX_TBL, SPEC["idx"], empty="指數數據取不到")
      + '<div class="two"><div><h3>各指數的寬度</h3>' + render(BR_TBL, SPEC["br"], empty="沒有數據")
      + "</div><div><h3>仍然有效的派發日（QQQ）</h3>" + render(DIST_TBL, SPEC["dist"], empty="近 25 個交易日沒有有效的派發日")
      + '<div class="note">派發日：跌 0.2% 以上而成交高於前一日。滿 25 個交易日、或 QQQ 收市較該日高出 5% 就失效。</div></div></div>'
      + CHART_IMG
      + '<details><summary>支柱明細（每個檢查項目）</summary><div class="sec"><table><thead><tr><th>支柱</th><th></th><th>檢查項目</th>'
        f'<th>現況</th><th class="num">得分</th></tr></thead><tbody>{detail_rows}</tbody></table></div></details>')

# --- 2 隔夜 ---
s2 = (render(OVN, SPEC["ovn"], empty="期貨數據取不到") +
      '<div class="note">變動由上一個收市日美東 16:00 起計，是真正的隔夜變動。VIX 和孳息在美股交易時段以外不更新。</div>')
if len(PMG):
    s2 += "<h3>盤前異動（成交金額最高的 " + str(TH["premarket_top_n"]) + f" 隻之中，盤前缺口 ≥ {TH['premarket_gap']:g}%）</h3>" + render(PMG, SPEC["pmg"], 25)
elif SCAN_PREMARKET:
    s2 += '<div class="note">盤前異動名單只在美東 4:00–9:35 之間執行才有數據。</div>'

# --- 3 資金流向 ---
s3 = ("<h3>11 個板塊（按 1 個月回報）</h3>" + render(SECT_TBL, SPEC["sect"])
      + "<h3>最強的行業組別</h3>" + render(GRP_TOP, SPEC["grp"], empty="沒有行業組別資料")
      + "<h3>最弱的行業組別</h3>" + render(GRP_BOT, SPEC["grp"], empty="沒有行業組別資料")
      + "<h3>行業 ETF</h3>" + render(IND_TBL, SPEC["ind"])
      + '<div class="note">行業組別用股票池內個股的中位數計算，每組最少 4 隻；排名綜合 1 個月、3 個月回報和高於 50 日線的比例。</div>')

# --- 4 龍頭 ---
s4 = (f'<div class="note">成交金額最高的 {len(LEAD)} 隻。高於 50 日線的比例 {LEAD_PCT50.iloc[-1]:.0f}%（5 日前 {LEAD_PCT50.iloc[-6]:.0f}%）。</div>'
      + render(LEAD_TBL, SPEC["lead"])
      + '<details><summary>RS 分解（各期回報）</summary><div class="sec"><div class="note">RS（v3）把每一期回報先排百分位再加權：'
        "1 個月 20%、3 個月 30%、6 個月 20%、9 個月 15%、12 個月 15%。舊算法把回報直接加權，12 個月升幅極大的股票即使近期大跌，分數仍會很高。</div>"
      + render(LEAD_TBL, SPEC["rsd"]) + "</div></details>")

# --- 5 做多 ---
long_note = "" if long_ok else '<div class="note">閘門未開，以下全部只列作觀察。</div>'
s5 = (long_note
      + f"<h3>VCP 候選（{len(VCP)}）</h3><div class='note'>通過 Trend Template、收縮逐次變小、量縮、距 pivot 5% 以內。</div>" + render(VCP, SPEC["vcp"], 15)
      + f"<h3>High Tight Flag（{len(HTF)}）</h3><div class='note'>旗桿：40 個交易日內由低位升 ≥ 90%。旗形：見頂後 3–25 日，回調不超過 25%。"
        f"「旗桿中」是剛見頂未夠 3 日，等旗形形成；「突破旗形」是上日收市升穿旗桿高位。{esc(HTF_NOTE)}</div>" + render(HTF, SPEC["htf"], 20)
      + f"<h3>收窄待發（{len(TIGHT)}）</h3><div class='note'>通過 Trend Template，10 日波幅在近半年最窄的四分一而且不超過 10%，距 10 日高位 6% 以內，10 日均量低於 50 日均量的 85%。Pivot 用 10 日高位。</div>" + render(TIGHT, SPEC["tight"], 15)
      + f"<h3>新高突破（{len(BO52)}）</h3><div class='note'>上日收市首次高於之前 252 日最高價。高於突破位超過 5% 的不追。</div>" + render(BO52, SPEC["bo"], 15)
      + f"<h3>抗跌強勢（{len(RESIL)}）</h3><div class='note'>Stage 2、RS ≥ 80、距 52 週高 8% 以內，RS 線創新高，自指數見頂（{PEAK_DATE:%m-%d}）以來仍然上升，而且高於 50 日線不超過 20%（未走遠）。同期 QQQ {QQQ_SINCE_PEAK:+.1f}%。</div>" + render(RESIL, SPEC["resil"], 20)
      + f"<h3>回調買點（{len(PULL)}）</h3><div class='note'>通過 Trend Template、RS ≥ 80，由 20 日高位回落 3% 以上，回到上升中的 21EMA 或 50 日線，近 3 日成交低於平均。</div>" + render(PULL, SPEC["pull"], 15)
      + f"<h3>向上缺口（{len(GAPUP)}）</h3><div class='note'>上日高開 ≥ 4%、成交 ≥ 2 倍、收在當日波幅上半。多數是財報或消息缺口。</div>" + render(GAPUP, SPEC["gap"], 12)
      + f"<h3>貼近歷史高位（{len(ATH)}）</h3>" + render(ATH, SPEC["ath"], 20)
      + f"<h3>月高首日突破（{len(BO1M)}）</h3>" + render(BO1M, SPEC["bo1m"], 12))

# --- 6 做空 ---
short_note = ("" if SHORT_GATE else '<div class="warnbox">空頭閘門未開，以下只作迴避名單和市場警號。</div>')
s6 = (short_note + (f'<div class="note">空頭時機：{esc(SHORT_TIMING)}。</div>' if SHORT_SETUP else "")
      + f"<h3>回抽阻力（{len(S_RETEST)}）</h3><div class='note'>Stage 4、RS ≤ 30、50 日線向下，近 3 日反彈到 21EMA 或 50 日線附近。反彈受阻回落才是入場點，止蝕放反彈高位之上。</div>" + render(S_RETEST, SPEC["retest"], 15)
      + f"<h3>新跌破（{len(BD)}）</h3><div class='note'>上日首次跌穿 52 週低位，或 Stage 4 股票首次跌穿月低。低於 50 日線 15% 以上或低於 21EMA 3 個 ATR 以上，標為已超跌。</div>" + render(BD, SPEC["bd"], 15)
      + f"<h3>墮落龍頭（{len(FALLEN)}）</h3><div class='note'>舊算法的 12 個月 RS ≥ 80，但已跌離 52 週高位 25% 以上並失守 50 日線。它們過去一年升幅仍然很大，但趨勢已壞；v3 的 RS 已反映這一點。</div>" + render(FALLEN, SPEC["fallen"], 15)
      + f"<h3>向下缺口（{len(GAPDN)}）</h3>" + render(GAPDN, SPEC["gap"], 12))

# --- 7 消息面 ---
def _news_li(n):
    link = f'<a href="{esc(n["url"])}" target="_blank">{esc(n["title"])}</a>' if n["url"] else esc(n["title"])
    return (f'<li><span class="m">{esc(n["when"][5:])}</span> [{esc(n["t"])}] {link}'
            + (f' <span class="m">（{esc(n["prov"])}）</span>' if n["prov"] else "") + "</li>")
if len(EARN_NEXT):
    EARN_NEXT["InList"] = EARN_NEXT["Symbol"].isin(WATCH + list(POSITIONS) + (list(HTF["Ticker"]) if len(HTF) else []))
theme_txt = "、".join(f"{k} {v} 則" for k, v in sorted(THEME_N.items(), key=lambda kv: -kv[1]))
s7 = ("<h3>昨日市場回顧（由數據計算）</h3><ul>" + "".join(f"<li>{esc(x)}</li>" for x in RECAP) + "</ul>"
      + ("<h3>日曆因素</h3><ul>" + "".join(f"<li>{esc(x)}</li>" for x in CAL_FLAGS) + "</ul>" if CAL_FLAGS else "")
      + "<h3>財報反應</h3><div class='note'>好消息不升是弱，壞消息不跌是強。剛公佈時盈利驚喜可能未有數字。</div>"
      + (render(EARN_REACT, SPEC["react"], 20) if len(EARN_REACT) else f'<div class="note">{esc(EARN_NOTE or "這兩日沒有股票池內的公司公佈財報。")}</div>')
      + f"<h3>{SESS:%m-%d} 及下一個交易日的財報（股票池內，按成交金額排序）</h3>"
      + (render(EARN_NEXT, SPEC["enext"], 25) if len(EARN_NEXT) else f'<div class="note">{esc(EARN_NOTE or "沒有列出。")}</div>')
      + "<h3>重點經濟數據</h3>" + (render(ECON, SPEC["econ"], 20) if len(ECON) else f'<div class="note">{esc(ECON_NOTE or "未取")}</div>')
      + "<h3>名單與持倉的財報風險（3 個交易日內）</h3>"
      + ("<ul>" + "".join(f"<li><b>{esc(t)}</b>（{esc(nm)}）：{esc(es)}</li>" for t, nm, es in EARN_SOON) + "</ul>" if EARN_SOON else '<div class="note">沒有。</div>')
      + ("<h3>市場要聞（美東時間）</h3>" + (f'<div class="note">主題：{esc(theme_txt)}</div>' if theme_txt else "") + "<ul>" + "".join(_news_li(n) for n in NEWS) + "</ul>" if NEWS else "")
      + ("<h3>AI 消息面</h3>__AI_NEWS__" if AI_NEWS else "")
      + '<div class="note">日曆和要聞不保證齊全；聯儲局官員講話和突發消息不在日曆內。</div>')

# --- 8 持倉 ---
s8 = (f'<div class="note">未平倉總風險佔戶口 {OPEN_RISK_PCT:.2f}%；多倉市值佔戶口 {LONG_EXPO:.0f}%，Regime {REG_L} 的上限是 {CAP_MAX[REG_L]}%'
      + ("，已超出上限。" if LONG_EXPO > CAP_MAX[REG_L] else "。") + "</div>" + render(POS_TBL, SPEC["pos"])) if len(POS_TBL) else \
     ""

# --- 文字摘要 ---
def tl(d, n=8):
    return ", ".join(d["Ticker"].head(n)) if len(d) else "無"
TXT = [f"盤前簡報 {SESS:%Y-%m-%d}（數據截至 {ASOF:%Y-%m-%d} 收市，執行 {RUN_TS:%m-%d %H:%M} ET）",
       f"Regime {REG_L} {REG_T}｜{SIDE}｜分數 {score_now:.0f}（昨 {score_prev:.0f}，5 日前 {score_5:.0f}）｜{CYCLE}",
       f"閘門：多頭 {'開' if LONG_GATE else '關'}，試單 {'開' if PILOT_GATE else '關'}，空頭 {'開' if SHORT_GATE else '關'}，超賣 {'是' if OVERSOLD else '否'}；空頭時機：{SHORT_TIMING}",
       "支柱：" + "，".join(f"{p.name} {PS[p.key].iloc[-1]:.0f}（5 日 {PS[p.key].iloc[-1] - PS[p.key].iloc[-6]:+.0f}）" for p in PILLARS),
       f"QQQ {q.c:.2f}；21EMA {q.ema21:.2f}；50 日線 {q.s50:.2f}；200 日線 {q.s200:.2f}；上日高低 {q.h:.2f}/{q.l:.2f}；20 日低 {q.lo20:.2f}；52 週高 {q.hi252:.2f}（{dd_from_high:.1f}%）；ATR {q.atr:.2f}；派發日 {DIST_N}",
       rally_txt,
       f"開市參考：{gap_txt}",
       f"寬度：>50 日線 {pct50_now:.0f}%，>200 日線 {PCT200.iloc[-1]:.0f}%，>20 日線 {PCT20.iloc[-1]:.0f}%（5 日前 {PCT20.iloc[-6]:.0f}%）；新高 {fnum(NH.iloc[-1], 0)} / 新低 {fnum(NL.iloc[-1], 0)}；突破成功率 {bo_txt}",
       f"波動與利率：VIX {fnum(vix_now, 1)}；VXN {fnum(VXN.iloc[-1] if VXN is not None else np.nan, 1)}；VIX/VIX3M {fnum(TERM.iloc[-1] if TERM is not None else np.nan, 2)}；10 年期 {fnum(TNX.iloc[-1] if TNX is not None else np.nan, 2)}%；{irx_txt.strip()}",
       "自收市以來：" + ("；".join(f"{r.Name} {r.Chg}" for r in OVN.itertuples()) if len(OVN) else "無數據"),
       "板塊 1 個月：" + ("，".join(f"{r.ETF} {r.R21:+.1f}%" for r in SECT_TBL.itertuples()) if len(SECT_TBL) else "無"),
       "最強行業組別：" + ("；".join(GRP_TOP["SubInd"].head(5)) if len(GRP_TOP) else "無") + "｜最弱：" + ("；".join(GRP_BOT["SubInd"].head(5)) if len(GRP_BOT) else "無"),
       "龍頭：" + "，".join(f"{r.Ticker}(S{str(r.Stage)[:1]},RS{'—' if isnan(r.RS) else format(r.RS, '.0f')})" for r in LEAD_TBL.itertuples()),
       f"做多觀察｜VCP: {tl(VCP)}｜High Tight Flag: {tl(HTF[HTF['Note'] == ''] if len(HTF) else HTF)}｜收窄: {tl(TIGHT)}｜新高突破: {tl(BO52)}｜抗跌強勢: {tl(RESIL, 12)}｜回調: {tl(PULL)}｜向上缺口: {tl(GAPUP)}",
       f"做空與迴避｜回抽阻力: {tl(S_RETEST)}｜新跌破: {tl(BD)}｜墮落龍頭: {tl(FALLEN, 12)}｜向下缺口: {tl(GAPDN)}",
       "昨日回顧：" + " ".join(RECAP),
       "財報反應：" + ("；".join(f"{r.Symbol} {'—' if isnan(r.Move) else format(r.Move, '+.1f') + '%'}（{r.Verdict}）" for r in EARN_REACT.head(10).itertuples()) if len(EARN_REACT) else "無"),
       f"{SESS:%m-%d} 財報：" + ("，".join(f"{r.Symbol}（{str(r.When)[6:]}）" for r in EARN_NEXT[EARN_NEXT["_d"] == SESS_D].head(15).itertuples()) if len(EARN_NEXT) else "無"),
       "重點數據：" + ("；".join(f"{r.Tier}{r.When[-5:]} {r.Event}" for r in ECON[ECON["_d"] == SESS_D].itertuples()) if len(ECON) and "_d" in ECON.columns else (ECON_NOTE or "無")),
       "日曆因素：" + (" ".join(CAL_FLAGS) if CAL_FLAGS else "無"),
       "財報風險（3 日內）：" + ("、".join(f"{t}（{nm}，{es}）" for t, nm, es in EARN_SOON) if EARN_SOON else "無"),
       "焦點名單：" + ("；".join(f"{r.Ticker}（{r.Setup}，{'觸發' if r.Status == '待升穿' else '已升穿'} {r.Trigger:.2f}，止蝕 {r.Stop:.2f}）" for r in FOCUS_L.itertuples()) if len(FOCUS_L) else "無")
       + ("｜做空：" + "；".join(f"{r.Ticker}（跌穿 {r.Trigger:.2f}，止蝕 {r.Stop:.2f}）" for r in FOCUS_S.itertuples()) if len(FOCUS_S) else ""),
       "標題：" + (" / ".join(n["title"] for n in NEWS[:8]) if NEWS else "無"),
       "今日劇本：" + " / ".join(PLAY)]
if len(POS_TBL):
    TXT.append("持倉：" + "；".join(f"{r.Ticker} 現價 {r.Px:.2f} 止蝕 {r.Stop:.2f}" for r in POS_TBL.itertuples() if hasattr(r, "Px") and not isnan(getattr(r, "Px", np.nan))))
if V6_OK and T6_TXT:                                        # v6：三條問題放在文字摘要最前，取代舊的「焦點名單」一行
    TXT = TXT[:2] + T6_TXT + [x for x in TXT[2:] if not x.startswith("焦點名單：")]
BRIEF_TXT = "\n".join(TXT) + OBB_TXT

# ---------- AI 消息面（選用）：用 Claude API 的網絡搜尋工具寫一段消息面 ----------
AI_TEXT, AI_SRC, AI_NOTE = "", [], ""
def ai_news(summary):
    key = None
    try:
        from google.colab import userdata
        key = userdata.get("ANTHROPIC_API_KEY")
    except Exception:
        key = None
    key = key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return "", [], "找不到 ANTHROPIC_API_KEY。請在 Colab 左邊的鑰匙圖示（Secrets）加入，並允許這個筆記本讀取。"
    prompt = (
        "你是美股趨勢交易者的盤前助手。以下是腳本按固定規則計算出來的盤前簡報摘要，"
        f"數據截至 {ASOF:%Y-%m-%d} 收市，為 {SESS:%Y-%m-%d} 的交易日準備。\n"
        "請用網絡搜尋查出最新的消息面，然後只輸出以下四節。用繁體中文，總長不超過 450 字；每節用「【】」作標題，其下每點以「- 」開頭。\n"
        "【隔夜與昨日要聞】最多 4 點，解釋摘要裡指數、板塊和龍頭股異動背後的原因。\n"
        "【今日事件】按美東時間列出今日的經濟數據（附市場預期）、聯儲局官員講話、重要財報和其他事件。\n"
        "【與名單有關的消息】只寫摘要內出現過的股票代號，說明財報、評級或消息；沒有就寫「沒有」。\n"
        "【對今日劇本的影響】最多 3 點：哪些事件代表要減注或等待。\n"
        "規則：只寫你搜尋到、有來源的事實，數字要準確，查不到就直接說查不到；"
        "不要推翻摘要裡的閘門結論，不要預測升跌，不要給買賣建議。\n\n===== 盤前簡報摘要 =====\n" + summary)
    body = {"model": AI_MODEL, "max_tokens": 2500,
            "tools": [{"type": "web_search_20250305", "name": "web_search", "max_uses": 6}]}
    headers = {"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
    msgs, texts, srcs = [{"role": "user", "content": prompt}], [], {}
    for _ in range(4):
        r = requests.post("https://api.anthropic.com/v1/messages", headers=headers, json={**body, "messages": msgs}, timeout=300)
        try:
            j = r.json()
        except Exception:
            return "", [], f"API 回應無法解讀（HTTP {r.status_code}）。"
        if r.status_code != 200:
            return "", [], f"API 回應 {r.status_code}：{str((j.get('error') or {}).get('message', ''))[:200]}"
        for blk in j.get("content", []):
            if blk.get("type") in ("server_tool_use", "web_search_tool_result"):
                texts = []                                   # 只保留最後一次搜尋之後寫的正文
            elif blk.get("type") == "text":
                texts.append(blk.get("text", ""))
                for c in blk.get("citations") or []:
                    if c.get("url"):
                        srcs[c["url"]] = c.get("title") or c["url"]
        if j.get("stop_reason") == "pause_turn":             # 長回合被暫停：把助手內容原樣送回去繼續
            msgs = msgs + [{"role": "assistant", "content": j["content"]}]
            continue
        break
    return "".join(texts).strip(), list(srcs.items())[:12], ""

if AI_NEWS:
    print("AI 消息面：呼叫 Claude API（會上網搜尋，需時約一分鐘）…")
    try:
        AI_TEXT, AI_SRC, AI_NOTE = ai_news(BRIEF_TXT)
    except Exception as e:
        AI_NOTE = f"AI 消息面失敗（{type(e).__name__}: {str(e)[:120]}）"

def ai_html():
    if not AI_NEWS:
        return ""
    if not AI_TEXT:
        return f'<div class="warnbox">{esc(AI_NOTE or "沒有回應")}</div>'
    out, in_ul = [], False
    for line in AI_TEXT.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("【"):
            if in_ul:
                out.append("</ul>"); in_ul = False
            out.append(f"<h3>{esc(line)}</h3>")
        elif line[:1] in "-•・":
            if not in_ul:
                out.append("<ul>"); in_ul = True
            out.append(f"<li>{esc(line[1:].strip())}</li>")
        else:
            if in_ul:
                out.append("</ul>"); in_ul = False
            out.append(f"<div>{esc(line)}</div>")
    if in_ul:
        out.append("</ul>")
    if AI_SRC:
        out.append('<div class="note">來源：' + "　".join(f'<a href="{esc(u)}" target="_blank">{esc(str(t)[:40])}</a>' for u, t in AI_SRC) + "</div>")
    out.append(f'<div class="note">由 {esc(AI_MODEL)} 根據網絡搜尋撰寫，可能有錯漏，重要事項請對照來源；它不改變上面按規則計算的閘門結論。</div>')
    return "".join(out)


s7 = s7.replace("__AI_NEWS__", ai_html())
print(f"  財報來源：{EARN_SRC}；經濟日曆來源：{ECON_SRC}")

# --- 焦點名單卡片 ---
focus_note = ("閘門已開：以下是按固定計分挑出的首選；規則要求升穿觸發價並通過五項入場確認。" if long_ok else
              "多頭與試單閘門未開：以下只列作觀察。")
focus_html = ('<details open><summary>焦點名單與提示價 <span class="cnt">由各名單自動挑選，最多 5 隻做多、3 隻做空</span></summary><div class="sec">'
              + f'<div class="warnbox">{esc(focus_note)}</div>' + "<h3>做多</h3>" + render(FOCUS_L, SPEC["focus_l"], empty="沒有合資格的候選")
              + ("<h3>做空（空頭條件成立時才列出；" + esc(SHORT_TIMING.split("：")[0]) + "）</h3>" + render(FOCUS_S, SPEC["focus_s"], empty="沒有合資格的候選") if SHORT_SETUP else "")
              + "<h3>提示價（可在 TradingView 逐個設定）</h3>" + render(ALERT_TBL, SPEC["alerts"], empty="沒有")
              + '<div class="note">計分：RS 為底；形態加分（VCP 8、HTF 和收窄 6、新高突破 5、回調 3）；板塊排名前四加 10；現價在觸發價之下 3% 以內加 8；'
                "RS 線新高加 5；U/D 量比 ≥ 1.2 加 4；高於 50 日線逾 20% 減 15；3 個交易日內有財報減 30。沒有 pivot 的名單用 10 日高位或 3 日高位作觸發價，"
                "止蝕取 1.5 倍 ATR（最少 3%、最多 8%）。這是篩選次序，不是買賣訊號。</div></div></details>")

# ---------- v6：縮圖、計劃卡、首頁（三條問題）----------
T6_UID = [0]
T6_HEAD = ""
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

def t6_px(t, days):
    """一隻股票最近的日線（o,h,l,c,v 和均線）。股票池成員用主數據，池外的 High Tight Flag 用另存的 6 個月日線。"""
    if t in C.columns:
        d = pd.DataFrame({"o": O[t], "h": H[t], "l": L[t], "c": C[t], "v": V[t],
                          "e21": EMA21[t], "s50": S50_ALL[t], "s200": S200[t], "v50": AVGVOL50[t]})
    elif t in HTF_PX:
        d = HTF_PX[t].copy()
        d["e21"] = d["c"].ewm(span=21, adjust=False).mean()
        d["s50"] = d["c"].rolling(50).mean()
        d["s200"] = np.nan
        d["v50"] = d["v"].rolling(50, min_periods=20).mean()
    else:
        return None
    d = d.dropna(subset=["h", "l", "c"]).tail(days).copy()
    d["o"] = d["o"].fillna(d["c"])
    return d if len(d) >= 20 else None

def t6_chart(t, lines=(), w=400, h=240, days=126, compact=False):
    """內嵌 SVG 日線圖：陰陽燭、21EMA、50 日線、200 日線、成交量和 50 日均量；lines 是要畫的橫線（名稱、價位、顏色）。"""
    d = t6_px(t, days)
    if d is None:
        return f'<div class="note">{esc(t)}：日線數據不足，畫不到圖。</div>'
    T6_UID[0] += 1
    uid = f"t6c{T6_UID[0]}"
    n = len(d)
    padl, padr = 3, (3 if compact else 78)
    padt, padb = (3 if compact else 18), (3 if compact else 14)
    vh = h * 0.17
    ph = h - padt - padb - vh - 4
    pw = w - padl - padr
    step = pw / n
    bw = max(min(step * 0.64, 6.0), 0.8)
    o_, h_, l_, c_v = d["o"].values.astype(float), d["h"].values.astype(float), d["l"].values.astype(float), d["c"].values.astype(float)
    lo, hi = float(np.nanmin(l_)), float(np.nanmax(h_))
    lines = [(lab, float(px), col) for lab, px, col in lines if not isnan(px) and lo * 0.85 <= px <= hi * 1.15]
    for _lab, px, _col in lines:
        lo, hi = min(lo, px), max(hi, px)
    span = (hi - lo) or max(hi * 0.01, 0.01)
    lo, hi = lo - span * 0.04, hi + span * 0.04
    Y = lambda p_: padt + (hi - p_) / (hi - lo) * ph
    X = lambda i: padl + (i + 0.5) * step
    y0 = h - padb
    vv = np.nan_to_num(d["v"].values.astype(float))
    vmax = max(float(np.percentile(vv, 98)) * 1.25 if n >= 10 else float(vv.max()), 1.0)
    up_w, dn_w, up_b, dn_b, vu, vd = [], [], [], [], [], []
    for i in range(n):
        x = X(i)
        yo, yc = Y(o_[i]), Y(c_v[i])
        wick = f"M{x:.1f},{Y(h_[i]):.1f}V{Y(l_[i]):.1f}"
        body = f"M{x - bw / 2:.1f},{min(yo, yc):.1f}h{bw:.1f}v{max(abs(yo - yc), 0.7):.1f}h{-bw:.1f}z"
        bh = min(vv[i] / vmax, 1.0) * vh
        vbar = f"M{x - bw / 2:.1f},{y0:.1f}v{-bh:.1f}h{bw:.1f}v{bh:.1f}z" if bh > 0 else ""
        if c_v[i] >= o_[i]:
            up_w.append(wick); up_b.append(body); vu.append(vbar)
        else:
            dn_w.append(wick); dn_b.append(body); vd.append(vbar)
    def path_of(vals, fy):
        seg, out = [], []
        for i, v in enumerate(vals):
            if isnan(v):
                if len(seg) > 1:
                    out.append("M" + "L".join(seg))
                seg = []
            else:
                seg.append(f"{X(i):.1f},{fy(float(v)):.1f}")
        if len(seg) > 1:
            out.append("M" + "L".join(seg))
        return "".join(out)
    P = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" role="img" aria-label="{esc(t)} 日線圖" '
         f'style="width:100%;height:auto;display:block;background:#fff;border:1px solid #e6e6e6;border-radius:8px">',
         f'<defs><clipPath id="{uid}"><rect x="{padl}" y="{padt}" width="{pw:.1f}" height="{ph:.1f}"/></clipPath></defs>']
    if not compact:
        prev_m = None
        for i, dt in enumerate(d.index):
            if prev_m is not None and dt.month != prev_m:
                x = X(i) - step / 2
                P.append(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{padt}" y2="{y0:.1f}" stroke="#f1f1f1"/>'
                         f'<text x="{x + 2:.1f}" y="{h - 3}" font-size="10" fill="#888">{dt.month}月</text>')
            prev_m = dt.month
        P.append(f'<text x="6" y="13" font-size="11.5" font-weight="700" fill="#333">{esc(t)}　日線（{n} 日）</text>'
                 f'<text x="{padl + pw - 150:.1f}" y="13" font-size="10.5" fill="#2b6cb0">21EMA</text>'
                 f'<text x="{padl + pw - 106:.1f}" y="13" font-size="10.5" fill="#dd6b20">50 日線</text>'
                 f'<text x="{padl + pw - 54:.1f}" y="13" font-size="10.5" fill="#8a94a6">200 日線</text>')
    G = [f'<g clip-path="url(#{uid})">']
    for col, key, wd in (("#a0aec0", "s200", 1.1), ("#dd6b20", "s50", 1.1), ("#2b6cb0", "e21", 1.0)):
        pth = path_of(d[key].values, Y)
        if pth:
            G.append(f'<path d="{pth}" fill="none" stroke="{col}" stroke-width="{wd}"/>')
    G.append('<path d="' + "".join(up_w) + '" stroke="#0a7d33" stroke-width="0.8" fill="none"/>')
    G.append('<path d="' + "".join(dn_w) + '" stroke="#c0392b" stroke-width="0.8" fill="none"/>')
    G.append('<path d="' + "".join(up_b) + '" fill="#0a7d33"/>')
    G.append('<path d="' + "".join(dn_b) + '" fill="#c0392b"/>')
    labs = []
    for lab, px, col in lines:
        y = Y(px)
        G.append(f'<line x1="{padl}" x2="{padl + pw:.1f}" y1="{y:.1f}" y2="{y:.1f}" stroke="{col}" stroke-width="1" stroke-dasharray="5 3"/>')
        labs.append([y, f"{lab} {px:,.2f}", col])
    G.append("</g>")
    P.append("".join(G))
    P.append(f'<line x1="{padl}" x2="{padl + pw:.1f}" y1="{y0 - vh - 2:.1f}" y2="{y0 - vh - 2:.1f}" stroke="#eee"/>')
    P.append('<path d="' + "".join(vu) + '" fill="#0a7d33" fill-opacity="0.45"/>')
    P.append('<path d="' + "".join(vd) + '" fill="#c0392b" fill-opacity="0.45"/>')
    v50 = path_of(d["v50"].values, lambda v: y0 - min(v / vmax, 1.0) * vh)
    if v50:
        P.append(f'<path d="{v50}" fill="none" stroke="#666" stroke-width="0.8"/>')
    if not compact:
        labs.append([Y(c_v[-1]), f"收市 {c_v[-1]:,.2f}", "#1a1a1a"])
        labs.sort(key=lambda z: z[0])
        for i in range(1, len(labs)):
            if labs[i][0] - labs[i - 1][0] < 12:
                labs[i][0] = labs[i - 1][0] + 12
        for y, txt, col in labs:
            y = min(max(y, padt + 6), y0 - 2)
            P.append(f'<text x="{padl + pw + 4:.1f}" y="{y + 3:.1f}" font-size="10.5" fill="{col}">{esc(txt)}</text>')
    P.append("</svg>")
    return "".join(P)

def t6_lines(c):
    """計劃卡縮圖上的三條線：觸發價、止蝕、2R。"""
    sgn = 1 if c["Side"] == "多" else -1
    rps = abs(c["Entry"] - c["Stop"])
    return [("觸發位", c["Trigger"], "#1a56db"), ("失效位", c["Stop"], "#c0392b"), ("2R", c["Entry"] + sgn * 2 * rps, "#6b7280")]

def t6_chips(c, cks):
    out = []
    for k in cks:
        v = c["Ck"].get(k)
        out.append(f'<span class="chip {"ok" if v is True else "no" if v is False else "na"}">{"✓" if v is True else "✗" if v is False else "–"} {esc(k)}</span>')
    return "".join(out)

def t6_sec(c):
    if not c["SecETF"]:
        return "—"
    return SECTOR_ETFS.get(c["SecETF"], c["SecETF"]) + ("" if isnan(c["SecRank"]) else f"（第 {c['SecRank']:.0f}）")

def t6_size_attrs(c, limit=None, shares=None):
    """倉位試算用的屬性：網頁上的試算工具按讀者輸入的戶口和風險 % 重算股數、金額和最大損失。"""
    is_long = c["Side"] == "多"
    base_r = ACCOUNT_EQUITY * BASE_RISK_PCT / 100
    mult = (LONG_RISK if is_long else ACCOUNT_EQUITY * BASE_RISK_PCT / 100 * TH["risk_mult"]["short"]) / base_r if base_r else 0.0
    a = (f' data-ticker="{esc(c["Ticker"])}" data-direction="{"long" if is_long else "short"}" data-entry="{c["Entry"]:.4f}"'
         f' data-stop="{c["Stop"]:.4f}" data-risk-mult="{mult:.6f}" data-atr="{t6_f(c.get("ATR%")) * c["Close"] / 100:.4f}"')
    if limit is not None:
        a += f' data-limit="{limit:.4f}"'
    if is_long and T6_BUD.get("expo_left") is not None:
        a += f' data-cap-pct="{T6_BUD["expo_left"]:.4f}"'
    return a

def t6_table(cands, cks, reason=False, tier=False):
    """分級表：每隻一行，八項清單用 ✓／✗／– 顯示。B 級的表不列止蝕和股數（在縮圖和 CSV 內）。"""
    if not cands:
        return '<div class="note">沒有。</div>'
    th = ("<th>代號</th><th>形態</th>" + ("<th>級別</th>" if tier else "") + ("<th>尚欠甚麼</th>" if reason else "") + '<th class="num">清單</th>'
          + "".join(f'<th class="ck">{esc(k)}</th>' for k in cks)
          + '<th class="num">收市</th><th class="num">技術觸發位</th><th class="num">現價距觸發</th>'
          + ("" if reason else '<th class="num">形態失效位</th><th class="num">風險</th><th class="num">試算股數</th>')
          + '<th class="num">RS</th><th>板塊</th><th>財報日</th>')
    body = []
    for c in cands:
        known = sum(1 for k in cks if c["Ck"].get(k) is not None)
        marks = "".join('<td class="ck g">✓</td>' if c["Ck"].get(k) is True else '<td class="ck r">✗</td>' if c["Ck"].get(k) is False
                        else '<td class="ck m">–</td>' for k in cks)
        body.append(f'<tr{"" if reason else t6_size_attrs(c)}><td><b>{esc(c["Ticker"])}</b></td><td>{esc(c["Setup"])}</td>'
                    + (f'<td>{esc(c["Tier"])}</td>' if tier else "")
                    + (f'<td class="wrap">{esc(c["Reason"] or "沒有")}</td>' if reason else "")
                    + f'<td class="num"><b>{c["NPass"]}/{known}</b></td>' + marks
                    + cell(c["Close"], "p") + cell(c["Trigger"], "p") + cell(c["Dist%"], "pct")
                    + ("" if reason else cell(c["Stop"], "p") + cell(c["Risk%"], "pctn") + f'<td class="num" data-f="shares">{c["Shares"]:,}</td>') + cell(c["RS"], "rs")
                    + f'<td>{esc(t6_sec(c))}</td><td>{esc(c["Earn"])}</td></tr>')
    return f'<div class="tw"><table><thead><tr>{th}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'

def t6_quote(c):
    """最新的盤前／盤後報價，和它現在屬於開市三種情況的哪一種。"""
    if c["Ticker"] not in PM:
        return ""
    px, ts = PM[c["Ticker"]]
    chg = (px / c["Close"] - 1) * 100
    if c["Side"] == "多":
        ref = c["Pivot"] if c["Through"] else c["Trigger"]
        k = 1 if px > c["Chase"] else 2 if px >= ref else 3
        dead = px <= c["Stop"]
    else:
        k = 1 if px < c["Chase"] else 2 if px <= c["Trigger"] else 3
        dead = px >= c["Stop"]
    chg_txt = "與上日收市相同" if abs(chg) < 0.05 else f"較上日收市 {chg:+.1f}%"
    return (f"最新報價 {px:,.2f}（{ts:%m-%d %H:%M} ET，{chg_txt}）："
            + ("已到形態失效位，形態作廢。" if dead else f"現在屬於情景 {k}。"))

def t6_card(c):
    """一隻首選股票的計劃卡：縮圖、原因、價位、股數、目標、開市三種情況、事件、放棄條件。"""
    is_long = c["Side"] == "多"
    gate = long_ok if is_long else T6_SGATE
    cks = T6_CK_L if is_long else T6_CK_S
    t, trig, stop, entry, chase, pivot = c["Ticker"], c["Trigger"], c["Stop"], c["Entry"], c["Chase"], c["Pivot"]
    rps = abs(entry - stop)
    sgn = 1 if is_long else -1
    t2, t3 = entry + sgn * 2 * rps, entry + sgn * 3 * rps
    known = sum(1 for k in cks if c["Ck"].get(k) is not None)
    name = str(NAME_OF.get(t, "") or "")[:34]
    H_ = [f'<div class="card"{t6_size_attrs(c)}><h4>{esc(t)}<small>{esc(name)}</small></h4>'
          f'<span class="chip t">{esc(T6_LAB_L if is_long else T6_LAB_S)}</span><span class="chip">{esc(c["Setup"])}</span>'
          f'<span class="chip">清單 {c["NPass"]}/{known}</span><span class="chip">{esc(t6_sec(c))}</span>']
    H_.append(t6_chart(t, t6_lines(c), days=PLAN["chart_days"]))
    H_.append(f'<div class="why"><b>入選原因：</b>{esc(c["Why"])}</div><div>{t6_chips(c, cks)}</div>')
    rows = []
    if is_long:
        state = (f"已升穿 pivot {pivot:,.2f}，現價高出 {c['Dist%']:.1f}%；規則買入區上限 {chase:,.2f}" if c["Through"]
                 else f"待升穿：上日收市 {c['Close']:,.2f}，距技術觸發位 {c['Dist%']:+.1f}%")
        rows.append(("狀態", state + ("" if gate else "。閘門未開：只列作觀察")))
        rows.append(("技術觸發位（Pivot）", f"{trig:,.2f}（pivot {pivot:,.2f} 之上 0.1%）"))
        rows.append(("規則追價上限", f"{chase:,.2f}（pivot 之上 {TH['extended_pct']:g}%），高於此價規則上不追"))
    else:
        rows.append(("狀態", f"待跌穿：上日收市 {c['Close']:,.2f}，高於技術觸發位 {c['Dist%']:.1f}%" + ("" if gate else "。空頭閘門未開：只列作觀察")))
        rows.append(("技術觸發位（Pivot）", f"{trig:,.2f}（3 日低位 {pivot:,.2f} 之下 0.1%）"))
        rows.append(("規則追空下限", f"{chase:,.2f}（觸發位之下 {PLAN['near_trigger']:g}%），低於此價規則上不追"))
    rows.append(("形態失效位", f"{stop:,.2f}（{c['StopSrc']}），距入場價 {c['Risk%']:.1f}%"))
    size = (f'<span data-f="shares">{c["Shares"]:,}</span> 股，約 $<span data-f="notional">{c["Shares"] * entry:,.0f}</span>'
            f'（戶口 <span data-f="pct">{c["Pos%"]:.1f}</span>%）；到形態失效位約損失 $<span data-f="loss">{c["Shares"] * rps:,.0f}</span>')
    if not gate:
        size += "。按" + ("試單" if is_long else "空頭") + "注碼試算"
    rows.append(("試算注碼", Raw(size + ("。" + esc(c["ShCap"]) if c["ShCap"] else ""))))
    if is_long:
        rows.append(("模型 2R 參考位", f"每股風險 {entry:,.2f} − {stop:,.2f} = {rps:,.2f}；2R = {entry:,.2f} + 2 × {rps:,.2f} = {t2:,.2f}；3R = {t3:,.2f}"))
    else:
        rows.append(("模型 2R 參考位", f"每股風險 {stop:,.2f} − {entry:,.2f} = {rps:,.2f}；2R = {entry:,.2f} − 2 × {rps:,.2f} = {t2:,.2f}；3R = {t3:,.2f}"))
    ev = [f"財報日 {c['Earn']}"]
    if c["Imp"] is not None:
        ev.append(f"期權引伸波幅 ±{t6_f(c['Imp'].get('Move%')):.1f}%（{c['Imp'].get('Exp')} 到期）")
    if not isnan(c["DTC"]):
        ev.append(f"沽空回補日數 {c['DTC']:.1f}" + ("，突破時有回補買盤" if (is_long and c["DTC"] >= PLAN["dtc_squeeze"]) else ""))
    if not isnan(c["ATR%"]):
        ev.append(f"ATR {c['ATR%']:.1f}%" + ("（失效位距離不足一個 ATR）" if c["Risk%"] < c["ATR%"] else ""))
    rows.append(("事件與波幅", "；".join(ev)))
    for o_t, v in c["Corr"][:2]:
        rows.append(("分散", f"與 {o_t} 的相關係數 {v:.2f}：規則視兩者為同一風險單位"))
    H_.append("<table><tbody>" + "".join(f"<tr><td>{esc(k)}</td><td>{v if isinstance(v, Raw) else esc(v)}</td></tr>" for k, v in rows) + "</tbody></table>")
    if is_long and c["Through"]:
        sc = [f"開市價高於 {chase:,.2f}：高於規則追價上限；回到買入區並企穩前不符合條件。",
              f"開在 {pivot:,.2f} 至 {chase:,.2f} 之間：仍在買入區；規則要求首 30 分鐘不跌回 {pivot:,.2f} 之下。",
              f"開在 {pivot:,.2f} 之下：突破未企穩；規則要求收市重上 {pivot:,.2f}。"]
    elif is_long:
        sc = [f"開市價高於 {chase:,.2f}：高於規則追價上限；回到 {trig:,.2f} 至 {chase:,.2f} 之間並企穩前不符合條件。",
              f"開在 {trig:,.2f} 至 {chase:,.2f} 之間（跳空升穿）：規則要求首 30 分鐘企在 {trig:,.2f} 之上，而且成交明顯放大。",
              f"開在 {trig:,.2f} 之下：規則要求升穿 {trig:,.2f} 而且成交高於平日；未升穿則不觸發。"]
    else:
        sc = [f"開市價低於 {chase:,.2f}：低於規則追空下限；反彈前不符合條件。",
              f"開在 {chase:,.2f} 至 {trig:,.2f} 之間（跳空跌穿）：規則要求首 30 分鐘反彈不過 {trig:,.2f}。",
              f"開在 {trig:,.2f} 之上：規則要求跌穿 {trig:,.2f}；未跌穿則不觸發。"]
    qt = t6_quote(c)
    H_.append("<b>開市情景（規則描述）</b><ol>" + "".join(f"<li>{esc(x)}</li>" for x in sc) + "</ol>"
              + (f'<div class="note">{esc(qt)}</div>' if qt else ""))
    if is_long:
        ab = [f"收市跌穿 {stop:,.2f}。"]
        if c["Main"] in ("VCP", "收窄", "HTF"):
            ab.append("觸發之前出現放量下跌、波幅重新擴大：形態作廢。")
        if c["Main"] == "回調":
            ab.append("收市跌穿所回調的均線。")
        ab.append(f"仍未觸發而財報日已進入 {PLAN['earn_days']} 個交易日內。")
        ab.append("觸發後 3 日內收市跌回 pivot 之下而且放量：規則視為突破失敗。")
        ab.append("多頭與試單閘門關閉。")
    else:
        ab = [f"收市升穿 {stop:,.2f}。", "收市重上 50 日線。", "空頭閘門關閉，或超賣閘門觸發。",
              f"回補日數升到 {PLAN['dtc_squeeze']:g} 日以上，或 {PLAN['earn_days']} 個交易日內有財報。"]
    H_.append("<b>形態失效條件</b><ul>" + "".join(f"<li>{esc(x)}</li>" for x in ab) + "</ul></div>")
    return "".join(H_)

def t6_thumb(c):
    return (f'<div class="thumb"><b>{esc(c["Ticker"])}</b> <span class="m">{esc(c["Setup"])}</span>'
            + t6_chart(c["Ticker"], t6_lines(c)[:2], w=250, h=120, days=PLAN["thumb_days"], compact=True)
            + f'<small>觸發 {c["Trigger"]:,.2f}（{c["Dist%"]:+.1f}%）・止蝕 {c["Stop"]:,.2f}</small>'
            + f'<small>尚欠：{esc(c["Reason"])}</small></div>')

def t6_followup_html():
    """之前名單的跟進和成績表。"""
    fu = T6_FU
    if not fu["prev"]:
        return f'<h3>之前名單的跟進</h3><div class="note">{esc(fu["note"] or "未有紀錄。")}</div>'
    P = []
    if fu["rows"]:
        body = "".join(f'<tr><td><b>{esc(e["ticker"])}</b></td><td>{esc(t6_side(e["side"], e["tier"]))}</td><td>{esc(e["asof"][5:])}</td>'
                       f'<td>{esc(e["setup"])}</td>' + cell(e["trigger"], "p") + cell(e["stop"], "p") + f'<td>{esc(e["st"])}</td>'
                       + ('<td class="num m">—</td>' if isnan(e["R"]) else f'<td class="num {"g" if e["R"] >= 0.05 else "r" if e["R"] <= -0.05 else "m"}"><b>{t6_r(e["R"])}</b></td>') + "</tr>"
                       for e in fu["rows"][:40])
        P.append('<div class="tw"><table><thead><tr><th>代號</th><th>方向與級別</th><th>首次列出</th><th>形態</th><th class="num">觸發價</th>'
                 f'<th class="num">止蝕</th><th>其後的結果</th><th class="num">現時結果</th></tr></thead><tbody>{body}</tbody></table></div>')
    else:
        P.append('<div class="note">最近幾個名單日沒有首選股票。</div>')
    if fu["score"]:
        srow = "".join(f'<tr><td>{esc(s["Grp"])}</td>' + cell(s["N"], "i") + cell(s["Trig"], "i") + cell(s["Trig%"], "pct0") + cell(s["Stopped"], "i")
                       + cell(s["Win%"], "pct0") + ('<td class="num m">—</td>' if isnan(s["AvgR"]) else f'<td class="num"><b>{s["AvgR"]:+.2f}R</b></td>') + "</tr>"
                       for s in fu["score"])
        P.append(f'<h3>成績表（共 {fu["n_days"]} 個名單日，規則版本 {esc(T6_RULES)}）</h3><div class="tw"><table><thead><tr><th>組別</th><th class="num">計劃數</th>'
                 '<th class="num">已觸發</th><th class="num">觸發比率</th><th class="num">其中止蝕</th><th class="num">現時為正</th><th class="num">平均結果</th>'
                 f"</tr></thead><tbody>{srow}</tbody></table></div>")
    P.append('<div class="note">做法：每個計劃只看列出之後的日線；同一隻股票連續幾日在同一級別只計一次，用第一日的觸發價和止蝕。'
             "假設在觸發價成交、在止蝕價離場，不計佣金、滑價和跳空，同日先後打到觸發價和止蝕的當作止蝕，所以數字偏樂觀。"
             "「預備」是閘門未開時列出的，實際上不會落盤，它的結果是用來檢查閘門有沒有幫你避開虧損。"
             "「全部候選」是對照組：首選的結果如果不比它好，分級就沒有用處。已觸發的計劃少於 30 個之前，這張表只是紀錄，不能當作證據。"
             + (f"另有 {fu['old_rules']} 筆舊規則版本的紀錄沒有計入。" if fu["old_rules"] else "") + "</div>")
    n_tr = sum(1 for e in fu["rows"] if e["trig"])
    n_st = sum(1 for e in fu["rows"] if e["R"] == -1.0)
    return (f'<details><summary style="font-size:13px;font-weight:600">之前名單的跟進與成績表（最近 {PLAN["follow_days"]} 個名單日的首選：'
            f'{len(fu["rows"])} 個計劃，已觸發 {n_tr}，其中止蝕 {n_st}）</summary>' + "".join(P) + "</details>")

def t6_history_html():
    """近 10 日回顧：每日一行，新到舊；摘要列出分數和 Regime 的走勢。表格收窄到手機可以一屏看完。"""
    if not T6_HIST:
        return ""
    old_first = T6_HIST[::-1]
    trend = " → ".join(fnum(r["score"], 0) for r in old_first[-6:])
    regs = " → ".join(r["regime"] or "—" for r in old_first[-6:])
    W = "white-space:normal;min-width:{}px"
    SM = '<div style="color:#888;font-size:11px;white-space:normal">{}</div>'
    body = []
    for r in T6_HIST:
        now_ = r["src"] == "now"
        day = f"{r['bd']:%m-%d}（{WD_ZH[r['bd'].weekday()]}）"
        hue = REG_HUE.get(r["regime"], "#999")
        sc = f'<td class="num">{fnum(r["score"], 0)} <b style="color:{hue}">{esc(r["regime"] or "—")}</b></td>'
        if r["src"] == "calc":
            body.append(f'<tr class="m"><td>{esc(day)}</td>' + sc
                        + f'<td colspan="2" style="{W.format(150)}">沒有執行紀錄；分數按今日的數據回算</td></tr>')
            continue
        run = ("今次 " if now_ else "") + "更新 " + str(r["run"])[5:16]
        names = esc("、".join(r["top"]) or "沒有")
        if r["new"] is None:
            chg = ""
        else:
            chg = " ".join([f'<span class="g">+{esc(t)}</span>' for t in r["new"]] + [f'<span class="r">−{esc(t)}</span>' for t in r["gone"]]) or '<span class="m">和上次相同</span>'
            chg = f'<div style="font-size:11px;white-space:normal">{chg}</div>'
        bold = ' style="font-weight:600"' if now_ else ""
        body.append(f'<tr{bold}><td>{esc(day)}{SM.format(esc(run))}</td>' + sc
                    + f'<td style="{W.format(80)}">{esc(r["gates"])}{SM.format(esc(r["cycle"])) if r["cycle"] else ""}</td>'
                    + f'<td style="{W.format(100)}"><span class="m">{esc(r["label"])}</span> {names}{chg}</td></tr>')
    where = "每日的完整簡報都保留在網站首頁的「之前的簡報」。"
    return (f'<details><summary style="font-size:13px;font-weight:600">近 10 日回顧（分數 {esc(trend)}；Regime {esc(regs)}）</summary>'
            '<div class="tw"><table><thead><tr><th>簡報日</th><th class="num">分數</th><th>閘門／週期</th>'
            '<th>首選／變化</th></tr></thead><tbody>' + "".join(body) + "</tbody></table></div>"
            '<div class="note">每行取自當日最後一次執行時存下的紀錄。分數旁的字母是 Regime；閘門指多頭、試單、空頭三個閘門哪幾個開著。首選下面的小字和上一次有分級紀錄的簡報比較：綠色「+」是新入選，紅色「−」是跌出'
            "（v6.1 起才有分級紀錄，之前的日子只有焦點名單，不作比較）。沒有執行紀錄的日子，用今日的數據按同一套規則回算分數，"
            "數字可能和當日看到的略有不同。" + esc(where) + "</div></details>")

def t6_timeline_html():
    """今晚時間表：香港時間、美東時間、事項。"""
    if not T6_TL:
        return ""
    o_h = next((x["et"] for x in T6_TL if x["what"] == "美股開市"), T6_TL[0]["et"]).tz_convert(HKT).normalize()
    rows = []
    for x in T6_TL:
        h = x["et"].tz_convert(HKT)
        nxt = '<span class="m">（翌日）</span>' if h.normalize() > o_h else ""
        st = ' style="font-weight:600"' if x["kind"] in ("系統", "市場") else ""
        rows.append(f'<tr{st}><td>{h:%H:%M}{nxt}</td><td class="m">{x["et"]:%H:%M}</td><td style="white-space:normal">{esc(x["what"])}</td></tr>')
    return ('<h3>今晚時間表（香港時間）</h3><div class="tw"><table><thead><tr><th>香港</th><th>美東</th><th>事項</th></tr></thead><tbody>'
            + "".join(rows) + '</tbody></table></div><div class="note">經濟數據只列重點項目；財報列出名單、持倉和當日成交金額最大的 3 隻。'
            "開市前公佈的財報按美東 09:00 排列，實際時間以公司公佈為準。</div>")

def t6_pos_html():
    """首頁的持倉表：先處理持倉，再看新倉。每隻兩行：價位一行，要處理的事項一行（手機上不用左右捲動）。"""
    if not len(POS_TBL):
        return ""
    SM = '<div class="s">{}</div>'
    rows = []
    for r in POS_TBL.to_dict("records"):
        if isnan(r.get("Px")):
            rows.append(f'<tr><td><b>{esc(r["Ticker"])}</b></td><td colspan="2" class="m w">無數據（不在股票池，或代號有誤）</td></tr>')
            continue
        pnl = "" if isnan(r.get("PnL%")) else f'<span class="{"g" if r["PnL%"] > 0 else "r"}">{r["PnL%"]:+.1f}%</span>'
        rr = "" if isnan(r.get("R")) else f'{round(r["R"], 1) + 0.0:+.1f}R'
        dd = "" if isnan(r.get("Days")) else f'持有 {r["Days"]:.0f} 日'
        act = r.get("Act") or ""
        rest = [x for x in str(r.get("Note", "")).split("；") if x and x != "—" and x not in act.split("；")]
        todo = (f'<b class="r">{esc(act)}</b>' if act else '<span class="g">暫時不用處理</span>') + (SM.format(esc("；".join(rest))) if rest else "")
        rows.append(f'<tr style="border-top:1px solid #ddd"><td style="border-bottom:0"><b>{esc(r["Ticker"])}</b>{SM.format(esc("　".join(x for x in (rr, dd) if x)))}</td>'
                    f'<td class="num" style="border-bottom:0">{r["Px"]:,.2f}<div style="font-size:11px">{pnl}</div></td>'
                    f'<td class="num" style="border-bottom:0">{r["Stop"]:,.2f}{SM.format(format(r["ToStop%"], "+.1f") + "%")}</td></tr>'
                    f'<tr><td colspan="3" class="w" style="padding-top:0">{todo}</td></tr>')
    return ('<h3>持倉：先處理，再開新倉</h3><div class="tw"><table class="cmp"><thead><tr><th>代號</th><th class="num">現價／盈虧</th>'
            '<th class="num">止蝕／距離</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table></div>"
            '<div class="note">現價用最新的盤後或盤前報價，沒有就用上日收市。R 倍數以現時止蝕計；持有日數需要入場日資料。'
            "紅字按 POS_RULES 的經驗值標示（見頁底「方法論與局限性」），是規則提示，不是指令。</div>")

def t6_orders_html():
    """富途下單清單：精簡表加可以照抄的文字。"""
    if not T6_ORD:
        return ""
    nl, ns = T6_BUD.get("n_long", 0), T6_BUD.get("n_short", 0)
    SM = '<div class="s">{}</div>'
    rows = []
    for o in T6_ORD:
        lg = o["Side"] == "買入"
        tag = ("上限內" if o["InSlot"] else "後備") + ("" if (long_ok if lg else T6_SGATE) else "・閘門未開")
        typ = "開市後限價單" if o["Mode"] == "開市後" else ("買入" if lg else "沽空") + "止損限價單"
        if o["Mode"] == "開市後":
            px1, px2 = f'{o["Pivot"]:,.2f}', f'pivot<br>上限 {o["Limit"]:,.2f}'
        else:
            px1, px2 = f'{o["Trigger"]:,.2f}', f'限價 {o["Limit"]:,.2f}'
        cls = "" if o["InSlot"] else ' class="m"'
        c_ = next((c for c in T6_LA + T6_SA if c["Ticker"] == o["Ticker"]), None)
        attrs = t6_size_attrs(c_, limit=o["Limit"]) if c_ else ""
        rows.append(f'<tr{cls}{attrs}><td><b>{esc(o["Ticker"])}</b>{SM.format(esc(typ))}{SM.format(esc(tag))}</td>'
                    f'<td class="num">{px1}{SM.format(px2)}</td>'
                    f'<td class="num"><span data-f="shares">{o["Shares"]:,}</span> 股{SM.format("失效位 " + format(o["Stop"], ",.2f"))}'
                    f'<div class="s">最大損失 $<span data-f="loss">{o["Risk"]:,.0f}</span></div></td></tr>')
    head = (f"規則示範上限：多頭 {nl} 單位" + (f"、空頭 {ns} 單位" if ns else "") + "；上限內按排序計，排前的失效才輪到後備。"
            "系統開市前更新（盤前價格重算）會按盤前價重新判斷每組參數。數量按頁頂設定的戶口和風險 % 試算。")
    def order_div(o):
        c_ = next((c for c in T6_LA + T6_SA if c["Ticker"] == o["Ticker"]), None)
        attrs = t6_size_attrs(c_, limit=o["Limit"]) if c_ else ""
        return (f'<div style="margin:3px 0" data-order{attrs} data-mode="{"open" if o["Mode"] == "開市後" else "stop"}" '
                f'data-trigger="{o["Trigger"]:.2f}" data-pivot="{o["Pivot"]:.2f}" data-sym="{esc(o["Ticker"])}">{esc(t6_order_line(o))}</div>')
    lines = "".join(order_div(o) for o in T6_ORD if o["InSlot"])
    return ('<h3>倉位與委託參數試算（按自訂戶口試算）</h3>'
            + ('' if long_ok else '<div class="note">多頭閘門未開：做多參數只作試算，規則上不適用。</div>')
            + f'<div class="note">{esc(head)}</div>'
            '<div class="tw"><table class="cmp"><thead><tr><th>代號</th><th class="num">觸發位</th><th class="num">試算數量</th>'
            '</tr></thead><tbody>' + "".join(rows) + "</tbody></table></div>"
            + (f'<details><summary style="font-size:13px;font-weight:600">模擬參數摘要（僅供參考，非交易指令）</summary>'
               f'<div style="font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12px">{lines}</div></details>' if lines else "")
            + '<details><summary style="font-size:13px;font-weight:600">單種和數量的說明</summary><div class="note">'
            "止損限價單：股價升到觸發價就以限價送出買單；開市價已高過限價就不會成交，等於不追。限價 = 觸發價 + "
            f"{PLAN['limit_atr']:g} 個 ATR，不超過追價上限。數量按限價（最差成交價）計，所以可能比參數卡少，每單位最大損失不變；"
            "跳空穿過失效位時實際損失會更大。部分券商的買入止損單要求觸發價高於現價：盤前價已越過觸發價時，預設參數不再適用；"
            "這種情況和已升穿 pivot 的形態都改為開市後判定。附加的止損單是止損市價單，只在常規時段觸發；"
            "部分券商介面在這種單沒有「附加訂單」，需要在成交後另設一張賣出止損單。沽空要融資戶口，並確認有貨可借。</div></details>")

BACKTEST_NOTE = ("做多規則（收窄與新高突破，配合多頭及試單閘門）以 2016–2022 年的歷史數據作樣本內回測："
                 "股票池是當時的 S&P 500 與 Nasdaq 100 成份股，每次成交計 25 bps 成本（佣金 10 bps、滑價 15 bps），出場規則按參數卡的假設。"
                 "結果：扣成本後 Sharpe −0.73，最大回撤 −41.5%，共 923 次交易，未通過四關驗證的第一關。"
                 "這是初步結果：未包括 S&P 400，部分已除牌公司缺少價格；完整重測進行中。做空規則未有回測。歷史回測不代表將來表現。")
DATA_NOTE = ["數據來自公開市場及交易所的延遲數據，可能延誤、缺漏或出錯；頁頂的「數據狀態」列出今次發現的問題。",
             "財報日取自公開來源，可能不完整；盤前價只作參考。",
             "成份股名單用當日的指數成份，過往日子的分數按今日的數據回算，可能和當日看到的略有不同。",
             "倉位試算只按讀者在頁頂輸入的參數計算，未計稅費、借貨成本和跳空；結果是數學試算，不是建議的倉位。"]
DISCLOSURE = ("研究聲明：本報告的全部內容由固定規則自動計算，所有讀者看到的內容相同，並不考慮任何人的財務狀況、投資目標或風險承受能力。"
              "頁內的倉位試算只按讀者自行輸入的參數計算。內容只供研究和教育用途，不構成投資建議、要約或招攬，亦不保證準確、完整或及時。"
              "過往表現（包括回測和跟進紀錄）不代表將來表現。")

def method_html():
    """方法論與局限性：八項清單、回測結果、跟進紀錄的判定方法、數據限制。"""
    return ('<details class="method"><summary>方法論與局限性</summary>'
            + ("<h4>八項清單與分級</h4>" + "".join(f"<p>{esc(x)}</p>" for x in METHOD_CK) if METHOD_CK else "")
            + f"<h4>回測</h4><p>{esc(BACKTEST_NOTE)}</p>"
            + "<h4>數據與試算的局限</h4><ul>" + "".join(f"<li>{esc(x)}</li>" for x in DATA_NOTE) + "</ul></details>")

def t6_page_head():
    """首頁：今日可否交易、看哪幾隻、每隻怎樣做。"""
    b = T6_BUD
    P = [f'<div class="hero" style="border-left-color:{REG_COLOR[0]};background:{REG_COLOR[1]}">',
         f'<div class="big" style="color:{REG_COLOR[0]}">Regime {REG_L} {REG_T}　·　規則狀態：{esc(SIDE)}</div>',
         f'<div class="mid">市場健康分數 <b>{score_now:.0f}</b> {score_arrow}（昨日 {score_prev:.0f}，5 日前 {score_5:.0f}；已在 {REG_L} 區 {REG_DAYS} 日）'
         f'　|　市場週期：<b>{esc(CYCLE)}</b></div>',
         "<div>" + pill("多頭閘門 " + ("開" if LONG_GATE else "關"), "on" if LONG_GATE else "off")
         + pill("試單閘門 " + ("開" if PILOT_GATE else "關"), "on" if PILOT_GATE else "off")
         + pill("空頭閘門 " + ("開" if SHORT_GATE else "關"), "bad" if SHORT_GATE else "off")
         + pill("超賣 " + ("是" if OVERSOLD else "否"), "wrn" if OVERSOLD else "off")
         + (pill("空頭時機：" + SHORT_TIMING.split("：")[0], "wrn") if SHORT_SETUP else "")
         + (pill("事件日", "wrn") if EVENT_DAY else "") + "</div>"]
    # 一、今日可否交易
    if LONG_GATE:
        a1 = f"多頭閘門開：規則示範注碼為標準風險的 {RISK_MULT * 100:.0f}%。"
    elif PILOT_GATE:
        a1 = "只有試單閘門開：規則示範注碼為標準風險的 25%。"
    else:
        a1 = "多頭與試單閘門均關閉：做多形態只列作觀察。"
    if SHORT_GATE:
        a1 += {"阻力區": "空頭閘門開，QQQ 已反彈到下降中的 21EMA 附近：規則容許反彈失敗的弱股形態。",
               "中間位置": "空頭閘門開，但 QQQ 未反彈到阻力：規則只容許已反彈到自身均線的弱股。",
               "破位邊緣": "空頭閘門開，但 QQQ 在破位邊緣：規則不追空。"}.get(SHORT_TIMING.split("：")[0], f"空頭閘門開：{SHORT_TIMING}。")
    elif SHORT_SETUP and OVERSOLD:
        a1 += "空頭條件成立，但市場超賣：規則不開新空頭形態。"
    if EVENT_DAY:
        a1 += "今日是事件日：規則把公佈前的示範注碼減半。"
    P.append(f'<div class="q">一、模型市況框架</div><div class="ans"><b>{esc(T6_VERDICT)}</b>{esc(a1)}</div>')
    new_txt = f"多頭 {b['n_long']} 單位" + (f"・空頭 {b['n_short']} 單位" if SHORT_SETUP else "")
    base_r = ACCOUNT_EQUITY * BASE_RISK_PCT / 100
    m_l, m_s = (b["risk_l"] / base_r if base_r else 0.0), (b["risk_s"] / base_r if base_r else 0.0)
    risk_txt6 = (f'$<span data-risk="long" data-risk-mult="{m_l:.6f}">{b["risk_l"]:,.0f}</span>（戶口 <span data-riskpct="long" data-risk-mult="{m_l:.6f}">'
                 f'{b["risk_l"] / ACCOUNT_EQUITY * 100:.2f}</span>%）'
                 + (f'・做空 $<span data-risk="short" data-risk-mult="{m_s:.6f}">{b["risk_s"]:,.0f}</span>' if SHORT_SETUP else ""))
    P.append(f'<div id="sizer-meta" hidden data-equity0="{ACCOUNT_EQUITY:g}" data-risk0="{BASE_RISK_PCT:g}" data-mult-long="{m_l:.4f}" '
             f'data-mult-short="{m_s:.4f}" data-event="{int(bool(EVENT_DAY))}"></div>')
    P.append('<div class="kv">'
             f'<div><small>規則示範新倉上限</small><b>{esc(new_txt)}</b></div>'
             f'<div><small>示範每單位風險（做多）</small><b>{risk_txt6}</b></div>'
             f'<div><small>未平倉風險／上限（{esc(b["heat_src"])}）</small><b>{OPEN_RISK_PCT:.2f}% ／ {b["heat_cap"]:g}%</b></div>'
             f'<div><small>多倉市值／Regime {REG_L} 上限</small><b>{LONG_EXPO:.0f}% ／ {b["expo_cap"]:.0f}%</b></div>'
             f'<div><small>突破成功率（5–15 日前的突破）</small><b>{esc(bo_txt)}</b></div>'
             f'<div><small>股票高於 50 日線</small><b>{pct50_now:.0f}%</b></div></div>')
    P.append(f'<div class="note">多頭上限受限於：{esc(b["lim_l"])}' + (f'；空頭上限受限於：{esc(b["lim_s"])}' if SHORT_SETUP else "")
             + "。風險上限指所有示範持倉同時觸及形態失效位時的最大損失（佔戶口 %）。</div>")
    key = [x for x in PLAY if x.startswith(("做多", "做空", "日曆", "反彈嘗試", "開市", "持倉", "突破成功率", "Regime", "盤前參考價"))]
    rest = [x for x in PLAY if x not in key]
    P.append("<ul>" + "".join(f"<li>{esc(x)}</li>" for x in key) + "</ul>")
    if rest:
        P.append(f'<details><summary style="font-size:13px;font-weight:600">其餘提醒（{len(rest)} 項）</summary><ul>'
                 + "".join(f"<li>{esc(x)}</li>" for x in rest) + "</ul></details>")
    P.append(t6_timeline_html())
    P.append(t6_pos_html())
    if TRIG:
        def crossed(a, dist):                                # 盤前參考價已經越過這個位
            if isnan(dist) or (a == "↑" and dist > 0) or (a == "↓" and dist < 0):
                return ""
            return '<b class="r">（參考價已' + ("高" if a == "↑" else "低") + "於此位）</b>"
        rows = "".join(f'<tr><td class="{"g" if a == "↑" else "r"}"><b>{a}</b></td><td>{esc(what)}{crossed(a, dist)}</td>'
                       f'<td class="num">{"—" if isnan(dist) else f"{dist:+.1f}%"}</td><td>{esc(mean)}</td></tr>' for a, what, dist, mean in TRIG)
        P.append(f'<details{"" if long_ok else " open"}><summary style="font-size:13px;font-weight:600">甚麼會改變結論（QQQ 的 {len(TRIG)} 個觸發位）</summary>'
                 '<div class="tw"><table><thead><tr><th></th><th>觸發條件（QQQ）</th><th class="num">距參考價</th>'
                 f'<th>意義</th></tr></thead><tbody>{rows}</tbody></table></div></details>')
    P.append("</div>")
    P.append(t6_history_html())

    # 二、看哪幾隻
    n_w = sum(1 for c in T6_L if c["Tier"] == "觀察")
    n_d = sum(1 for c in T6_L if c["Tier"] == "剔除")
    rs_ = t6_reasons(T6_L)
    P.append(f'<div class="q">二、符合規則的技術形態<small>股票池 {len(TICKS)} 隻 → 做多候選 {len(T6_L)} 隻 → {esc(T6_TOP_L)} {len(T6_LA)}・B 級 {len(T6_LB)}・觀察 {n_w}・剔除 {n_d}</small></div>')
    if rs_:
        P.append('<div class="note">未入選的原因：' + "、".join(f"{esc(k)} {v} 隻" for k, v in rs_) + "。</div>")
    if DATA_HOLE:
        P.append(f'<div class="note">數據狀態：{len(DATA_HOLE)} 隻缺收市價，未計入掃描和分級（詳見頁頂）。</div>')
    fu = T6_FU
    if fu["prev"]:
        P.append(f'<div class="note"><b>與上一份名單（{esc(fu["prev"][5:])}）比較</b>：新入選 ' + (esc("、".join(fu["new"])) or "沒有")
                 + "；留在名單 " + (esc("、".join(fu["stay"])) or "沒有") + "；跌出 "
                 + ("；".join(f"<b>{esc(t)}</b>（{esc(why)}）" for t, why in fu["gone"]) or "沒有") + "。</div>")
    if not long_ok:
        P.append('<div class="note">多頭閘門未開，因此沒有 A 級。以下「預備」形態已符合其餘條件，只列作觀察；閘門狀態改變的條件見上面的觸發位。</div>')
    P.append(f"<h3>{esc(T6_LAB_L)}（最多 {PLAN['a_max']} 隻）</h3>" + t6_table(T6_LA, T6_CK_L))
    P.append(f"<h3>做多 B 級：接近成熟，只作觀察（最多 {PLAN['b_max']} 隻）</h3>" + t6_table(T6_LB, T6_CK_L, reason=True))
    if T6_WATCH or T6_WATCH_NA:
        P.append("<h3>自選名單體檢（額外加入的代號，用同一套清單檢查）</h3>" + t6_table(T6_WATCH, T6_CK_L, reason=True, tier=True)
                 + ('<div class="note">沒有數據：' + esc("、".join(T6_WATCH_NA)) + "。</div>" if T6_WATCH_NA else "")
                 + '<div class="note">「尚欠甚麼」是系統按規則列出的反對理由；級別是「自選」的，代表它不在任何掃描名單。</div>')
    if SHORT_SETUP:
        P.append(f"<h3>{esc(T6_LAB_S)}（回抽阻力名單，最多 {PLAN['s_a_max']} 隻；{esc(SHORT_TIMING.split('：')[0])}）</h3>" + t6_table(T6_SA, T6_CK_S))
        if T6_SB:
            P.append("<h3>做空 B 級</h3>" + t6_table(T6_SB, T6_CK_S, reason=True))
    if T6_DIV:
        P.append("<h3>分散檢查</h3><ul>" + "".join(f"<li>{esc(x)}</li>" for x in T6_DIV) + "</ul>")
    METHOD_CK.append('A 級條件：形態完成、現價在觸發價之下 ' + f"{PLAN['near_trigger']:g}% 以內（或已升穿但仍在買入區）、{PLAN['earn_days']} 個交易日內沒有財報、"
             f"形態低位距入場價不超過 {MAX_STOP_PCT:g}%、同板塊最多 {PLAN['per_sector']} 隻、閘門容許；另外要在 Stage 2，八項清單最多 {PLAN['max_fails']} 項不通過。"
             f"B 級是欠一至兩項而且距觸發價不超過 {PLAN['b_far']:g}% 的。排序按清單通過的項數、形態、RS。清單：趨勢 = Stage 2；RS ≥ " + f"{PLAN['rs_min']}；板塊 = 1 個月回報排前 {PLAN['sec_top']}；"
             f"收縮 = VCP，或 10 日波幅在半年內最窄的 {PLAN['tight_pct'] * 100:.0f}%；成交 = 未突破的看量縮（10 日均量低於 50 日均量的 {PLAN['vol_dry'] * 100:.0f}%），"
             f"剛突破的看突破日放量；資金 = U/D 量比 ≥ {PLAN['ud_min']:g}；「–」是沒有數據。門檻是經驗值；A 級是規則排序，不是買入訊號。")
    others = [c for c in T6_L if c["Tier"] in ("觀察", "剔除")]
    if others:
        orows = "".join(f'<tr><td><b>{esc(c["Ticker"])}</b></td><td>{esc(c["Setup"])}</td><td>{esc(c["Tier"])}</td><td class="wrap">{esc(c["Reason"])}</td>'
                        + cell(c["RS"], "rs") + cell(c["Dist%"], "pct") + "</tr>"
                        for c in sorted(others, key=lambda x: (x["Tier"] != "觀察", -x["NPass"], x["NFail"]))[:60])
        P.append(f'<details><summary style="font-size:13px;font-weight:600">其餘候選與未入選原因（{len(others)} 隻）</summary><div class="tw"><table><thead><tr>'
                 '<th>代號</th><th>形態</th><th>級別</th><th>原因</th><th class="num">RS</th><th class="num">現價距觸發</th></tr></thead>'
                 f"<tbody>{orows}</tbody></table></div>" + ('<div class="note">只顯示首 60 隻，完整名單在 scan_tiers_long 的 CSV。</div>' if len(others) > 60 else "") + "</details>")

    # 三、每隻怎樣做
    P.append('<div class="q">三、形態參數卡<small>每個首選形態一張卡；圖上藍線是技術觸發位（Pivot），紅線是形態失效位，灰線是模型 2R 參考位</small></div>')
    P.append(t6_orders_html())
    cards = [t6_card(c) for c in T6_LA] + [t6_card(c) for c in T6_SA]
    if cards:
        P.append('<div class="cards">' + "".join(cards) + "</div>")
    else:
        P.append('<div class="note">今日沒有符合規則的首選形態。</div>')
    if T6_LB:
        P.append(f"<h3>B 級縮圖總覽（{len(T6_LB)} 隻，近 {PLAN['thumb_days']} 日）</h3>" + '<div class="thumbs">' + "".join(t6_thumb(c) for c in T6_LB) + "</div>")
    P.append("<h3>提示價（可在 TradingView 逐個設定）</h3>" + render(ALERT_TBL, SPEC["alerts"], empty="沒有"))
    P.append(t6_followup_html())
    P.append(method_html())
    P.append('<div class="more">以下是資料章節，按需要展開。</div>')
    return "".join(P)

if V6_OK:
    try:
        T6_HEAD = T6_CSS + t6_page_head()
    except Exception as e:
        t6_fail("首頁與計劃卡", e)

def quality_badge(items):
    """數據狀態：沒有問題時是一個小標籤；有問題時是可展開的標籤，逐項列出。"""
    if not items:
        return '<div class="dq ok">數據狀態：正常</div>'
    return (f'<details class="dq"><summary>數據狀態：{len(items)} 項注意</summary><ul>'
            + "".join(f"<li>{esc(x)}</li>" for x in items) + "</ul></details>")
warn_html = quality_badge(quality + T6_ERR)
PAGE = (CSS + '<div class="pmb">'
        + f"<h1>盤前簡報　{SESS:%Y-%m-%d}</h1>"
        + f'<div class="sub">數據截至 {ASOF:%Y-%m-%d} 收市　·　執行時間 {RUN_TS:%m-%d %H:%M} ET　·　股票池 {len(TICKS)} 隻</div>'
        + warn_html + (T6_HEAD + overview.replace("<details open>", "<details>", 1) if V6_OK else "".join(hero) + focus_html + overview)
        + section("1　Nasdaq 技術面與市場健康", s1, not V6_OK)
        + section("2　隔夜與盤前", s2, not V6_OK)
        + section("3　消息面與事件", s7, not V6_OK, ("事件日　" if EVENT_DAY else "") + (f"{len(EARN_SOON)} 隻名單內股票 3 日內有財報" if EARN_SOON else ""))
        + (OBB_SECTION.replace("<details open>", "<details>", 1) if V6_OK else OBB_SECTION)
        + section("4　資金流向：板塊與行業組別", s3, not V6_OK, "、".join(TOP3) + " 領先" if TOP3 else "")
        + section("5　龍頭股", s4, False, f"{LEAD_PCT50.iloc[-1]:.0f}% 高於 50 日線")
        + section("6　做多形態", s5, long_ok and not V6_OK, f"VCP {len(VCP)}・HTF {int((HTF['Note'] == '').sum()) if len(HTF) else 0}・收窄 {len(TIGHT)}・突破 {len(BO52)}・抗跌 {len(RESIL)}・回調 {len(PULL)}")
        + section("7　做空形態與迴避名單", s6, SHORT_GATE and not V6_OK, f"回抽 {len(S_RETEST)}・跌破 {len(BD)}・墮落龍頭 {len(FALLEN)}")
        + (section("8　持倉檢查", s8, True) if len(POS_TBL) else "")
        + section("文字摘要（可複製）", f"<pre>{esc(BRIEF_TXT)}</pre>", False)
        + f'<div class="disc">{esc(DISCLOSURE)}</div>'
        + "</div>")

def news_text():
    L = [f"===== 消息面（文字版）{SESS:%Y-%m-%d} =====", "【昨日市場回顧】"] + ["  " + x for x in RECAP]
    if CAL_FLAGS:
        L += ["【日曆因素】"] + ["  " + x for x in CAL_FLAGS]
    L.append("【財報反應】")
    if len(EARN_REACT):
        for r in EARN_REACT.head(15).itertuples():
            sp = "盈利驚喜 —" if isnan(r.Surp) else f"盈利驚喜 {r.Surp:+.1f}%"
            mv = "股價 —" if isnan(r.Move) else f"股價 {r.Move:+.1f}%"
            L.append(f"  {r.Symbol:<6}{r.When}｜{sp}｜{mv}（{r.Src}）｜{r.Verdict}")
    else:
        L.append("  " + (EARN_NOTE or "這兩日沒有股票池內的公司公佈財報。"))
    L.append(f"【{SESS:%m-%d} 及下一個交易日的財報】")
    if len(EARN_NEXT):
        for r in EARN_NEXT.head(20).itertuples():
            L.append(f"  {r.Symbol:<6}{r.When}｜{str(r.Company)[:28]}" + ("｜在名單或持倉內" if getattr(r, "InList", False) else ""))
    else:
        L.append("  " + (EARN_NOTE or "沒有列出。"))
    L.append("【重點經濟數據（美東時間）】")
    if len(ECON):
        for r in ECON.head(15).itertuples():
            ex = "" if isnan(getattr(r, "Expected", np.nan)) else f"｜預期 {r.Expected}"
            la = "" if isnan(getattr(r, "Last", np.nan)) else f"｜前值 {r.Last}"
            L.append(f"  {r.Tier:<4}{getattr(r, 'When', '')}　{r.Event}{ex}{la}")
    else:
        L.append("  " + (ECON_NOTE or "未取"))
    L.append("【名單與持倉的財報風險（3 個交易日內）】")
    L += ["  " + "、".join(f"{t}（{nm}，{es}）" for t, nm, es in EARN_SOON)] if EARN_SOON else ["  沒有。"]
    if NEWS:
        L.append("【市場要聞（美東時間）】")
        L += [f"  {n['when'][5:]} [{n['t']}] {n['title']}" + (f"（{n['prov']}）" if n["prov"] else "") for n in NEWS]
    if AI_NEWS:
        L.append("【AI 消息面】")
        L += ["  " + x for x in (AI_TEXT or AI_NOTE or "沒有回應").splitlines() if x.strip()]
        if AI_SRC:
            L += ["  來源："] + [f"    {str(t_)[:60]}　{u}" for u, t_ in AI_SRC]
    return "\n".join(L)
NEWS_TXT = news_text()

try:
    from IPython.display import HTML, display
    display(HTML(PAGE))
except Exception:
    print(BRIEF_TXT)
if V6_OK and T6_TXT:                                        # v6：三條問題的文字版，方便複製
    print("\n===== 今日三問（文字版）=====\n" + "\n".join(T6_TXT))
for _x6 in T6_ERR:
    print("⚠ " + _x6)
if USE_OPENBB and len(OBB_LOG):
    _bad6 = [str(_r6.get("Feed")) + "：" + str(_r6.get("Status")) for _r6 in OBB_LOG if _r6.get("Status") != "成功"]
    print(f"補充數據層：{OBB_OKN}/{len(OBB_LOG)} 項成功" + ("；" + "、".join(_bad6) if _bad6 else ""))
if PRINT_NEWS_TEXT:
    print("\n" + NEWS_TXT + "\n")

# ---------- 存檔 ----------
# v6.2：跨日累積的檔案（daily_log、tier_history、score_history）放在 premarket_brief/ 第一層；
#       每日的檔案放在 premarket_brief/年-月/，檔名以簡報日開頭，再加執行時間（美東），同一日跑幾次都不會互相覆蓋；
#       各個名單的 CSV 放在 premarket_brief/年-月/data/執行編號/。
out_dir = HIST_DIR
DAY_DIR = os.path.join(HIST_DIR, f"{SESS_D:%Y-%m}")
DATA_DIR = os.path.join(DAY_DIR, "data", RUN_ID)
os.makedirs(DATA_DIR, exist_ok=True)
tag = f"{ASOF:%Y-%m-%d}"                                      # 數據日（daily_log 和 tier_history 仍然用它對應價格）
DASH_PATH = os.path.join(DAY_DIR, f"{RUN_ID}_dashboard.html")
with open(DASH_PATH, "w", encoding="utf-8") as f:
    f.write('<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f"<title>盤前簡報 {SESS:%Y-%m-%d}（執行 {RUN_TS:%m-%d %H:%M} ET）</title></head>"
            f"<body style='margin:0;background:#f3f3f3;padding:12px'>{PAGE}</body></html>")
with open(os.path.join(DAY_DIR, f"{RUN_ID}_brief.txt"), "w", encoding="utf-8") as f:
    f.write(BRIEF_TXT + "\n\n" + NEWS_TXT)

HIST = PS.copy()
HIST["score"] = SCORE
HIST["regime"] = REGIME.map(lambda x: REG_NAME[int(x)][0])
HIST["qqq_close"] = Q["c"]
HIST["pct_above_50"], HIST["pct_above_200"] = PCT50, PCT200
HIST["new_highs"], HIST["new_lows"] = NH, NL
HIST["vix"] = VIX if VIX is not None else np.nan
HIST = HIST.dropna(subset=["score"])
HIST.index.name = "date"
HIST.round(2).to_csv(os.path.join(out_dir, "score_history.csv"))

log_row = pd.DataFrame([{
    "brief_date": f"{SESS:%Y-%m-%d}", "run_id": RUN_ID, "dashboard": os.path.relpath(DASH_PATH, HIST_DIR),
    "asof": tag, "run_et": f"{RUN_TS:%Y-%m-%d %H:%M}", "score": round(score_now, 1), "regime": REG_L,
    "long_gate": LONG_GATE, "pilot_gate": PILOT_GATE, "short_gate": SHORT_GATE, "oversold": OVERSOLD,
    "qqq_close": round(float(q.c), 2), "pct_above_50": round(pct50_now, 1), "vix": vix_now,
    "new_highs": NH.iloc[-1], "new_lows": NL.iloc[-1],
    "bo_follow_pct": BO_FOLLOW if np.isnan(BO_FOLLOW) else round(BO_FOLLOW, 1), "bo_follow_n": BO_FOLLOW_N,
    "vcp_candidates": len(VCP), "fresh_52w_breakouts": len(BO52), "ath_closes": COUNTS["收市創歷史新高"],
    "cycle": CYCLE, "short_timing": SHORT_TIMING, "event_day": EVENT_DAY, "earn_fetch_failed": len(EARN_FAIL),
    "earn_source": EARN_SRC, "obb_feeds_ok": OBB_OKN, "obb_feeds": len(OBB_LOG),
    "tier_top_label": T6_TOP_L, "tier_top": ",".join(c_["Ticker"] for c_ in T6_LA), "tier_b": ",".join(c_["Ticker"] for c_ in T6_LB),
    "tier_short": ",".join(c_["Ticker"] for c_ in T6_SA), "long_candidates": len(T6_L), "new_long_slots": T6_BUD.get("n_long", ""),
    "focus_long": ",".join(FOCUS_L["Ticker"]) if len(FOCUS_L) else "", "htf": len(HTF), "tight": len(TIGHT), "resilient": len(RESIL), "pullback": len(PULL),
    "short_retest": len(S_RETEST), "breakdowns": len(BD), "fallen_leaders": len(FALLEN),
    "traded": "", "followed_plan": "", "notes": ""}])
log_path = os.path.join(out_dir, "daily_log.csv")
if os.path.exists(log_path):                                  # v6.2：每次執行一行，只剔除同一個執行編號（重複存檔）
    old = pd.read_csv(log_path, dtype=str)
    if "run_id" in old.columns:
        old = old[old["run_id"] != RUN_ID]
    log_row = pd.concat([old, log_row.astype(str)], ignore_index=True)
log_row.to_csv(log_path, index=False)

if V6_OK:                                                    # v6.1：今日全部候選存入名單紀錄，下次執行時用來做跟進和成績表
    try:
        _hp = os.path.join(out_dir, "tier_history.csv")
        _hn = t6_hist_rows().astype(str)
        if os.path.exists(_hp):
            _ho = pd.read_csv(_hp, dtype=str)
            if "asof" in _ho.columns:
                _hn = pd.concat([_ho[_ho["asof"] != tag], _hn], ignore_index=True)
        _hn.to_csv(_hp, index=False)
    except Exception as e:
        print(f"名單紀錄存不到（{type(e).__name__}: {str(e)[:100]}）")

SCANS = [("focus_long", FOCUS_L), ("focus_short", FOCUS_S), ("alerts", ALERT_TBL), ("earnings_reaction", EARN_REACT), ("vcp", VCP), ("htf", HTF), ("tight", TIGHT), ("breakout_52w", BO52), ("resilient", RESIL), ("pullback", PULL), ("gap_up", GAPUP),
         ("ath", ATH), ("breakout_1m", BO1M), ("short_retest", S_RETEST), ("breakdown", BD), ("fallen_leaders", FALLEN), ("gap_down", GAPDN)]
SCANS += [("tiers_long", T6_FR_L), ("tiers_short", T6_FR_S)]
SCANS += [("obb_movers", OBB_MOV), ("obb_implied_move", OBB_IMP), ("obb_short_interest", OBB_SI), ("obb_status", pd.DataFrame(OBB_LOG))]
for name, d in SCANS:
    if len(d):
        d.round(3).to_csv(os.path.join(DATA_DIR, f"scan_{name}.csv"), index=False)
F.round(3).to_csv(os.path.join(DATA_DIR, "universe_snapshot.csv"))

# TradingView 觀察名單：在 TradingView 的觀察名單選單選「匯入名單」即可
tv = []
for sec_name, d, n in (T6_TV if (V6_OK and T6_TV) else [("FOCUS", FOCUS_L, 5), ("FOCUS SHORT", FOCUS_S, 3)]) + [("VCP", VCP, 20), ("HIGH TIGHT FLAG", HTF[HTF["Note"] == ""] if len(HTF) else HTF, 20), ("TIGHT", TIGHT, 20), ("NEW HIGH BREAKOUT", BO52, 20), ("RESILIENT", RESIL, 25),
                       ("PULLBACK", PULL, 20), ("GAP UP", GAPUP, 15), ("SHORT RETEST", S_RETEST, 20), ("BREAKDOWN", BD, 20),
                       ("FALLEN LEADERS", FALLEN, 20)]:
    if len(d):
        tv.append("###" + sec_name)
        tv += [t.replace("-", ".") for t in d["Ticker"].head(n)]
with open(os.path.join(DAY_DIR, f"{RUN_ID}_tradingview.txt"), "w", encoding="utf-8") as f:
    f.write(",".join(tv))
if V6_OK:                                                    # v6.3：給格子 2「開市前快速更新」讀取的計劃檔
    try:
        import json
        _plan = t6_plan_dict()
        for _pp in (os.path.join(HIST_DIR, "latest_plan.json"), os.path.join(DATA_DIR, "plan.json")):
            with open(_pp, "w", encoding="utf-8") as f:
                json.dump(_plan, f, ensure_ascii=False, indent=1)
        if T6_ORD_TXT:
            with open(os.path.join(DAY_DIR, f"{RUN_ID}_futu_orders.txt"), "w", encoding="utf-8") as f:
                f.write("\n".join(T6_ORD_TXT))
    except Exception as e:
        print(f"計劃檔存不到（{type(e).__name__}: {str(e)[:120]}），格子 2 會讀不到今日的名單")
_on_drive = SAVE_TO_DRIVE and HIST_DIR == DRIVE_DIR
print(("已存到 Google Drive：我的雲端硬碟 → premarket_brief → " if _on_drive else "已存到 Colab 的臨時資料夾（工作階段結束就會刪除）：")
      + f"{SESS_D:%Y-%m}/\n  {RUN_ID}_dashboard.html（下載後用瀏覽器打開）\n  {RUN_ID}_brief.txt（文字摘要和消息面）\n"
      f"  {RUN_ID}_tradingview.txt（匯入 TradingView）\n  {RUN_ID}_futu_orders.txt（富途下單清單，有首選股票時才有）\n"
      f"  data/{RUN_ID}/（各個名單的 CSV）\n  第一層的 latest_plan.json 給格子 2「開市前快速更新」讀取\n"
      "  第一層的 daily_log.csv 是每次執行一行的總表，用 Google 試算表打開就可以看到每日的概況。")
