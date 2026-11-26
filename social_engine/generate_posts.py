"""Post copy in three editions (Traditional Chinese, English, Simplified Chinese), written by Claude from the context only.

    posts, source = generate(ctx, "daily")        # source: "claude" or "template"

The writer sees nothing but the compact context from context.py and must cite it verbatim; compliance_gate.py then
checks every text. Without an API key (or when the API is down) the same context is put into fixed sentences, so a
dry run works offline and an API outage does not stop the posts.
"""
import json
import os

from . import compliance_gate, config, context

_client = None


def client():
    global _client
    if _client is None:
        import anthropic
        _client = anthropic.Anthropic(max_retries=config.CLAUDE_MAX_RETRIES, timeout=config.CLAUDE_TIMEOUT_S)
    return _client


def have_key():
    return bool(os.environ.get("ANTHROPIC_API_KEY", "").strip() or os.environ.get("ANTHROPIC_AUTH_TOKEN", "").strip())


FALLBACK_MODELS = ("claude-sonnet-5-5", "claude-opus-5-5", "claude-fable-5")     # models with the server-side refusal fallback


def ask(model, system, user, schema, max_tokens):
    """One structured request. Returns the parsed JSON object; raises on a refusal, a cut-off reply or an API error."""
    import anthropic
    kw = dict(model=model, max_tokens=max_tokens, system=system, messages=[{"role": "user", "content": user}],
              output_config={"format": {"type": "json_schema", "schema": schema}})
    c = client()
    resp = None
    if model.startswith(FALLBACK_MODELS):
        try:                                             # a safety-classifier decline is re-run on the default fallback model in the same call
            resp = c.beta.messages.create(betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kw)
        except (anthropic.BadRequestError, TypeError):
            resp = None
    if resp is None:
        resp = c.messages.create(**kw)
    if resp.stop_reason in ("refusal", "max_tokens"):
        raise RuntimeError(f"Claude stopped with {resp.stop_reason}")
    text = next((b.text for b in resp.content if b.type == "text"), "")
    return json.loads(text)


# ---------- prompts ----------
SYSTEM = """You write the social media posts of an automated US pre-market research brief. The brief is produced by fixed rules: \
a 0-100 Market Health Score built from five weighted pillars, a regime grade from A (strongest) to E (weakest), three gates \
(long, pilot, short) that say which kinds of rule-matched setups the rules would list today, sector rotation, and tonight's calendar. \
The readers are swing traders in Hong Kong, Taiwan, mainland China and on English-language finance social media. They read the post \
on a phone, next to an image card that already shows the numbers, and they decide in two seconds whether to keep reading.

Voice: an institutional market-telemetry desk. Calm, exact, dense with data, impersonal. No hype, no predictions, no first person \
plural selling anything. At most two to four simple markers such as 🔴 🟢 📊 in the Telegram and Xiaohongshu texts, and at most one in the \
X and Threads texts; no other emoji.

Grounding. The JSON in <data> is the only source of facts. Every number, date, time, ticker, sector ETF and event you mention must be in \
it, written exactly as it appears there (do not round further, do not convert, do not compute new figures such as differences or \
ratios). If something is not in the data, leave it out: no prices, news, company stories, causes or forecasts from your own knowledge. \
A deterministic checker rejects any post that contains a figure or symbol that is not in the data, so an invented number means the \
post is not published.

Compliance. The posts describe what the rules measured; they never tell anyone to trade. Do not write buy, sell or short as an \
instruction, and do not promise outcomes. Call listed names "rule-matched technical setups" (符合規則的技術形態 / 符合规则的技术形态) and \
describe gates objectively ("the short gate is open"). Do not name data vendors, tools or file formats. A short "not investment advice" \
line (非投資建議 / 非投资建议 / Not investment advice) is welcome in the longer texts.

Always state the Market Health Score and the regime grade exactly as given. When grade_held_by_hysteresis is true, the score sits in the \
band of score_band_grade but the grade stays at regime_grade until the score holds the higher band for two sessions in a row; say so \
plainly when you mention the band.

Write each edition natively in its own language, not as a translation of another: Traditional Chinese as a Hong Kong or Taiwan trader \
writes it, Simplified Chinese as mainland readers write it, English as finance Twitter writes it. Keep upper-case for tickers only."""

