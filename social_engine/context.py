"""Reads the newest brief (data.json, the three summary files, the ledger files, the pre-open text) and turns it into
one compact, already-rounded context. The cards, the writer and the compliance gate all read this same context,
so a number can only reach a post if it is in here.
"""
import glob
import json
import os
import re

from . import config

PILLAR_NAMES = {"trend": ("趨勢", "趋势", "Trend"), "breadth": ("寬度", "宽度", "Breadth"), "risk": ("風險偏好", "风险偏好", "Risk appetite"),
                "vol": ("波動率", "波动率", "Volatility"), "rates": ("利率與信貸", "利率与信贷", "Rates & credit")}
FUTURES = (("NQ", "Nasdaq 100 期貨"), ("ES", "S&P 500 期貨"), ("RTY", "Russell 2000 期貨"))


def _json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _r(x, nd=1):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    if x != x:
        return None
    x = round(x, nd)
    return int(x) if nd == 0 else x


def tri(tc, sc, en):
    return {"tc": tc, "sc": sc, "en": en}


def load_brief(state=None, date=None):
    """The newest brief (or the newest one for `date`) with everything around it. None when there is no data.json yet."""
    state = state or config.state_dir()
    runs = []
    for p in glob.glob(os.path.join(state, "site", "briefs", "*", "data.json")):
        d = _json(p)
        if not d or "summary" not in d:
            continue
        s = d["summary"]
        if date and s.get("brief_date") != date:
            continue
        runs.append(((s.get("brief_date", ""), s.get("run_et", ""), os.path.basename(os.path.dirname(p))), p, d))
    if not runs:
        return None
    _, path, data = max(runs, key=lambda x: x[0])
    folder = os.path.dirname(path)
    summaries = {}
    for lang in config.LANGS:
        summaries[lang] = _json(os.path.join(folder, f"summary_{lang}.json")) or (data["summary"] if lang == "tc" else None)
    for lang in config.LANGS:
        summaries[lang] = summaries[lang] or summaries["tc"]
    brief_date = data["summary"]["brief_date"]
    ledger = _json(os.path.join(state, "ledger", "signal_ledger.json"), {}) or {}
    history = _json(os.path.join(state, "ledger", "regime_history.json"), []) or []
    pre = None
    stems = sorted(d for d in glob.glob(os.path.join(state, "site", "preopen", f"{brief_date}_*")) if os.path.isdir(d))
    if stems:
        texts = {}
        for lang in config.LANGS:
            try:
                texts[lang] = open(os.path.join(stems[-1], f"preopen_{lang}.txt"), encoding="utf-8").read()
            except OSError:
                texts[lang] = ""
        if texts["tc"]:
            pre = {"stem": os.path.basename(stems[-1]), "texts": texts, "summary": _json(os.path.join(stems[-1], "summary_tc.json"), {})}
    return {"state": state, "folder": folder, "run_id": os.path.basename(folder), "data": data, "summaries": summaries,
            "ledger": ledger, "history": history, "preopen": pre}


def parse_preopen(texts):
    """Numbers from the pre-open text summary (written by the pre-open script in a fixed format)."""
    tc = texts.get("tc", "")
    lines = {lang: [ln for ln in texts.get(lang, "").splitlines()] for lang in config.LANGS}
    out = {"futures": {}, "vix": None, "vix_change": None, "qqq_price": None, "qqq_change_pct": None, "qqq_gap_atr": None, "scenario": None,
           "run_et": None, "run_hkt": None}
    m = re.search(r"美東 (\d{2}:\d{2})・香港 (\d{2}:\d{2})", tc)
    if m:
        out["run_et"], out["run_hkt"] = m.group(1), m.group(2)
    for i, ln in enumerate(lines["tc"]):
        if ln.startswith("大市："):
            for code, name in FUTURES:
                m = re.search(re.escape(name) + r" ([+\-−]\d+(?:\.\d+)?)%", ln)
                if m:
                    out["futures"][code] = float(m.group(1).replace("−", "-"))
            m = re.search(r"VIX (\d+(?:\.\d+)?)(?:（([+\-−]\d+(?:\.\d+)?)）)?", ln)
            if m:
                out["vix"] = float(m.group(1))
                out["vix_change"] = float(m.group(2).replace("−", "-")) if m.group(2) else None
            m = re.search(r"QQQ \S+ ([\d,]+(?:\.\d+)?)（([+\-−]\d+(?:\.\d+)?)%，([+\-−]\d+(?:\.\d+)?) 個 ATR", ln)
            if m:
                out["qqq_price"] = float(m.group(1).replace(",", ""))
                out["qqq_change_pct"] = float(m.group(2).replace("−", "-"))
                out["qqq_gap_atr"] = float(m.group(3).replace("−", "-"))
        elif ln.startswith("開市情景："):
            out["scenario"] = {lang: (lines[lang][i].split("：", 1)[-1].split(": ", 1)[-1].strip() if i < len(lines[lang]) and lines[lang][i].strip()
                                      else ln.split("：", 1)[1].strip()) for lang in config.LANGS}
    return out


