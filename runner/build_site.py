"""Build the public website from the state folder (no network, no trading code).

Reads   state/site/briefs/<run>/summary_tc.json, state/site/preopen/<stem>/summary_tc.json,
        state/premarket_out/score_history.csv
Writes  state/site/index.html (Traditional Chinese), state/site/zh-hans/index.html, state/site/en/index.html,
        state/site/latest/<lang>.html (always opens the newest full brief), state/site/assets/site.css + site.js,
        the Simplified Chinese and English copies of every brief and pre-open page that lacks them,
        and the bar at the top of those pages (back to the home page, language switch)
The full briefs themselves (briefs/<run>/<lang>.html) are written by run_brief.py and only linked from here.
"""
import csv
import glob
import hashlib
import html
import json
import os
import shutil
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import LANGS, ROOT, ensure_languages, env, now_et, strip_bar  # noqa: E402

LANG_DIR = {"tc": "", "sc": "zh-hans/", "en": "en/"}             # the home page is Traditional Chinese
HTML_LANG = {"en": "en", "tc": "zh-Hant", "sc": "zh-Hans"}
LANG_NAME = {"en": "English", "tc": "繁體", "sc": "简体"}
ARCHIVE_SHOWN = 30                                                # older briefs sit in a folded list below these
REG_ORDER = ["E", "D", "C", "B", "A"]
REG_BANDS = {"E": (0, 25), "D": (25, 40), "C": (40, 55), "B": (55, 70), "A": (70, 100)}

