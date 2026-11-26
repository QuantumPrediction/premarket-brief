"""Deterministic checks every post must pass before a publisher may send it (plus an optional short model review).

    failures = check("x", text, ctx)        # [] means the text may be published

Checks: leaked internal words, advice wording, tickers and numbers that are not in the brief's data, the score and
grade quoted, links, platform length limits, and Telegram HTML. Nothing here calls a network except llm_review().
"""
import json
import re
from html.parser import HTMLParser

from . import config, context

URL_RX = re.compile(r"https?://[^\s<>\"'）)]+", re.I)
TAG_RX = re.compile(r"<[^>]*>")
ALWAYS_OK_NUMBERS = {21, 50, 200, 100, 500, 400, 600, 52, 24, 2000}      # index and indicator names: 21EMA, 50DMA, S&P 500, 52-week...
SCORE_WORDS = r"(?:market health score|health score|score|健康分數|健康分数|健檢分數|分數|分数|評分|评分|得分)"
GRADE_WORDS = r"(?:regime|grade|市況級別|市况级别|級別|级别|等級|等级|評級|评级)"


def x_length(text):
    """Length the way X counts it: most Latin characters weigh 1, CJK and emoji weigh 2."""
    n = 0
    for ch in text:
        c = ord(ch)
        n += 1 if (c <= 0x10FF or 0x2000 <= c <= 0x200D or 0x2010 <= c <= 0x201F or 0x2032 <= c <= 0x2037) else 2
    return n


def visible(text, html=False):
    return TAG_RX.sub(" ", text).replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">") if html else text


# ---------- words ----------
def check_words(text):
    out = []
    for pat in config.BANNED_LEAKS:
        m = re.search(pat, text, re.I)
        if m:
            out.append(f"internal or data-vendor wording «{m.group(0)}» must not appear")
    clean = text
    for pat in config.ALLOWED_DISCLAIMERS:
        clean = re.sub(pat, " ", clean, flags=re.I)
    for pat in config.BANNED_ADVICE:
        m = re.search(pat, clean, re.I)
        if m:
            out.append(f"advice or promise wording «{m.group(0)}» is not allowed (describe rule-matched setups and gates objectively)")
    return out


# ---------- tickers ----------
def check_tickers(text, ctx):
    allowed = set(ctx["_gate"]["tickers"])
    body = URL_RX.sub(" ", text)
    body = re.sub(r"#\w+", " ", body)                                   # hashtags
    bad = []
    for m in re.finditer(r"(?<![A-Za-z0-9&$])\$?([A-Z]{2,5})(?![A-Za-z0-9])", body):
        t = m.group(1)
        if t in config.NOT_TICKERS or t in allowed:
            continue
        if t not in bad:
            bad.append(t)
    return [f"symbol «{t}» is not in today's data" for t in bad]


# ---------- numbers ----------
def _numbers_in(obj, into):
    if isinstance(obj, bool) or obj is None:
        return
    if isinstance(obj, (int, float)):
        into.add(round(abs(float(obj)), 4))
    elif isinstance(obj, str):
        for m in re.finditer(r"\d[\d,]*(?:\.\d+)?", obj):
            try:
                into.add(round(float(m.group(0).replace(",", "")), 4))
            except ValueError:
                pass
    elif isinstance(obj, dict):
        for k, v in obj.items():
            _numbers_in(str(k), into)                                   # names such as pct_above_50dma carry the indicator's own number
            _numbers_in(v, into)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _numbers_in(v, into)


def known_numbers(ctx):
    nums = set()
    _numbers_in(context.public(ctx), nums)
    _numbers_in(ctx["_gate"].get("score_exact"), nums)
    return nums


def check_numbers(text, ctx):
    """Every figure in the text must be a figure of the context (rounded no further than the text shows it).
    Small counts (0-10), index and indicator names (21EMA, S&P 500 ...) and clock times / dates of the brief pass."""
    known = known_numbers(ctx)
    body = URL_RX.sub(" ", text)
    body = re.sub(r"#\w+", " ", body)
    strings = json.dumps(context.public(ctx), ensure_ascii=False)
    bad = []
    for m in re.finditer(r"(?<![A-Za-z\d.])(\d{1,2}):(\d{2})(?!\d)", body):              # clock times
        if m.group(0) not in strings and m.group(0).zfill(5) not in strings:
            bad.append(m.group(0))
    body = re.sub(r"(?<![A-Za-z\d.])\d{1,2}:\d{2}(?!\d)", " ", body)
    for m in re.finditer(r"\d{4}-\d{2}-\d{2}|(?<![\d.])\d{1,2}[/\-]\d{1,2}(?![\d.%])|\d{1,2} ?月 ?\d{1,2} ?日", body):   # dates
        digits = [int(x) for x in re.findall(r"\d+", m.group(0))]
        if not any(all(f"{v:02d}" in day or str(v) in day for v in digits) for day in set(re.findall(r"\d{4}-\d{2}-\d{2}|\d{2}-\d{2}", strings))):
            bad.append(m.group(0))
    body = re.sub(r"\d{4}-\d{2}-\d{2}|(?<![\d.])\d{1,2}[/\-]\d{1,2}(?![\d.%])|\d{1,2} ?月 ?\d{1,2} ?日", " ", body)
    for m in re.finditer(r"(?<![A-Za-z\d.,])\d[\d,]*(?:\.\d+)?", body):
        raw = m.group(0).rstrip(",")
        try:
            v = float(raw.replace(",", ""))
        except ValueError:
            continue
        nd = len(raw.split(".")[1]) if "." in raw else 0
        if nd == 0 and (v <= 10 or v in ALWAYS_OK_NUMBERS):
            continue
        if any(abs(round(k, nd) - v) < 1e-9 or abs(k - v) < 1e-9 for k in known):
            continue
        if raw not in bad:
            bad.append(raw)
    return [f"figure «{b}» is not in today's data (cite numbers exactly as given)" for b in bad]