EDITIONS = {
    "x_en": ("X post, English, at most {x} characters including line breaks. A punchy opening line that states the regime tension, then "
             "three or four short bullet lines of telemetry (start each with •). No links and no web addresses of any kind. "
             "Quote schedule times in New York time (ET), never Hong Kong time: the readers are global. "
             "End with this cue or a close variant: {cue}"),
    "threads_tc": ("Threads post, Traditional Chinese, at most {th} characters. Open with today's regime tension (for example breadth "
                   "against distribution days, or which sectors lead while the grade is weak), then three concrete takeaways as short "
                   "numbered lines, then one neutral question that invites discussion (for example 你今晚會重點觀察哪個強勢板塊？). No links."),
    "telegram_tc": ("Telegram channel post, Traditional Chinese, Telegram HTML: only <b>, <i>, <code> and <a href=\"...\"> tags, every tag "
                    "closed, and &lt; &gt; &amp; for those three characters. Structured and scannable: a bold headline with the date, "
                    "then short labelled lines (score and grade, gates, QQQ levels, breadth, sectors, volatility, tonight's times in "
                    "Hong Kong time), then one italic line that this is automated market telemetry and not investment advice. "
                    "Do not put a link in the text; a button with the link is added under the post."),
    "xhs_sc": ("Xiaohongshu note, Simplified Chinese. title: catchy but factual, at most {xt} characters. body: four short numbered points "
               "that follow the four carousel slides in order (1 regime scorecard, 2 pillars and breadth, 3 sector rotation, 4 tonight's "
               "calendar and volatility), then one closing line saying the figures are computed automatically by fixed rules, the wording "
               "is AI-assisted, and it is not investment advice. hashtags: five to eight, without the # sign, chosen from topics like "
               "美股, 美股复盘, 波段交易, 美股盘前, 量化筛选, 市场宽度, 板块轮动. No links."),
}
MODE_BRIEF = {
    "daily": "This is the daily brief post, published after the main run. Cover the regime, breadth, sectors and tonight's calendar.",
    "premarket": ("This is the pre-market gap flash, published about 45 minutes before the US open. Lead with the overnight futures gap "
                  "in data.premarket (NQ, ES and QQQ pre-market), then VIX and the VIX/VIX3M ratio, then tonight's Hong Kong-time "
                  "timeline. You may tag two or three tickers from rule_matched_setups as rule-matched technical setups, by symbol and "
                  "pattern only. Keep it fast: shorter than the daily post. If a premarket figure is null, leave it out."),
    "ledger": ("This is the forward-ledger update: a transparent scoreboard of how previously listed setups went, graded by fixed rules. "
               "Report the focus list against the control group from data.ledger (listed, triggered, reached 2R, invalidated, average "
               "R) and the latest statuses in data.ledger.recent. State wins and losses with the same weight. Say that R is "
               "hypothetical and not a traded result. The score and grade are optional here."),
    "weekly": ("This is the weekend review. Summarise the brief dates in data.week (score and grade path, gates, QQQ close) and the "
               "ledger. Each text is a list of two or three parts that read in order as a thread; every part must stand within the "
               "platform's limit. The score and grade of the latest date should appear in part one."),
}
MODE_KEYS = {"daily": ("threads_tc", "x_en", "telegram_tc", "xhs_sc"), "premarket": ("x_en", "telegram_tc"),
             "ledger": ("threads_tc", "x_en", "telegram_tc"), "weekly": ("threads_tc", "x_en", "telegram_tc")}
XHS_SCHEMA = {"type": "object", "properties": {"title": {"type": "string"}, "body": {"type": "string"},
                                                "hashtags": {"type": "array", "items": {"type": "string"}}},
              "required": ["title", "body", "hashtags"], "additionalProperties": False}


def schema_for(mode, keys=None):
    props = {}
    for k in keys or MODE_KEYS[mode]:
        if k == "xhs_sc":
            props[k] = XHS_SCHEMA
        elif mode == "weekly" and k in ("threads_tc", "x_en"):
            props[k] = {"type": "array", "items": {"type": "string"}}
        else:
            props[k] = {"type": "string"}
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


def cue():
    return f"Full interactive dashboard + {config.premarket_et()} ET pre-open gap refresh → link in bio."