# label: (English, Traditional Chinese, Simplified Chinese)
L = {
    "site": ("US Pre-market Brief", "美股盤前簡報", "美股盘前简报"),
    "tagline": ("An automated morning workflow for US stocks: market regime, breadth and technical screening across the S&P 500, "
                "Nasdaq 100 and S&P 400, recalculated by fixed rules every trading day before the open.",
                "自動化的美股晨間工作流程：每個交易日開市前，按固定規則為標普 500、納指 100 和標普 400 股票整理市況級別、市場寬度和技術形態篩選。",
                "自动化的美股晨间工作流程：每个交易日开盘前，按固定规则为标普 500、纳指 100 和标普 400 股票整理市况级别、市场宽度和技术形态筛选。"),
    "brief_for": ("Brief for", "簡報日", "简报日"),
    "data_to": ("data to the close of", "數據截至", "数据截至"),
    "updated": ("Updated", "更新於", "更新于"),
    "hk": ("Hong Kong", "香港", "香港"),
    "regime": ("Regime", "市況級別", "市况级别"),
    "score": ("Market health score", "市場健康分數", "市场健康分数"),
    "score_vs": ("yesterday {a}, 5 days ago {b}", "昨日 {a}，5 日前 {b}", "昨日 {a}，5 日前 {b}"),
    "range_note": ("Score bands: E below 25, D 25–39, C 40–54, B 55–69, A 70 and above. A downgrade applies the same day; an upgrade "
                   "needs two consecutive sessions in the higher band, so the score can sit above its grade’s band.",
                   "分數區間：E 低於 25，D 25–39，C 40–54，B 55–69，A 70 或以上。降級即日生效；升級要連續兩個交易日留在較高區間，"
                   "所以分數有時會高於級別所屬的區間。",
                   "分数区间：E 低于 25，D 25–39，C 40–54，B 55–69，A 70 或以上。降级即日生效；升级要连续两个交易日留在较高区间，"
                   "所以分数有时会高于级别所属的区间。"),
    "held": ("Score {s} is in the {r} band; an upgrade needs two consecutive sessions there, so the grade stays {g}",
             "分數 {s} 屬 {r} 區；升級要連續兩個交易日留在較高區間，暫維持 {g} 級",
             "分数 {s} 属 {r} 区；升级要连续两个交易日留在较高区间，暂维持 {g} 级"),
    "hist_held": ("* The score had entered a higher band but not yet for two consecutive sessions, so the grade stayed the same.",
                  "＊ 分數已進入較高區間，但未連續兩個交易日，級別暫時維持。",
                  "＊ 分数已进入较高区间，但未连续两个交易日，级别暂时维持。"),
    "tg_text": ("Free Telegram Alerts: Daily {a} HKT Regime Brief + {b} HKT Pre-Market Gap Refresh", "免費訂閱 Telegram 頻道：每日 {a} 市場健檢 ＋ {b} 開市前缺口更新",
                "免费订阅 Telegram 频道：每日 {a} 市场健检 ＋ {b} 开盘前缺口更新"),
    "tg_cta": ("Join Free", "立即加入", "立即加入"),
    "gate_long": ("Long gate", "多頭閘門", "多头闸门"), "gate_pilot": ("Pilot gate", "試單閘門", "试单闸门"),
    "gate_short": ("Short gate", "空頭閘門", "空头闸门"), "oversold": ("Oversold", "超賣", "超卖"),
    "open": ("open", "開", "开"), "closed": ("closed", "關", "关"), "yes": ("yes", "是", "是"), "no": ("no", "否", "否"),
    "event_day": ("Event day: key data during the session", "事件日：交易時段內有重要數據", "事件日：交易时段内有重要数据"),
    "new_pos": ("Rule exposure limit (demo)", "規則示範新倉上限", "规则示范新仓上限"),
    "n_long_short": ("{a} long / {b} short units", "多 {a}／空 {b} 單位", "多 {a}／空 {b} 单位"),
    "universe": ("Stocks scanned", "掃描股票", "扫描股票"),
    "above50": ("Above 50-day average", "高於 50 日線", "高于 50 日线"),
    "bo": ("Breakouts that held", "突破成功率", "突破成功率"),
    "vix": ("VIX", "VIX", "VIX"),
    "anchor": ("QQQ close", "QQQ 收市", "QQQ 收盘"),
    "cycle": ("Market cycle", "市場週期", "市场周期"),
    "open_brief": ("Open today’s full brief", "打開今日完整簡報", "打开今日完整简报"),
    "open_pre": ("Automated pre-market refresh", "系統開市前更新", "系统开盘前更新"),
    "pre_time": ("checked at {t} ET", "美東 {t} 檢查", "美东 {t} 检查"),
    "no_pre": ("The automated pre-market refresh runs about 45 minutes before the open", "開市前約 45 分鐘有系統開市前更新", "开盘前约 45 分钟有系统开盘前更新"),
    "plan_h": ("Today’s rule output", "今日規則結果", "今日规则结果"),
    "picks_none": ("No setup matches the rules today.", "今日沒有符合規則的形態。", "今日没有符合规则的形态。"),
    "b_h": ("Near ready, watch only", "接近成熟，只作觀察", "接近成熟，只作观察"),
    "live_h": ("Rule-matched setups", "符合規則的技術形態（Rule-Matched Setups）", "符合规则的技术形态（Rule-Matched Setups）"),
    "live_none": ("No setup matches the rules with its gate open today.", "今日沒有閘門已開而又符合規則的形態。",
                  "今日没有闸门已开而又符合规则的形态。"),
    "watch_h": ("Watch list: gate closed", "觀察名單：閘門關閉", "观察名单：闸门关闭"),
    "watch_note": ("These setups meet the other rules, but their gate is closed. The levels are for reference only.",
                   "這些形態符合其餘規則，但對應的閘門未開；以下價位只作參考。",
                   "这些形态符合其余规则，但对应的闸门未开；以下价位只作参考。"),
    "watch_tag": ("watch only", "只觀察", "只观察"),
    "c_alert": ("Alert", "提示價", "提示价"),
    "side_long": ("Long", "做多", "做多"), "side_short": ("Short", "做空", "做空"),
    "sp_max": ("gate open; rule limit {n} units", "閘門開；規則示範上限 {n} 單位", "闸门开；规则示范上限 {n} 单位"),
    "sp_max1": ("gate open; rule limit 1 unit", "閘門開；規則示範上限 1 單位", "闸门开；规则示范上限 1 单位"),
    "sp_zero": ("gate open; rule limit 0 units today", "閘門開；今日規則示範上限為零", "闸门开；今日规则示范上限为零"),
    "sp_closed_l": ("gate closed", "閘門關閉", "闸门关闭"),
    "sp_closed_s": ("gate closed", "閘門關閉", "闸门关闭"),
    "sp_watch": ("{k} on the watch list", "{k} 隻只作觀察", "{k} 只仅作观察"),
    "play_h": ("Rule summary", "規則摘要", "规则摘要"),
    "c_ticker": ("Stock", "股票", "股票"), "c_setup": ("Setup", "形態", "形态"), "c_trigger": ("Pivot", "技術觸發位", "技术触发位"),
    "c_stop": ("Invalidation", "形態失效位", "形态失效位"), "c_risk": ("Risk", "風險", "风险"), "c_dist": ("Price vs pivot", "現價距觸發位", "现价距触发位"),
    "c_cat": ("Earnings", "財報", "财报"), "c_why": ("Why", "理由", "理由"), "c_missing": ("Still missing", "尚欠", "尚欠"), "c_side": ("Side", "方向", "方向"),
    "c_date": ("Date", "日期", "日期"),
    "hist_h": ("Market health score, last {n} sessions", "市場健康分數（最近 {n} 個交易日）", "市场健康分数（最近 {n} 个交易日）"),
    "hist_note": ("Dashed lines mark the Regime bands. Hover or use the arrow keys for each day’s value.",
                  "虛線是各級別的分界。把滑鼠移到圖上或用方向鍵看每日數值。",
                  "虚线是各级别的分界。把鼠标移到图上或用方向键看每日数值。"),
    "show_data": ("Show the data", "顯示數據", "显示数据"),
    "subs_h": ("11 sectors, 1-month return", "11 個板塊的 1 個月回報", "11 个板块的 1 个月回报"),
    "subs_note": ("Sector ETF returns; blue is up, red is down. Hover a bar for the 3-month return and the share of stocks above the 50-day average.",
                  "用板塊 ETF 計算；藍色是升，紅色是跌。把滑鼠移到橫條上，可看 3 個月回報和高於 50 日線的股票比例。",
                  "用板块 ETF 计算；蓝色是升，红色是跌。把鼠标移到横条上，可看 3 个月回报和高于 50 日线的股票比例。"),
    "c_group": ("Sector", "板塊", "板块"), "c_1m": ("1 month", "1 個月", "1 个月"), "c_3m": ("3 months", "3 個月", "3 个月"),
    "c_above": ("Above 50-day", "高於 50 日線", "高于 50 日线"), "c_top": ("vs S&P 500, 1 month", "1 個月相對標普", "1 个月相对标普"),
    "tl_h": ("Tonight’s timeline (Hong Kong time)", "今晚時間表（香港時間）", "今晚时间表（香港时间）"),
    "next_day": ("next day", "翌日", "翌日"),
    "sec_tip": ("{n} ({c}): 1M {a}% · 3M {b}% · vs S&P 500 {x}% · above 50-day {p}%",
                "{n}（{c}）：1 個月 {a}%，3 個月 {b}%，相對標普 {x}%，{p}% 股票高於 50 日線",
                "{n}（{c}）：1 个月 {a}%，3 个月 {b}%，相对标普 {x}%，{p}% 股票高于 50 日线"),
    "tl_none": ("No timeline for this session.", "這個交易日沒有時間表。", "这个交易日没有时间表。"),
    "c_hk": ("Hong Kong", "香港", "香港"), "c_et": ("New York", "美東", "美东"), "c_kind": ("Type", "類別", "类别"),
    "arch_h": ("Earlier briefs", "之前的簡報", "之前的简报"),
    "c_verdict": ("Call", "結論", "结论"), "c_brief": ("Full brief", "完整簡報", "完整简报"), "c_pre": ("Pre-open", "開市前", "开盘前"),
    "how_h": ("How the brief is built", "簡報怎樣產生", "简报怎样产生"),
    "how": ((
        "Scan the S&P 500, Nasdaq 100 and S&P 400 stocks, with their sectors and industry groups.",
        "Score the market from QQQ’s trend, breadth, risk appetite, volatility and rates, then set Regime A to E.",
        "Open or close the long, pilot and short gates; with a gate closed, its setups are listed for observation only.",
        "Grade every setup A or B with an 8-item checklist and work out an illustrative size from a fixed risk per unit.",
        "List no new setups just before earnings, and recalculate every parameter against pre-market prices before the open.",
    ), (
        "掃描標普 500、納指 100 和標普 400 的股票，連板塊和行業組別。",
        "按 QQQ 的趨勢、市場寬度、風險胃納、波動和利率計分，定出 A 至 E 級市況。",
        "決定多頭、試單和空頭閘門開或關；閘門關閉時，對應的形態只列作觀察。",
        "用八項清單把每個形態分成 A 級或 B 級，按固定每單位風險試算注碼。",
        "財報前不列出新形態；開市前系統再用盤前價重算每組參數。",
    ), (
        "扫描标普 500、纳指 100 和标普 400 的股票，连板块和行业组别。",
        "按 QQQ 的趋势、市场宽度、风险胃纳、波动和利率计分，定出 A 至 E 级市况。",
        "决定多头、试单和空头闸门开或关；闸门关闭时，对应的形态只列作观察。",
        "用八项清单把每个形态分成 A 级或 B 级，按固定每单位风险试算仓位。",
        "财报前不列出新形态；开盘前系统再用盘前价重算每组参数。",
    )),
    "dist_note": ("Price vs pivot = (close − pivot) ÷ pivot, the same figure as in the full brief. For longs a negative number means the price "
                  "has not crossed above the pivot; for shorts a positive number means it has not broken below it. The pre-market refresh uses "
                  "pre-market prices.",
                  "現價距觸發位 =（收市價 − 技術觸發位）÷ 技術觸發位，與完整簡報的數字相同。做多為負數代表未升穿觸發位；做空為正數代表未跌穿。"
                  "系統開市前更新改用盤前價。",
                  "现价距触发位 =（收盘价 − 技术触发位）÷ 技术触发位，与完整简报的数字相同。做多为负数代表未升穿触发位；做空为正数代表未跌穿。"
                  "系统开盘前更新改用盘前价。"),
    "demo_note": ("Share counts and amounts in the full brief start from a demonstration account of {a}; set your own figures at the top of the brief.",
                  "完整簡報內的股數和金額預設按示範戶口 {a} 試算，可在簡報頁頂改用自己的參數。",
                  "完整简报内的股数和金额默认按示范账户 {a} 试算，可在简报页顶改用自己的参数。"),
    "disclaimer": ("Research disclosure: everything here is calculated automatically by fixed rules and is the same for every reader; it does not take "
                   "anyone’s financial situation, objectives or risk tolerance into account. Position sizes are arithmetic from the figures each reader "
                   "enters. For research and education only; not investment advice, an offer or a solicitation, and not guaranteed to be accurate, "
                   "complete or timely. Past results, including the follow-up record, do not indicate future results.",
                   "研究聲明：本網站的全部內容由固定規則自動計算，所有讀者看到的內容相同，並不考慮任何人的財務狀況、投資目標或風險承受能力。"
                   "倉位試算只按讀者自行輸入的參數計算。內容只供研究和教育用途，不構成投資建議、要約或招攬，亦不保證準確、完整或及時。"
                   "過往表現（包括跟進紀錄）不代表將來表現。",
                   "研究声明：本网站的全部内容由固定规则自动计算，所有读者看到的内容相同，并不考虑任何人的财务状况、投资目标或风险承受能力。"
                   "仓位试算只按读者自行输入的参数计算。内容只供研究和教育用途，不构成投资建议、要约或招揽，亦不保证准确、完整或及时。"
                   "过往表现（包括跟进记录）不代表将来表现。"),
    "pro_h": ("Full report", "完整報告", "完整报告"),
    "pro_body": ("The full report adds the rule-matched setup tables, setup cards with charts, the watch list, the position-size simulator "
                 "and the follow-up record of earlier setups.",
                 "完整報告另外包括：符合規則的技術形態表、附圖的形態參數卡、觀察名單、倉位試算工具，以及之前名單的跟進紀錄。",
                 "完整报告另外包括：符合规则的技术形态表、附图的形态参数卡、观察名单、仓位试算工具，以及之前名单的跟进记录。"),
    "pro_cta": ("Subscription details coming soon", "訂閱詳情稍後公佈", "订阅详情稍后公布"),
    "sz_label": ("Position-size simulator", "倉位試算", "仓位试算"),
    "sz_equity": ("Account (USD)", "戶口資金（美元）", "账户资金（美元）"),
    "sz_risk": ("Base risk per unit (%)", "每單位基準風險（%）", "每单位基准风险（%）"),
    "sz_scale": ("Scale by Regime", "按 Regime 縮放", "按 Regime 缩放"),
    "sz_broker": ("Parameter format", "參數格式", "参数格式"),
    "sz_generic": ("Generic", "通用", "通用"), "sz_futu": ("Futu", "富途", "富途"), "sz_ibkr": ("IBKR", "IBKR", "IBKR"),
    "sz_note": ("Arithmetic from the figures you enter, not a recommended position. Settings are kept in this browser only.",
                "只按你輸入的參數作數學試算，不是建議的倉位。設定只存在這部裝置的瀏覽器。",
                "只按你输入的参数作数学试算，不是建议的仓位。设置只存在这台设备的浏览器。"),
    "sources": ("Data: Aggregated Delayed Market & Exchange Data", "數據來源：公開市場及交易所延遲數據整理", "数据来源：公开市场及交易所延迟数据整理"),
    "built": ("Page built {t} ET", "網頁產生於美東 {t}", "网页生成于美东 {t}"),
    "empty": ("No brief has been published yet. In GitHub, open Actions, choose “Daily pre-market brief” and press “Run workflow”.",
              "還未有簡報。在 GitHub 打開 Actions，選「Daily pre-market brief」，按「Run workflow」。",
              "还未有简报。在 GitHub 打开 Actions，选“Daily pre-market brief”，按“Run workflow”。"),
    "open_brief_short": ("Open", "打開", "打开"),
    "arch_more": ("{n} earlier briefs", "更早的 {n} 份簡報", "更早的 {n} 份简报"),
    "home": ("Home", "首頁", "首页"),
    "skip": ("Skip to today’s plan", "跳到今日計劃", "跳到今日计划"),
    "lang": ("Language", "語言", "语言"),
}
IDX = {"en": 0, "tc": 1, "sc": 2}
PUN = {"en": {"c": ", ", "p": ". ", "k": ": ", "o": " (", "x": ")"},
       "tc": {"c": "，", "p": "。", "k": "：", "o": "（", "x": "）"}}
