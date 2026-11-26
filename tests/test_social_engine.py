"""Tests of the social engine: compliance gate, post log (no double posting), cards, publishers (with a fake network).

    pytest tests/test_social_engine.py

tests/fixtures/sample_state is a trimmed copy of a real run (brief date 2026-11-27) laid out like the state folder;
the pre-open text in it is a sample in the pre-open script's own format.
"""
import datetime as dt
import json
import os
import shutil
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "sample_state")
SOCIAL_ENV = ("ENABLE_TELEGRAM_PUBLIC", "ENABLE_TELEGRAM_DRAFTS", "ENABLE_THREADS", "ENABLE_X", "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN",
              "TELEGRAM_BOT_TOKEN", "TELEGRAM_PUBLIC_CHAT_ID", "TELEGRAM_DRAFTS_CHAT_ID", "THREADS_USER_ID", "THREADS_ACCESS_TOKEN",
              "X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_SECRET", "TELEGRAM_PUBLIC_URL", "SITE_BASE_URL", "BUILD_MODE")


@pytest.fixture()
def state(tmp_path, monkeypatch):
    dst = tmp_path / "state"
    shutil.copytree(FIXTURE, dst)
    for k in SOCIAL_ENV:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("STATE_DIR", str(dst))
    monkeypatch.setenv("SOCIAL_PREVIEW_DIR", str(tmp_path / "preview"))
    return str(dst)


@pytest.fixture()
def ctx(state):
    from social_engine import context
    return context.build_context(context.load_brief(state), "daily")


def gate():
    from social_engine import compliance_gate
    return compliance_gate


GOOD_X = "Market Health Score 29 · Regime E\n• Short gate open\n• 56% above 50DMA\n• XLP +12.8% 1M excess\nLink in bio."


# ---------------- context ----------------
def test_context_reads_the_brief(ctx):
    assert ctx["market_health_score"] == 29 and ctx["regime_grade"] == "E"
    assert ctx["grade_held_by_hysteresis"] and ctx["score_band_grade"] == "D"
    assert [s["etf"] for s in ctx["sectors_leading"]] == ["XLP", "XLRE", "XLV"]
    assert [s["etf"] for s in ctx["sectors_lagging"]] == ["XLI", "XLE", "XLK"]
    assert [p["score"] for p in ctx["pillars"]] == [17, 55, 25, 0, 50]
    assert ctx["qqq"] == {"close": 633.93, "ema21": 666.84, "dma50": 707.05, "dma200": 683.5}
    assert "XLK" in ctx["_gate"]["tickers"] and "USFD" in ctx["_gate"]["tickers"]
    assert all(set(s) == {"ticker", "direction", "pattern", "gate_open"} for s in ctx["rule_matched_setups"])    # tags only: no prices


def test_preopen_text_is_parsed(state):
    from social_engine import context
    c = context.build_context(context.load_brief(state), "premarket")
    p = c["premarket"]
    assert p["futures"] == {"NQ": 0.35, "ES": 0.2, "RTY": -0.1}
    assert (p["vix"], p["vix_change"], p["qqq_price"], p["qqq_change_pct"], p["qqq_gap_atr"]) == (27.5, -0.79, 640.0, 0.96, 0.26)
    assert p["run_hkt"] == "21:47"


# ---------------- compliance gate ----------------
def test_good_post_passes(ctx):
    assert gate().check("x", GOOD_X, ctx) == []


def test_blocks_hallucinated_ticker(ctx):
    fails = gate().check("x", GOOD_X.replace("XLP +12.8%", "NVDA +12.8%"), ctx)
    assert any("NVDA" in f for f in fails)


def test_standard_acronyms_are_not_tickers(ctx):
    text = GOOD_X + "\nVIX 28.3, FOMC, CPI, ETF, 21EMA, VIX3M, HKT, AI"
    assert not any("symbol" in f for f in gate().check("x", text, ctx))


@pytest.mark.parametrize("leak", ["Yahoo Finance", "yhoof2", "^GSPC", "^IXIC", "OpenBB", "fred_api", "Colab", "跑格子", "Sharpe 1.2", "四關", "scan.csv"])
def test_blocks_internal_leaks(ctx, leak):
    assert any("internal" in f for f in gate().check("threads", f"市場健康分數 29，市況級別 E。{leak}", ctx))


