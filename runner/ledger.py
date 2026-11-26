"""Signal ledger and regime history (kept on the data branch under state/ledger/, published with the website).

Every run of the brief:
  1. grades the open records again from their listing date, using only the daily bars after that date;
  2. adds today's setups: the top setups (A grade, or "ready" when the gate is closed) and, as a control group,
     the other candidates;
  3. upserts today's market record into regime_history.json.

Grading rules (fixed, the same for every record; no record is ever removed):
  PENDING      listed, not triggered yet
  TRIGGERED    the bar's high (short: low) reached the pivot within 5 trading days, before the invalidation level
               and before the earnings date; entry is the pivot, or the open when the bar gapped through it
  HIT_2R       after the trigger, the 2R level was reached before the invalidation level
  INVALIDATED  the invalidation level was reached first (before or after the trigger); when the invalidation level
               and the 2R level (or the pivot) are both reached on the same bar, the invalidation level counts first
  EXPIRED      not triggered within 5 trading days, or the earnings date arrived first
R is measured against the planned risk |pivot − invalidation|. A gap through a level fills at the open.
A ticker that is listed again while its record is still open is not added a second time.
"""
import datetime as dt
import json
import math
import os
import re

LISTING_DAYS = 5
MIN_SAMPLE = 10
OPEN = ("PENDING", "TRIGGERED")
STATUS_TC = {"PENDING": "待觸發", "TRIGGERED": "已觸發", "HIT_2R": "達 2R", "INVALIDATED": "已失效", "EXPIRED": "已過期"}


def _f(x):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(x) or math.isinf(x) else x


def _load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _save(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=0, separators=(",", ":"))
    os.replace(tmp, path)


def earnings_date(text, asof):
    """'02-23' or '2027-02-23' → the next such date on or after asof; anything else → None."""
    text = str(text or "").strip()
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
    if m:
        return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.search(r"(?<!\d)(\d{1,2})-(\d{1,2})(?!\d)", text)
    if not m:
        return None
    try:
        d = dt.date(asof.year, int(m.group(1)), int(m.group(2)))
    except ValueError:
        return None
    return d if d >= asof else dt.date(asof.year + 1, d.month, d.day)


def bars_after(G, ticker, asof):
    """Daily bars after asof as (date, open, high, low, close); missing days are skipped."""
    O, H, L, C = G["O"], G["H"], G["L"], G["C"]
    if ticker not in C.columns:
        return []
    idx = C.index[C.index > asof]
    out = []
    for d in idx:
        o, h, l, c = (_f(F.at[d, ticker]) for F in (O, H, L, C))
        if None in (h, l, c):
            continue
        out.append((d.date(), o if o is not None else c, h, l, c))
    return out


def grade(rec, bars):
    """Replay the record from its listing date. Returns the record with status and R fields set."""
    r = dict(rec)
    for k in ("trigger_date", "exit_date", "entry_px", "exit_px", "realized_r", "current_r", "note"):
        r[k] = None
    r["status"], r["days"] = "PENDING", 0
    long_ = r["direction"] == "long"
    sg = 1 if long_ else -1
    piv, inv, tgt = r["pivot"], r["invalidation"], r["target_2r"]
    risk = abs(piv - inv)
    earn = dt.date.fromisoformat(r["earnings"]) if r.get("earnings") else None
    if not risk > 0:
        r["status"], r["note"] = "EXPIRED", "no_risk"
        return r
    R = lambda px: round((px - r["entry_px"]) * sg / risk, 3)
    for d, o, h, l, c in bars:
        r["days"] += 1
        up_to = (lambda lvl: h >= lvl) if long_ else (lambda lvl: l <= lvl)
        down_to = (lambda lvl: l <= lvl) if long_ else (lambda lvl: h >= lvl)
        if r["status"] == "PENDING":
            if earn and d >= earn:
                r.update(status="EXPIRED", exit_date=str(d), note="earnings")
                break
            hit_p, hit_i = up_to(piv), down_to(inv)
            if hit_i and not hit_p:
                r.update(status="INVALIDATED", exit_date=str(d), note="before_trigger")
                break
            if hit_p:
                entry = max(o, piv) if long_ else min(o, piv)
                r.update(status="TRIGGERED", trigger_date=str(d), entry_px=round(entry, 4))
                if hit_i:                                        # same bar: the invalidation level counts first
                    r.update(status="INVALIDATED", exit_date=str(d), exit_px=inv, realized_r=R(inv), note="same_bar")
                    break
                if up_to(tgt):
                    r.update(status="HIT_2R", exit_date=str(d), exit_px=tgt, realized_r=R(tgt))
                    break
                r["current_r"] = R(c)
                continue
            if r["days"] >= LISTING_DAYS:
                r.update(status="EXPIRED", exit_date=str(d), note="no_trigger")
                break
        else:
            if down_to(inv):
                px = o if (o - inv) * sg <= 0 else inv               # gap through the level: the open
                r.update(status="INVALIDATED", exit_date=str(d), exit_px=round(px, 4), realized_r=R(px))
                break
            if up_to(tgt):
                px = o if (o - tgt) * sg >= 0 else tgt
                r.update(status="HIT_2R", exit_date=str(d), exit_px=round(px, 4), realized_r=R(px))
                break
            r["current_r"] = R(c)
    if r["status"] not in OPEN:
        r["current_r"] = None
    return r


