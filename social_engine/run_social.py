"""Command line of the social engine.

    python -m social_engine.run_social --mode daily --dry-run          # cards + copy + compliance report into social_preview/
    python -m social_engine.run_social --mode daily --render-only      # PNG cards into the website folder (before Pages is deployed)
    python -m social_engine.run_social --mode daily --publish-only     # write, check and post (after Pages is deployed)
    python -m social_engine.run_social --mode daily --publish-only --platform x

Modes: daily, premarket, ledger, weekly. A platform posts only when its ENABLE_* variable is "true" and its secrets exist.
Every post is recorded in social_post_log.json under (brief date, mode, platform), so a second run never posts twice.
The command always exits 0 unless --strict is given: a social problem must never fail the brief's workflow.
"""
import argparse
import datetime as dt
import json
import os
import sys
import traceback

from . import config, context, generate_posts, render_cards
from .publishers import PublishError, telegram_pub, threads_pub, x_pub

KEY_OF = {"telegram_public": "telegram_tc", "xhs_drafts": "xhs_sc", "threads": "threads_tc", "x": "x_en"}
ALIASES = {"telegram": "telegram_public", "drafts": "xhs_drafts", "xhs": "xhs_drafts", "twitter": "x"}
CAROUSEL = ("01_regime", "02_breadth", "03_sectors", "04_calendar")
IMAGES = {   # (mode, platform) -> file names
    ("daily", "telegram_public"): ["wide_tc_summary.png"], ("daily", "x"): ["wide_en_summary.png"],
    ("daily", "threads"): [f"carousel_tc_{n}.png" for n in CAROUSEL], ("daily", "xhs_drafts"): [f"carousel_sc_{n}.png" for n in CAROUSEL],
    ("premarket", "telegram_public"): ["wide_tc_premarket.png"], ("premarket", "x"): ["wide_en_premarket.png"],
    ("ledger", "telegram_public"): ["ledger_wide_tc.png"], ("ledger", "x"): ["ledger_wide_en.png"], ("ledger", "threads"): ["ledger_tc.png"],
    ("weekly", "telegram_public"): ["wide_tc_weekly.png"], ("weekly", "x"): ["wide_en_weekly.png"], ("weekly", "threads"): [],
}


def say(msg):
    print(msg, flush=True)


# ---------- the post log (idempotency) ----------
def load_log(path):
    try:
        with open(path, encoding="utf-8") as f:
            log = json.load(f)
    except (OSError, ValueError):
        log = {}
    log.setdefault("schema", 1)
    log.setdefault("posts", {})
    return log


def save_log(path, log):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=1, sort_keys=True)
    os.replace(tmp, path)


def log_key(brief_date, mode, platform):
    return f"{brief_date}|{mode}|{platform}"


def already_posted(log, brief_date, mode, platform):
    return log["posts"].get(log_key(brief_date, mode, platform), {}).get("status") == "posted"


def record(log, path, brief_date, mode, platform, result):
    log["posts"][log_key(brief_date, mode, platform)] = {"status": "posted", "at_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), **result}
    save_log(path, log)                                   # saved after every post: a crash later cannot cause a second post


# ---------- when a mode has nothing to say ----------
def skip_reason(ctx, mode, log):
    if mode == "premarket" and not ctx.get("premarket"):
        return "no pre-open update for this brief date yet"
    if mode == "weekly" and not ctx.get("week"):
        return "no regime history yet"
    if mode == "ledger":
        L = ctx["ledger"]
        if L["focus"]["triggered"] == 0:
            return "no focus-list setup has triggered yet"
        last = log.get("ledger") or {}
        if last.get("brief_date") == ctx["brief_date"]:
            return None                                   # today's ledger run: the per-platform log decides
        new_close = sorted(L["closed_ids"]) != sorted(last.get("closed_ids", []))
        try:
            days = (dt.date.fromisoformat(ctx["brief_date"]) - dt.date.fromisoformat(last["brief_date"])).days
        except (KeyError, ValueError):
            days = 99
        if not new_close and days < 3:
            return f"no setup closed since the last ledger post ({last.get('brief_date')}) and it was {days} day(s) ago"
    return None


# ---------- drafts (written once per brief run, reused by the per-platform steps) ----------
def draft_path(state, ctx, mode):
    return os.path.join(config.drafts_dir(state), f"{ctx['brief_date']}_{mode}.json")


def load_draft(state, ctx, mode):
    try:
        with open(draft_path(state, ctx, mode), encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError):
        return None
    fresh = d.get("run_id") == ctx["_run_id"] and d.get("data_sig") == data_sig(ctx)
    return d if fresh and all(r.get("ok") for r in d.get("report", {}).values()) else None      # a blocked draft is written again on a re-run


def data_sig(ctx):
    """Changes when the numbers behind the posts change (a second pre-open update, a re-run of the brief)."""
    import hashlib
    return hashlib.sha1(json.dumps(context.public(ctx), ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:12]


def save_draft(path, ctx, result):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"run_id": ctx["_run_id"], "data_sig": data_sig(ctx), **result}, f, ensure_ascii=False, indent=1)