def edition_text(key):
    return EDITIONS[key].format(x=config.X_TARGET, th=config.THREADS_TARGET, xt=config.XHS_TITLE_MAX, cue=cue())


def user_prompt(ctx, mode, keys):
    parts = ["<data>", json.dumps(context.public(ctx), ensure_ascii=False), "</data>", "", MODE_BRIEF[mode], "",
             "Write these texts and return them as one JSON object with exactly these keys:"]
    parts += [f"- {k}: {edition_text(k)}" for k in keys]
    return "\n".join(parts)


def normalize(posts, mode):
    """threads_tc and x_en are always lists of parts (one part outside weekly mode)."""
    out = {}
    for k, v in posts.items():
        if k in ("threads_tc", "x_en"):
            v = [str(p).strip() for p in (v if isinstance(v, list) else [v]) if str(p).strip()][:3]
        elif k == "xhs_sc":
            v = {"title": str(v.get("title", "")).strip(), "body": str(v.get("body", "")).strip(),
                 "hashtags": [str(t).strip().lstrip("#") for t in v.get("hashtags", []) if str(t).strip()]}
        else:
            v = str(v).strip()
        out[k] = v
    return out


def generate(ctx, mode):
    """Returns (posts, source). Falls back to the fixed-sentence copy when Claude cannot be reached."""
    keys = MODE_KEYS[mode]
    if have_key():
        try:
            got = ask(config.model_writer(), SYSTEM, user_prompt(ctx, mode, keys), schema_for(mode), config.MAX_TOKENS_WRITER)
            return normalize(got, mode), "claude"
        except Exception as e:                                           # noqa: BLE001 - any API trouble: use the fixed sentences
            print(f"Claude writer unavailable ({type(e).__name__}: {e}); using the fixed-sentence copy.", flush=True)
    else:
        print("No ANTHROPIC_API_KEY: using the fixed-sentence copy.", flush=True)
    return normalize(template_posts(ctx, mode), mode), "template"


def repair(key, value, failures, ctx, mode):
    """One rewrite of a text that failed the gate, with the exact reasons. Returns the new value, or None when Claude is unavailable."""
    if not have_key():
        return None
    user = (user_prompt(ctx, mode, (key,)) + "\n\nYour previous draft of this text was rejected by the checker:\n<draft>\n"
            + json.dumps(value, ensure_ascii=False) + "\n</draft>\n<reasons>\n" + "\n".join(f"- {f}" for f in failures)
            + "\n</reasons>\nRewrite it so that every reason is resolved. Keep what was fine.")
    try:
        got = ask(config.model_writer(), SYSTEM, user, schema_for(mode, (key,)), config.MAX_TOKENS_WRITER)
    except Exception as e:                                               # noqa: BLE001
        print(f"Repair of {key} failed ({type(e).__name__}: {e}).", flush=True)
        return None
    return normalize(got, mode)[key]


def gated(ctx, mode, posts=None, source=None, qa=None):
    """Generate (unless given), check, repair once, check again.
    Returns {"posts", "source", "report": {key: {"ok", "failures", "repaired", "first_failures"}}}."""
    if posts is None:
        posts, source = generate(ctx, mode)
    qa = config.llm_qa_on() and have_key() and source == "claude" if qa is None else qa

    def failures_of(key):
        f = compliance_gate.check_posts({key: posts[key]}, ctx, mode)[key]
        if not f and qa:
            f = compliance_gate.llm_review(key, posts[key], ctx, ask)
        return f
    report = {}
    for key in list(posts):
        fails = failures_of(key)
        entry = {"ok": not fails, "failures": fails, "repaired": False, "first_failures": []}
        if fails:
            fixed = repair(key, posts[key], fails, ctx, mode)
            if fixed is None and source == "claude":                     # no repair possible: the fixed sentences are the second attempt
                fixed = normalize(template_posts(ctx, mode), mode).get(key)
            if fixed is not None:
                entry["first_failures"], entry["repaired"] = fails, True
                posts[key] = fixed
                fails = failures_of(key)
                entry.update(ok=not fails, failures=fails)
        report[key] = entry
    return {"posts": posts, "source": source, "report": report}


# ---------- fixed-sentence copy (no model) ----------
def sg(v, nd=1):
    return "–" if v is None else f"{v:+.{nd}f}"


