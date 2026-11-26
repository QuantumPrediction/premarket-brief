"""PNG scorecards from the brief's own numbers: HTML templates filled from the context, then a Playwright screenshot.
No image model is involved, so every figure on a card is the figure in data.json.

    files, issues = render(ctx, "daily", out_dir)      # issues: text that does not fit its box (empty = clean)
"""
import datetime as dt
import html
import os
import shutil

from . import config

HERE = os.path.dirname(os.path.abspath(__file__))
HTML_LANG = {"tc": "zh-Hant", "sc": "zh-Hans", "en": "en"}
BANDS = (("E", 0, 25), ("D", 25, 40), ("C", 40, 55), ("B", 55, 70), ("A", 70, 100))        # same bands as the website
GCOL = {"A": "#13753f", "B": "#3f7f24", "C": "#9a6200", "D": "#b4501c", "E": "#b03030"}

# label: (Traditional Chinese, Simplified Chinese, English)
T = {
    "disc": ("自動市況統計・非投資建議", "自动市况统计・非投资建议", "Automated Market Telemetry · Not Investment Advice"),
    "asof": ("數據截至 {d}", "数据截至 {d}", "Data to {d}"),
    "s1": ("市況總覽", "市况总览", "Regime scorecard"), "s2": ("五大支柱與市場寬度", "五大支柱与市场宽度", "Pillars & breadth"),
    "s3": ("板塊輪動", "板块轮动", "Sector rotation"), "s4": ("今晚時間表", "今晚时间表", "Tonight's calendar"),
    "wide": ("每日市況一覽", "每日市况一览", "Daily market dashboard"), "pre": ("開市前缺口更新", "开盘前缺口更新", "Pre-market gap refresh"),
    "led": ("形態跟進紀錄", "形态跟进记录", "Forward ledger"), "wk": ("一週回顧", "一周回顾", "Week in review"),
    "score": ("市場健康分數", "市场健康分数", "Market Health Score"),
    "prev": ("前一日 {a}・5 日前 {b}", "前一日 {a}・5 日前 {b}", "Prev session {a} · 5 sessions ago {b}"),
    "grade": ("市況級別", "市况级别", "Regime"),
    "hold": ("分數 {s} 屬 {r} 區，升級需連兩日留於高區間，暫維持 {g} 級", "分数 {s} 属 {r} 区，升级需连两日留于高区间，暂维持 {g} 级",
             "Score {s} sits in the {r} band; an upgrade needs two straight sessions there, so the grade stays {g}"),
    "g_long": ("多頭閘門", "多头闸门", "Long gate"), "g_pilot": ("試單閘門", "试单闸门", "Pilot gate"), "g_short": ("空頭閘門", "空头闸门", "Short gate"),
    "open": ("開", "开", "Open"), "closed": ("關", "关", "Closed"),
    "close": ("QQQ 收市", "QQQ 收盘", "QQQ close"), "ema21": ("21EMA", "21EMA", "21EMA"), "dma50": ("50 日線", "50 日线", "50DMA"),
    "dma200": ("200 日線", "200 日线", "200DMA"), "above": ("收市在其上", "收盘在其上", "Close above"), "below": ("收市在其下", "收盘在其下", "Close below"),
    "pillars": ("五大支柱（0–100）", "五大支柱（0–100）", "Five pillars (0–100)"), "weight": ("權重 {w}%", "权重 {w}%", "{w}% weight"),
    "p50": ("高於 50 日線的股票", "高于 50 日线的股票", "Stocks above 50DMA"), "p200": ("高於 200 日線的股票", "高于 200 日线的股票", "Stocks above 200DMA"),
    "dd": ("派發日（近 25 日）", "派发日（近 25 日）", "Distribution days (25 sessions)"), "bo": ("突破成功率", "突破成功率", "Breakout success rate"),
    "universe": ("股票池 {n} 隻", "股票池 {n} 只", "Universe of {n} stocks"), "qqq": ("以 QQQ 計", "以 QQQ 计", "Counted on QQQ"),
    "bo_s": ("近期突破後能守住的比例", "近期突破后能守住的比例", "Share of recent breakouts that held"),
    "lead": ("領先板塊（1 個月超額回報最高）", "领先板块（1 个月超额回报最高）", "Leading sectors (highest 1M excess return)"),
    "lag": ("落後板塊（1 個月超額回報最低）", "落后板块（1 个月超额回报最低）", "Lagging sectors (lowest 1M excess return)"),
    "c_sec": ("板塊 ETF", "板块 ETF", "Sector ETF"), "c_r": ("1 個月", "1 个月", "1M return"), "c_ex": ("超額", "超额", "1M excess"),
    "c_p": ("> 50 日線", "> 50 日线", "> 50DMA"),
    "sec_note": ("超額回報以大市為基準；最右一欄是板塊成份股高於 50 日線的比例。", "超额回报以大盘为基准；最右一栏是板块成份股高于 50 日线的比例。",
                 "Excess return is measured against the market; the last column is the share of constituents above the 50DMA."),
    "ev_h": ("今晚重點（香港時間）", "今晚重点（香港时间）", "Tonight's key times (HKT)"), "et": ("美東 {t}", "美东 {t}", "{t} ET"),
    "next": ("翌日", "次日", "next day"),
    "no_macro": ("今晚沒有重點經濟數據或大型財報。", "今晚没有重点经济数据或大型财报。", "No major macro releases or large-cap earnings tonight."),
    "k_macro": ("數據", "数据", "Macro"), "k_earnings": ("財報", "财报", "Earnings"), "k_market": ("市場", "市场", "Market"), "k_other": ("其他", "其他", "Other"),
    "vol": ("波動率期限結構", "波动率期限结构", "Volatility term structure"), "ratio": ("VIX／VIX3M", "VIX／VIX3M", "VIX / VIX3M"),
    "back": ("逆價差：短期風險溢價較高", "逆价差：短期风险溢价较高", "Backwardation: near-term risk priced higher"),
    "contango": ("正價差：期限結構正常", "正价差：期限结构正常", "Contango: normal term structure"),
    "cta": ("完整互動簡報：免費網頁版", "完整互动简报：免费网页版", "Full interactive brief: free on the web"),
    "cta2": ("每日 {a} 市場健檢＋{b} 開市前缺口更新（香港時間）・連結在個人檔案", "每日 {a} 市场健检＋{b} 开盘前缺口更新（香港时间）・链接在个人主页",
             "Daily {a} HKT regime brief + {b} HKT pre-market gap refresh · link in bio"),
    "sectors": ("板塊：領先與落後", "板块：领先与落后", "Sectors: leaders vs laggards"),
    "fut": ("期貨隔夜變動", "期货隔夜变动", "Overnight futures"), "qqq_pre": ("QQQ 盤前", "QQQ 盘前", "QQQ pre-market"),
    "gap_atr": ("{v} 個 ATR", "{v} 个 ATR", "{v} ATR"), "scen": ("開市情景", "开盘情景", "Opening scenario"),
    "vix_chg": ("較上日 {v}", "较上日 {v}", "{v} vs prior close"), "no_quote": ("未有報價", "暂无报价", "No quote yet"),
    "focus": ("首選名單", "首选名单", "Focus list"), "control": ("對照組（其餘候選）", "对照组（其余候选）", "Control group (other candidates)"),
    "l_listed": ("列出", "列出", "Listed"), "l_trig": ("已觸發", "已触发", "Triggered"), "l_open": ("跟進中", "跟进中", "Open"),
    "l_2r": ("達 2R", "达 2R", "Reached 2R"), "l_inv": ("失效", "失效", "Invalidated"), "l_avg": ("平均 R（已完結）", "平均 R（已完结）", "Average R (closed)"),
    "l_recent": ("首選名單最近狀態", "首选名单最近状态", "Focus list: latest status"),
    "l_rule": ("全部按同一套固定規則評定，紀錄不會刪除；R 為假設值，並非實際交易。", "全部按同一套固定规则评定，记录不会删除；R 为假设值，并非实际交易。",
               "Graded by one fixed rule set; no record is ever removed. R is hypothetical, not a traded result."),
    "st_TRIGGERED": ("觸發", "触发", "Triggered"), "st_HIT_2R": ("達 2R", "达 2R", "Reached 2R"), "st_INVALIDATED": ("失效", "失效", "Invalidated"),
    "st_EXPIRED": ("過期", "过期", "Expired"), "st_PENDING": ("待觸發", "待触发", "Pending"),
    "long": ("做多", "做多", "Long"), "short": ("做空", "做空", "Short"),
    "wk_h": ("最近 {n} 個簡報日", "最近 {n} 个简报日", "Last {n} brief dates"), "wk_qqq": ("QQQ {v}", "QQQ {v}", "QQQ {v}"),
}
IDX = {"tc": 0, "sc": 1, "en": 2}