# ---------- score and grade ----------
def check_score_grade(text, ctx, require=True):
    g = ctx["_gate"]
    out = []
    scores = {float(x) for x in g["scores"]} | ({float(g["score_exact"])} if g.get("score_exact") is not None else set())
    cited = [float(m.group(1)) for m in re.finditer(SCORE_WORDS + r"\D{0,14}?(\d{1,3}(?:\.\d)?)(?![\d%])", text, re.I)]
    for v in cited:
        if v not in scores:
            out.append(f"score «{v:g}» does not match the data (Market Health Score is {g['current_score']})")
    grades = [m.group(1).upper() for m in re.finditer(GRADE_WORDS + r"\s*[:：]?\s*([A-E])(?![A-Za-z])", text, re.I)]
    grades += [m.group(1).upper() for m in re.finditer(r"(?<![A-Za-z])([A-E])\s*(?:級|级|區|区|[- ]grade\b|[- ]band\b)", text)]
    for gr in grades:
        if gr not in g["grades"]:
            out.append(f"grade «{gr}» does not match the data (regime grade is {g['current_grade']})")
    if require:
        if float(g["current_score"]) not in cited and not re.search(rf"(?<![\d.]){g['current_score']}(?![\d.%])", text):
            out.append(f"the post must state the Market Health Score {g['current_score']}")
        if g["current_grade"] not in grades:
            out.append(f"the post must state the regime grade {g['current_grade']}")
    return list(dict.fromkeys(out))


# ---------- links ----------
def check_urls(text, allow=True):
    urls = URL_RX.findall(text)
    if not allow:
        return [f"no links are allowed in this post (found {urls[0]})"] if urls else []
    ok = tuple(u for u in (config.site_base_url(), config.telegram_public_url()) if u)
    return [f"link «{u}» is not one of the brief's own addresses" for u in urls if not u.startswith(ok)]