@pytest.mark.parametrize("phrase", ["落單", "照抄", "買入訊號", "賣出訊號", "必升", "必跌", "穩賺", "保證獲利", "必賺", "穩贏", "Buy now", "short now",
                                    "GUARANTEED", "this is financial advice"])
def test_blocks_advice_wording(ctx, phrase):
    assert any("advice or promise" in f for f in gate().check("threads", f"市場健康分數 29，市況級別 E。{phrase}", ctx))


@pytest.mark.parametrize("ok", ["Not financial advice.", "非投資建議", "非投资建议", "not investment advice"])
def test_disclaimers_are_allowed(ctx, ok):
    assert gate().check("threads", f"市場健康分數 29，市況級別 E。{ok}", ctx) == []


def test_blocks_oversized_tweet(ctx):
    long = GOOD_X + "\n" + "Breadth is weak. " * 20
    assert any("too long for X" in f for f in gate().check("x", long, ctx))


def test_x_counts_cjk_and_emoji_double():
    g = gate()
    assert g.x_length("abc") == 3 and g.x_length("市況") == 4 and g.x_length("🟢") == 2


@pytest.mark.parametrize("url", ["https://quantumprediction.github.io/premarket-brief/", "http://t.me/x", "HTTPS://example.com"])
def test_blocks_urls_in_x(ctx, url):
    assert any("no links" in f for f in gate().check("x", GOOD_X + " " + url, ctx))


def test_blocks_wrong_score_and_grade(ctx):
    g = gate()
    assert any("score «31»" in f for f in g.check("x", GOOD_X.replace("Score 29", "Score 31"), ctx))
    assert any("grade «C»" in f for f in g.check("x", GOOD_X.replace("Regime E", "Regime C"), ctx))
    assert any("must state the Market Health Score" in f for f in g.check("x", "Regime E\n• Short gate open", ctx))
    assert any("must state the regime grade" in f for f in g.check("x", "Market Health Score 29\n• Short gate open", ctx))


def test_hysteresis_band_grade_is_allowed(ctx):
    assert gate().check("threads", "市場健康分數 29，屬 D 區，暫維持 E 級。市況級別 E。", ctx) == []


def test_blocks_invented_figures(ctx):
    g = gate()
    assert any("«57»" in f for f in g.check("x", GOOD_X.replace("56%", "57%"), ctx))
    assert any("«650.25»" in f for f in g.check("x", GOOD_X + "\nQQQ 650.25", ctx))
    assert g.check("x", GOOD_X + "\nQQQ 633.93, 21EMA 666.84, 200DMA 683.50", ctx) == []       # 683.5 may be written 683.50
    assert any("«20:00»" in f for f in g.check("x", GOOD_X + "\n20:00 HKT", ctx))
    assert g.check("x", GOOD_X + "\nUS open 22:30 HKT", ctx) == []


def test_threads_limit(ctx):
    assert any("too long for Threads" in f for f in gate().check("threads", "市場健康分數 29，市況級別 E。" + "寬度偏弱。" * 110, ctx))


def test_telegram_html(ctx):
    g = gate()
    ok = "<b>美股盤前簡報</b>\n市場健康分數 <b>29</b>・市況級別 <b>E</b>\n<i>非投資建議</i> <code>QQQ</code> <a href=\"https://quantumprediction.github.io/premarket-brief/\">網站</a>"
    assert g.check("telegram", ok, ctx) == []
    assert any("never closed" in f for f in g.check("telegram", ok + "<b>未關", ctx))
    assert any("out of order" in f for f in g.check("telegram", ok.replace("<b>29</b>", "<b><i>29</b></i>"), ctx))
    assert any("not supported" in f for f in g.check("telegram", ok + "<div>x</div>", ctx))
    assert any("bare <" in f for f in g.check("telegram", ok + " 8 < 10", ctx))
    assert any("bare &" in f for f in g.check("telegram", ok + " S&P", ctx))
    assert any("href" in f for f in g.check("telegram", ok + "<a>x</a>", ctx))
    assert any("not one of the brief's own" in f for f in g.check("telegram", ok + ' <a href="https://example.com/">x</a>', ctx))


def test_xhs_pack_rules(ctx):
    g = gate()
    good = {"title": "美股盘前｜健康分29・E级", "body": "1. 市况：健康分数 29，市况级别 E。\n非投资建议。", "hashtags": ["美股", "美股复盘", "波段交易", "美股盘前", "量化筛选"]}
    assert g.check_posts({"xhs_sc": good}, ctx)["xhs_sc"] == []
    assert any("title too long" in f for f in g.check_posts({"xhs_sc": {**good, "title": "美" * 21}}, ctx)["xhs_sc"])
    assert any("5 to 8" in f for f in g.check_posts({"xhs_sc": {**good, "hashtags": ["美股"]}}, ctx)["xhs_sc"])


