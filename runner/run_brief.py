"""Cell 1 (v6.3) on GitHub Actions: run the full brief once, then save the page and a small summary for the website.

Settings come from GitHub repository variables and secrets (see README.md). Output goes into the
state folder, which the workflow keeps on the `data` branch between runs:
  state/premarket_out/              the script's own folder (daily_log.csv, tier_history.csv, latest_plan.json, ...)
  state/site/briefs/<run id>/       tc.html, brief_tc.txt, summary_tc.json, and the sc / en copies
"""
import datetime as dt
import html
import json
import math
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (HK, LANGS, ROOT, ensure_languages, env, env_bool, env_num, github_wording, now_et, redirect_page, run_script,
                    translate_doc, write)  # noqa: E402
import ledger  # noqa: E402

SCRIPT = "premarket_brief_v6_3.py"
HIST = "premarket_out"


def num(x, nd=2):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(x) else round(x, nd)


def summary(G):
    """Everything the website's home page shows, in the script's own words."""
    F, secn = G["F"], G.get("SECTOR_ETFS", {})
    sec = lambda t: secn.get(str(F.at[t, "SecETF"]), "") if (t in F.index and "SecETF" in F.columns) else ""

    def pick(c, tier, live=False):
        t = c["Ticker"]
        close, trig, stop = num(c.get("Close")), num(c.get("Trigger")), num(c.get("Stop"))
        dist = (trig / close - 1) * 100 if (close and trig) else None
        risk = abs(trig - stop) / trig * 100 if (trig and stop) else None
        return {"ticker": t, "name": str(G["NAME_OF"].get(t, "") or "")[:40], "side": "做多" if c.get("Side") == "多" else "做空",
                "tier": tier, "setup": str(c.get("Setup", "")), "sector": sec(t), "close": close, "trigger": trig, "stop": stop,
                "dist": num(dist, 1), "risk": num(risk, 1), "earn": str(c.get("Earn", "") or ""),
                "missing": str(c.get("Reason", "") or "") or "；".join(str(m[1]) for m in c.get("Miss", []) or []),   # what the brief shows as 尚欠
                "why": str(c.get("Why", "") or ""), "live": bool(live)}   # live = its gate is open today, so it can become an order

    long_ok, short_ok = bool(G.get("long_ok")), bool(G.get("T6_SGATE"))
    picks = ([pick(c, G.get("T6_TOP_L", "A 級"), long_ok) for c in G.get("T6_LA", [])]
             + [pick(c, G.get("T6_TOP_S", "A 級"), short_ok) for c in G.get("T6_SA", [])])
    bgrade = [pick(c, "B 級") for c in G.get("T6_LB", [])[:10]]
    timeline, day0 = [], None
    for x in G.get("T6_TL", []):
        ts, h = x["et"], x["et"].tz_convert(HK)
        day0 = day0 or h.date()
        timeline.append({"et": f"{ts:%H:%M}", "hk": f"{h:%H:%M}", "next": h.date() > day0, "what": str(x["what"]), "kind": str(x["kind"]),
                         "code": {"我": "me", "系統": "me", "市場": "mkt", "數據": "data", "財報": "earn"}.get(str(x["kind"]), "other")})
    secs = []
    st = G.get("SECT_TBL")
    if st is not None and len(st):
        secs = [{"code": r["ETF"], "name": r["Name"], "r21": num(r["R21"], 1), "r63": num(r["R63"], 1), "ex21": num(r["Ex21"], 1),
                 "pct50": num(r.get("Pct50"), 0)} for _, r in st.iterrows()]
    bud = G.get("T6_BUD", {}) or {}
    run_ts = G["RUN_TS"]
    sess = G["SESS_D"]
    return {
        "run_id": G["RUN_ID"], "brief_date": f"{sess:%Y-%m-%d}", "asof": f"{G['ASOF']:%Y-%m-%d}",
        "run_et": f"{run_ts:%Y-%m-%d %H:%M}", "run_hk": f"{run_ts.astimezone(HK):%Y-%m-%d %H:%M}" if getattr(run_ts, "tzinfo", None) else "",
        "regime": G["REG_L"], "regime_name": G["REG_T"], "side": G["SIDE"], "verdict": G.get("T6_VERDICT", ""),
        "cycle": G.get("CYCLE", ""), "short_timing": G.get("SHORT_TIMING", ""),
        "score": num(G["score_now"], 1), "score_prev": num(G["score_prev"], 1), "score_5": num(G["score_5"], 1),
        "gates": {"long": bool(G["LONG_GATE"]), "pilot": bool(G["PILOT_GATE"]), "short": bool(G["SHORT_GATE"]), "oversold": bool(G["OVERSOLD"])},
        "event_day": bool(G.get("EVENT_DAY")), "n_long": int(bud.get("n_long", 0) or 0), "n_short": int(bud.get("n_short", 0) or 0),
        "universe": len(G.get("TICKS", [])), "long_candidates": len(G.get("T6_L", [])),
        "pct50": num(G.get("pct50_now"), 0), "vix": num(G.get("vix_now"), 1), "bo_follow": num(G.get("BO_FOLLOW"), 0),
        "anchor": "QQQ", "anchor_close": num(G["q"].c, 2), "picks_live": long_ok or short_ok, "long_ok": long_ok, "short_ok": short_ok,
        "play": list(G.get("PLAY", []))[:8], "picks": picks, "bgrade": bgrade, "timeline": timeline, "sectors": secs,
    }


