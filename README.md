# US Pre-market Brief (v6.3) – automatic daily site

This repository runs the US pre-market brief v6.3 on GitHub Actions every US trading day and publishes rules-based market research as a website with GitHub Pages. The two scripts started as the Google Colab cells; the copies here are the web edition (impersonal research wording, position-size simulator, signal ledger), so they no longer match the Colab files line for line.

- **Daily pre-market brief** (`.github/workflows/brief.yml`): about 07:17 New York time, Monday to Friday. Runs cell 1 over the S&P 500, Nasdaq 100 and S&P 400 and rebuilds the website.
- **Automated pre-market refresh** (`.github/workflows/preopen.yml`): about 08:47 New York time. Runs cell 2 against that morning's plan and adds it to the website.
- **Test run** (`.github/workflows/test-run.yml`): runs on every push to a `feat/**` branch (or by hand). Runs both scripts with the branch's code, builds and checks the website, and keeps it as a downloadable artifact. Nothing is published and the `data` branch is not changed.
- Website: `https://<your-user-name>.github.io/<repository-name>/` in Traditional Chinese, with `zh-hans/` (Simplified Chinese) and `en/` (English); a switch at the top of every page changes language. `latest/<tc|sc|en>.html` always opens the newest full brief.
- v6.3 writes Traditional Chinese. `runner/i18n.py` makes the Simplified Chinese copy by character conversion and the English copy from a phrase table (`runner/i18n_table.json`, `runner/i18n_v63.json`). If an English page shows a Chinese phrase, add it to `i18n_v63.json`.

## Setup in short

1. Upload everything in this folder to a new **public** repository (GitHub Pages is free for public repositories).
2. Optional. Change settings in `settings.txt` (edit it on GitHub and commit); every line has a default, so you can skip this.
   API keys never go in that file: add `ANTHROPIC_API_KEY` (paid, for AI news) or `FRED_API_KEY` (free) under Settings → Secrets and variables → Actions → Secrets, only if you use them.
   A repository variable with the same name as a `settings.txt` line overrides the file.
3. Settings → Pages → Build and deployment → Source: **GitHub Actions**.
4. Actions → Daily pre-market brief → Run workflow. When it finishes, open the site address shown on the run page.

The website and `settings.txt` are public. Do not put your real account size or positions in `DEMO_ACCOUNT` or `DEMO_POSITIONS`.

## Files

| Path | What it is |
| --- | --- |
| `scripts/premarket_brief_v6_3.py` | Cell 1, web edition |
| `scripts/preopen_update_v6_3.py` | Cell 2, web edition (automated pre-market refresh) |
| `settings.txt` | The Colab form values, one per line (account, risk, universe, AI news, ...) |
| `runner/common.py` | Runs a Colab script on Actions: Colab stand-ins and form values from `settings.txt` |
| `runner/run_brief.py`, `runner/run_preopen.py` | Run cell 1 / cell 2 and save the website copies |
| `runner/build_site.py` | Builds the home pages, adds missing translations, the top bar and the position-size simulator to each brief page, copies the ledger files to `site/data/`; `BUILD_MODE=freemium_split` also writes a public teaser to `state/site_free` |
| `runner/sizer.js` | The position-size simulator (plain JavaScript): recalculates shares, amounts and maximum loss from the reader's account and risk %, and writes the order parameters in Generic, Futu or IBKR format; settings stay in the browser |
| `runner/ledger.py` | Signal ledger (`signal_ledger.json`) and regime history (`regime_history.json`): grades every top setup and, as a control group, the other candidates by fixed rules (see the file's header) |
| `runner/check_site.py` | Checks the built website: local links, leftover notebook wording, sizer data, JSON, script syntax, page sizes |
| `runner/i18n.py` | Traditional Chinese to Simplified Chinese and English |
| `runner/time_window.py` | Lets one of the two daily schedules through (US daylight saving) |
| `runner/state.sh` | Saves and restores history on the `data` branch (one commit, replaced each run) |

History (daily log, tier history, plan file, score history, signal ledger, regime history, website archive) lives on the `data` branch. Each brief run also writes `briefs/<run id>/data.json` with the numbers, tables and chart series of that run, for other front ends. The website keeps the newest run of each brief date for `ARCHIVE_DAYS` (365 by default); archived pages made with the old template (data-vendor links or notebook wording) are removed, with the redirects that pointed to them. Delete that branch to start fresh.

`BUILD_MODE` in `settings.txt`: `full` (default) publishes everything; `freemium_split` publishes only the teaser (score, grade, score chart, sectors, calendar and a box describing the full report) and keeps the full site in `state/site` for a paid host.

To update the scripts later, replace the two files in `scripts/` and carry over the web-edition changes. If the new file names differ (for example v6.4), change `SCRIPT` near the top of `runner/run_brief.py` and the file name in `runner/run_preopen.py`.

Research disclosure: the output is calculated automatically by fixed rules and is the same for every reader. It is for research and education only, not investment advice, an offer or a solicitation. Past results, including backtests and the follow-up record, do not indicate future results. Whether a paid service built on this needs a licence depends on how it is run; get legal advice before charging for it.