def test_fixed_sentence_copy_passes_in_every_mode(state):
    from social_engine import context, generate_posts
    brief = context.load_brief(state)
    for mode in ("daily", "premarket", "ledger", "weekly"):
        got = generate_posts.gated(context.build_context(brief, mode), mode)
        assert got["source"] == "template"
        assert {k: v["failures"] for k, v in got["report"].items()} == {k: [] for k in generate_posts.MODE_KEYS[mode]}, mode


def test_one_repair_then_block(ctx, monkeypatch):
    """A failing draft gets exactly one rewrite with the reasons; a second failure is final."""
    from social_engine import generate_posts
    calls = []
    monkeypatch.setattr(generate_posts, "have_key", lambda: True)

    def fake_ask(model, system, user, schema, max_tokens):
        calls.append(user)
        return {"x_en": "Market Health Score 29 · Regime E. Buy now."}
    monkeypatch.setattr(generate_posts, "ask", fake_ask)
    got = generate_posts.gated(ctx, "daily", posts={"x_en": ["Market Health Score 29 · Regime E. NVDA guaranteed."]}, source="claude", qa=False)
    assert len(calls) == 1 and "NVDA" in calls[0] and "rejected by the checker" in calls[0]
    rep = got["report"]["x_en"]
    assert rep["repaired"] and not rep["ok"] and any("Buy now" in f or "buy now" in f.lower() for f in rep["failures"])

    monkeypatch.setattr(generate_posts, "ask", lambda *a: {"x_en": GOOD_X})
    got = generate_posts.gated(ctx, "daily", posts={"x_en": ["Score 31, Regime E"]}, source="claude", qa=False)
    assert got["report"]["x_en"]["ok"] and got["report"]["x_en"]["repaired"] and got["posts"]["x_en"] == [GOOD_X]


# ---------------- post log: no double posting ----------------
class FakeResponse:
    def __init__(self, body, status=200):
        self._body, self.status_code = body, status

    def json(self):
        return self._body


def enable(monkeypatch, *platforms):
    from social_engine import config
    for p in platforms:
        monkeypatch.setenv(config.FLAG[p], "true")
        for k in config.SECRETS[p]:
            monkeypatch.setenv(k, "test-value")


def run(*argv):
    from social_engine import run_social
    return run_social.main(list(argv))


def test_retry_does_not_post_twice(state, monkeypatch):
    from social_engine import config, run_social
    from social_engine.publishers import telegram_pub, x_pub
    enable(monkeypatch, "telegram_public", "x")
    sent = {"telegram": 0, "x": 0}
    monkeypatch.setattr(run_social.render_cards, "render", lambda *a, **k: ({}, []))
    monkeypatch.setattr(telegram_pub, "post_public", lambda *a, **k: sent.__setitem__("telegram", sent["telegram"] + 1) or {"message_ids": [1]})
    monkeypatch.setattr(x_pub, "post_thread", lambda *a, **k: sent.__setitem__("x", sent["x"] + 1) or {"ids": ["9"]})
    monkeypatch.setattr(telegram_pub, "alert", lambda *a, **k: True)
    assert run("--mode", "daily", "--publish-only") == 0
    assert sent == {"telegram": 1, "x": 1}
    log = json.load(open(config.post_log_path(state)))
    assert log["posts"]["2026-11-27|daily|x"]["status"] == "posted" and log["posts"]["2026-11-27|daily|telegram_public"]["message_ids"] == [1]
    assert run("--mode", "daily", "--publish-only") == 0        # the workflow is re-run
    assert run("--mode", "daily", "--publish-only", "--platform", "x") == 0
    assert sent == {"telegram": 1, "x": 1}
    assert run("--mode", "premarket", "--publish-only") == 0    # another mode is its own entry
    assert sent == {"telegram": 2, "x": 2}