def plain(x):
    """Anything from the script, made safe for JSON (numpy numbers, dates, NaN, sets, small tables)."""
    if x is None or isinstance(x, (bool, str)):
        return x
    if isinstance(x, (int, float)):
        return None if isinstance(x, float) and (math.isnan(x) or math.isinf(x)) else x
    if isinstance(x, dict):
        return {str(k): plain(v) for k, v in x.items()}
    if isinstance(x, (list, tuple, set)):
        return [plain(v) for v in x]
    if hasattr(x, "item") and not hasattr(x, "columns"):       # numpy scalar
        try:
            return plain(x.item())
        except (ValueError, TypeError):
            pass
    if hasattr(x, "isoformat"):
        return x.isoformat()
    if hasattr(x, "to_dict") and hasattr(x, "columns"):         # a small DataFrame
        return [plain(r) for r in x.to_dict("records")]
    return str(x)


CAND_KEYS = ("Ticker", "Side", "Tier", "Setup", "Main", "Close", "Trigger", "Entry", "Pivot", "Chase", "Stop", "StopSrc", "Risk%", "Dist%",
             "Through", "NPass", "NFail", "Fails", "Ck", "RS", "ATR%", "Earn", "Reason", "Why", "Shares", "Pos%")


def data_json(G, s, recs):
    """One structured file per run with the brief's numbers, tables and chart series, for other front ends."""
    def series(obj, n=250):
        try:
            x = obj.dropna().iloc[-n:]
            return [[f"{d:%Y-%m-%d}", round(float(v), 4)] for d, v in x.items()]
        except Exception:                                            # noqa: BLE001
            return []
    Q = G.get("Q")
    qqq = {k: series(Q[k]) for k in ("c", "ema21", "s50", "s200")} if Q is not None else {}
    cands = {side: [{k: plain(c.get(k)) for k in CAND_KEYS} for c in G.get(name, [])] for side, name in (("long", "T6_L"), ("short", "T6_S"))}
    return plain({
        "schema": 1, "generated_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "summary": s,
        "market": {"score": G.get("score_now"), "regime": G.get("REG_L"), "regime_name": G.get("REG_T"), "rule_state": G.get("SIDE"),
                   "cycle": G.get("CYCLE"), "short_timing": G.get("SHORT_TIMING"), "event_day": G.get("EVENT_DAY"),
                   "gates": s.get("gates"), "budget": G.get("T6_BUD"), "breakout_success_rate": G.get("BO_FOLLOW"),
                   "pct_above_50": G.get("pct50_now"), "vix": G.get("vix_now")},
        "demo_account": {"equity": G.get("ACCOUNT_EQUITY"), "base_risk_pct": G.get("BASE_RISK_PCT")},
        "candidates": cands, "orders": G.get("T6_ORD", []), "playbook": list(G.get("PLAY", [])), "quality": list(G.get("quality", [])),
        "series": {"score": series(G.get("SCORE")) if G.get("SCORE") is not None else [], "qqq": qqq},
        "ledger": {"summary": ledger.summary(recs), "recent": [r for r in recs if r["group"] == "top"][-60:]},
    })


def prune(state, keep_days):
    """Keep the data branch small: site archive for keep_days, the script's daily folders for 14 days."""
    today = now_et().date()
    for sub in ("site/briefs", "site/preopen"):
        base = os.path.join(state, sub)
        if not os.path.isdir(base):
            continue
        by_date = {}
        for r in os.listdir(base):                             # several runs for one brief date: keep the newest only
            try:
                run_et = json.load(open(os.path.join(base, r, "summary_tc.json"), encoding="utf-8")).get("run_et", "")
            except (OSError, ValueError):
                continue
            by_date.setdefault(r[:10], []).append((run_et, r))
        for runs in by_date.values():
            keep = sorted(runs)[-1][1]
            older = [r for _, r in sorted(runs)[:-1]]
            older += [r for r in os.listdir(base) if r[:10] == keep[:10] and r != keep and r not in older]   # earlier forwards
            for r in older:                                    # an older run of the same date: its links now open the newest run
                shutil.rmtree(os.path.join(base, r), ignore_errors=True)
                for lang in LANGS:
                    write(os.path.join(base, r, f"{lang}.html"), redirect_page(f"../{keep}/{lang}.html"))
        for r in sorted(os.listdir(base))[:-5]:                # always keep the last 5
            try:
                d = dt.date.fromisoformat(r[:10])
            except ValueError:
                continue
            if (today - d).days > keep_days:
                shutil.rmtree(os.path.join(base, r), ignore_errors=True)
    hist = os.path.join(state, HIST)
    for month in os.listdir(hist) if os.path.isdir(hist) else []:
        mdir = os.path.join(hist, month)
        if not (os.path.isdir(mdir) and len(month) == 7):
            continue
        for root, dirs, files in os.walk(mdir, topdown=False):
            for fn in files:
                d = None
                for part in [fn] + os.path.relpath(root, mdir).split(os.sep)[::-1]:   # file name, else its folder (data/<run id>/)
                    try:
                        d = dt.date.fromisoformat(part[:10])
                        break
                    except ValueError:
                        continue
                if d and (today - d).days > 14:
                    os.remove(os.path.join(root, fn))
            for dn in dirs:
                p = os.path.join(root, dn)
                if os.path.isdir(p) and not os.listdir(p):
                    os.rmdir(p)
        if not os.listdir(mdir):
            os.rmdir(mdir)