def t(key, lang, **kw):
    s = T[key][IDX[lang]]
    return s.format(**kw) if kw else s


def e(x):
    return html.escape("" if x is None else str(x))


def num(x, nd=2, sign=False, pct=False):
    if x is None:
        return "–"
    s = f"{x:+,.{nd}f}" if sign else f"{x:,.{nd}f}"
    return s.replace("-", "−") + ("%" if pct else "")


def tone(x):
    return "m" if x is None else "g" if x > 0 else "r" if x < 0 else "m"


def bar_color(v):
    return "#0a7d33" if v >= 60 else "#b7791f" if v >= 40 else "#c0392b"


# ---------- pieces shared by the portrait and the wide card ----------
def score_block(c, lang):
    return (f'<div class="scorebox"><div class="lbl">{e(t("score", lang))}</div><div class="score">{c["market_health_score"]}<span>/100</span></div>'
            f'<div class="delta">{e(t("prev", lang, a=c["score_previous_session"], b=c["score_5_sessions_ago"]))}</div></div>')


def grade_block(c, lang, cap=True):
    g = c["regime_grade"]
    return (f'<div class="grade g{e(g)}">' + (f'<div class="cap">{e(t("grade", lang))}</div>' if cap else "")
            + f'<div class="letter">{e(g)}</div><div class="gname">{e(c["regime_name"][lang])}</div></div>')