def test_failed_platform_is_retried_but_posted_one_is_not(state, monkeypatch):
    from social_engine import config, run_social
    from social_engine.publishers import PublishError, telegram_pub, x_pub
    enable(monkeypatch, "telegram_public", "x")
    sent, alerts, fail = {"telegram": 0, "x": 0}, [], {"x": True}
    monkeypatch.setattr(run_social.render_cards, "render", lambda *a, **k: ({}, []))
    monkeypatch.setattr(telegram_pub, "post_public", lambda *a, **k: sent.__setitem__("telegram", sent["telegram"] + 1) or {"message_ids": [1]})

    def x_post(*a, **k):
        if fail["x"]:
            raise PublishError("X post: 429 rate limit")
        sent["x"] += 1
        return {"ids": ["9"]}
    monkeypatch.setattr(x_pub, "post_thread", x_post)
    monkeypatch.setattr(telegram_pub, "alert", lambda text, **k: alerts.append(text) or True)
    assert run("--mode", "daily", "--publish-only") == 0         # an outage never fails the run
    assert sent == {"telegram": 1, "x": 0} and "429" in alerts[-1]
    assert "2026-11-27|daily|x" not in json.load(open(config.post_log_path(state)))["posts"]
    fail["x"] = False
    assert run("--mode", "daily", "--publish-only") == 0
    assert sent == {"telegram": 1, "x": 1}


def test_nothing_is_posted_when_flags_are_off_or_dry_run(state, monkeypatch):
    from social_engine import run_social
    from social_engine.publishers import telegram_pub, threads_pub, x_pub

    def boom(*a, **k):
        raise AssertionError("a publisher was called")
    for mod, name in ((telegram_pub, "post_public"), (telegram_pub, "post_xhs_pack"), (threads_pub, "post_thread"), (x_pub, "post_thread")):
        monkeypatch.setattr(mod, name, boom)
    monkeypatch.setattr(run_social.render_cards, "render", lambda *a, **k: ({}, []))
    assert run("--mode", "daily", "--publish-only") == 0         # every ENABLE_* flag is unset
    enable(monkeypatch, "telegram_public", "xhs_drafts", "threads", "x")
    assert run("--mode", "daily", "--dry-run") == 0
    preview = os.path.join(os.environ["SOCIAL_PREVIEW_DIR"], "2026-11-27")
    assert {"daily_posts.md", "daily_posts.json", "daily_compliance_report.json"} <= set(os.listdir(preview))


def test_blocked_text_is_not_published_and_is_reported(state, monkeypatch):
    from social_engine import generate_posts, run_social
    from social_engine.publishers import telegram_pub, x_pub
    enable(monkeypatch, "x")
    alerts = []
    monkeypatch.setattr(run_social.render_cards, "render", lambda *a, **k: ({}, []))
    monkeypatch.setattr(generate_posts, "template_posts", lambda c, m: {"x_en": "Market Health Score 29 · Regime E. NVDA guaranteed. Buy now."})
    monkeypatch.setattr(x_pub, "post_thread", lambda *a, **k: (_ for _ in ()).throw(AssertionError("posted a blocked text")))
    monkeypatch.setattr(telegram_pub, "alert", lambda text, **k: alerts.append(text) or True)
    assert run("--mode", "daily", "--publish-only", "--platform", "x") == 0
    assert "blocked by the compliance gate" in alerts[-1] and "NVDA" in alerts[-1]
    assert run("--mode", "daily", "--publish-only", "--platform", "x", "--force", "--strict") == 1


def test_ledger_mode_skips_until_a_setup_triggers(state, monkeypatch):
    from social_engine import context, run_social
    c = context.build_context(context.load_brief(state), "ledger")
    assert c["ledger"]["focus"]["triggered"] == 0
    assert "triggered" in run_social.skip_reason(c, "ledger", run_social.load_log("/nonexistent"))
    c["ledger"]["focus"]["triggered"], c["ledger"]["closed_ids"] = 2, ["a"]
    assert run_social.skip_reason(c, "ledger", {"posts": {}}) is None
    assert "no setup closed" in run_social.skip_reason(c, "ledger", {"ledger": {"brief_date": "2026-11-26", "closed_ids": ["a"]}})
    assert run_social.skip_reason(c, "ledger", {"ledger": {"brief_date": "2026-11-26", "closed_ids": []}}) is None      # a setup closed since
    assert run_social.skip_reason(c, "ledger", {"ledger": {"brief_date": "2026-11-23", "closed_ids": ["a"]}}) is None   # twice a week