def ledger_stats(recs):
    """Same arithmetic as runner/ledger.py stats()."""
    n = len(recs)
    done = [r for r in recs if r["status"] != "PENDING"]
    trig = [r for r in recs if r.get("trigger_date")]
    closed = [r for r in trig if r["status"] in ("HIT_2R", "INVALIDATED")]
    rr = [r["realized_r"] for r in closed if r.get("realized_r") is not None]
    return {"listed": n, "pending": n - len(done), "triggered": len(trig), "open": sum(1 for r in recs if r["status"] == "TRIGGERED"),
            "closed": len(closed), "hit_2r": sum(1 for r in closed if r["status"] == "HIT_2R"),
            "invalidated": sum(1 for r in closed if r["status"] == "INVALIDATED"),
            "trigger_rate_pct": _r(len(trig) / len(done) * 100, 0) if done else None,
            "hit_2r_rate_pct": _r(sum(1 for r in closed if r["status"] == "HIT_2R") / len(closed) * 100, 0) if closed else None,
            "avg_r": _r(sum(rr) / len(rr), 2) if rr else None}


def _ledger_block(records):
    top = [r for r in records if r.get("group") == "top"]
    other = [r for r in records if r.get("group") == "other"]
    moved = sorted([r for r in top if r["status"] != "PENDING"], key=lambda r: (r.get("exit_date") or r.get("trigger_date") or r["date_listed"], r["ticker"]),
                   reverse=True)[:8]
    recent = [{"ticker": r["ticker"], "direction": r["direction"], "status": r["status"], "listed": r["date_listed"],
               "r": _r(r["realized_r"] if r.get("realized_r") is not None else r.get("current_r"), 2)} for r in moved]
    return {"focus": ledger_stats(top), "control": ledger_stats(other), "recent": recent,
            "closed_ids": sorted(r["id"] for r in top if r["status"] in ("HIT_2R", "INVALIDATED"))}