def main():
    state = os.path.abspath(env("STATE_DIR", os.path.join(ROOT, "state")))
    acct = env_num("DEMO_ACCOUNT", 100000)
    values = dict(
        ACCOUNT_EQUITY=int(acct) if acct == int(acct) else acct, BASE_RISK_PCT=env_num("RISK_PCT", 0.75),
        MAX_HEAT_PCT=env_num("MAX_HEAT_PCT", 0), POSITIONS_TEXT=env("DEMO_POSITIONS", ""),
        UNIVERSE=env("UNIVERSE", "sp500+ndx100+sp400"), EXTRA_TICKERS_TEXT=env("EXTRA_TICKERS", ""), SAVE_TO_DRIVE=False,
        FETCH_EVENTS=True, SCAN_PREMARKET=True, HTF_WIDE_SCAN=env_bool("HTF_WIDE_SCAN", False), USE_OPENBB=env_bool("USE_OPENBB", True),
        PRINT_NEWS_TEXT=False, AI_NEWS=env_bool("AI_NEWS", False) and bool(os.environ.get("ANTHROPIC_API_KEY")),
        AI_MODEL=env("AI_MODEL", "claude-sonnet-5-5"))
    print(f"Running cell 1 (v6.3) · universe {values['UNIVERSE']} · account {values['ACCOUNT_EQUITY']:,} · risk {values['BASE_RISK_PCT']}% "
          f"· AI news {'on' if values['AI_NEWS'] else 'off'}", flush=True)
    os.environ["PMB_WEB"] = "1"                                                  # web edition: the text summary is a linked .txt file
    G = run_script(os.path.join(ROOT, "scripts", SCRIPT), values, state)

    run_id = G["RUN_ID"]
    out = os.path.join(state, "site", "briefs", run_id)
    dash = github_wording(open(os.path.join(state, G["DASH_PATH"]), encoding="utf-8").read())   # the script's paths are relative to state/
    txt = github_wording(G["BRIEF_TXT"] + "\n\n" + G["NEWS_TXT"])
    dash = re.sub(r"<svg.*?</svg>", lambda m: re.sub(r"(?<=\d)\.0(?!\d)", "", m.group(0)), dash, flags=re.S)   # 12.0 -> 12 inside charts
    s = summary(G)
    try:                                                                          # the follow-up section comes from the ledger
        recs, _ = ledger.update(state, G)
        led = ledger.html_tc(recs, lambda x: html.escape(str(x), quote=True), G.get("LEDGER_NOTE", ""))
        dash = re.sub(r"<!--ledger-->.*?<!--/ledger-->", lambda m: "<!--ledger-->" + led + "<!--/ledger-->", dash, count=1, flags=re.S)
        s["ledger"] = ledger.summary(recs)
    except Exception as e:                                                        # noqa: BLE001 - the brief still publishes
        print(f"Ledger skipped: {type(e).__name__}: {e}", flush=True)
        recs = []
    write(os.path.join(out, "tc.html"), translate_doc(dash, "tc"))
    write(os.path.join(out, "brief_tc.txt"), txt)
    write(os.path.join(out, "summary_tc.json"), json.dumps(s, ensure_ascii=False, indent=1))
    try:
        write(os.path.join(out, "data.json"), json.dumps(data_json(G, s, recs), ensure_ascii=False, separators=(",", ":")))
    except Exception as e:                                                        # noqa: BLE001
        print(f"data.json skipped: {type(e).__name__}: {e}", flush=True)
    ensure_languages(out)                                                         # Simplified Chinese and English copies
    write(os.path.join(state, "marks", "brief.txt"), f"{now_et():%Y-%m-%d} {run_id}\n")
    prune(state, int(env_num("ARCHIVE_DAYS", 365)))
    print(f"Saved site files for {run_id} in {out}")


if __name__ == "__main__":
    main()