# ---------------- publishers (fake network) ----------------
def test_telegram_long_caption_becomes_a_follow_up_message(tmp_path, monkeypatch):
    from social_engine.publishers import telegram_pub
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    monkeypatch.setenv("TELEGRAM_PUBLIC_CHAT_ID", "@c")
    img = tmp_path / "a.png"
    img.write_bytes(b"png")
    calls = []

    class S:
        def post(self, url, data=None, files=None, timeout=None):
            calls.append((url.rsplit("/", 1)[-1], dict(data or {})))
            return FakeResponse({"ok": True, "result": {"message_id": len(calls)}})
    telegram_pub.post_public("<b>短</b>", str(img), session=S())
    assert calls[0][0] == "sendPhoto" and calls[0][1]["parse_mode"] == "HTML" and "開啟完整盤前簡報" in calls[0][1]["reply_markup"] and len(calls) == 1
    calls.clear()
    telegram_pub.post_public("<b>長</b>" + "字" * 1100, str(img), session=S())
    assert [c[0] for c in calls] == ["sendPhoto", "sendMessage"]
    assert "caption" not in calls[0][1] and "reply_markup" not in calls[0][1] and "reply_markup" in calls[1][1]


def test_telegram_errors_never_show_the_token(monkeypatch):
    import requests
    from social_engine.publishers import PublishError, telegram_pub
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:SECRET")

    class S:
        def post(self, url, **k):
            raise requests.ConnectionError(f"cannot reach {url}")
    with pytest.raises(PublishError) as e:
        telegram_pub.send_message("@c", "x", session=S())
    assert "SECRET" not in str(e.value)


def test_threads_carousel_flow(monkeypatch):
    from social_engine.publishers import threads_pub
    monkeypatch.setenv("THREADS_USER_ID", "42")
    monkeypatch.setenv("THREADS_ACCESS_TOKEN", "tok")
    calls, heads = [], {"n": 0}

    class S:
        def head(self, url, **k):
            heads["n"] += 1
            return FakeResponse({}, 404 if heads["n"] <= 4 else 200)        # the first round of four is not deployed yet

        def request(self, method, url, params=None, data=None, timeout=None):
            path = url.split("v1.0/")[1]
            calls.append((method, path, dict(params or data or {})))
            if method == "GET":
                return FakeResponse({"status": "FINISHED"})
            return FakeResponse({"id": f"id{len(calls)}"})
    urls = [f"https://example.github.io/social/2026-11-27/carousel_tc_0{i}.png" for i in range(1, 5)]
    got = threads_pub.post_thread(["說明文字"], urls, session=S(), sleep=lambda s: None)
    assert heads["n"] == 8
    posts = [c for c in calls if c[0] == "POST"]
    assert [c[2].get("media_type") for c in posts[:5]] == ["IMAGE"] * 4 + ["CAROUSEL"]
    assert all(c[2]["is_carousel_item"] == "true" for c in posts[:4])
    assert posts[4][2]["children"].count(",") == 3 and posts[4][2]["text"] == "說明文字"
    assert posts[5][1] == "42/threads_publish" and got["ids"] == [posts[5] and "id" + str(len(calls))]


def test_threads_waits_for_public_images_then_gives_up():
    from social_engine.publishers import PublishError, threads_pub

    class S:
        def head(self, url, **k):
            return FakeResponse({}, 404)
    naps = []
    with pytest.raises(PublishError):
        threads_pub.verify_assets(["https://e/x.png"], session=S(), sleep=naps.append)
    assert naps == [15] * 5                                                 # six tries, 15 seconds apart


def test_x_posts_image_and_text_without_links(tmp_path):
    from social_engine.publishers import PublishError, x_pub
    img = tmp_path / "w.png"
    img.write_bytes(b"png")
    calls = []

    class S:
        def post(self, url, json=None, files=None, data=None, timeout=None):
            calls.append((url, json))
            if url.endswith("/media/upload"):
                return FakeResponse({"data": {"id": "777"}})
            return FakeResponse({"data": {"id": str(100 + len(calls))}}, 201)
    got = x_pub.post_thread(["first", "second"], str(img), session=S())
    assert calls[1] == ("https://api.x.com/2/tweets", {"text": "first", "media": {"media_ids": ["777"]}})
    assert calls[2][1] == {"text": "second", "reply": {"in_reply_to_tweet_id": got["ids"][0]}}
    with pytest.raises(PublishError):
        x_pub.post_thread(["see https://example.com"], None, session=S())


