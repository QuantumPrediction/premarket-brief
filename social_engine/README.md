# Social engine

Turns each brief (`briefs/<run id>/data.json`, the three `summary_*.json` files, `signal_ledger.json`, `regime_history.json`
and the pre-open text) into PNG scorecards and checked posts for Telegram, Threads, X and a Xiaohongshu draft pack.

- **Cards** are HTML + CSS rendered by headless Chromium (Playwright). No image model is used, so every figure on a card
  is the figure in `data.json`.
- **Copy** is written by Claude from one compact context (`context.py`) and nothing else. Without an API key, or when the
  API is down, the same context is put into fixed sentences, so posts still go out.
- **Compliance gate** (`compliance_gate.py`): every text is checked before any publisher runs. A failing text gets one
  rewrite with the exact reasons; a second failure is not published and is reported to the private Telegram chat.
- **No double posting**: `social/social_post_log.json` (on the `data` branch) records every post under
  (brief date, mode, platform).
- **Isolated from the brief**: every social step has `continue-on-error`, publishing runs in its own job after the
  website is live, and the command exits 0 whatever a platform does.

Everything is off until you turn a platform on. With no variables and no secrets set, the brief workflows behave exactly
as before.

## Where things live

This repository keeps history on the `data` branch (the `state/` folder on the runner) and publishes the website as a
Pages artifact, so nothing is committed to `main` by the workflows:

| What | Where |
| --- | --- |
| PNG cards | `state/site/social/<brief date>/` → served at `<site>/social/<brief date>/<file>.png` (also copied to the teaser site with `BUILD_MODE=freemium_split`); folders older than 7 trading days are deleted |
| Post log | `state/social/social_post_log.json` |
| Checked drafts of the current run | `state/social/drafts/<brief date>_<mode>.json` (kept 14 days) |
| Threads token expiry date | `state/social/threads_token.json` (the date only, never the token) |
| Dry-run output | `social_preview/<brief date>/` (not committed) |

## Modes

| Mode | When | Posts to | Cards |
| --- | --- | --- | --- |
| `daily` | after the daily brief is published | Telegram channel, Threads (4-slide carousel), X, Xiaohongshu pack (private chat) | `carousel_<tc\|sc>_01_regime` … `04_calendar` (1080×1350), `wide_<en\|tc>_summary` (1600×900) |
| `premarket` | after the pre-open update is published | Telegram channel, X | `wide_<en\|tc>_premarket` |
| `ledger` | with the daily run, when a focus-list setup has closed since the last ledger post, or 3 days have passed; never while nothing has triggered | Telegram channel, Threads, X | `ledger_<tc\|en>` (1080×1350), `ledger_wide_<tc\|en>` (1600×900) |
| `weekly` | Saturday 11:00 Hong Kong time | Telegram channel, Threads, X (two- or three-part threads) | `wide_<en\|tc>_weekly` |

The signal ledger is graded when the brief runs, so the ledger post follows the daily brief instead of a separate
after-close schedule.

## Try it locally (posts nothing)

```bash
pip install -r requirements.txt -r social_engine/requirements.txt pytest
```

```bash
python -m playwright install --with-deps chromium
```

```bash
sudo apt-get install -y fonts-noto-cjk fonts-inter
```

```bash
pytest tests/test_social_engine.py
```

Put a copy of the `data` branch in `state/` (or point `STATE_DIR` at one), then:

```bash
python -m social_engine.run_social --mode daily --dry-run
```

