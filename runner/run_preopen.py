"""Cell 2 (v6.3) on GitHub Actions: the pre-open update, saved for the website.

Reads state/premarket_out/latest_plan.json written by the last cell 1 run, and saves
  state/site/preopen/<stem>/tc.html, preopen_tc.txt, summary_tc.json
"""
import glob
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import LANGS, ROOT, env, now_et, run_script, translate, translate_doc, write  # noqa: E402


def main():
    state = os.path.abspath(env("STATE_DIR", os.path.join(ROOT, "state")))
    t0 = time.time()
    G = run_script(os.path.join(ROOT, "scripts", "preopen_update_v6_3.py"),
                   dict(SAVE_TO_DRIVE=False, POSITIONS_OVERRIDE=env("DEMO_POSITIONS", "")), state)
    new = [p for p in glob.glob(os.path.join(state, "premarket_out", "*", "*_preopen.html")) if os.path.getmtime(p) >= t0 - 1]
    if not new:
        print("Cell 2 saved no page (no plan file yet?): run the daily brief first. The website is left as it is.")
        return
    html_path = max(new, key=os.path.getmtime)
    stem = os.path.basename(html_path)[: -len("_preopen.html")]
    doc = open(html_path, encoding="utf-8").read()
    txt_path = html_path[: -len(".html")] + ".txt"
    txt = open(txt_path, encoding="utf-8").read() if os.path.exists(txt_path) else ""
    out = os.path.join(state, "site", "preopen", stem)
    now = now_et()
    for lang in LANGS:
        t = translate(G, txt, lang, False)
        write(os.path.join(out, f"{lang}.html"), translate_doc(G, doc, lang))
        write(os.path.join(out, f"preopen_{lang}.txt"), t)
        lines = [ln.rstrip() for ln in t.splitlines() if ln.strip()]
        write(os.path.join(out, f"summary_{lang}.json"),
              json.dumps({"stem": stem, "brief_date": stem[:10], "run_et": f"{now:%Y-%m-%d %H:%M}", "head": lines[:14]}, ensure_ascii=False, indent=1))
    write(os.path.join(state, "marks", "preopen.txt"), f"{now:%Y-%m-%d} {stem}\n")
    print(f"Saved site files for {stem} in {out}")


if __name__ == "__main__":
    main()