PUN["sc"] = PUN["tc"]


def t(key, lang, **kw):
    s = L[key][IDX[lang]]
    return s.format(**kw) if kw else s


def e(x):
    return html.escape("" if x is None else str(x))


def fmt(x, nd=2, sign=False):
    if x is None:
        return "–"
    s = f"{x:+,.{nd}f}" if sign else f"{x:,.{nd}f}"
    return s.replace("-", "−")


def load(state):
    briefs = {}
    for p in sorted(glob.glob(os.path.join(state, "site", "briefs", "*", f"summary_{LANGS[0]}.json"))):
        run = os.path.basename(os.path.dirname(p))
        try:
            s = {lang: json.load(open(p.replace(f"_{LANGS[0]}.json", f"_{lang}.json"), encoding="utf-8")) for lang in LANGS}
        except (OSError, ValueError):
            continue
        briefs.setdefault(s[LANGS[0]]["brief_date"], []).append((run, s))
    pre = {}
    for p in sorted(glob.glob(os.path.join(state, "site", "preopen", "*", f"summary_{LANGS[0]}.json"))):
        run = os.path.basename(os.path.dirname(p))
        try:
            s = {lang: json.load(open(p.replace(f"_{LANGS[0]}.json", f"_{lang}.json"), encoding="utf-8")) for lang in LANGS}
        except (OSError, ValueError):
            continue
        pre.setdefault(s[LANGS[0]]["brief_date"], []).append((run, s))
    newest = lambda v: max(v, key=lambda rs: (rs[1][LANGS[0]].get("run_et", ""), rs[0]))   # noqa: E731
    latest = {d: newest(v) for d, v in briefs.items()}               # the last run of each brief date
    latest_pre = {d: newest(v) for d, v in pre.items()}
    hist = []
    path = os.path.join(state, "premarket_out", "score_history.csv")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                try:
                    hist.append((r["date"][:10], float(r["score"]), r.get("regime", "")))
                except (KeyError, ValueError):
                    pass
    return latest, latest_pre, hist


# ---------- the one bold element: the score on a reference-range bar, like a lab result ----------
def range_bar(s, lang):
    score, prev = s.get("score"), s.get("score_prev")
    segs = []
    for r in REG_ORDER:
        lo, hi = REG_BANDS[r]
        cur = "cur" if r == s["regime"] else ""
        segs.append(f'<div class="seg r{r} {cur}" style="flex:{hi - lo}"><span>{r}</span></div>')
    mk = ""
    if score is not None:
        mk += f'<div class="mark" style="left:{min(max(score, 0), 100):.1f}%"><b>{e(s.get("score_txt") or fmt(score, 0))}</b></div>'
    if prev is not None:
        mk += f'<div class="prevmark" style="left:{min(max(prev, 0), 100):.1f}%" title="{e(t("score_vs", lang, a=fmt(prev, 0), b=fmt(s.get("score_5"), 0)))}"></div>'
    return (f'<div class="range" role="img" aria-label="{e(t("score", lang))} {fmt(score, 0)} / 100, {e(t("regime", lang))} {e(s["regime"])}">'
            f'<div class="segs">{"".join(segs)}</div>{mk}</div>')


def gate(label, on, lang, word_on="open", word_off="closed", bad=False):
    state = "on" if on else "off"
    if on and bad:
        state = "warn"
    icon = ('<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3.5 8.5l3 3 6-7" /></svg>' if on else
            '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M4.5 4.5l7 7M11.5 4.5l-7 7" /></svg>')
    return f'<li class="gate {state}">{icon}<span>{e(label)}</span> <b>{e(t(word_on if on else word_off, lang))}</b></li>'


def score_chart(hist, lang, n=120):
    rows = hist[-n:]
    if len(rows) < 5:
        return ""
    W, H, l_, r_, t_, b_ = 760, 280, 52, 40, 22, 38
    pw, ph = W - l_ - r_, H - t_ - b_
    X = lambda i: l_ + pw * i / (len(rows) - 1)
    Y = lambda v: t_ + ph * (1 - v / 100)
    pts = " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, (_, v, _r) in enumerate(rows))
    grid = []
    for v in (25, 40, 55, 70):
        grid.append(f'<line class="band" x1="{l_}" x2="{W - r_}" y1="{Y(v):.1f}" y2="{Y(v):.1f}"/>')
    for v in (0, 25, 40, 55, 70, 100):
        grid.append(f'<text class="tick" x="{l_ - 6}" y="{Y(v) + 4:.1f}" text-anchor="end">{v}</text>')
    for r in REG_ORDER:
        lo, hi = REG_BANDS[r]
        grid.append(f'<text class="bandlab" x="{W - r_ + 8}" y="{Y((lo + hi) / 2) + 4:.1f}">{r}</text>')
    months, last = [], None
    for i, (d, _, _r) in enumerate(rows):
        if d[:7] != last:
            last = d[:7]
            if i > 3:
                months.append(f'<text class="tick" x="{X(i):.1f}" y="{H - 10}" text-anchor="middle">{d[:7]}</text>')
    i_end = len(rows) - 1
    end = (f'<circle class="dot" cx="{X(i_end):.1f}" cy="{Y(rows[-1][1]):.1f}" r="4.5"/>'
           f'<text class="endlab" x="{X(i_end) - 8:.1f}" y="{Y(rows[-1][1]) - 10:.1f}" text-anchor="end">{fmt(rows[-1][1], 0)}</text>')
    data = json.dumps([[d, round(v, 1), rg] for d, v, rg in rows])
    return (f'<figure class="chart" data-kind="line"><svg viewBox="0 0 {W} {H}" tabindex="0" role="img" '
            f'aria-label="{e(t("hist_h", lang, n=len(rows)))}"><line class="axis" x1="{l_}" x2="{W - r_}" y1="{Y(0):.1f}" y2="{Y(0):.1f}"/>'
            + "".join(grid) + "".join(months)
            + f'<polyline class="line" points="{pts}"/>{end}<line class="cross" x1="0" x2="0" y1="{t_}" y2="{t_ + ph}" visibility="hidden"/>'
            f'<circle class="hov" r="5" visibility="hidden"/></svg><div class="tip" hidden></div>'
            f'<script type="application/json" class="pts">{data}</script>'
            f'<script type="application/json" class="geo">{json.dumps({"l": l_, "pw": pw, "t": t_, "ph": ph, "W": W})}</script></figure>')


def subs_chart(subs, lang):
    if not subs:
        return ""
    vals = [s["r21"] for s in subs if s["r21"] is not None]
    if not vals:
        return ""
    lim = max(5.0, max(abs(v) for v in vals))
    rows = []
    for s in subs:
        v = s["r21"] or 0.0
        w = abs(v) / lim * 50
        side = "pos" if v >= 0 else "neg"
        left = 50 if v >= 0 else 50 - w
        tip = t("sec_tip", lang, n=s["name"], c=s["code"], a=fmt(v, 1, True), b=fmt(s["r63"], 1, True), x=fmt(s["ex21"], 1, True), p=fmt(s["pct50"], 0))
        rows.append(f'<div class="hrow" tabindex="0" data-tip="{e(tip)}"><span class="hname">{e(s["name"])} <small>{e(s["code"])}</small></span>'
                    f'<span class="htrack"><span class="zero"></span><span class="hbar {side}" style="left:{left:.2f}%;width:{w:.2f}%"></span></span>'
                    f'<span class="hval">{fmt(v, 1, True)}%</span></div>')
    table = "".join(f'<tr><td>{e(s["name"])} <small>{e(s["code"])}</small></td><td class="n">{fmt(s["r21"], 1, True)}%</td><td class="n">{fmt(s["r63"], 1, True)}%</td>'
                    f'<td class="n">{fmt(s["pct50"], 0)}%</td><td class="n">{fmt(s["ex21"], 1, True)}%</td></tr>' for s in subs)
    return (f'<div class="hbars" data-kind="bars">{"".join(rows)}<div class="tip" hidden></div></div>'
            f'<details class="data"><summary>{e(t("show_data", lang))}</summary><div class="scroll"><table><thead><tr><th>{e(t("c_group", lang))}</th>'
            f'<th class="n">{e(t("c_1m", lang))}</th><th class="n">{e(t("c_3m", lang))}</th><th class="n">{e(t("c_above", lang))}</th>'
            f'<th class="n">{e(t("c_top", lang))}</th></tr></thead><tbody>{table}</tbody></table></div></details>')


