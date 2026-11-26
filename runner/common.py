"""Shared helpers: run the Colab scripts on GitHub Actions without changing them.

The two scripts in scripts/ (v6.3) are the same files you paste into Colab. This module
1. fakes the two Colab-only modules (google.colab.userdata reads GitHub secrets from
   environment variables; google.colab.drive refuses, so files stay in the state folder),
2. replaces the Colab form values (#@param lines) with values from settings.txt
   (or a GitHub repository variable of the same name, which wins when set),
3. runs the script in its own namespace and hands that namespace back to the runner.
English and Simplified Chinese copies are made afterwards by i18n.py.
"""
import datetime as dt
import importlib
import os
import re
import sys
import types
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import i18n  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ET, HK = ZoneInfo("America/New_York"), ZoneInfo("Asia/Hong_Kong")
LANGS = ("tc", "sc", "en")                       # v6.3 writes Traditional Chinese; i18n.py makes the other two
HTML_LANG = {"en": "en", "tc": "zh-Hant", "sc": "zh-Hans"}
FONT_CSS = {"tc": "",
            "sc": '<style>.pmb{font-family:-apple-system,"Segoe UI","Noto Sans SC","PingFang SC","Microsoft YaHei",sans-serif}</style>',
            "en": '<style>.pmb{font-family:-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,"Liberation Sans",sans-serif}</style>'}


SETTINGS_FILE = os.path.join(ROOT, "settings.txt")


def load_settings(path=SETTINGS_FILE):
    """Read settings.txt (NAME=value lines, # comments) into the environment.

    A GitHub repository variable with the same name, when set, still wins over the file."""
    if not os.path.exists(path):
        return {}
    got = {}
    for line in open(path, encoding="utf-8-sig"):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip().upper(), v.strip().strip('"').strip("'")
        got[k] = v
        if v and not os.environ.get(k, "").strip():
            os.environ[k] = v
    return got


load_settings()


def env(name, default=""):
    """Setting from a GitHub variable or secret (empty values fall back to the default)."""
    v = os.environ.get(name, "")
    return v.strip() if v.strip() else default


def env_bool(name, default=False):
    v = env(name, "")
    return default if v == "" else v.lower() in ("1", "true", "yes", "on")


def env_num(name, default):
    try:
        return float(env(name, str(default)))
    except ValueError:
        return default


def install_colab_stubs():
    """google.colab.userdata -> environment variables; google.colab.drive -> not available."""
    try:
        sys.modules.setdefault("google", importlib.import_module("google"))   # namespace package from protobuf etc.
    except ImportError:
        sys.modules["google"] = types.ModuleType("google")
    colab = types.ModuleType("google.colab")
    userdata = types.ModuleType("google.colab.userdata")
    userdata.get = lambda key: os.environ.get(key) or None
    drive = types.ModuleType("google.colab.drive")

    def _mount(*a, **k):
        raise RuntimeError("Google Drive is not available on GitHub Actions")
    drive.mount = _mount
    colab.userdata, colab.drive = userdata, drive
    sys.modules.update({"google.colab": colab, "google.colab.userdata": userdata, "google.colab.drive": drive})
    sys.modules["google"].colab = colab


def set_form(src, values):
    """Replace each Colab form line `NAME = ...  #@param ...` with NAME = <value>."""
    for name, val in values.items():
        rx = re.compile(rf"^{name}\s*=\s*[^\n]*?(\s*#@param[^\n]*)?$", re.M)
        found = rx.findall(src)
        if len(found) != 1:
            raise RuntimeError(f"form field {name} found {len(found)} times in the script")
        src = rx.sub(lambda m: f"{name} = {val!r}" + (m.group(1) or ""), src, count=1)
    return src


