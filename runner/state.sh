#!/usr/bin/env bash
# History lives on a separate branch called "data": daily_log.csv, tier_history.csv, latest_plan.json,
# the company-profile cache and the website archive. Each save replaces the branch with ONE fresh commit,
# so the repository does not grow day after day.
#   bash runner/state.sh restore      # data branch -> $STATE_DIR (empty folder on the first run)
#   bash runner/state.sh save "msg"   # $STATE_DIR -> data branch
set -euo pipefail
STATE="${STATE_DIR:-state}"
URL="${STATE_REPO_URL:-https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_REPOSITORY}.git}"
case "${1:-}" in
  restore)
    rm -rf "$STATE"
    if git ls-remote --exit-code --heads "$URL" data >/dev/null 2>&1; then
      git clone --quiet --depth 1 --branch data "$URL" "$STATE"
      rm -rf "$STATE/.git"
      echo "Restored history from the data branch."
    else
      mkdir -p "$STATE"
      echo "No data branch yet: this is the first run, starting with empty history."
    fi
    ;;
  save)
    cd "$STATE"
    rm -rf .git
    git init --quiet -b data
    git config user.name "github-actions[bot]"
    git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
    git add -A
    git commit --quiet -m "${2:-update}: $(TZ=America/New_York date '+%Y-%m-%d %H:%M') ET"
    git -c push.negotiate=false push --quiet --force "$URL" data
    rm -rf .git
    echo "Saved history to the data branch."
    ;;
  *)
    echo "usage: state.sh restore|save [message]" >&2
    exit 2
    ;;
esac