def hold_note(c, lang):
    if not c["grade_held_by_hysteresis"]:
        return ""
    return f'<div class="hold">{e(t("hold", lang, s=c["market_health_score"], r=c["score_band_grade"], g=c["regime_grade"]))}</div>'


def pills(c, lang):
    out = []
    for key, lab, good in (("long", "g_long", True), ("pilot", "g_pilot", True), ("short", "g_short", False)):
        on = c["gates_open"][key]
        cls = ("on-g" if good else "on-r") if on else "off"
        out.append(f'<div class="pill {cls}"><div class="k">{e(t(lab, lang))}</div><div class="v">{e(t("open" if on else "closed", lang))}</div></div>')
    return '<div class="pills">' + "".join(out) + "</div>"


def band_bar(c):
    segs = "".join(f'<i style="width:{hi - lo}%;background:{GCOL[g]}"></i>' for g, lo, hi in BANDS)
    labs = "".join(f'<span class="lab" style="left:{(lo + hi) / 2}%">{g}</span>' for g, lo, hi in BANDS)
    x = max(1.0, min(99.0, float(c["market_health_score"])))
    return f'<div class="band"><div class="bar">{segs}</div>{labs}<span class="mark" style="left:{x}%"></span></div>'


def pillar_rows(c, lang):
    rows = []
    for p in c["pillars"]:
        v = p["score"]
        rows.append(f'<div class="brow"><div class="k">{e(p["name"][lang])}<small>{e(t("weight", lang, w=p["weight_pct"]))}</small></div>'
                    f'<div class="trk"><i style="width:{max(2, min(100, v))}%;background:{bar_color(v)}"></i></div><div class="v">{v}</div></div>')
    return '<div class="bars">' + "".join(rows) + "</div>" if rows else ""