def picks_table(picks, lang, watch=False):
    """watch=True: the gate is closed, so the trigger is only an alert price and the row is shown muted."""
    body = "".join(
        f'<tr><th scope="row"><b>{e(p["ticker"])}</b><small>{e(p["name"])}</small></th><td class="side">{e(p["side"])}'
        + (f'<small><span class="tagw">{e(t("watch_tag", lang))}</span></small>' if watch else f'<small>{e(p["tier"])}</small>') + '</td>'
        f'<td class="wrap">{e(p["setup"])}<small>{e(p["sector"])}</small></td><td class="n">{fmt(p["trigger"])}</td><td class="n">{fmt(p["stop"])}</td>'
        f'<td class="n">{fmt(p["risk"], 1)}%</td><td class="n">{fmt(p["dist"], 1, True)}%</td><td class="n">{e(p["earn"]) or "–"}</td></tr>'
        + (f'<tr class="why"><td colspan="8"><div class="whyt"><span class="quiet">{e(t("c_why", lang))}{PUN[lang]["k"]}</span>{e(p["why"])}</div></td></tr>' if p.get("why") else "")
        for p in picks)
    return (f'<div class="scroll"><table class="picks{" watch" if watch else ""}"><thead><tr><th>{e(t("c_ticker", lang))}</th><th>{e(t("c_side", lang))}</th>'
            f'<th>{e(t("c_setup", lang))}</th><th class="n">{e(t("c_alert" if watch else "c_trigger", lang))}</th><th class="n">{e(t("c_stop", lang))}</th>'
            f'<th class="n">{e(t("c_risk", lang))}</th><th class="n">{e(t("c_dist", lang))}</th><th class="n">{e(t("c_cat", lang))}</th></tr></thead>'
            f'<tbody>{body}</tbody></table></div>')


def split_picks(s, s_tc):
    """Picks that can become orders today, and picks whose gate is closed. Older summaries have no live flag:
    there the brief's own label decides (預備 = gate closed)."""
    tc = s_tc.get("picks", [])
    live, watch = [], []
    for i, p in enumerate(s.get("picks", [])):
        ok = p["live"] if "live" in p else (tc[i].get("tier") != "預備" if i < len(tc) else True)
        (live if ok else watch).append(p)
    return live, watch


def side_ok(s, s_tc, side_tc):
    """Is this side's gate open today (the brief's long_ok / short gate)?"""
    key = "long_ok" if side_tc == "做多" else "short_ok"
    if key in s:
        return bool(s[key])
    mine = [p for p in s_tc.get("picks", []) if p.get("side") == side_tc]
    if mine:
        return mine[0].get("tier") != "預備"
    g = s["gates"]
    return bool(g["long"] or g["pilot"]) if side_tc == "做多" else bool(g["short"])


def side_plan(s, s_tc, watch_tc, lang):
    """Two lines, long and short, saying plainly what may be done today."""
    rows = []
    for side_tc, lab, n, closed in (("做多", "side_long", s.get("n_long", 0), "sp_closed_l"), ("做空", "side_short", s.get("n_short", 0), "sp_closed_s")):
        k = sum(1 for p in watch_tc if p.get("side") == side_tc)
        if side_ok(s, s_tc, side_tc):
            on, txt = n > 0, t("sp_max1" if n == 1 else "sp_max", lang, n=n) if n > 0 else t("sp_zero", lang)
        else:
            on, txt = False, t(closed, lang) + (PUN[lang]["c"] + t("sp_watch", lang, k=k) if k else "")
        rows.append(f'<li class="{"on" if on else "off"}"><b>{e(t(lab, lang))}</b><span>{e(txt)}</span></li>')
    return f'<ul class="sideplan">{"".join(rows)}</ul>'


def bgrade_table(rows, lang):
    if not rows:
        return ""
    body = "".join(f'<tr><th scope="row"><b>{e(p["ticker"])}</b><small>{e(p["sector"])}</small></th><td class="wrap">{e(p["setup"])}</td>'
                   f'<td class="n">{fmt(p["dist"], 1, True)}%</td><td class="wrap">{e(p["missing"] or p["why"]) or "–"}</td></tr>' for p in rows)
    return (f'<details class="near"><summary>{e(t("b_h", lang))}{PUN[lang]["o"]}{len(rows)}{PUN[lang]["x"]}</summary><div class="scroll"><table class="bgrade"><thead><tr><th>{e(t("c_ticker", lang))}</th><th>{e(t("c_setup", lang))}</th>'
            f'<th class="n">{e(t("c_dist", lang))}</th><th>{e(t("c_missing", lang))}</th></tr></thead><tbody>{body}</tbody></table></div></details>')


def timeline_list(tl, lang, tl_tc=None):
    if not tl:
        return f'<p class="quiet">{e(t("tl_none", lang))}</p>'
    tl_tc = tl_tc or tl                                          # older summaries have no kind code: use the Chinese kind
    code = [x.get("code") or KIND.get(y.get("kind"), "other") for x, y in zip(tl, tl_tc)]
    items = "".join(f'<li class="k-{e(c)}"><time>{e(x["hk"])}' + (f'<small>{e(t("next_day", lang))}</small>' if x.get("next") else "")
                    + f'</time><span class="et">{e(t("c_et", lang))} {e(x["et"])}</span><span class="what">{e(x["what"])}</span>'
                    f'<span class="kind">{e(x["kind"])}</span></li>' for x, c in zip(tl, code))
    return f'<ol class="timeline">{items}</ol>'


KIND = {"我": "me", "系統": "me", "市場": "mkt", "數據": "data", "財報": "earn"}


def archive_table(latest, latest_pre, lang, up):
    rows = []
    for d in sorted(latest, reverse=True):
        run, S = latest[d]
        x = S[lang]
        link = f'<a href="{up}briefs/{e(run)}/{lang}.html">{e(t("open_brief_short", lang))}</a>'
        pre = ""
        if d in latest_pre:
            prun, _ = latest_pre[d]
            pre = f'<a href="{up}preopen/{e(prun)}/{lang}.html">{e(t("c_pre", lang))}</a>'
        rows.append(f'<tr><td class="n">{e(d)}</td><td class="side"><span class="chip r{e(x["regime"])}">{e(x["regime"])}</span> {e(x["regime_name"])}</td>'
                    f'<td class="n">{fmt(x["score"], 0)}</td><td class="wrap">{e(x["verdict"])}</td><td class="links">{link}</td><td class="pre">{pre}</td></tr>')
    head = (f'<thead><tr><th class="n">{e(t("c_date", lang))}</th><th>{e(t("regime", lang))}</th>'
            f'<th class="n">{e(t("score", lang))}</th><th>{e(t("c_verdict", lang))}</th><th>{e(t("c_brief", lang))}</th><th>{e(t("c_pre", lang))}</th></tr></thead>')
    out = f'<div class="scroll"><table class="archive">{head}<tbody>{"".join(rows[:ARCHIVE_SHOWN])}</tbody></table></div>'
    if len(rows) > ARCHIVE_SHOWN:
        out += (f'<details class="older"><summary>{e(t("arch_more", lang, n=len(rows) - ARCHIVE_SHOWN))}</summary>'
                f'<div class="scroll"><table class="archive">{head}<tbody>{"".join(rows[ARCHIVE_SHOWN:])}</tbody></table></div></details>')
    return out


def telegram_banner(lang):
    """A slim banner below the hero card that leads to the free Telegram channel; nothing when TELEGRAM_PUBLIC_URL is not set."""
    url = env("TELEGRAM_PUBLIC_URL", "")
    if not re.fullmatch(r"https://(t\.me|telegram\.me)/[A-Za-z0-9_+/\-]+", url):
        return ""
    text = t("tg_text", lang, a=env("SOCIAL_DAILY_HKT", "20:15"), b=env("SOCIAL_PREMARKET_HKT", "21:47"))
    return (f'<aside class="tgbar"><span>{e(text)}</span><a class="tgbtn" href="{e(url)}" rel="noopener">{e(t("tg_cta", lang))} →</a></aside>')


def analytics_tag():
    """Cloudflare Web Analytics (cookie-free), only when CF_ANALYTICS_TOKEN is set."""
    token = env("CF_ANALYTICS_TOKEN", "")
    if not re.fullmatch(r"[A-Za-z0-9]{16,64}", token):
        return ""
    return ('<script defer src="https://static.cloudflareinsights.com/beacon.min.js" data-cf-beacon=\'{"token":"' + token + '"}\'></script>')


