"""Decide whether a scheduled run should go ahead (prints go=true/false for GitHub Actions).

GitHub cron runs in UTC and knows nothing about US daylight saving, so each workflow has two
schedules one hour apart. This check lets exactly one of them through, by New York time:
  brief    06:50–09:20 ET (cell 1, before the open, while pre-market data is fresh)
  preopen  08:30–09:29 ET (cell 2, 30–60 minutes before the 09:30 open)
and only if that job has not already run today. Manual runs ("Run workflow") always go.
Usage: python runner/time_window.py brief|preopen <event name> [state dir]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import now_et  # noqa: E402

WINDOWS = {"brief": ((6, 50), (9, 20)), "preopen": ((8, 30), (9, 29))}


def main():
    kind, event = sys.argv[1], sys.argv[2]
    state = sys.argv[3] if len(sys.argv) > 3 else "state"
    now = now_et()
    if event != "schedule":
        go, why = True, "manual run"
    elif now.weekday() >= 5:
        go, why = False, "weekend"
    else:
        (h0, m0), (h1, m1) = WINDOWS[kind]
        inside = (h0, m0) <= (now.hour, now.minute) < (h1, m1)
        mark = os.path.join(state, "marks", f"{kind}.txt")
        done = os.path.exists(mark) and open(mark).read().split(" ")[0] == f"{now:%Y-%m-%d}"
        go = inside and not done
        why = "already ran today" if done else ("inside the window" if inside else "outside the window (the other schedule covers it)")
    print(f"{kind}: {now:%Y-%m-%d %H:%M} ET, {why} -> {'run' if go else 'skip'}", file=sys.stderr)
    print(f"go={'true' if go else 'false'}")


if __name__ == "__main__":
    main()