def sector_rows(rows, lang, cls):
    out = []
    for s in rows:
        out.append(f'<div class="srow {cls}"><div class="n"><b>{e(s["etf"])}</b><span>{e(s["name"][lang])}</span></div>'
                   f'<div class="x {tone(s["return_1m_pct"])}">{num(s["return_1m_pct"], 1, True, True)}</div>'
                   f'<div class="x {tone(s["excess_1m_pct"])}">{num(s["excess_1m_pct"], 1, True, True)}</div>'
                   f'<div class="p">{num(s["pct_above_50dma"], 0, pct=True)}</div></div>')
    return "".join(out)


def sector_head(lang):
    return f'<div class="shead"><span>{e(t("c_sec", lang))}</span><span>{e(t("c_r", lang))}</span><span>{e(t("c_ex", lang))}</span><span>{e(t("c_p", lang))}</span></div>'


def events_html(c, lang, limit, wide=False):
    key = [x for x in c["tonight_events"] if x["kind"] in ("macro", "earnings")]
    rest = [x for x in c["tonight_events"] if x["kind"] not in ("macro", "earnings")]
    rows = (key + rest)[:limit] if key else rest[:limit]
    rows.sort(key=lambda x: (x["next_day_hkt"], x["hkt"]))
    out = [] if key else [f'<div class="none">{e(t("no_macro", lang))}</div>']
    for x in rows:
        nx = f' <small>{e(t("next", lang))}</small>' if (x["next_day_hkt"] and wide) else ""
        sub = "" if wide else f'<small>{e(t("et", lang, t=x["et"]))}{"・" + e(t("next", lang)) if x["next_day_hkt"] else ""}</small>'
        tag = "" if wide else f'<small>{e(t("k_" + x["kind"], lang))}</small>'
        out.append(f'<div class="ev {e(x["kind"])}"><div class="tm">{e(x["hkt"])}{nx}{sub}</div><div class="w">{tag}{e(x["what"][lang])}</div></div>')
    return '<div class="events">' + "".join(out) + "</div>"


def term_note(c, lang):
    r = c["volatility"]["vix_vix3m_ratio"]
    return "" if r is None else t("back" if r > 1 else "contango", lang)


def ledger_kv(st, lang):
    rows = [("l_listed", st["listed"]), ("l_trig", st["triggered"]), ("l_open", st["open"]), ("l_2r", st["hit_2r"]), ("l_inv", st["invalidated"]),
            ("l_avg", "–" if st["avg_r"] is None else num(st["avg_r"], 2, True) + "R")]
    return '<div class="kv">' + "".join(f"<span>{e(t(k, lang))}</span><b>{e(v)}</b>" for k, v in rows) + "</div>"


def ledger_rows(c, lang, limit):
    out = []
    col = {"TRIGGERED": "a", "HIT_2R": "g", "INVALIDATED": "r", "EXPIRED": "m", "PENDING": "m"}
    for r in c["ledger"]["recent"][:limit]:
        out.append(f'<div class="lrow"><b>{e(r["ticker"])}</b><span>{e(t(r["direction"], lang))}・{e(r["listed"][5:])}</span>'
                   f'<span class="st {col.get(r["status"], "m")}">{e(t("st_" + r["status"], lang))}</span>'
                   f'<span class="rr {tone(r["r"])}">{"–" if r["r"] is None else num(r["r"], 2, True) + "R"}</span></div>')
    return '<div class="lrows">' + "".join(out) + "</div>"


# ---------- the cards ----------
def slide_regime(c, lang):
    q = c["qqq"]

    def lvl(key):
        v = q.get(key)
        if key == "close" or v is None or q["close"] is None:
            sub = "&nbsp;"
        else:
            up = q["close"] >= v
            sub = f'<span class="{"g" if up else "r"}">{"▲" if up else "▼"} {e(t("above" if up else "below", lang))}</span>'
        return f'<div><div class="k">{e(t(key, lang))}</div><div class="v">{num(v)}</div><div class="s">{sub}</div></div>'
    return (f'<div class="hero">{score_block(c, lang)}{grade_block(c, lang)}</div>{band_bar(c)}{hold_note(c, lang)}{pills(c, lang)}'
            f'<div class="panel levels">{lvl("close")}{lvl("ema21")}{lvl("dma50")}{lvl("dma200")}</div>')


