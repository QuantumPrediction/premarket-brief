"""Shared helpers: run the Colab scripts on GitHub Actions without changing them.

The two scripts in scripts/ (v6.3) are the same files you paste into Colab. This module
1. fakes the two Colab-only modules (google.colab.userdata reads GitHub secrets from
   environment variables; google.colab.drive refuses, so files stay in the state folder),
2. replaces the Colab form values (#@param lines) with values from settings.txt
   (or a GitHub repository variable of the same name, which wins when set),
3. runs the script in its own namespace and hands that namespace back, so the runner
   can reuse the script's own translation function for the other two languages.
"""
import datetime as dt
import importlib
import os
import re
import sys
import types
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ET, HK = ZoneInfo("America/New_York"), ZoneInfo("Asia/Hong_Kong")
LANGS = ("tc",)                                  # v6.3 writes Traditional Chinese only
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


def translate(G, text, lang, html=True):
    """Translate output written in Traditional Chinese with the script's own table."""
    if lang == "tc" or not text or "_tr" not in G:        # v6.3 has no translation table
        return text
    old = G["_LANG"]
    G["_LANG"] = lang
    G["_TR"].clear()
    try:
        return G["_tr"](text, html)
    finally:
        G["_LANG"] = old
        G["_TR"].clear()


def translate_doc(G, doc, lang):
    """A whole saved HTML page: text, <html lang>, and a font that suits the language."""
    if lang == "tc" or "_tr" not in G:
        return doc
    out = translate(G, doc, lang, True)
    out = out.replace('<html lang="zh-Hant">', f'<html lang="{HTML_LANG[lang]}">', 1)
    return out.replace("</body>", FONT_CSS[lang] + "</body>", 1)


def now_et():
    return dt.datetime.now(ET)


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


if __name__ == "__main__":          # python3 runner/common.py NAME [default]: print the setting in effect (used by the workflow)
    print(env(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else ""))