def prune_drafts(state, keep_days=14):
    base = config.drafts_dir(state)
    for name in os.listdir(base) if os.path.isdir(base) else []:
        try:
            if (dt.date.today() - dt.date.fromisoformat(name[:10])).days > keep_days:
                os.remove(os.path.join(base, name))
        except ValueError:
            continue


def preview_markdown(ctx, mode, result, files, issues):
    out = [f"# Social preview: {mode} · brief {ctx['brief_date']}", "", f"Copy written by: **{result['source']}**", ""]
    for key, value in result["posts"].items():
        rep = result["report"][key]
        out += [f"## {key} — {'PASS' if rep['ok'] else 'BLOCKED'}" + (" (after one repair)" if rep["repaired"] else ""), ""]
        if key == "xhs_sc":
            out += ["**Title**", "", value["title"], "", "**Body**", "", value["body"], "", "**Hashtags**", "", " ".join("#" + t for t in value["hashtags"]), ""]
        else:
            for i, part in enumerate(value if isinstance(value, list) else [value]):
                n = generate_posts.compliance_gate.x_length(part) if key == "x_en" else len(part)
                out += [f"*Part {i + 1} · {n} characters*", "", "```", part, "```", ""]
        for f in rep["first_failures"]:
            out.append(f"- first draft: {f}")
        for f in rep["failures"]:
            out.append(f"- **failure**: {f}")
        out.append("")
    out += ["## Cards", ""] + [f"- {name}" for name in sorted(files)] + [""]
    out += ["## Card fit problems", ""] + ([f"- {x}" for x in issues] or ["- none"]) + [""]
    return "\n".join(out)


# ---------- publishing ----------
def publish_one(platform, mode, ctx, posts, img_dir):
    """Returns the dict stored in the log. Raises PublishError (or anything else) on failure."""
    names = IMAGES.get((mode, platform), [])
    paths = [os.path.join(img_dir, n) for n in names if os.path.exists(os.path.join(img_dir, n))]
    date = ctx["brief_date"]
    if platform == "telegram_public":
        return telegram_pub.post_public(posts["telegram_tc"], paths[0] if paths else None, "tc")
    if platform == "xhs_drafts":
        return telegram_pub.post_xhs_pack(posts["xhs_sc"], paths, date)
    if platform == "threads":
        urls = [f"{config.site_base_url()}/social/{date}/{n}" for n in names] if len(paths) == len(names) else []
        return threads_pub.post_thread(posts["threads_tc"], urls)
    if platform == "x":
        return x_pub.post_thread(posts["x_en"], paths[0] if paths else None)
    raise PublishError(f"unknown platform {platform}")