def build_context(brief, mode="daily"):
    """One JSON-safe dict. Keys that start with "_" are for the gate and the renderer and are never sent to the writer."""
    d, S = brief["data"], brief["summaries"]
    s, mk = d["summary"], d.get("market", {})
    series = d.get("series", {}).get("qqq", {})
    lv = mk.get("anchor_levels") or {}

    def level(key, skey):
        v = lv.get(key)
        if v is None and series.get(skey):
            v = series[skey][-1][1]
        return _r(v, 2)

    score_txt = lambda v: str(_r(v, 0)) if v is not None else None      # noqa: E731
    score = int(s.get("score_txt") or score_txt(s["score"]))
    held = bool(s.get("regime_held")) and s.get("regime_raw") not in (None, s["regime"])
    pillars = [{"key": p["key"], "name": tri(*PILLAR_NAMES.get(p["key"], (p.get("name", p["key"]),) * 3)), "weight_pct": _r(p["weight"], 0),
                "score": _r(p["score"], 0)} for p in mk.get("pillars") or [] if p.get("score") is not None]
    vix, vix3m = _r(mk.get("vix", s.get("vix")), 1), _r(mk.get("vix3m"), 1)
    ratio = _r(mk.get("vix_term"), 2)
    names = lambda i, key: tri(*(S[lg]["sectors"][i].get(key) if i < len(S[lg].get("sectors", [])) else s["sectors"][i].get(key) for lg in config.LANGS))  # noqa: E731
    order = sorted(range(len(s.get("sectors", []))), key=lambda i: (s["sectors"][i].get("ex21") is None, -(s["sectors"][i].get("ex21") or 0)))
    sec = lambda i: {"etf": s["sectors"][i]["code"], "name": names(i, "name"), "return_1m_pct": s["sectors"][i].get("r21"),      # noqa: E731
                     "excess_1m_pct": s["sectors"][i].get("ex21"), "pct_above_50dma": _r(s["sectors"][i].get("pct50"), 0)}
    events = []
    for i, x in enumerate(s.get("timeline", [])):
        if x.get("code") == "me":
            continue
        what = tri(*(S[lg]["timeline"][i]["what"] if i < len(S[lg].get("timeline", [])) else x["what"] for lg in config.LANGS))
        events.append({"hkt": x["hk"], "et": x["et"], "next_day_hkt": bool(x.get("next")), "what": what,
                       "kind": {"data": "macro", "earn": "earnings", "mkt": "market"}.get(x.get("code"), "other")})
    setups = []
    for i, p in enumerate(s.get("picks", [])[:3]):
        setups.append({"ticker": p["ticker"], "direction": "long" if p["side"] == "做多" else "short",
                       "pattern": tri(*(S[lg]["picks"][i]["setup"] if i < len(S[lg].get("picks", [])) else p["setup"] for lg in config.LANGS)),
                       "gate_open": bool(p.get("live"))})
    records = (brief.get("ledger") or {}).get("records", [])
    ctx = {
        "mode": mode, "brief_date": s["brief_date"], "data_as_of": s["asof"],
        "market_health_score": score, "score_previous_session": int(s.get("score_prev_txt") or score_txt(s.get("score_prev")) or score),
        "score_5_sessions_ago": int(s.get("score_5_txt") or score_txt(s.get("score_5")) or score),
        "regime_grade": s["regime"], "regime_name": tri(*(S[lg]["regime_name"] for lg in config.LANGS)),
        "grade_held_by_hysteresis": held, "score_band_grade": s.get("regime_raw") if held else s["regime"],
        "rule_state": tri(*(S[lg].get("side", "") for lg in config.LANGS)), "cycle": tri(*(S[lg].get("cycle", "") for lg in config.LANGS)),
        "gates_open": {"long": bool(s["gates"]["long"]), "pilot": bool(s["gates"]["pilot"]), "short": bool(s["gates"]["short"])},
        "qqq": {"close": level("close", "c") or _r(s.get("anchor_close"), 2), "ema21": level("ema21", "ema21"), "dma50": level("dma50", "s50"),
                "dma200": level("dma200", "s200")},
        "pillars": pillars,
        "breadth": {"pct_above_50dma": _r(mk.get("pct_above_50", s.get("pct50")), 0), "pct_above_200dma": _r(mk.get("pct_above_200"), 0),
                    "distribution_days_25_sessions": mk.get("distribution_days"),
                    "breakout_success_rate_pct": _r(mk.get("breakout_success_rate", s.get("bo_follow")), 0)},
        "volatility": {"vix": vix, "vix3m": vix3m, "vix_vix3m_ratio": ratio},
        "sectors_leading": [sec(i) for i in order[:3]], "sectors_lagging": [sec(i) for i in order[-3:]] if len(order) >= 6 else [],
        "tonight_events": events, "has_macro_or_earnings": any(e["kind"] in ("macro", "earnings") for e in events),
        "event_day": bool(s.get("event_day")),
        "rule_matched_setups": setups, "universe_size": s.get("universe"),
        "playbook_notes": tri(*([str(x) for x in S[lg].get("play", [])[:8]] for lg in config.LANGS)),
        "ledger": _ledger_block(records),
        "links": {"dashboard": config.site_url("tc"), "telegram_channel": config.telegram_public_url() or None,
                  "daily_post_hkt": config.daily_hkt(), "premarket_refresh_hkt": config.premarket_hkt(),
                  "premarket_refresh_et": config.premarket_et()},
    }
    if mode == "premarket":
        ctx["premarket"] = parse_preopen(brief["preopen"]["texts"]) if brief.get("preopen") else None
    week = []
    if mode == "weekly":
        week = [{"brief_date": h["date"], "score": _r(h.get("score"), 0), "grade": h.get("grade"), "qqq_close": _r(h.get("qqq_close"), 2),
                 "long_gate": bool(h.get("long_gate")), "short_gate": bool(h.get("short_gate")),
                 "breakout_success_rate_pct": _r(h.get("breakout_success_rate"), 0)} for h in (brief.get("history") or [])[-5:]]
        ctx["week"] = week
    # ---- for the gate ----
    tickers = {"QQQ", "SPY", "IWM"}
    for side in ("long", "short"):
        tickers.update(str(c.get("Ticker", "")) for c in d.get("candidates", {}).get(side, []))
    tickers.update(str(p.get("ticker", "")) for p in s.get("picks", []) + s.get("bgrade", []))
    tickers.update(str(o.get("Ticker", "")) for o in d.get("orders", []))
    tickers.update(str(x.get("code", "")) for x in s.get("sectors", []))
    tickers.update(str(r.get("ticker", "")) for r in records)
    tickers.update(re.findall(r"\b[A-Z]{2,5}\b", " ".join(str(x) for x in s.get("play", []))))     # tickers the playbook names (earnings risk)
    grades = {s["regime"]} | ({s.get("regime_raw")} if held else set()) | {w["grade"] for w in week if w.get("grade")}
    scores = {score, ctx["score_previous_session"], ctx["score_5_sessions_ago"]} | {w["score"] for w in week if w.get("score") is not None}
    ctx["_gate"] = {"tickers": sorted(t for t in tickers if t), "grades": sorted(g for g in grades if g), "scores": sorted(scores),
                    "score_exact": s.get("score"), "current_score": score, "current_grade": s["regime"]}
    ctx["_run_id"] = brief["run_id"]
    return ctx


def public(ctx):
    """The part of the context the writer sees."""
    return {k: v for k, v in ctx.items() if not k.startswith("_")}


def for_lang(ctx, lang):
    """The public context with every {tc, sc, en} value reduced to one language (shorter prompts, no mixed scripts)."""
    def walk(x):
        if isinstance(x, dict):
            if set(x) == set(config.LANGS):
                return x[lang]
            return {k: walk(v) for k, v in x.items()}
        if isinstance(x, list):
            return [walk(v) for v in x]
        return x
    return walk(public(ctx))