def records_today(G, brief_date, asof):
    """Today's top setups and the other candidates (control group)."""
    top = [(c, "top") for c in list(G.get("T6_LA", [])) + list(G.get("T6_SA", []))]
    seen = {(c["Ticker"], c["Side"]) for c, _ in top}
    other = [(c, "other") for c in list(G.get("T6_L", [])) + list(G.get("T6_S", [])) if (c["Ticker"], c["Side"]) not in seen]
    long_ok, short_ok = bool(G.get("long_ok")), bool(G.get("T6_SGATE"))
    out = []
    for c, grp in top + other:
        piv, inv = _f(c.get("Trigger")), _f(c.get("Stop"))
        if piv is None or inv is None:
            continue
        long_ = c["Side"] == "多"
        risk = abs(piv - inv)
        e = G.get("EARN", {}).get(c["Ticker"]) if isinstance(G.get("EARN"), dict) else None
        e = e.date() if hasattr(e, "date") and callable(e.date) else e
        if not isinstance(e, dt.date) or e < asof:
            e = None if "剛公佈" in str(c.get("Earn", "")) else earnings_date(c.get("Earn"), asof)
        out.append({"id": f'{asof}_{c["Ticker"]}_{"L" if long_ else "S"}_{grp}', "date_listed": str(brief_date), "asof": str(asof),
                    "ticker": c["Ticker"], "direction": "long" if long_ else "short", "group": grp,
                    "grade": {"A": "A", "預備": "READY", "B": "B"}.get(str(c.get("Tier")), str(c.get("Tier"))),
                    "gate_open": long_ok if long_ else short_ok, "pattern": str(c.get("Setup", "")),
                    "pivot": round(piv, 4), "invalidation": round(inv, 4),
                    "target_2r": round(piv + 2 * risk if long_ else piv - 2 * risk, 4),
                    "earnings": str(e) if e else None, "status": "PENDING"})
    return out


def update(state, G):
    """Grade, add today's records, save. Returns (ledger list, regime history list)."""
    base = os.path.join(state, "ledger")
    p_led, p_reg = os.path.join(base, "signal_ledger.json"), os.path.join(base, "regime_history.json")
    led = _load(p_led, {"schema": 1, "records": []})
    recs = led.get("records", [])
    asof = G["ASOF"].date() if hasattr(G["ASOF"], "date") else G["ASOF"]
    brief_date = G["SESS_D"]
    import pandas as pd
    # 1. re-grade the open records (a rerun on the same day gives the same result)
    for i, r in enumerate(recs):
        if r["status"] in OPEN and r["asof"] < str(asof):
            recs[i] = grade(r, bars_after(G, r["ticker"], pd.Timestamp(r["asof"])))
    # 2. today's records: one open record per ticker, direction and group; same-day reruns replace their own records
    recs = [r for r in recs if not (r["asof"] == str(asof) and r["status"] == "PENDING" and r.get("days", 0) == 0)]
    open_keys = {(r["ticker"], r["direction"], r["group"]) for r in recs if r["status"] in OPEN}
    for r in records_today(G, brief_date, asof):
        if (r["ticker"], r["direction"], r["group"]) in open_keys:
            continue
        r.update(days=0, trigger_date=None, exit_date=None, entry_px=None, exit_px=None, realized_r=None, current_r=None, note=None)
        recs.append(r)
    recs.sort(key=lambda r: (r["asof"], r["group"], r["ticker"]))
    led = {"schema": 1, "rules": __doc__.split("Grading rules")[1].strip(), "updated": str(asof), "records": recs}
    _save(p_led, led)
    # 3. regime history
    reg = _load(p_reg, [])
    reg = [x for x in reg if x.get("date") != str(brief_date)]
    q = G.get("q")
    reg.append({"date": str(brief_date), "asof": str(asof), "run_et": f'{G["RUN_TS"]:%Y-%m-%d %H:%M}',
                "score": _f(G.get("score_now")), "grade": G.get("REG_L"), "qqq_close": _f(getattr(q, "c", None)),
                "long_gate": bool(G.get("LONG_GATE")), "pilot_gate": bool(G.get("PILOT_GATE")), "short_gate": bool(G.get("SHORT_GATE")),
                "breakout_success_rate": _f(G.get("BO_FOLLOW")), "event_day": bool(G.get("EVENT_DAY"))})
    reg.sort(key=lambda x: x["date"])
    _save(p_reg, reg)
    return recs, reg