Open `social_preview/<brief date>/daily_posts.md` (all copy with character counts and the gate's verdict),
`daily_compliance_report.json`, and the PNG files. The run also reports any text that does not fit its box on a card.
Add `--strict` to get exit code 1 when a text is blocked or a card does not fit. Without `ANTHROPIC_API_KEY` the dry run
uses the fixed-sentence copy.

On GitHub: Actions → **Social weekly recap** → Run workflow with *dry run* ticked (choose any mode) → download the
`social-preview` artifact. Every push to a `feat/**` branch also runs the tests and a strict dry run in **Test run**.

## Setup on GitHub

Settings → Secrets and variables → Actions. Add only what the platforms you want need.

### Secrets

| Name | Purpose |
| --- | --- |
| `ANTHROPIC_API_KEY` | Claude API key for the copy and the short review (optional: without it the fixed-sentence copy is used) |
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather |
| `TELEGRAM_PUBLIC_CHAT_ID` | Public channel, `@yourchannel` or `-100…` |
| `TELEGRAM_DRAFTS_CHAT_ID` | Private channel or chat for the Xiaohongshu pack, run summaries and alerts |
| `THREADS_USER_ID` | Threads numeric user id |
| `THREADS_ACCESS_TOKEN` | Threads long-lived token (60 days) |
| `X_API_KEY`, `X_API_SECRET`, `X_ACCESS_TOKEN`, `X_ACCESS_SECRET` | X app keys and the account's access token (OAuth 1.0a, Read and Write) |
| `GH_SECRETS_PAT` | Optional. Fine-grained token with *Secrets: read and write* on this repository, so the Threads token is renewed automatically |

### Variables

| Name | Purpose | Default |
| --- | --- | --- |
| `ENABLE_TELEGRAM_PUBLIC`, `ENABLE_TELEGRAM_DRAFTS`, `ENABLE_THREADS`, `ENABLE_X` | `true` turns the platform on | off |
| `TELEGRAM_PUBLIC_URL` | Invite link (`https://t.me/…`) shown in the banner on the home pages; no banner while empty | empty |
| `CF_ANALYTICS_TOKEN` | Cloudflare Web Analytics token; no script while empty | empty |
| `SITE_BASE_URL` | Public address of the website (Threads fetches the images from it) | `https://quantumprediction.github.io/premarket-brief` |
| `BRAND_NAME_TC`, `BRAND_NAME_SC`, `BRAND_NAME_EN`, `BRAND_WATERMARK` | White-label names and the card footer | 美股盤前簡報, 美股盘前简报, Premarket Brief, the site address |
| `ANTHROPIC_MODEL_WRITER`, `ANTHROPIC_MODEL_QA` | Claude model ids | `claude-sonnet-5-5`, `claude-haiku-5-5` |
| `SOCIAL_LLM_QA` | `false` turns the short model review off (the deterministic checks always run) | `true` |
| `SOCIAL_DAILY_HKT`, `SOCIAL_PREMARKET_HKT` | The two Hong Kong times quoted on cards, in Chinese posts and in the banner. The brief runs at about 07:17 New York time, which is 20:17 HKT in winter and 19:17 in summer; set `19:15` / `20:47` for the summer months if you want them exact | `20:15`, `21:47` |
| `SOCIAL_PREMARKET_ET` | The pre-open refresh in New York time, quoted in the English X post | `08:47` |

### Steps

1. **Dry run first.** Run *Social weekly recap* with *dry run* ticked and mode `daily`; look at the artifact.
2. **Telegram.** Create a bot with @BotFather, add it as an admin of the public channel and of a private channel (or
   group) for drafts. Add `TELEGRAM_BOT_TOKEN`, `TELEGRAM_PUBLIC_CHAT_ID`, `TELEGRAM_DRAFTS_CHAT_ID`. To find a private
   chat id, post in the chat and open `https://api.telegram.org/bot<TOKEN>/getUpdates`. Set
   `ENABLE_TELEGRAM_DRAFTS=true` first: the Xiaohongshu pack and all alerts arrive privately, nothing is public yet.
   Then `ENABLE_TELEGRAM_PUBLIC=true` and `TELEGRAM_PUBLIC_URL`.
3. **Threads.** In a Meta developer app with the Threads API (`threads_basic`, `threads_content_publish`), create a
   long-lived token for the account. Add `THREADS_USER_ID` and `THREADS_ACCESS_TOKEN`, then `ENABLE_THREADS=true`.
   Either add `GH_SECRETS_PAT` (renewed on the 1st of each month), or renew by hand when the private chat warns you
   10 days before expiry, then run *Threads token refresh* with *token renewed* ticked.
4. **X.** In the X developer portal set the app to Read and Write, then create the access token and secret. Add the
   four `X_*` secrets, then `ENABLE_X=true`. Posts never contain a link (the gate and the publisher both refuse one).
5. **Xiaohongshu.** Nothing to set up: the four Simplified Chinese slides and a copy-ready title, body and hashtags
   arrive in the private chat every day. Save the images, paste the text, publish.

Turning a platform off again is one variable: set its `ENABLE_*` to `false`.

## What the gate checks

- **Leaks**: data-vendor names, index symbols with a caret, notebook and tool names, `csv`, and the like.
- **Advice wording**: imperative or promissory phrases in English and both Chinese scripts. "Not investment advice" style
  disclaimers are allowed.
- **Tickers**: every upper-case symbol must be in `data.json` or the ledger (common acronyms such as VIX, FOMC, ETF excepted).
- **Figures**: every number, clock time and date must be in the context, rounded no further than the text shows. Counts
  up to 10 and indicator names (21EMA, 50DMA, S&P 500) pass.
- **Score and grade**: must match the data; daily and pre-market posts must state both. When the grade is held by
  hysteresis, the band's letter is also accepted.
- **Links**: none on X, Threads or Xiaohongshu; on Telegram only the brief's own addresses.
- **Limits**: X 280 (counted the way X counts, CJK and emoji double), Threads 500, Xiaohongshu title 20, Telegram 4,096.
- **Telegram HTML**: allowed tags only, balanced, `<a>` with an `href`, no bare `<`, `>` or `&`.
- **Model review** (optional, Claude Haiku): flags claims the data does not support. If the reviewer is unreachable the
  deterministic result stands.

The word lists and limits are at the bottom of `config.py`.

## Files

| Path | What it is |
| --- | --- |
| `config.py` | Brand, switches, models, limits, word lists, paths |
| `context.py` | Reads the brief and builds the one context that cards, writer and gate share |
| `render_cards.py`, `templates/` | Cards: HTML templates → PNG, fit check, 7-trading-day clean-up |
| `generate_posts.py` | Claude writer, one repair pass, fixed-sentence fallback |
| `compliance_gate.py` | The checks above |
| `publishers/` | `telegram_pub.py`, `threads_pub.py`, `x_pub.py` |
| `refresh_threads_token.py` | Threads token renewal and expiry warning |
| `run_social.py` | Command line: `--mode`, `--dry-run`, `--render-only`, `--publish-only`, `--platform`, `--date`, `--force`, `--strict` |