def run_script(path, values, workdir):
    """Run a Colab script with the given form values inside workdir; returns its namespace."""
    install_colab_stubs()
    os.environ["PMB_SKIP_INSTALL"] = "1"          # packages come from requirements.txt
    src = set_form(open(path, encoding="utf-8").read(), values)
    os.makedirs(workdir, exist_ok=True)
    here = os.getcwd()
    os.chdir(workdir)
    G = {"__name__": "__main__", "__file__": path}
    try:
        exec(compile(src, os.path.basename(path), "exec"), G)
    finally:
        os.chdir(here)
    return G


def translate(text, lang, html=False):
    """Text written by v6.3 in Traditional Chinese -> lang (see i18n.py)."""
    return i18n.translate(text, lang, html)


def translate_doc(doc, lang):
    """A whole saved HTML page: text, <html lang>, and a font that suits the language."""
    out = doc if lang == "tc" else i18n.translate(doc, lang, True)
    out = re.sub(r"<html(?: lang=\"[^\"]*\")?>", f'<html lang="{HTML_LANG[lang]}">', out, count=1)
    out = out.replace('href="brief_tc.txt"', f'href="brief_{lang}.txt"')                # the text summary in the same language
    return out if lang == "tc" else out.replace("</body>", FONT_CSS[lang] + "</body>", 1)


def redirect_page(target):
    """A tiny page that sends the visitor on to target (kept where an older link pointed)."""
    return (f'<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="refresh" content="0; url={target}">'
            f'<link rel="canonical" href="{target}"><title>Pre-market brief</title></head><body><a href="{target}">{target}</a></body></html>')


BAR_RX = re.compile(r"<!--sitebar[^>]*-->.*?<!--/sitebar-->", re.S)


def strip_bar(doc):
    """Remove what build_site.py added to a saved page (the language bar and its style)."""
    return BAR_RX.sub("", doc)


def ensure_languages(folder):
    """A brief or pre-open folder holds the Traditional Chinese files; add the other languages if missing."""
    import json
    made = 0
    tc_html = os.path.join(folder, "tc.html")
    for lang in LANGS:
        if lang == "tc":
            continue
        path = os.path.join(folder, f"{lang}.html")
        if os.path.exists(tc_html) and not os.path.exists(path):
            write(path, translate_doc(strip_bar(open(tc_html, encoding="utf-8").read()), lang))
            made += 1
        for stem in ("brief", "preopen"):
            src, dst = os.path.join(folder, f"{stem}_tc.txt"), os.path.join(folder, f"{stem}_{lang}.txt")
            if os.path.exists(src) and not os.path.exists(dst):
                write(dst, translate(open(src, encoding="utf-8").read(), lang))
        src, dst = os.path.join(folder, "summary_tc.json"), os.path.join(folder, f"summary_{lang}.json")
        if os.path.exists(src) and not os.path.exists(dst):
            write(dst, json.dumps(i18n.translate_obj(json.load(open(src, encoding="utf-8")), lang), ensure_ascii=False, indent=1))
    return made


def now_et():
    return dt.datetime.now(ET)


# Lines the Colab script writes about Google Drive. On GitHub the history is kept on the data branch
# and every brief stays on the website, so these are replaced before the pages are published.
GITHUB_WORDING = [
    ("要在表單勾選 SAVE_TO_DRIVE，名單才會存到 Google Drive，下次執行才可以跟進。", "今日的名單已存起來，下次執行就會有跟進。"),
    ("；這次沒有存到 Google Drive，紀錄只存在這次的 Colab 工作階段", ""),
    ("這次沒有存到 Google Drive，紀錄只存在 Colab 的臨時資料夾，工作階段結束就會刪除。要回看之前的簡報，請勾選 SAVE_TO_DRIVE，並在彈出的視窗允許 Colab 連接 Google Drive。",
     "每日的完整簡報都保留在網站首頁的「之前的簡報」。"),
]


def github_wording(text):
    for old, new in GITHUB_WORDING:
        text = text.replace(old, new)
    return text


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


if __name__ == "__main__":          # python3 runner/common.py NAME [default]: print the setting in effect (used by the workflow)
    print(env(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else ""))