def page(lang, latest, latest_pre, hist, mode="full"):
    """mode "full": the whole home page. mode "free": the public teaser of BUILD_MODE=freemium_split
    (score, grade, score chart, sectors, calendar and a box describing the full report; no setups, no links to full briefs)."""
    free = mode == "free"
    up = "../" if LANG_DIR[lang] else ""
    nav = "".join(f'<a href="{up}{LANG_DIR[lg]}index.html" hreflang="{HTML_LANG[lg]}"' + (' aria-current="page"' if lg == lang else "")
                  + f">{LANG_NAME[lg]}</a>" for lg in LANGS) if len(LANGS) > 1 else ""
    head = (f'<!doctype html><html lang="{HTML_LANG[lang]}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{e(t("site", lang))}</title><meta name="description" content="{e(t("tagline", lang))}">'
            '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
            '<link href="https://fonts.googleapis.com/css2?family=Atkinson+Hyperlegible+Next:wght@400;600;800&display=swap" rel="stylesheet">'
            f'<link rel="stylesheet" href="{up}assets/site.css?v={ASSET_VER}"></head><body>'
            f'<a class="skip" href="#plan">{e(t("skip", lang))}</a>'
            f'<header class="top"><div class="wrap"><a class="brand" href="{up}{LANG_DIR[lang]}index.html">{e(t("site", lang))}</a>'
            f'<nav aria-label="{e(t("lang", lang))}">{nav}</nav></div></header><main class="wrap">')
    foot = (f'</main><footer class="wrap"><p>{e(t("tagline", lang))}</p><p class="disc">{e(t("disclaimer", lang))}</p><p class="quiet">{e(t("sources", lang))}</p>'
            f'<p class="quiet">{e(t("built", lang, t=f"{now_et():%Y-%m-%d %H:%M}"))}</p></footer>'
            f'<script src="{up}assets/site.js?v={ASSET_VER}" defer></script>{analytics_tag()}</body></html>')
    if not latest:
        return head + f'<section class="empty"><h1>{e(t("site", lang))}</h1><p>{e(t("tagline", lang))}</p><p>{e(t("empty", lang))}</p></section>' + foot
    d = max(latest)
    run, S = latest[d]
    s = S[lang]
    g, p = s["gates"], PUN[lang]
    live, watch = split_picks(s, S["tc"])
    watch_tc = split_picks(S["tc"], S["tc"])[1]
    pre_btn = f'<span class="btn ghost" aria-disabled="true">{e(t("no_pre", lang))}</span>'
    if d in latest_pre:
        prun, P = latest_pre[d]
        pre_btn = (f'<a class="btn ghost" href="{up}preopen/{e(prun)}/{lang}.html">{e(t("open_pre", lang))}'
                   f'<small>{e(t("pre_time", lang, t=P[lang]["run_et"][11:]))}</small></a>')
    stats = [(t("score", lang), s.get("score_txt") or f'{fmt(s["score"], 0)}',
              t("score_vs", lang, a=s.get("score_prev_txt") or fmt(s["score_prev"], 0), b=s.get("score_5_txt") or fmt(s["score_5"], 0))),
             (t("new_pos", lang), t("n_long_short", lang, a=s["n_long"], b=s["n_short"]), ""),
             (t("above50", lang), f'{fmt(s["pct50"], 0)}%', ""),
             (t("bo", lang), "–" if s["bo_follow"] is None else f'{fmt(s["bo_follow"], 0)}%', ""),
             (t("vix", lang), fmt(s["vix"], 1), ""),
             (t("anchor", lang), fmt(s["anchor_close"]), ""),
             (t("universe", lang), f'{s["universe"]:,}', "")]
    stat_html = "".join(f'<div><dt>{e(a)}</dt><dd>{e(b)}' + (f'<small>{e(c)}</small>' if c else "") + "</dd></div>" for a, b, c in stats)
    acct = env("DEMO_ACCOUNT", "100000")
    try:
        acct = f"${float(acct):,.0f}"
    except ValueError:
        acct = "$100,000"
    body = (
        f'<section class="hero r{e(s["regime"])}" aria-labelledby="verdict">'
        f'<div class="tag" aria-hidden="true"><span class="letter">{e(s["regime"])}</span><span class="tagname">{e(s["regime_name"])}</span></div>'
        f'<div class="herotext"><p class="when">{e(t("brief_for", lang))} <b>{e(s["brief_date"])}</b>{p["c"]}{e(t("data_to", lang))} {e(s["asof"])}{p["p"]}'
        f'{e(t("updated", lang))} {e(s["run_et"][11:])} ET{p["o"]}{e(t("hk", lang))} {e(s["run_hk"][11:])}{p["x"]}{p["p"].strip()}</p>'
        f'<h1 id="verdict">{e(s["verdict"] or s["side"])}</h1>'
        f'<p class="sub">{e(t("regime", lang))} {e(s["regime"])} {e(s["regime_name"])}'
        f'{p["k"]}{e(s["side"])}{p["p"]}{e(t("cycle", lang))}{p["k"]}{e(s["cycle"])}{p["p"].strip()}</p>'
        + (f'<p class="holdp"><span class="hold">{e(t("held", lang, s=s.get("score_txt") or fmt(s["score"], 0), r=s.get("regime_raw", ""), g=s["regime"]))}</span></p>'
           if s.get("regime_held") else "")
        + range_bar(s, lang) + f'<p class="small quiet">{e(t("range_note", lang))}</p>'
        f'<ul class="gates">{gate(t("gate_long", lang), g["long"], lang)}{gate(t("gate_pilot", lang), g["pilot"], lang)}'
        f'{gate(t("gate_short", lang), g["short"], lang, bad=True)}{gate(t("oversold", lang), g["oversold"], lang, "yes", "no", bad=True)}</ul>'
        + (f'<p class="event">{e(t("event_day", lang))}</p>' if s.get("event_day") else "")
        + ("" if free else f'<div class="actions"><a class="btn" href="{up}briefs/{e(run)}/{lang}.html">{e(t("open_brief", lang))}</a>{pre_btn}</div>')
        + f'</div></section>'
        f'{telegram_banner(lang)}<dl class="stats">{stat_html}</dl>'
        + (f'<section id="plan" class="pro"><h2>{e(t("pro_h", lang))}</h2><p>{e(t("pro_body", lang))}</p>'
           f'<p><span class="btn ghost" aria-disabled="true">{e(t("pro_cta", lang))}</span></p></section>' if free else
        f'<section id="plan" class="grid2"><div><h2>{e(t("plan_h", lang))}</h2>{side_plan(s, S["tc"], watch_tc, lang)}'
        f'<h3>{e(t("live_h", lang))}</h3>'
        + (picks_table(live, lang) if live else f'<p class="quiet">{e(t("live_none" if s["picks"] else "picks_none", lang))}</p>')
        + (f'<h3>{e(t("watch_h", lang))}</h3><p class="small quiet">{e(t("watch_note", lang))}</p>{picks_table(watch, lang, watch=True)}' if watch else "")
        + f'{bgrade_table(s["bgrade"], lang)}<p class="small quiet">{e(t("dist_note", lang))}</p>'
        f'<p class="small quiet">{e(t("demo_note", lang, a=acct))}</p></div>'
        f'<aside><h2>{e(t("play_h", lang))}</h2><ul class="play">' + "".join(f"<li>{e(x)}</li>" for x in s["play"]) + "</ul></aside></section>")
        + f'<section class="grid2 tlsec"><div><h2>{e(t("tl_h", lang))}</h2>{timeline_list(s.get("timeline", []), lang, S["tc"].get("timeline", []))}</div>'
        f'<div><h2>{e(t("subs_h", lang))}</h2><p class="small quiet">{e(t("subs_note", lang))}</p>{subs_chart(s.get("sectors", []), lang)}</div></section>')
    sc = score_chart(hist, lang)
    if sc:
        n = min(120, len(hist))
        held = lambda v, rg: rg in REG_BANDS and not (REG_BANDS[rg][0] <= v < REG_BANDS[rg][1] or (rg == "A" and v >= 70))   # noqa: E731
        rows = "".join(f'<tr><td class="n">{e(d_)}</td><td class="n">{fmt(v, 1)}</td><td>{e(rg)}{"＊" if held(v, rg) else ""}</td></tr>'
                       for d_, v, rg in reversed(hist[-n:]))
        any_held = any(held(v, rg) for _, v, rg in hist[-n:])
        body += (f'<section><h2>{e(t("hist_h", lang, n=n))}</h2>{sc}<p class="small quiet">{e(t("hist_note", lang))}</p>'
                 f'<details class="data"><summary>{e(t("show_data", lang))}</summary><div class="scroll"><table><thead><tr>'
                 f'<th class="n">{e(t("c_date", lang))}</th><th class="n">{e(t("score", lang))}</th><th>{e(t("regime", lang))}</th></tr></thead>'
                 f'<tbody>{rows}</tbody></table></div>'
                 + (f'<p class="small quiet">{e(t("hist_held", lang))}</p>' if any_held else "") + '</details></section>')
    if not free:
        body += f'<section><h2>{e(t("arch_h", lang))}</h2>{archive_table(latest, latest_pre, lang, up)}</section>'
    body += f'<section class="how"><h2>{e(t("how_h", lang))}</h2><ol>' + "".join(f"<li>{e(x)}</li>" for x in L["how"][IDX[lang]]) + "</ol></section>"
    return head + body + foot