def px(v):
    return "–" if v is None else f"{v:.2f}"


def _gates(c, lang):
    g = c["gates_open"]
    w = {"tc": ("多頭", "試單", "空頭", "開", "關"), "sc": ("多头", "试单", "空头", "开", "关"), "en": ("long", "pilot", "short", "open", "closed")}[lang]
    if lang == "en":
        return "Gates: " + ", ".join(f"{w[i]} {w[3] if g[k] else w[4]}" for i, k in enumerate(("long", "pilot", "short")))
    return "・".join(f"{w[i]}閘門{w[3] if g[k] else w[4]}".replace("閘門", "闸门" if lang == "sc" else "閘門") for i, k in enumerate(("long", "pilot", "short")))


def _hold(c, lang):
    if not c["grade_held_by_hysteresis"]:
        return ""
    s, r, g = c["market_health_score"], c["score_band_grade"], c["regime_grade"]
    return {"tc": f"分數 {s} 屬 {r} 區，升級需連兩日留於高區間，暫維持 {g} 級。", "sc": f"分数 {s} 属 {r} 区，升级需连两日留于高区间，暂维持 {g} 级。",
            "en": f"Score {s} sits in the {r} band; the grade stays {g} until it holds for two sessions."}[lang]


def _secs(rows, key="excess_1m_pct", n=3):
    return "、".join(f'{s["etf"]} {sg(s[key])}%' for s in rows[:n])


def _events(c, lang, n=5):
    rows = sorted(c["tonight_events"], key=lambda x: (x["next_day_hkt"], x["hkt"]))[:n]
    return "\n".join(f'{x["hkt"]}　{x["what"][lang]}' for x in rows)


def _tags(c, lang):
    w = {"tc": ("做多", "做空"), "sc": ("做多", "做空"), "en": ("long", "short")}[lang]
    return "、".join(f'{s["ticker"]}（{w[0] if s["direction"] == "long" else w[1]}・{s["pattern"][lang]}）' for s in c["rule_matched_setups"][:3])


def _led_line(st, lang):
    avg = "–" if st["avg_r"] is None else f'{st["avg_r"]:+.2f}R'
    if lang == "en":
        return f'{st["listed"]} listed, {st["triggered"]} triggered, {st["hit_2r"]} reached 2R, {st["invalidated"]} invalidated, avg {avg}'
    return f'列出 {st["listed"]}・觸發 {st["triggered"]}・達 2R {st["hit_2r"]}・失效 {st["invalidated"]}・平均 {avg}'