def slide_breadth(c, lang):
    b = c["breadth"]
    tiles = [(t("p50", lang), num(b["pct_above_50dma"], 0), "%", t("universe", lang, n=f'{c["universe_size"]:,}') if c.get("universe_size") else ""),
             (t("p200", lang), num(b["pct_above_200dma"], 0), "%", t("universe", lang, n=f'{c["universe_size"]:,}') if c.get("universe_size") else ""),
             (t("dd", lang), num(b["distribution_days_25_sessions"], 0), "", t("qqq", lang)),
             (t("bo", lang), num(b["breakout_success_rate_pct"], 0), "%", t("bo_s", lang))]
    th = "".join(f'<div class="tile"><div class="k">{e(k)}</div><div class="v">{e(v)}' + (f"<small>{u}</small>" if u and v != "–" else "")
                 + f'</div><div class="s">{e(s)}</div></div>' for k, v, u, s in tiles)
    bars = pillar_rows(c, lang)
    return (f'<h2>{e(t("pillars", lang))}</h2><div class="panel">{bars}</div>' if bars else "") + f'<div class="tiles">{th}</div>'


def slide_sectors(c, lang):
    return (f'<div class="sgroup"><h2>{e(t("lead", lang))}</h2>{sector_head(lang)}{sector_rows(c["sectors_leading"], lang, "up")}</div>'
            f'<div class="sgroup"><h2>{e(t("lag", lang))}</h2>{sector_head(lang)}{sector_rows(c["sectors_lagging"], lang, "dn")}</div>'
            f'<div class="none">{e(t("sec_note", lang))}</div>')


def slide_calendar(c, lang):
    v = c["volatility"]
    vol = (f'<div class="tiles"><div class="tile"><div class="k">VIX</div><div class="v">{num(v["vix"], 1)}</div><div class="s">VIX3M {num(v["vix3m"], 1)}</div></div>'
           f'<div class="tile"><div class="k">{e(t("ratio", lang))}</div><div class="v {"r" if (v["vix_vix3m_ratio"] or 0) > 1 else ""}">{num(v["vix_vix3m_ratio"], 2)}</div>'
           f'<div class="s">{e(term_note(c, lang))}</div></div></div>')
    cta = (f'<div class="cta"><div class="big">{e(t("cta", lang))}</div>'
           f'<div class="sm">{e(t("cta2", lang, a=config.daily_hkt(), b=config.premarket_hkt()))}</div></div>')
    return f'<div><h2>{e(t("ev_h", lang))}</h2><div style="height:14px"></div>{events_html(c, lang, 5)}</div><div><h2>{e(t("vol", lang))}</h2><div style="height:14px"></div>{vol}</div>{cta}'


def wide_summary(c, lang):
    q, b = c["qqq"], c["breadth"]
    lv = "".join(f'<div>{e(t(k, lang))}<b>{num(q.get(k))}</b></div>' for k in ("close", "ema21", "dma50", "dma200"))
    left = (f'<div class="col"><div class="top"><div><h2>{e(t("score", lang))}</h2><div class="score">{c["market_health_score"]}</div>'
            f'<div class="delta">{e(t("prev", lang, a=c["score_previous_session"], b=c["score_5_sessions_ago"]))}</div></div>{grade_block(c, lang, cap=False)}</div>'
            f'{hold_note(c, lang)}{pills(c, lang)}<div class="levels">{lv}</div></div>')
    mini = "".join(f"<div><b>{e(v)}</b>{e(k)}</div>" for k, v in (
        (t("c_p", lang), num(b["pct_above_50dma"], 0, pct=True)), (t("dma200", lang).replace("200", "> 200"), num(b["pct_above_200dma"], 0, pct=True)),
        (t("dd", lang).split("（")[0].split(" (")[0], num(b["distribution_days_25_sessions"], 0)), (t("bo", lang), num(b["breakout_success_rate_pct"], 0, pct=True))))
    mid = f'<div class="col"><h2>{e(t("pillars", lang))}</h2>{pillar_rows(c, lang)}<div class="mini">{mini}</div></div>'
    right = (f'<div class="col"><h2>{e(t("sectors", lang))}</h2><div class="sgroup">{sector_head(lang)}{sector_rows(c["sectors_leading"], lang, "up")}</div>'
             f'<div class="sgroup">{sector_rows(c["sectors_lagging"], lang, "dn")}</div>'
             f'<div class="sub">VIX {num(c["volatility"]["vix"], 1)}・VIX3M {num(c["volatility"]["vix3m"], 1)}・{e(t("ratio", lang))} {num(c["volatility"]["vix_vix3m_ratio"], 2)}</div></div>')
    return left + mid + right