CSS = r"""
:root{--paper:#ffffff;--panel:#ffffff;--ink:#1d2a2e;--ink2:#574f43;--muted:#7a6f5f;--rule:#eadcb6;--brand:#0b6574;--brand-ink:#ffffff;
--rA:#13753f;--rB:#3f7f24;--rC:#9a6200;--rD:#b4501c;--rE:#b03030;
--tA:#dff1e6;--tB:#e7f1dc;--tC:#f6ecd5;--tD:#f8e3d6;--tE:#f6dddd;--line:#2a78d6;--pos:#2a78d6;--neg:#e34948;--grid:#ece2c8;--focus:#0b6574}
@media (prefers-color-scheme:dark){:root{--paper:#10191c;--panel:#162327;--ink:#e8f0f0;--ink2:#b7c7cb;--muted:#8fa3a8;--rule:#2b3b40;--brand:#5fc0cf;--brand-ink:#0b1d21;
--rA:#4cc47f;--rB:#8fc46a;--rC:#e0a541;--rD:#ec8a55;--rE:#ec6b6b;--tA:#16362a;--tB:#22341b;--tC:#3a2f17;--tD:#3d2618;--tE:#3d1e1e;--line:#3987e5;--pos:#3987e5;--neg:#e66767;--grid:#2c2c2a;--focus:#5fc0cf}}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--paper);color:var(--ink);font:400 16px/1.55 "Atkinson Hyperlegible Next","Atkinson Hyperlegible",system-ui,-apple-system,"Segoe UI",sans-serif}
html[lang=zh-Hant] body{font-family:"Atkinson Hyperlegible Next",system-ui,-apple-system,"PingFang TC","Noto Sans TC","Microsoft JhengHei",sans-serif}
html[lang=zh-Hans] body{font-family:"Atkinson Hyperlegible Next",system-ui,-apple-system,"PingFang SC","Noto Sans SC","Microsoft YaHei",sans-serif}
a{color:var(--brand)}
a:focus-visible,summary:focus-visible,[tabindex]:focus-visible,.btn:focus-visible{outline:3px solid var(--focus);outline-offset:3px;border-radius:4px}
.wrap{max-width:1120px;margin:0 auto;padding:0 20px}
.tgbar{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px 16px;margin-top:14px;padding:10px 16px;border:1px solid var(--rule);border-left:4px solid var(--brand);border-radius:10px;background:var(--panel);font-size:15px;line-height:1.4}
.tgbtn{font-weight:700;text-decoration:none;white-space:nowrap;color:var(--brand)}.tgbtn:hover{text-decoration:underline}
.holdp{margin:-4px 0 10px}
.hold{display:inline-block;margin:0;padding:1px 9px;border:1px solid currentColor;border-radius:999px;font-size:.82em;font-weight:600;line-height:1.5}
.skip{position:absolute;left:-999px;top:8px}.skip:focus{left:12px;background:var(--panel);padding:6px 10px;z-index:9}
.top{border-bottom:1px solid var(--rule);background:var(--panel)}
.top .wrap{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px 16px;min-height:56px;padding-top:6px;padding-bottom:6px}
.brand{font-weight:800;font-size:17px;color:var(--ink);text-decoration:none;letter-spacing:-.01em}
.top nav{display:inline-flex;background:var(--paper);border:1px solid var(--rule);border-radius:999px;padding:3px}
.top nav a{text-decoration:none;color:var(--ink2);font-size:15px;padding:6px 14px;border-radius:999px;min-height:32px;display:inline-flex;align-items:center}
.top nav a:hover{color:var(--ink)}
.top nav a[aria-current=page]{background:var(--brand);color:var(--brand-ink);font-weight:600}
details.older{margin-top:14px}details.older summary{cursor:pointer;color:var(--brand);font-weight:600;padding:6px 0}
main{padding-bottom:24px}
h1{font-size:clamp(26px,3.4vw,38px);line-height:1.18;font-weight:800;letter-spacing:-.015em;margin:.2em 0 .35em;max-width:26ch}
html[lang^=zh] h1{max-width:20em;letter-spacing:0}
h2{font-size:22px;line-height:1.3;font-weight:800;margin:0 0 12px;letter-spacing:-.01em}
h3{font-size:16px;font-weight:600;margin:20px 0 8px}
section{margin-top:44px}
p{margin:.4em 0}
.small{font-size:14px}.quiet{color:var(--ink2)}
.hero{display:grid;grid-template-columns:184px 1fr;gap:32px;margin-top:28px;padding:28px;border-radius:14px;background:var(--panel);border:1px solid var(--rule)}
.hero .tag{border-radius:12px;display:flex;flex-direction:column;align-items:center;justify-content:center;aspect-ratio:1/1.15;color:#fff;align-self:start}
.hero.rA .tag{background:var(--rA)}.hero.rB .tag{background:var(--rB)}.hero.rC .tag{background:var(--rC)}.hero.rD .tag{background:var(--rD)}.hero.rE .tag{background:var(--rE)}
@media (prefers-color-scheme:dark){.hero .tag{color:#0b1d21}}
.letter{font-size:112px;font-weight:800;line-height:1}
.tagname{font-size:16px;font-weight:600;margin-top:2px;text-align:center;padding:0 8px}
.when{color:var(--ink2);font-size:15px}
.sub{font-size:17px;color:var(--ink2)}
.range{position:relative;margin:22px 0 6px;padding-top:30px}
.segs{display:flex;gap:2px;height:14px}
.seg{position:relative;border-radius:3px;opacity:.38}
.seg span{position:absolute;top:18px;left:50%;transform:translateX(-50%);font-size:13px;color:var(--ink2)}
.seg.cur{opacity:1}.seg.cur span{color:var(--ink);font-weight:800}
.rA{--c:var(--rA)}.rB{--c:var(--rB)}.rC{--c:var(--rC)}.rD{--c:var(--rD)}.rE{--c:var(--rE)}
.seg{background:var(--c)}
.mark{position:absolute;top:0;transform:translateX(-50%);display:flex;flex-direction:column;align-items:center}
.mark b{font-size:20px;line-height:1;font-weight:800}
.mark::after{content:"";width:3px;height:26px;background:var(--ink);border-radius:2px;margin-top:2px}
.prevmark{position:absolute;top:28px;width:9px;height:9px;border-radius:50%;border:2px solid var(--ink2);background:var(--panel);transform:translate(-50%,0)}
.range + p{margin-top:26px}
.gates{list-style:none;padding:0;margin:16px 0 0;display:flex;flex-wrap:wrap;gap:8px 18px}
.gate{display:flex;align-items:center;gap:6px;font-size:15px}
.gate svg{width:18px;height:18px;fill:none;stroke-width:2.2;stroke-linecap:round;stroke-linejoin:round;border-radius:50%;padding:2px}
.gate.on svg{stroke:#fff;background:var(--rA)}.gate.off svg{stroke:var(--ink2);background:var(--rule)}.gate.warn svg{stroke:#fff;background:var(--rD)}
.gate.off b{color:var(--ink2);font-weight:600}
.event{margin-top:12px;font-weight:600;color:var(--rC)}
.actions{display:flex;flex-wrap:wrap;gap:12px;margin-top:22px}
.btn{display:inline-flex;flex-direction:column;justify-content:center;min-height:48px;padding:10px 18px;border-radius:10px;background:var(--brand);color:var(--brand-ink);font-weight:600;text-decoration:none}
.btn small{font-weight:400;font-size:13px;opacity:.85}
.btn.ghost{background:transparent;color:var(--brand);border:1.5px solid var(--brand)}
.btn[aria-disabled=true]{color:var(--ink2);border-color:var(--rule);font-weight:400}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:0;margin:20px 0 0;border-top:1px solid var(--rule);border-bottom:1px solid var(--rule)}
.stats div{padding:14px 16px 14px 0}
.stats dt{font-size:14px;color:var(--ink2)}
.stats dd{margin:2px 0 0;font-size:22px;font-weight:800}
.stats dd small{display:block;font-size:13px;font-weight:400;color:var(--ink2)}
.grid2{display:grid;grid-template-columns:minmax(0,1.6fr) minmax(0,1fr);gap:40px}
.play{margin:0;padding-left:20px}.play li{margin:0 0 10px}
.scroll{overflow-x:auto;-webkit-overflow-scrolling:touch}
table{border-collapse:collapse;width:100%;font-size:15px;font-variant-numeric:tabular-nums}
th,td{text-align:left;vertical-align:top;padding:9px 12px 9px 0;border-bottom:1px solid var(--rule)}
thead th{font-size:13px;font-weight:600;color:var(--ink2);border-bottom:1.5px solid var(--ink2);white-space:nowrap}
tbody th{font-weight:400;white-space:nowrap}
td small,th small{display:block;font-size:13px;color:var(--ink2)}
.n{text-align:right;white-space:nowrap}
td.wrap{min-width:180px}
.picks tbody th b{font-size:17px}
table.picks{min-width:600px}table.bgrade{min-width:520px}table.archive{min-width:680px}
td.links,td.links a,td.pre{white-space:nowrap}td.side{white-space:nowrap}
.chip{display:inline-block;min-width:22px;text-align:center;border-radius:5px;font-weight:800;color:#fff;background:var(--c);padding:0 5px}
@media (prefers-color-scheme:dark){.chip{color:#0b1d21}}
.archive td.links a{margin-right:8px}
.timeline{list-style:none;margin:0;padding:0;border-left:2px solid var(--rule);margin-left:6px}
.timeline li{position:relative;display:grid;grid-template-columns:86px 1fr auto;gap:2px 12px;padding:9px 0 9px 16px}
.timeline li::before{content:"";position:absolute;left:-7px;top:15px;width:12px;height:12px;border-radius:50%;background:var(--panel);border:2px solid var(--muted)}
.timeline li.k-me::before{background:var(--brand);border-color:var(--brand)}
.timeline li.k-mkt::before{border-color:var(--ink)}
.timeline li.k-earn::before{border-color:var(--rC)}
.timeline time{font-weight:800;font-variant-numeric:tabular-nums;font-size:17px}
.timeline time small{font-weight:400;color:var(--ink2);font-size:13px;margin-left:6px}
.timeline .et{grid-column:1;grid-row:2;color:var(--muted);font-size:13px;font-variant-numeric:tabular-nums;white-space:nowrap}
.timeline .what{grid-column:2;grid-row:1/3;align-self:center}
.timeline .kind{grid-column:3;grid-row:1/3;align-self:center;font-size:13px;color:var(--ink2);border:1px solid var(--rule);border-radius:999px;padding:1px 9px;white-space:nowrap}
.timeline li.k-me .what{font-weight:600}
table.picks tr.why td{padding-top:0;font-size:14px;color:var(--ink2);border-top:0}
details.near{margin:20px 0 8px}details.near summary{font-size:16px;font-weight:600;cursor:pointer}details.near[open] summary{margin-bottom:8px}
.sideplan{list-style:none;margin:0 0 6px;padding:0;display:grid;gap:8px}
.sideplan li{display:flex;gap:14px;align-items:baseline;padding:9px 14px;border:1px solid var(--rule);border-radius:8px}
.sideplan li b{flex:none;min-width:3em}
.sideplan li.on{border-color:var(--brand);box-shadow:inset 4px 0 0 var(--brand)}
.sideplan li.on span{font-weight:600}
.sideplan li.off{color:var(--ink2)}
table.picks.watch tbody th b{font-size:16px;font-weight:600;color:var(--ink2)}
table.picks.watch td,table.picks.watch tbody th small{color:var(--ink2)}
.tagw{display:inline-block;margin-top:2px;font-size:12px;line-height:1.5;border:1px solid var(--muted);border-radius:999px;padding:0 8px;color:var(--ink2)}
.whyt{position:sticky;left:0;max-width:calc(100vw - 40px)}
table.picks tr:has(+ tr.why) > *{border-bottom:0}
.hname small{color:var(--muted);font-size:12px}
.chart{margin:0;position:relative}
.chart svg{width:100%;height:auto;display:block;outline:none}
.chart .axis{stroke:var(--muted);stroke-width:1}
.chart .band{stroke:var(--grid);stroke-width:1;stroke-dasharray:4 4}
@media (prefers-color-scheme:dark){.chart .band{stroke:#3a4a4f}}
.chart .tick{font-size:12px;fill:var(--muted)}
.chart .bandlab{font-size:13px;font-weight:800;fill:var(--ink2)}
.chart .line{fill:none;stroke:var(--line);stroke-width:2;stroke-linejoin:round;stroke-linecap:round}
.chart .dot,.chart .hov{fill:var(--line);stroke:var(--panel);stroke-width:2}
.chart .endlab{font-size:14px;font-weight:800;fill:var(--ink)}
.chart .cross{stroke:var(--muted);stroke-width:1}
.tip{position:absolute;pointer-events:none;background:var(--panel);border:1px solid var(--rule);border-radius:8px;padding:6px 10px;font-size:14px;box-shadow:0 2px 8px rgba(0,0,0,.12);white-space:nowrap;z-index:2}
.tip b{display:block;font-size:16px}
.hbars{position:relative;margin-top:8px}
.hrow{display:grid;grid-template-columns:minmax(96px,132px) 1fr 60px;align-items:center;gap:12px;padding:5px 0;outline:none}
.hname{font-size:15px}
.htrack{position:relative;height:18px}
.zero{position:absolute;left:50%;top:-4px;bottom:-4px;width:1px;background:var(--muted)}
.hbar{position:absolute;top:0;height:18px;border-radius:0 4px 4px 0}
.hbar.neg{border-radius:4px 0 0 4px;background:var(--neg)}.hbar.pos{background:var(--pos)}
.hrow:hover .hbar,.hrow:focus-visible .hbar{filter:brightness(1.12)}
.hval{text-align:right;font-variant-numeric:tabular-nums;font-size:15px}
details.data{margin-top:10px}details.data summary{cursor:pointer;color:var(--brand);font-size:15px}
.how ol{padding-left:22px;max-width:70ch}.how li{margin-bottom:8px}
.empty{margin:60px 0;max-width:60ch}
footer{border-top:1px solid var(--rule);margin-top:56px;padding-top:18px;padding-bottom:40px;font-size:14px;max-width:1120px}
footer p{max-width:80ch}
@media (max-width:820px){
 .hero{grid-template-columns:1fr;gap:18px;padding:20px}
 .hero .tag{flex-direction:row;aspect-ratio:auto;justify-content:flex-start;gap:14px;padding:10px 16px;width:auto}
 .letter{font-size:56px}.tagname{font-size:17px;text-align:left}
 .grid2{grid-template-columns:minmax(0,1fr);gap:28px}
 .hrow{grid-template-columns:108px 1fr 56px;gap:8px}
 nav a{margin-left:10px}
}
@media (max-width:600px){
 .chart .tick{font-size:22px}.chart .bandlab{font-size:22px}.chart .endlab{font-size:26px}
 .chart .line{stroke-width:3.5}.chart .axis,.chart .cross{stroke-width:2}
}
@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}
.pro{border:1px solid var(--rule);border-radius:10px;padding:16px 20px;margin:28px 0}
.pro h2{margin-top:0}
footer .disc{font-size:13px;line-height:1.6;color:var(--ink2)}
"""