def run(args):
    mode, dry = args.mode, args.dry_run
    state = config.state_dir()
    brief = context.load_brief(state, args.date)
    if not brief:
        say("Social engine: no brief with a data.json found; nothing to do.")
        return 0
    ctx = context.build_context(brief, mode)
    date = ctx["brief_date"]
    log_path = config.post_log_path(state)
    log = load_log(log_path)
    reason = skip_reason(ctx, mode, log)
    if not reason and mode == "daily" and not ctx["pillars"] and not dry:
        reason = "this brief's data.json has no pillar data (made before the social engine); the next brief run adds it"
    if reason and not args.force:
        say(f"Social engine ({mode}, {date}): skipped, {reason}.")
        return 0
    say(f"Social engine: mode {mode}, brief {date} ({ctx['_run_id']})" + (", dry run" if dry else ""))
    problems = 0

    # ---- cards ----
    img_dir = os.path.join(config.preview_dir(), date) if dry else render_cards.publish_dirs(state, date)[0]
    files, issues = {}, []
    wanted = {n for (m, _), names in IMAGES.items() if m == mode for n in names}
    have_all = all(os.path.exists(os.path.join(img_dir, n)) for n in wanted)
    if not args.publish_only or not have_all:
        try:
            files, issues = render_cards.render(ctx, mode, img_dir)
            if not dry:
                render_cards.mirror(files, state, date)
                gone = render_cards.prune(state)
                if gone:
                    say("Old card folders removed: " + ", ".join(gone))
            say(f"Cards: {len(files)} PNG files in {img_dir}")
            for x in issues:
                say(f"  card fit problem: {x}")
        except Exception as e:                                           # noqa: BLE001 - posts can still go out without an image
            problems += 1
            say(f"Cards not rendered: {type(e).__name__}: {e}")
            if args.render_only:
                traceback.print_exc()
    if args.render_only:
        return 1 if (args.strict and (problems or issues)) else 0

    # ---- copy + compliance ----
    result = None if (dry or args.force) else load_draft(state, ctx, mode)
    if result:
        say("Copy: reusing the checked draft of this brief run.")
    else:
        result = generate_posts.gated(ctx, mode)
        save_draft(os.path.join(img_dir, f"{mode}_posts.json") if dry else draft_path(state, ctx, mode), ctx, result)
    posts, report = result["posts"], result["report"]
    for key, rep in report.items():
        say(f"  {key}: {'pass' if rep['ok'] else 'BLOCKED'}" + (" (after one repair)" if rep["repaired"] else "") + "".join(f"\n      - {f}" for f in rep["failures"]))
    if dry:
        with open(os.path.join(img_dir, f"{mode}_compliance_report.json"), "w", encoding="utf-8") as f:
            json.dump({"mode": mode, "brief_date": date, "source": result["source"], "report": report, "card_fit_problems": issues}, f, ensure_ascii=False, indent=1)
        with open(os.path.join(img_dir, f"{mode}_posts.md"), "w", encoding="utf-8") as f:
            f.write(preview_markdown(ctx, mode, result, files, issues))
        say(f"Preview written to {img_dir} ({mode}_posts.md, {mode}_posts.json, {mode}_compliance_report.json).")

    # ---- platforms ----
    only = ALIASES.get(args.platform, args.platform)
    lines = []
    for platform in config.MODE_PLATFORMS[mode]:
        if only != "all" and platform != only:
            continue
        key = KEY_OF[platform]
        rep = report.get(key, {"ok": False, "failures": ["no text was written"]})
        if not config.enabled(platform):
            say(f"  {platform}: off ({config.FLAG[platform]} is not true)" + ("" if rep["ok"] else "; its text is blocked by the gate"))
            if not rep["ok"]:
                problems += 1
            continue
        if already_posted(log, date, mode, platform) and not args.force:
            say(f"  {platform}: already posted for {date} ({mode}); skipped.")
            continue
        if not rep["ok"]:
            problems += 1
            lines.append(f"⛔ {platform}: blocked by the compliance gate\n" + "\n".join(f"   - {f}" for f in rep["failures"][:6]))
            continue
        miss = config.missing_secrets(platform)
        if dry:
            say(f"  {platform}: would post" + (f" (missing secrets: {', '.join(miss)})" if miss else ""))
            continue
        if miss:
            problems += 1
            lines.append(f"⚠️ {platform}: not posted, missing secrets {', '.join(miss)}")
            continue
        try:
            got = publish_one(platform, mode, ctx, posts, img_dir)
            record(log, log_path, date, mode, platform, got)
            lines.append(f"✅ {platform}: posted")
        except PublishError as e:
            problems += 1
            lines.append(f"❌ {platform}: {e}")
        except Exception as e:                                           # noqa: BLE001 - one platform never stops the others
            problems += 1
            lines.append(f"❌ {platform}: {type(e).__name__}")
            traceback.print_exc()
    if mode == "ledger" and not dry and any(already_posted(log, date, mode, p) for p in config.MODE_PLATFORMS[mode]):
        log["ledger"] = {"brief_date": date, "closed_ids": ctx["ledger"]["closed_ids"]}
        save_log(log_path, log)
    for ln in lines:
        say("  " + ln)
    if lines and not dry:
        if issues:
            lines.append("🖼 card fit problems: " + "; ".join(issues[:4]))
        telegram_pub.alert(f"Social run · {mode} · brief {date} · copy by {result['source']}\n" + "\n".join(lines))
        prune_drafts(state)
    return 1 if (args.strict and (problems or issues)) else 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m social_engine.run_social", description=__doc__.split("\n\n")[0])
    ap.add_argument("--mode", choices=config.MODES, default="daily")
    ap.add_argument("--dry-run", action="store_true", help="write everything to social_preview/ and post nothing")
    ap.add_argument("--render-only", action="store_true", help="only render the PNG cards")
    ap.add_argument("--publish-only", action="store_true", help="use the cards already rendered; write, check and post")
    ap.add_argument("--platform", default="all", help="all, telegram_public, xhs_drafts, threads or x")
    ap.add_argument("--date", default=None, help="brief date YYYY-MM-DD (default: the newest brief)")
    ap.add_argument("--force", action="store_true", help="ignore the post log, the cached draft and the mode's skip rule")
    ap.add_argument("--strict", action="store_true", help="exit 1 when a text is blocked, a card does not fit or a platform fails")
    args = ap.parse_args(argv)
    try:
        return run(args)
    except Exception as e:                                               # noqa: BLE001
        traceback.print_exc()
        if not args.dry_run:
            telegram_pub.alert(f"Social run · {args.mode}: stopped by {type(e).__name__}")
        return 1 if args.strict else 0


if __name__ == "__main__":
    sys.exit(main())