def wide_premarket(c, lang):
    p = c.get("premarket") or {}
    fut = p.get("futures") or {}
    tiles = "".join(f'<div class="tile"><div class="k">{k}</div><div class="v {tone(fut.get(k))}">{num(fut.get(k), 2, True, True)}</div></div>'
                    for k in ("NQ", "ES", "RTY"))
    vix = p.get("vix")
    tiles += (f'<div class="tile"><div class="k">VIX</div><div class="v">{num(vix, 2) if vix is not None else "–"}</div><div class="s">'
              + (e(t("vix_chg", lang, v=num(p["vix_change"], 2, True))) if p.get("vix_change") is not None else (e(t("no_quote", lang)) if vix is None else "")) + "</div></div>")
    qq = (f'<div class="kv"><span>{e(t("qqq_pre", lang))}</span><b>{num(p.get("qqq_price"))}</b><span>&nbsp;</span>'
          f'<b class="{tone(p.get("qqq_change_pct"))}">{num(p.get("qqq_change_pct"), 2, True, True)}・{e(t("gap_atr", lang, v=num(p.get("qqq_gap_atr"), 2, True)))}</b></div>'
          if p.get("qqq_price") is not None else "")
    scen = f'<div><h2>{e(t("scen", lang))}</h2><div class="note">{e((p.get("scenario") or {}).get(lang, ""))}</div></div>' if p.get("scenario") else ""
    left = (f'<div class="col"><div class="top"><div><h2>{e(t("score", lang))}</h2><div class="score">{c["market_health_score"]}</div></div>'
            f'{grade_block(c, lang, cap=False)}</div>{hold_note(c, lang)}{pills(c, lang)}</div>')
    mid = f'<div class="col"><h2>{e(t("fut", lang))}</h2><div class="tiles">{tiles}</div>{qq}{scen}</div>'
    right = f'<div class="col" style="justify-content:flex-start"><h2>{e(t("ev_h", lang))}</h2>{events_html(c, lang, 7, wide=True)}</div>'
    return left + mid + right


def ledger_portrait(c, lang):
    L = c["ledger"]
    return (f'<div class="lgrid"><div class="panel lcol"><h3>{e(t("focus", lang))}</h3><div class="sub">&nbsp;</div>{ledger_kv(L["focus"], lang)}</div>'
            f'<div class="panel lcol"><h3>{e(t("control", lang))}</h3><div class="sub">&nbsp;</div>{ledger_kv(L["control"], lang)}</div></div>'
            f'<div><h2>{e(t("l_recent", lang))}</h2><div style="height:12px"></div>{ledger_rows(c, lang, 6)}</div><div class="none">{e(t("l_rule", lang))}</div>')


def ledger_wide(c, lang):
    L = c["ledger"]
    return (f'<div class="col" style="justify-content:flex-start"><h2>{e(t("focus", lang))}</h2>{ledger_kv(L["focus"], lang)}</div>'
            f'<div class="col" style="justify-content:flex-start"><h2>{e(t("control", lang))}</h2>{ledger_kv(L["control"], lang)}</div>'
            f'<div class="col" style="justify-content:flex-start"><h2>{e(t("l_recent", lang))}</h2>{ledger_rows(c, lang, 7)}<div class="sub">{e(t("l_rule", lang))}</div></div>')