JS = r"""
(function(){
  function place(tip, box, x, y){
    var w = tip.offsetWidth, W = box.clientWidth;
    tip.style.left = Math.max(0, Math.min(W - w, x - w / 2)) + 'px';
    tip.style.top = Math.max(0, y - tip.offsetHeight - 14) + 'px';
  }
  function show(tip, head, rest){
    tip.textContent = '';
    var b = document.createElement('b'); b.textContent = head; tip.appendChild(b);
    var s = document.createElement('span'); s.textContent = rest; tip.appendChild(s);
    tip.hidden = false;
  }
  document.querySelectorAll('figure.chart[data-kind=line]').forEach(function(fig){
    var svg = fig.querySelector('svg'), tip = fig.querySelector('.tip');
    var pts = JSON.parse(fig.querySelector('.pts').textContent), g = JSON.parse(fig.querySelector('.geo').textContent);
    var cross = svg.querySelector('.cross'), hov = svg.querySelector('.hov'), idx = pts.length - 1;
    function at(i){
      idx = Math.max(0, Math.min(pts.length - 1, i));
      var p = pts[idx], x = g.l + g.pw * idx / (pts.length - 1), y = g.t + g.ph * (1 - p[1] / 100);
      cross.setAttribute('x1', x); cross.setAttribute('x2', x); cross.setAttribute('visibility', 'visible');
      hov.setAttribute('cx', x); hov.setAttribute('cy', y); hov.setAttribute('visibility', 'visible');
      var k = svg.clientWidth / g.W;
      show(tip, p[1].toFixed(1), p[0] + '  ' + (p[2] ? 'Regime ' + p[2] : ''));
      place(tip, fig, x * k, y * k);
    }
    function hide(){ cross.setAttribute('visibility', 'hidden'); hov.setAttribute('visibility', 'hidden'); tip.hidden = true; }
    svg.addEventListener('pointermove', function(ev){
      var r = svg.getBoundingClientRect(), x = (ev.clientX - r.left) / r.width * g.W;
      at(Math.round((x - g.l) / g.pw * (pts.length - 1)));
    });
    svg.addEventListener('pointerleave', hide);
    svg.addEventListener('focus', function(){ at(idx); });
    svg.addEventListener('blur', hide);
    svg.addEventListener('keydown', function(ev){
      if (ev.key === 'ArrowLeft') { at(idx - 1); ev.preventDefault(); }
      if (ev.key === 'ArrowRight') { at(idx + 1); ev.preventDefault(); }
    });
  });
  document.querySelectorAll('.hbars').forEach(function(box){
    var tip = box.querySelector('.tip');
    box.querySelectorAll('.hrow').forEach(function(row){
      function on(){
        var parts = row.getAttribute('data-tip').split(' · ');
        show(tip, parts[0], parts.slice(1).join(' · '));
        var bar = row.querySelector('.htrack').getBoundingClientRect(), b0 = box.getBoundingClientRect();
        place(tip, box, bar.left - b0.left + bar.width / 2, row.getBoundingClientRect().top - b0.top);
      }
      row.addEventListener('pointerenter', on); row.addEventListener('focus', on);
      row.addEventListener('pointerleave', function(){ tip.hidden = true; });
      row.addEventListener('blur', function(){ tip.hidden = true; });
    });
  });
})();
"""