# ---------- Telegram HTML ----------
class _Tags(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.stack, self.errors = [], []

    def handle_starttag(self, tag, attrs):
        if tag not in config.ALLOWED_TAGS:
            self.errors.append(f"tag <{tag}> is not supported by Telegram")
            return
        a = dict(attrs)
        if tag == "a" and not (a.get("href") or "").startswith(("https://", "http://", "tg://")):
            self.errors.append("<a> needs an href with a full link")
        if tag != "a" and tag != "code" and tag != "pre" and tag != "blockquote" and attrs:
            self.errors.append(f"<{tag}> must not have attributes")
        self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        self.errors.append(f"self-closing <{tag}/> is not supported by Telegram")

    def handle_endtag(self, tag):
        if not self.stack or self.stack[-1] != tag:
            self.errors.append(f"</{tag}> closes nothing or is out of order")
            if tag in self.stack:
                while self.stack and self.stack.pop() != tag:
                    pass
        else:
            self.stack.pop()

    def handle_entityref(self, name):
        if name not in ("lt", "gt", "amp", "quot"):
            self.errors.append(f"entity &{name}; is not supported by Telegram")


def check_telegram_html(text):
    p = _Tags()
    p.feed(text)
    p.close()
    errs = list(p.errors)
    errs += [f"<{t}> is never closed" for t in p.stack]
    rest = TAG_RX.sub("", text)
    if "<" in rest or ">" in rest:
        errs.append("a bare < or > must be written as &lt; or &gt;")
    if re.search(r"&(?!(?:lt|gt|amp|quot|#\d+|#x[0-9a-fA-F]+);)", text):
        errs.append("a bare & must be written as &amp;")
    return list(dict.fromkeys(errs))


# ---------- one platform ----------
def check(platform, text, ctx, mode=None):
    """platform: x, threads, telegram, xhs_title, xhs_body, hashtags. Returns the list of failures (empty = pass)."""
    mode = mode or ctx.get("mode", "daily")
    if not isinstance(text, str) or not text.strip():
        return ["the text is empty"]
    html = platform == "telegram"
    out = check_telegram_html(text) if html else []
    body = visible(text, html)
    out += check_words(text)
    out += check_tickers(body, ctx)
    out += check_numbers(body, ctx)
    if platform in ("x", "threads", "telegram", "xhs_body"):
        out += check_score_grade(body, ctx, require=mode in ("daily", "premarket"))
    if platform == "x":
        out += check_urls(text, allow=False)
        if x_length(text) > config.X_MAX:
            out.append(f"too long for X: {x_length(text)} of {config.X_MAX} characters (aim for {config.X_TARGET})")
    elif platform == "threads":
        out += check_urls(text, allow=False)
        if len(text) > config.THREADS_MAX:
            out.append(f"too long for Threads: {len(text)} of {config.THREADS_MAX} characters (aim for {config.THREADS_TARGET})")
    elif platform == "telegram":
        out += check_urls(text)
        if len(body) > config.TELEGRAM_TEXT_MAX:
            out.append(f"too long for Telegram: {len(body)} of {config.TELEGRAM_TEXT_MAX} characters")
    elif platform == "xhs_title":
        out += check_urls(text, allow=False)
        if len(text) > config.XHS_TITLE_MAX:
            out.append(f"title too long: {len(text)} of {config.XHS_TITLE_MAX} characters")
    elif platform in ("xhs_body", "hashtags"):
        out += check_urls(text, allow=False)
    return list(dict.fromkeys(out))


def check_posts(posts, ctx, mode=None):
    """All texts of one run. Returns {key: [failures]} for every key, e.g. "x_en", "threads_tc", "xhs_sc"."""
    report = {}
    for key, platform in (("x_en", "x"), ("threads_tc", "threads"), ("telegram_tc", "telegram")):
        if key not in posts:
            continue
        parts = posts[key] if isinstance(posts[key], list) else [posts[key]]
        fails = []
        for i, part in enumerate(parts):
            first = i == 0
            got = check(platform, part, ctx, mode) if first else [f for f in check(platform, part, ctx, mode) if "must state" not in f]
            fails += [f"part {i + 1}: {f}" if len(parts) > 1 else f for f in got]
        if not parts:
            fails.append("the text is empty")
        report[key] = fails
    if "xhs_sc" in posts:
        x = posts["xhs_sc"] or {}
        tags = x.get("hashtags") or []
        fails = [f"title: {f}" for f in check("xhs_title", x.get("title", ""), ctx, mode)]
        fails += [f"body: {f}" for f in check("xhs_body", x.get("body", ""), ctx, mode)]
        fails += [f"hashtags: {f}" for f in check("hashtags", " ".join("#" + t.lstrip("#") for t in tags), ctx, mode)] if tags else ["hashtags: none given"]
        if tags and not 5 <= len(tags) <= 8:
            fails.append(f"hashtags: {len(tags)} given, 5 to 8 needed")
        report["xhs_sc"] = fails
    return report


# ---------- optional short model review ----------
QA_SYSTEM = ("You review one short social media post about a rules-based US market brief before it is published. "
             "You are given the data the post was written from and the post. Report a problem only when you are sure of it: "
             "a number, date, ticker, sector or event that is not in the data or contradicts it; a claim about news, forecasts or causes "
             "that the data does not contain; or wording that tells the reader to trade or promises a result. "
             "Style, tone and length are not your concern.")
QA_SCHEMA = {"type": "object", "properties": {"pass": {"type": "boolean"}, "problems": {"type": "array", "items": {"type": "string"}}},
             "required": ["pass", "problems"], "additionalProperties": False}


def llm_review(key, text, ctx, ask):
    """ask(model, system, user, schema, max_tokens) -> dict; injected by generate_posts so this module stays network-free.
    Returns a list of failures; an unavailable reviewer is not a failure (the deterministic checks already ran)."""
    lang = key.rsplit("_", 1)[-1] if key.rsplit("_", 1)[-1] in config.LANGS else "tc"
    user = ("<data>\n" + json.dumps(context.for_lang(ctx, lang), ensure_ascii=False) + "\n</data>\n<post>\n"
            + (text if isinstance(text, str) else json.dumps(text, ensure_ascii=False)) + "\n</post>")
    try:
        got = ask(config.model_qa(), QA_SYSTEM, user, QA_SCHEMA, config.MAX_TOKENS_QA)
    except Exception as e:                                               # noqa: BLE001
        print(f"Model review skipped for {key}: {type(e).__name__}: {e}", flush=True)
        return []
    return [] if got.get("pass") else [f"reviewer: {p}" for p in got.get("problems", [])[:5]] or ["reviewer: did not pass"]