def wide_weekly(c, lang):
    days = "".join(f'<div class="wkd"><div class="d">{e(w["brief_date"][5:])}</div><div class="sc">{e(w["score"])}</div>'
                   f'<div class="gr" style="background:{GCOL.get(w["grade"], "#8b949a")}">{e(w["grade"])}</div>'
                   f'<div class="q">{e(t("wk_qqq", lang, v=num(w["qqq_close"])))}</div></div>' for w in c.get("week", []))
    L = c["ledger"]
    return (f'<div class="col"><h2>{e(t("wk_h", lang, n=len(c.get("week", []))))}・{e(t("score", lang))}</h2><div class="wk">{days}</div>'
            f'{pills(c, lang)}</div><div class="col" style="justify-content:flex-start"><h2>{e(t("focus", lang))}</h2>{ledger_kv(L["focus"], lang)}'
            f'<h2 style="margin-top:14px">{e(t("control", lang))}</h2>{ledger_kv(L["control"], lang)}</div>')


# name, template, size, builder, title key, grid columns
CAROUSEL = (("01_regime", slide_regime, "s1"), ("02_breadth", slide_breadth, "s2"), ("03_sectors", slide_sectors, "s3"), ("04_calendar", slide_calendar, "s4"))


def plan(ctx, mode):
    """[(file name, template, (w, h), lang, kind, title key, page text, content html, columns)]"""
    out = []
    sq, wd = "card_square_4x5.html", "card_wide_16x9.html"
    if mode == "daily":
        for lang in ("tc", "sc"):
            for i, (name, fn, title) in enumerate(CAROUSEL):
                out.append((f"carousel_{lang}_{name}.png", sq, (1080, 1350), lang, name[3:], title, f"{i + 1} / {len(CAROUSEL)}", fn(ctx, lang), ""))
        for lang in ("en", "tc"):
            out.append((f"wide_{lang}_summary.png", wd, (1600, 900), lang, "summary", "wide", "", wide_summary(ctx, lang), "1.08fr 1fr 1.12fr"))
    elif mode == "premarket":
        for lang in ("en", "tc"):
            out.append((f"wide_{lang}_premarket.png", wd, (1600, 900), lang, "premarket", "pre", "", wide_premarket(ctx, lang), "0.9fr 1.15fr 1.1fr"))
    elif mode == "ledger":
        for lang in ("tc", "en"):
            out.append((f"ledger_{lang}.png", sq, (1080, 1350), lang, "ledger", "led", "", ledger_portrait(ctx, lang), ""))
            out.append((f"ledger_wide_{lang}.png", wd, (1600, 900), lang, "ledger", "led", "", ledger_wide(ctx, lang), "0.8fr 0.8fr 1.3fr"))
    elif mode == "weekly":
        for lang in ("en", "tc"):
            out.append((f"wide_{lang}_weekly.png", wd, (1600, 900), lang, "weekly", "wk", "", wide_weekly(ctx, lang), "1.9fr 1fr"))
    return out


def page_html(ctx, item):
    name, template, size, lang, kind, title, page, content, columns = item
    doc = open(os.path.join(HERE, "templates", template), encoding="utf-8").read()
    footer = f'{config.watermark()}・{ctx["brief_date"]}・{t("disc", lang)}'
    fill = {"html_lang": HTML_LANG[lang], "lang": lang, "kind": kind, "brand": e(config.brand(lang)), "slide_title": e(t(title, lang)),
            "date": e(ctx["brief_date"]), "sub_date": e(t("asof", lang, d=ctx["data_as_of"][5:])), "content": content, "footer": e(footer),
            "page": e(page), "columns": columns or "1fr", "week_n": str(max(1, len(ctx.get("week", []))))}
    for k, v in fill.items():
        doc = doc.replace("{{" + k + "}}", v)
    return doc