def test_threads_token_refresh_stores_the_new_secret(state, monkeypatch):
    from social_engine import refresh_threads_token as rt
    monkeypatch.setenv("THREADS_ACCESS_TOKEN", "old")
    monkeypatch.setenv("GH_SECRETS_PAT", "pat")
    monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")
    from nacl import encoding, public
    key = public.PrivateKey.generate()
    puts = []

    class S:
        def get(self, url, params=None, headers=None, timeout=None):
            if "refresh_access_token" in url:
                assert params == {"grant_type": "th_refresh_token", "access_token": "old"}
                return FakeResponse({"access_token": "new", "expires_in": 5184000})
            return FakeResponse({"key": key.public_key.encode(encoding.Base64Encoder()).decode(), "key_id": "k1"})

        def put(self, url, headers=None, json=None, timeout=None):
            puts.append((url, json))
            return FakeResponse({}, 204)
    assert rt.main(session=S(), today=dt.date(2026, 11, 1)) == 0
    import base64
    assert puts[0][0].endswith("/repos/o/r/actions/secrets/THREADS_ACCESS_TOKEN")
    assert public.SealedBox(key).decrypt(base64.b64decode(puts[0][1]["encrypted_value"])) == b"new"
    assert rt.load_meta()["expires_on"] == "2026-12-31"


def test_threads_token_warns_ten_days_before_expiry(state, monkeypatch):
    from social_engine import refresh_threads_token as rt
    from social_engine.publishers import telegram_pub
    monkeypatch.setenv("THREADS_ACCESS_TOKEN", "old")
    alerts = []
    monkeypatch.setattr(telegram_pub, "alert", lambda text, **k: alerts.append(text) or True)
    rt.save_meta({"expires_on": "2026-12-31"})
    rt.main(today=dt.date(2026, 12, 20))
    assert alerts == []
    rt.main(today=dt.date(2026, 12, 21))
    assert len(alerts) == 1 and "10 day" in alerts[0]


# ---------------- cards ----------------
def test_old_card_folders_are_pruned(state):
    from social_engine import render_cards
    for d in ("2026-10-01", "2026-11-20", "notes"):
        os.makedirs(os.path.join(state, "site", "social", d))
    gone = render_cards.prune(state, today=dt.date(2026, 11, 27))
    assert gone == ["site/social/2026-10-01"]
    assert sorted(os.listdir(os.path.join(state, "site", "social"))) == ["2026-11-20", "notes"]


def test_card_plan_and_numbers(ctx):
    from social_engine import render_cards
    items = render_cards.plan(ctx, "daily")
    names = [i[0] for i in items]
    assert names == ([f"carousel_{lg}_{n}.png" for lg in ("tc", "sc") for n in ("01_regime", "02_breadth", "03_sectors", "04_calendar")]
                     + ["wide_en_summary.png", "wide_tc_summary.png"])
    hero = render_cards.page_html(ctx, items[0])
    assert ">29<" in hero and "分數 29 屬 D 區，升級需連兩日留於高區間，暫維持 E 級" in hero and "633.93" in hero and "自動市況統計・非投資建議" in hero
    assert "{{" not in hero
    wide = render_cards.page_html(ctx, items[-2])
    assert "Automated Market Telemetry · Not Investment Advice" in wide and "XLK" in wide and "−10.9%" in wide


def _chromium():
    try:
        from playwright.sync_api import sync_playwright
        from social_engine import config
        with sync_playwright() as pw:
            pw.chromium.launch(**({"executable_path": config.chromium_path()} if config.chromium_path() else {})).close()
        return True
    except Exception:                                                       # noqa: BLE001
        return False


@pytest.mark.skipif(not _chromium(), reason="Playwright Chromium is not installed")
@pytest.mark.parametrize("mode,count", [("daily", 10), ("premarket", 2), ("ledger", 4), ("weekly", 2)])
def test_cards_render_at_size_with_nothing_clipped(state, tmp_path, mode, count):
    import struct
    from social_engine import context, render_cards
    c = context.build_context(context.load_brief(state), mode)
    files, issues = render_cards.render(c, mode, str(tmp_path / "out"))
    assert len(files) == count and issues == []
    for name, path in files.items():
        head = open(path, "rb").read(24)
        assert head[:8] == b"\x89PNG\r\n\x1a\n"
        size = struct.unpack(">II", head[16:24])
        assert size == ((1080, 1350) if name.startswith(("carousel", "ledger_tc", "ledger_en")) else (1600, 900)), name