def template_posts(c, mode):
    s, g = c["market_health_score"], c["regime_grade"]
    b, v, q = c["breadth"], c["volatility"], c["qqq"]
    lead, lag = c["sectors_leading"], c["sectors_lagging"]
    d = c["brief_date"]
    name = c["regime_name"]
    brand_tc = config.brand("tc")
    disc_tc = "<i>自動市況統計，按固定規則計算，非投資建議。</i>"
    vol_tc = f'VIX {v["vix"]}' + (f'・VIX／VIX3M {v["vix_vix3m_ratio"]}' if v["vix_vix3m_ratio"] is not None else "")
    vol_en = f'VIX {v["vix"]}' + (f', VIX/VIX3M {v["vix_vix3m_ratio"]}' if v["vix_vix3m_ratio"] is not None else "")
    dd = b["distribution_days_25_sessions"]
    if mode == "daily":
        x = (f"Health Score {s} · Regime {g} ({name['en']})\n• {_gates(c, 'en')}\n"
             f"• {b['pct_above_50dma']}% above 50DMA" + (f", {dd} distribution days" if dd is not None else "") + "\n"
             + (f"• 1M excess: {lead[0]['etf']} {sg(lead[0]['excess_1m_pct'])}% vs {lag[-1]['etf']} {sg(lag[-1]['excess_1m_pct'])}%\n" if lead and lag else "")
             + f"• {vol_en}\n{cue()}")
        th = (f"【{brand_tc}｜{d}】市場健康分數 {s}，市況級別 {g}（{name['tc']}）。{_hold(c, 'tc')}\n\n"
              f"1. 閘門：{_gates(c, 'tc')}\n2. 寬度：{b['pct_above_50dma']}% 股票高於 50 日線" + (f"，近 25 日派發日 {dd} 個" if dd is not None else "") + "\n"
              + (f"3. 板塊（1 個月超額）：領先 {_secs(lead, n=2)}；落後 {_secs(lag[::-1], n=2)}\n" if lead and lag else "")
              + "\n以上為固定規則的統計，非投資建議。你今晚會重點觀察哪個板塊？")
        tg = (f"<b>{brand_tc}｜{d}</b>\n📊 市場健康分數 <b>{s}</b>・市況級別 <b>{g}（{name['tc']}）</b>\n" + (_hold(c, "tc") + "\n" if _hold(c, "tc") else "")
              + f"\n<b>閘門</b>　{_gates(c, 'tc')}\n<b>QQQ</b>　收市 {px(q['close'])}｜21EMA {px(q['ema21'])}｜50 日線 {px(q['dma50'])}｜200 日線 {px(q['dma200'])}\n"
              f"<b>寬度</b>　{b['pct_above_50dma']}% 高於 50 日線" + (f"・{b['pct_above_200dma']}% 高於 200 日線" if b["pct_above_200dma"] is not None else "")
              + (f"・派發日 {dd} 個" if dd is not None else "") + f"・突破成功率 {b['breakout_success_rate_pct']}%\n"
              + (f"<b>板塊</b>（1 個月超額）\n🟢 {_secs(lead)}\n🔴 {_secs(lag[::-1])}\n" if lead and lag else "")
              + f"<b>波動</b>　{vol_tc}\n\n<b>今晚（香港時間）</b>\n{_events(c, 'tc')}\n\n{disc_tc}")
        pl = "；".join(f"{p['name']['sc']} {p['score']}" for p in c["pillars"])
        body = (f"1️⃣ 市况：健康分数 {s}，市况级别 {g}（{name['sc']}）。{_hold(c, 'sc')}{_gates(c, 'sc')}。\n"
                f"2️⃣ 宽度：{b['pct_above_50dma']}% 股票高于 50 日线" + (f"，近 25 日派发日 {dd} 个" if dd is not None else "") + (f"。五大支柱：{pl}" if pl else "") + "。\n"
                + (f"3️⃣ 板块（1 个月超额）：领先 {_secs(lead)}；落后 {_secs(lag[::-1])}。\n" if lead and lag else "")
                + f"4️⃣ 今晚：{vol_tc}。" + ("今晚有重点数据或财报，详见第 4 张图。" if c["has_macro_or_earnings"] else "今晚没有重点经济数据或大型财报。")
                + "\n\n数据由程序按固定规则自动统计，文字由 AI 辅助整理，非投资建议。")
        xhs = {"title": f"美股盘前｜健康分{s}・{g}级{name['sc']}"[:config.XHS_TITLE_MAX], "body": body,
               "hashtags": ["美股", "美股复盘", "波段交易", "美股盘前", "量化筛选", "市场宽度"]}
        return {"threads_tc": th, "x_en": x, "telegram_tc": tg, "xhs_sc": xhs}
    if mode == "premarket":
        p = c.get("premarket") or {}
        f = p.get("futures") or {}
        fut_en = " · ".join(f"{k} {sg(f[k], 2)}%" for k in ("NQ", "ES") if f.get(k) is not None)
        fut_tc = "・".join(f"{k} {sg(f[k], 2)}%" for k in ("NQ", "ES", "RTY") if f.get(k) is not None)
        qq_en = f"QQQ pre-market {px(p['qqq_price'])} ({sg(p['qqq_change_pct'], 2)}%, {sg(p['qqq_gap_atr'], 2)} ATR)" if p.get("qqq_price") is not None else ""
        qq_tc = f"QQQ 盤前 {px(p['qqq_price'])}（{sg(p['qqq_change_pct'], 2)}%，{sg(p['qqq_gap_atr'], 2)} 個 ATR）" if p.get("qqq_price") is not None else ""
        x = (f"Pre-market gap check · Market Health Score {s}, Regime {g}\n" + (f"• {fut_en}\n" if fut_en else "") + (f"• {qq_en}\n" if qq_en else "")
             + f"• {vol_en} (prior close)\n• {_gates(c, 'en')}\nFull interactive dashboard → link in bio.")
        tags = _tags(c, "tc")
        tg = (f"<b>開市前缺口更新｜{d}</b>\n📊 市場健康分數 <b>{s}</b>・市況級別 <b>{g}（{name['tc']}）</b>\n\n" + (f"<b>期貨</b>　{fut_tc}\n" if fut_tc else "")
              + (f"<b>QQQ</b>　{qq_tc}\n" if qq_tc else "") + f"<b>波動</b>　{vol_tc}（上日收市）\n<b>閘門</b>　{_gates(c, 'tc')}\n"
              + (f"<b>開市情景</b>　{p['scenario']['tc']}\n" if p.get("scenario") else "")
              + (f"<b>符合規則的技術形態</b>　{tags}\n" if tags else "") + f"\n<b>今晚（香港時間）</b>\n{_events(c, 'tc')}\n\n{disc_tc}")
        return {"x_en": x, "telegram_tc": tg}
    L = c["ledger"]
    if mode == "ledger":
        rec_tc = "\n".join(f"{r['ticker']}　{'做多' if r['direction'] == 'long' else '做空'}　{ {'TRIGGERED': '觸發', 'HIT_2R': '達 2R', 'INVALIDATED': '失效', 'EXPIRED': '過期'}.get(r['status'], r['status'])}"
                           + (f"　{r['r']:+.2f}R" if r["r"] is not None else "") for r in L["recent"][:6])
        x = (f"Forward ledger update · {d}\n• Focus list: {_led_line(L['focus'], 'en')}\n• Control group: {_led_line(L['control'], 'en')}\n"
             "R is hypothetical, graded by fixed rules. Not investment advice.")
        th = (f"【形態跟進紀錄｜{d}】按同一套固定規則評定，紀錄不會刪除。\n\n1. 首選名單：{_led_line(L['focus'], 'tc')}\n2. 對照組：{_led_line(L['control'], 'tc')}\n"
              "3. R 為假設值，並非實際交易結果。\n\n非投資建議。你會怎樣比較首選名單與對照組？")
        tg = (f"<b>形態跟進紀錄｜{d}</b>\n\n<b>首選名單</b>　{_led_line(L['focus'], 'tc')}\n<b>對照組</b>　{_led_line(L['control'], 'tc')}\n"
              + (f"\n<b>最近狀態</b>\n{rec_tc}\n" if rec_tc else "") + f"\nR 為假設值，並非實際交易結果。\n{disc_tc}")
        return {"threads_tc": th, "x_en": x, "telegram_tc": tg}
    wk = c.get("week", [])
    path_en = " → ".join(f"{w['score']} ({w['grade']})" for w in wk)
    path_tc = " → ".join(f"{w['score']}（{w['grade']}）" for w in wk)
    days_tc = "\n".join(f"{w['brief_date']}　分數 {w['score']}・{w['grade']} 級・QQQ {px(w['qqq_close'])}" for w in wk)
    x = [f"Week in review · Market Health Score {s}, Regime {g}\nScore path: {path_en}\n{_gates(c, 'en')}",
         f"Forward ledger\n• Focus list: {_led_line(L['focus'], 'en')}\n• Control group: {_led_line(L['control'], 'en')}\nR is hypothetical. Not investment advice."]
    th = [f"【一週回顧｜{d}】市場健康分數 {s}，市況級別 {g}（{name['tc']}）。\n分數路徑：{path_tc}\n閘門：{_gates(c, 'tc')}",
          f"形態跟進紀錄\n首選名單：{_led_line(L['focus'], 'tc')}\n對照組：{_led_line(L['control'], 'tc')}\nR 為假設值，非投資建議。你下週會先看哪個指標？"]
    tg = (f"<b>一週回顧｜{d}</b>\n📊 市場健康分數 <b>{s}</b>・市況級別 <b>{g}（{name['tc']}）</b>\n\n<b>本週各簡報日</b>\n{days_tc}\n\n<b>閘門</b>　{_gates(c, 'tc')}\n"
          f"<b>首選名單</b>　{_led_line(L['focus'], 'tc')}\n<b>對照組</b>　{_led_line(L['control'], 'tc')}\n\n{disc_tc}")
    return {"threads_tc": th, "x_en": x, "telegram_tc": tg}
