# US Pre-market Brief (v6.3) – automatic daily site

This repository runs the US pre-market brief v6.3 (the same two scripts used in Google Colab) on GitHub Actions every US trading day and publishes a dashboard website with GitHub Pages.

- **Daily pre-market brief** (`.github/workflows/brief.yml`): about 07:17 New York time, Monday to Friday. Runs cell 1 over the S&P 500, Nasdaq 100 and S&P 400 and rebuilds the website.
- **Pre-open update** (`.github/workflows/preopen.yml`): about 08:47 New York time. Runs cell 2 against that morning's plan and adds it to the website.
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
| `scripts/premarket_brief_v6_3.py` | Cell 1, unchanged from the Colab version |
| `scripts/preopen_update_v6_3.py` | Cell 2, unchanged from the Colab version |
| `settings.txt` | The Colab form values, one per line (account, risk, universe, AI news, ...) |
| `runner/common.py` | Runs a Colab script on Actions: Colab stand-ins and form values from `settings.txt` |
| `runner/run_brief.py`, `runner/run_preopen.py` | Run cell 1 / cell 2 and save the website copies |
| `runner/build_site.py` | Builds the dashboard pages from the saved summaries, adds missing translations and the top bar of each full brief |
| `runner/i18n.py` | Traditional Chinese to Simplified Chinese and English |
| `runner/time_window.py` | Lets one of the two daily schedules through (US daylight saving) |
| `runner/state.sh` | Saves and restores history on the `data` branch (one commit, replaced each run) |

History (daily log, tier history, plan file, score history, website archive) lives on the `data` branch. The website keeps the newest run of each brief date for `ARCHIVE_DAYS` (365 by default). Delete that branch to start fresh.

To update the scripts later, replace the two files in `scripts/`. If the new file names differ (for example v6.4), change `SCRIPT` near the top of `runner/run_brief.py` and the file name in `runner/run_preopen.py`.

For research and demonstration only. Not investment advice; data can be late or wrong, and nothing here guarantees a profit.