def stats(recs):
    n = len(recs)
    done = [r for r in recs if r["status"] != "PENDING"]
    trig = [r for r in recs if r.get("trigger_date")]
    closed = [r for r in trig if r["status"] in ("HIT_2R", "INVALIDATED")]
    rr = [r["realized_r"] for r in closed if r.get("realized_r") is not None]
    return {"n": n, "pending": n - len(done), "triggered": len(trig), "open": sum(1 for r in recs if r["status"] == "TRIGGERED"),
            "trigger_rate": len(trig) / len(done) if done else None,
            "hit2r_rate": sum(1 for r in closed if r["status"] == "HIT_2R") / len(closed) if closed else None,
            "avg_r": sum(rr) / len(rr) if rr else None, "closed": len(closed)}


def summary(recs):
    top = [r for r in recs if r["group"] == "top"]
    return {"top": stats(top), "top_gate_open": stats([r for r in top if r.get("gate_open")]),
            "top_gate_closed": stats([r for r in top if not r.get("gate_open")]),
            "other": stats([r for r in recs if r["group"] == "other"]), "min_sample": MIN_SAMPLE}


def html_tc(recs, esc, note):
    """之前名單的跟進（繁體；網站另外翻譯成簡體和英文）。"""
    top = sorted([r for r in recs if r["group"] == "top"], key=lambda r: (r["date_listed"], r["ticker"]), reverse=True)
    S = summary(recs)

    def pct(x):
        return "—" if x is None else f"{x * 100:.0f}%"

    def rtxt(x):
        return "—" if x is None else f"{x + 0.0:+.2f}R"

    rows = []
    for g, lab in (("top_gate_open", "首選：閘門開（A 級）"), ("top_gate_closed", "首選：閘門關（預備）"), ("top", "首選合計"),
                   ("other", "其餘候選（對照組）")):
        s = S[g]
        if s["n"] == 0:
            continue
        if s["n"] < MIN_SAMPLE:
            rows.append(f'<tr><td>{esc(lab)}</td><td colspan="4" class="m">累積樣本中（{s["n"]} 筆）</td></tr>')
        else:
            rows.append(f'<tr><td>{esc(lab)}</td><td class="num">{s["n"]}</td><td class="num">{pct(s["trigger_rate"])}</td>'
                        f'<td class="num">{pct(s["hit2r_rate"])}</td><td class="num"><b>{rtxt(s["avg_r"])}</b></td></tr>')
    stat_tbl = ('<div class="tw"><table><thead><tr><th>組別</th><th class="num">總數</th><th class="num">觸發比率</th>'
                '<th class="num">達 2R 比率</th><th class="num">平均 R</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table></div>") if rows else ""
    badge = {"PENDING": "m", "TRIGGERED": "a", "HIT_2R": "g", "INVALIDATED": "r", "EXPIRED": "m"}
    body = []
    for r in top[:30]:
        rv = r["realized_r"] if r.get("realized_r") is not None else r.get("current_r")
        body.append(f'<tr><td><b>{esc(r["ticker"])}</b></td><td>{"做多" if r["direction"] == "long" else "做空"}'
                    f'{"" if r.get("gate_open") else "（預備）"}</td><td>{esc(r["date_listed"][5:])}</td>'
                    f'<td><b class="{badge[r["status"]]}">{STATUS_TC[r["status"]]}</b></td><td class="num">{r.get("days", 0)}</td>'
                    f'<td class="num">{rtxt(rv)}</td><td class="num">{r["pivot"]:,.2f}</td><td class="num">{r["invalidation"]:,.2f}</td></tr>')
    recent = ('<div class="tw"><table><thead><tr><th>代號</th><th>方向</th><th>列出日</th><th>狀態</th><th class="num">已過交易日</th>'
              '<th class="num">R（假設）</th><th class="num">觸發位</th><th class="num">失效位</th></tr></thead><tbody>' + "".join(body)
              + "</tbody></table></div>") if body else '<div class="note">未有紀錄：今日列出的形態會由下一個交易日開始跟進。</div>'
    n_top = S["top"]["n"]
    head = f"之前名單的跟進（首選 {n_top} 筆" + (f"，其中 {S['top']['triggered']} 筆已觸發" if n_top else "") + "）"
    return (f'<details open><summary style="font-size:13px;font-weight:600">{esc(head)}</summary>' + stat_tbl + recent
            + f'<div class="note">{esc(note)}</div></details>')
