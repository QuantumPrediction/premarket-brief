"""Settings of the social engine: brand, platform switches, models, limits, word lists and paths.

Everything is read from environment variables (GitHub repository variables and secrets) with safe defaults,
so a white-label copy needs no code change. `settings.txt` lines are used when the variable is not set,
exactly like the brief itself. Values are read when asked for, so tests can change the environment.
"""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LANGS = ("tc", "sc", "en")
MODES = ("daily", "premarket", "ledger", "weekly")


def _settings_file():
    got = {}
    path = os.path.join(ROOT, "settings.txt")
    if os.path.exists(path):
        for line in open(path, encoding="utf-8-sig"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                got[k.strip().upper()] = v.strip().strip('"').strip("'")
    return got


_FILE = _settings_file()


def env(name, default=""):
    v = os.environ.get(name, "").strip() or _FILE.get(name, "").strip()
    return v or default


def env_bool(name, default=False):
    v = env(name, "")
    return default if v == "" else v.lower() in ("1", "true", "yes", "on")


def env_int(name, default):
    try:
        return int(float(env(name, str(default))))
    except ValueError:
        return default


# ---------- brand ----------
def brand(lang):
    return {"tc": env("BRAND_NAME_TC", "美股盤前簡報"), "sc": env("BRAND_NAME_SC", "美股盘前简报"),
            "en": env("BRAND_NAME_EN", "Premarket Brief")}[lang]


def site_base_url():
    return env("SITE_BASE_URL", "https://quantumprediction.github.io/premarket-brief").rstrip("/")


def site_url(lang="tc"):
    return site_base_url() + {"tc": "/", "sc": "/zh-hans/", "en": "/en/"}[lang]


def telegram_public_url():
    """The invite link of the free channel; empty until the repository variable is set."""
    v = env("TELEGRAM_PUBLIC_URL", "")
    return v if re.fullmatch(r"https://(t\.me|telegram\.me)/[A-Za-z0-9_+/\-]+", v) else ""


def watermark():
    return env("BRAND_WATERMARK", re.sub(r"^https?://", "", site_base_url()))


def daily_hkt():
    return env("SOCIAL_DAILY_HKT", "20:15")          # the brief runs at about 07:17 New York time: 20:17 HKT in winter, 19:17 in summer


def premarket_hkt():
    return env("SOCIAL_PREMARKET_HKT", "21:47")


def premarket_et():
    return env("SOCIAL_PREMARKET_ET", "08:47")       # the same refresh in New York time, for the English X post


# ---------- platform switches (all off until the repository variable says "true") ----------
PLATFORMS = ("telegram_public", "xhs_drafts", "threads", "x")
FLAG = {"telegram_public": "ENABLE_TELEGRAM_PUBLIC", "xhs_drafts": "ENABLE_TELEGRAM_DRAFTS", "threads": "ENABLE_THREADS", "x": "ENABLE_X"}
SECRETS = {"telegram_public": ("TELEGRAM_BOT_TOKEN", "TELEGRAM_PUBLIC_CHAT_ID"),
           "xhs_drafts": ("TELEGRAM_BOT_TOKEN", "TELEGRAM_DRAFTS_CHAT_ID"),
           "threads": ("THREADS_USER_ID", "THREADS_ACCESS_TOKEN"),
           "x": ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_SECRET")}
MODE_PLATFORMS = {"daily": ("telegram_public", "xhs_drafts", "threads", "x"), "premarket": ("telegram_public", "x"),
                  "ledger": ("telegram_public", "threads", "x"), "weekly": ("telegram_public", "threads", "x")}


def enabled(platform):
    return env_bool(FLAG[platform], False)


def any_enabled():
    return any(enabled(p) for p in PLATFORMS)


def missing_secrets(platform):
    return [k for k in SECRETS[platform] if not os.environ.get(k, "").strip()]


def alerts_ready():
    """Alerts go to the private drafts chat whenever the bot token and that chat id exist (no switch needed)."""
    return not missing_secrets("xhs_drafts")


# ---------- Claude ----------
def model_writer():
    return env("ANTHROPIC_MODEL_WRITER", "claude-sonnet-5-5")


def model_qa():
    return env("ANTHROPIC_MODEL_QA", "claude-haiku-5-5")


MAX_TOKENS_WRITER = 8000        # caps for one request (the reply itself is a few hundred tokens; the rest is thinking room)
MAX_TOKENS_QA = 2000
CLAUDE_TIMEOUT_S = 90.0
CLAUDE_MAX_RETRIES = 2


def llm_qa_on():
    return env_bool("SOCIAL_LLM_QA", True)


# ---------- limits ----------
X_TARGET, X_MAX = 260, 280
THREADS_TARGET, THREADS_MAX = 450, 500
TELEGRAM_CAPTION_MAX, TELEGRAM_TEXT_MAX = 1024, 4096
XHS_TITLE_MAX = 20
PRUNE_TRADING_DAYS = 7          # card folders older than this many weekdays are deleted (the post log is kept for good)

# ---------- compliance word lists (regular expressions, case-insensitive) ----------
BANNED_LEAKS = [r"yahoo", r"yhoo", r"yhoof2", r"\^gspc", r"\^ixic", r"\^[A-Z]{2,6}\b", r"openbb", r"fred_api", r"colab", r"跑格子", r"sharpe",
                r"四關", r"四关", r"\bcsv\b"]
BANNED_ADVICE = [r"落單", r"落单", r"照抄", r"買入訊號", r"买入信号", r"賣出訊號", r"卖出信号", r"必升", r"必跌", r"必漲", r"必涨", r"必賺", r"必赚",
                 r"穩賺", r"稳赚", r"穩贏", r"稳赢", r"保證獲利", r"保证获利", r"buy now", r"sell now", r"short now", r"guaranteed", r"financial advice",
                 r"investment advice", r"投資建議", r"投资建议"]
# Disclaimers are allowed to name what the post is not; they are taken out before the advice words are searched.
ALLOWED_DISCLAIMERS = [r"not (?:financial|investment) advice", r"非投資建議", r"非投资建议", r"不構成(?:任何)?投資建議", r"不构成(?:任何)?投资建议"]
# Upper-case words that are not tickers.
NOT_TICKERS = set("""USD HKD HKT ET EST EDT UTC GMT EMA DMA SMA MA VIX VXN PCE GDP CPI PPI FOMC FTD RS ATR ETF VCP HTF AI US HK TW UK EU
NQ ES RTY SPX NDX DJI NYSE SEC FED ISM PMI NFP JOLTS ADP EPS IPO YTD QOQ YOY MOM AM PM CTA API XHS II III IV OK USA CEO CFO PR TC SC EN
NASDAQ RSI MACD ATH PT EOD BTC OPEX PCR DXY""".split())
ALLOWED_TAGS = {"b", "strong", "i", "em", "u", "s", "code", "pre", "a", "blockquote", "tg-spoiler"}

# ---------- paths ----------
def state_dir():
    return os.path.abspath(env("STATE_DIR", os.path.join(ROOT, "state")))


def build_mode():
    return env("BUILD_MODE", "full").lower()


def post_log_path(state=None):
    return os.path.join(state or state_dir(), "social", "social_post_log.json")


def drafts_dir(state=None):
    return os.path.join(state or state_dir(), "social", "drafts")


def site_dirs(state=None):
    """The website folders that get the PNG cards: the full site, and the public teaser when it exists."""
    state = state or state_dir()
    out = [os.path.join(state, "site")]
    if build_mode() == "freemium_split" and os.path.isdir(os.path.join(state, "site_free")):
        out.append(os.path.join(state, "site_free"))
    return out


def preview_dir():
    return os.path.abspath(env("SOCIAL_PREVIEW_DIR", os.path.join(ROOT, "social_preview")))


def chromium_path():
    """Normally empty (Playwright's own Chromium). Set SOCIAL_CHROMIUM_PATH to use another Chrome binary."""
    return env("SOCIAL_CHROMIUM_PATH", "")