BAR_VER = "4"
BAR_CSS = """<style>
body{background:#ffffff!important}
.sitebar{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;max-width:1200px;margin:0 auto 12px;
font:400 15px/1.4 -apple-system,"Segoe UI",Roboto,"Noto Sans TC","Noto Sans SC","PingFang TC","Microsoft JhengHei",sans-serif}
.sitebar a{color:#0b6574;text-decoration:none}
.sitebar .home{font-weight:600;padding:8px 0}
.sitebar .home:hover{text-decoration:underline}
.sitebar .langs{display:inline-flex;background:#fff;border:1px solid #e6d7ae;border-radius:999px;padding:3px}
.sitebar .langs a{padding:6px 14px;border-radius:999px;color:#574f43}
.sitebar .langs a[aria-current=page]{background:#0b6574;color:#fff;font-weight:600}
.sitebar a:focus-visible{outline:3px solid #0b6574;outline-offset:2px}
.sizer{font:14px/1.45 -apple-system,"Segoe UI","Noto Sans TC","PingFang TC","Microsoft JhengHei",sans-serif;color:#1d2a2e;background:#fff;
border-bottom:1px solid #e6d7ae;padding:10px 16px}
.sizer .sz-row{max-width:1180px;margin:0 auto;display:flex;flex-wrap:wrap;gap:10px 18px;align-items:flex-end}
.sizer label{display:flex;flex-direction:column;gap:3px;font-size:12.5px;color:#574f43}
.sizer input[type=number],.sizer select{font:inherit;font-size:15px;padding:6px 8px;border:1px solid #cdbf98;border-radius:6px;background:#fff;color:#1d2a2e;min-width:0}
.sizer #sz-eq{width:9.5em}.sizer #sz-risk{width:5.5em}
.sizer input[aria-invalid=true]{border-color:#b3261e;outline:2px solid #f3c6c2}
.sizer .sz-pre{display:flex;gap:6px;align-items:center}
.sizer .sz-pre button{font:inherit;font-size:13px;padding:6px 10px;border:1px solid #cdbf98;border-radius:999px;background:#fff;color:#1d2a2e;cursor:pointer}
.sizer .sz-pre button:hover{border-color:#0b6574}
.sizer .sz-tog{flex-direction:row;align-items:center;gap:6px;font-size:13.5px;color:#1d2a2e;padding-bottom:7px}
.sizer .sz-tog input{width:18px;height:18px;accent-color:#0b6574}
.sizer .sz-out{max-width:1180px;margin:6px auto 0;font-size:12.5px;color:#574f43}
.sizer .sz-out b{color:#1d2a2e}
.sizer button:focus-visible,.sizer input:focus-visible,.sizer select:focus-visible{outline:3px solid #0b6574;outline-offset:2px}
@media (min-width:760px){.sizer{position:sticky;top:0;z-index:20;box-shadow:0 1px 0 #e6d7ae}}
</style>"""


def sizer_bar(lang, up):
    """The position-size simulator's controls; sizer.js fills in the values and does the arithmetic."""
    presets = "".join(f'<button type="button" data-eq="{v}">{v // 1000}k</button>' for v in (25000, 50000, 100000, 250000))
    opts = "".join(f'<option value="{k}">{e(t("sz_" + k, lang))}</option>' for k in ("generic", "futu", "ibkr"))
    return (f'<section id="sizer" class="sizer" aria-label="{e(t("sz_label", lang))}" hidden><div class="sz-row">'
            f'<label>{e(t("sz_equity", lang))}<input id="sz-eq" type="number" inputmode="numeric" min="100" step="1000" value="100000"></label>'
            f'<span class="sz-pre">{presets}</span>'
            f'<label>{e(t("sz_risk", lang))}<input id="sz-risk" type="number" inputmode="decimal" min="0.05" max="10" step="0.05" value="0.75"></label>'
            f'<label class="sz-tog"><input id="sz-scale" type="checkbox" checked>{e(t("sz_scale", lang))}</label>'
            f'<label>{e(t("sz_broker", lang))}<select id="sz-broker">{opts}</select></label></div>'
            f'<p class="sz-out"><b id="sz-eff" aria-live="polite"></b>　{e(t("sz_note", lang))}</p></section>'
            f'<script src="{up}assets/sizer.js?v={ASSET_VER}" defer></script>')


def decorate(doc, lang, depth):
    """Add the bar (back to the home page, language switch) and the page colour to a saved brief or pre-open page;
    pages with sizer data also get the position-size simulator."""
    up = "../" * depth
    langs = "".join(f'<a href="{lg}.html" hreflang="{HTML_LANG[lg]}" lang="{HTML_LANG[lg]}"' + (' aria-current="page"' if lg == lang else "")
                    + f">{LANG_NAME[lg]}</a>" for lg in LANGS)
    bar = (f'<!--sitebar v{BAR_VER}-->{BAR_CSS}<nav class="sitebar"><a class="home" href="{up}{LANG_DIR[lang]}index.html">‹ {e(t("site", lang))}</a>'
           f'<span class="langs" aria-label="{e(t("lang", lang))}">{langs}</span></nav>'
           + (sizer_bar(lang, up) if 'id="sizer-meta"' in doc else "") + '<!--/sitebar-->')
    doc = strip_bar(doc)
    m = re.search(r"<body[^>]*>", doc)
    return doc[:m.end()] + bar + doc[m.end():] if m else bar + doc


def prepare_pages(site):
    """Every brief and pre-open folder: make the missing languages, then add the bar where it is missing or out of date."""
    made = fixed = 0
    for kind in ("briefs", "preopen"):
        for folder in sorted(glob.glob(os.path.join(site, kind, "*"))):
            if not os.path.isdir(folder):
                continue
            made += ensure_languages(folder)
            for lang in LANGS:
                path = os.path.join(folder, f"{lang}.html")
                if not os.path.exists(path):
                    continue
                doc = open(path, encoding="utf-8").read()
                if f"<!--sitebar v{BAR_VER}-->" not in doc and 'http-equiv="refresh"' not in doc:
                    open(path, "w", encoding="utf-8").write(decorate(doc, lang, 2))   # site/<kind>/<run>/<lang>.html: two levels below the site root
                    fixed += 1
    return made, fixed


SIZER_JS = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "sizer.js"), encoding="utf-8").read()
ASSET_VER = hashlib.sha1((CSS + JS + SIZER_JS).encode("utf-8")).hexdigest()[:8]   # new file name whenever the style changes, so browsers don't keep an old copy


def redirect(target):
    return (f'<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="refresh" content="0; url={target}">'
            f'<link rel="canonical" href="{target}"><title>Latest brief</title></head><body><a href="{target}">{target}</a></body></html>')


def write_home(site, latest, latest_pre, hist, mode):
    os.makedirs(os.path.join(site, "assets"), exist_ok=True)
    open(os.path.join(site, "assets", "site.css"), "w", encoding="utf-8").write(CSS.strip() + "\n")
    open(os.path.join(site, "assets", "site.js"), "w", encoding="utf-8").write(JS.strip() + "\n")
    open(os.path.join(site, ".nojekyll"), "w").close()
    for lang in LANGS:
        path = os.path.join(site, LANG_DIR[lang], "index.html")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "w", encoding="utf-8").write(page(lang, latest, latest_pre, hist, mode))


def publish_data(state, site, names):
    """Copy ledger files (state/ledger/) into site/data/ so other front ends can read them."""
    os.makedirs(os.path.join(site, "data"), exist_ok=True)
    for name in names:
        src = os.path.join(state, "ledger", name)
        if os.path.exists(src):
            shutil.copyfile(src, os.path.join(site, "data", name))


def main():
    """BUILD_MODE=full (default): state/site is the whole website.
    BUILD_MODE=freemium_split: state/site is still the whole website (the full report), and state/site_free is the public teaser;
    publish state/site_free and serve state/site behind a paywall."""
    state = os.path.abspath(env("STATE_DIR", os.path.join(ROOT, "state")))
    mode = env("BUILD_MODE", "full").strip().lower()
    site = os.path.join(state, "site")
    made, fixed = prepare_pages(site)
    latest, latest_pre, hist = load(state)
    write_home(site, latest, latest_pre, hist, "full")
    open(os.path.join(site, "assets", "sizer.js"), "w", encoding="utf-8").write(SIZER_JS.strip() + "\n")
    publish_data(state, site, ("signal_ledger.json", "regime_history.json"))
    if latest:
        run = latest[max(latest)][0]
        os.makedirs(os.path.join(site, "latest"), exist_ok=True)
        for lang in LANGS:
            open(os.path.join(site, "latest", f"{lang}.html"), "w", encoding="utf-8").write(redirect(f"../briefs/{run}/{lang}.html"))
    free = os.path.join(state, "site_free")
    if mode == "freemium_split":
        shutil.rmtree(free, ignore_errors=True)
        write_home(free, latest, latest_pre, hist, "free")
        publish_data(state, free, ("regime_history.json",))
    elif os.path.isdir(free):
        shutil.rmtree(free, ignore_errors=True)
    print(f"Website built in {site} ({mode}): {len(latest)} brief dates, {len(latest_pre)} pre-open updates, {len(hist)} score points; "
          f"{made} translated pages added, {fixed} pages given the language bar" + (f"; teaser in {free}" if mode == "freemium_split" else ""))


if __name__ == "__main__":
    main()