# Text that leaves the page or its own box: returns a list of short descriptions (empty = everything fits).
FIT_JS = """() => {
  const out = [], W = innerWidth, H = innerHeight;
  for (const el of document.querySelectorAll('body, body *')) {
    const cs = getComputedStyle(el);
    if (cs.position === 'absolute' || el.tagName === 'I') continue;
    const r = el.getBoundingClientRect();
    if (!r.width || !r.height) continue;
    const what = (el.className || el.tagName) + ' «' + el.textContent.trim().slice(0, 24) + '»';
    if (r.right > W + 1 || r.bottom > H + 1 || r.left < -1 || r.top < -1) out.push('outside the card: ' + what);
    if (cs.display !== 'inline' && (el.scrollWidth > el.clientWidth + 1 || (cs.overflowY !== 'visible' && el.scrollHeight > el.clientHeight + 1))) {
      out.push('does not fit its box: ' + what);       // tight line-heights make scrollHeight unreliable for visible boxes; the parent test covers those
    }
    const p = el.parentElement;
    if (p && p !== document.documentElement) {
      const pr = p.getBoundingClientRect();
      if (r.right > pr.right + 1 || r.bottom > pr.bottom + 1) out.push('spills out of its parent: ' + what);
    }
  }
  return [...new Set(out)];
}"""


def render(ctx, mode, out_dir, keep_html=False):
    """Writes the PNG files of one mode into out_dir. Returns ({file name: path}, [fit problems])."""
    from playwright.sync_api import sync_playwright
    items = plan(ctx, mode)
    files, issues = {}, []
    if not items:
        return files, issues
    os.makedirs(out_dir, exist_ok=True)
    with sync_playwright() as pw:
        kw = {"executable_path": config.chromium_path()} if config.chromium_path() else {}
        browser = pw.chromium.launch(args=["--no-sandbox", "--font-render-hinting=none"], **kw)
        try:
            for item in items:
                name, size = item[0], item[2]
                page = browser.new_page(viewport={"width": size[0], "height": size[1]}, device_scale_factor=1)
                doc = page_html(ctx, item)
                page.set_content(doc, wait_until="load")
                page.evaluate("document.fonts.ready")
                issues += [f"{name}: {x}" for x in page.evaluate(FIT_JS)]
                path = os.path.join(out_dir, name)
                page.screenshot(path=path, type="png", clip={"x": 0, "y": 0, "width": size[0], "height": size[1]})
                page.close()
                files[name] = path
                if keep_html:
                    open(path[:-4] + ".html", "w", encoding="utf-8").write(doc)
        finally:
            browser.close()
    return files, issues


def publish_dirs(state, brief_date):
    return [os.path.join(site, "social", brief_date) for site in config.site_dirs(state)]


def mirror(files, state, brief_date):
    """Copy the PNG files of the first website folder into the other ones (the public teaser of freemium_split)."""
    dirs = publish_dirs(state, brief_date)
    for d in dirs[1:]:
        os.makedirs(d, exist_ok=True)
        for name, path in files.items():
            shutil.copyfile(path, os.path.join(d, name))


def trading_days_between(d, today):
    """Weekdays after d up to and including today (holidays are not looked up: a holiday week keeps one folder less)."""
    n, cur = 0, d
    while cur < today:
        cur += dt.timedelta(days=1)
        n += cur.weekday() < 5
    return n


def prune(state, today=None, days=None):
    """Delete social/<date>/ image folders older than `days` trading days so the data branch stays light."""
    today = today or dt.date.today()
    days = config.PRUNE_TRADING_DAYS if days is None else days
    gone = []
    for site in ("site", "site_free"):
        base = os.path.join(state, site, "social")
        for name in sorted(os.listdir(base)) if os.path.isdir(base) else []:
            try:
                d = dt.date.fromisoformat(name[:10])
            except ValueError:
                continue
            if trading_days_between(d, today) > days:
                shutil.rmtree(os.path.join(base, name), ignore_errors=True)
                gone.append(f"{site}/social/{name}")
    return gone
