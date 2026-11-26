"""Check the built website before it is published (used by the test-run workflow; safe to run any time).

    python3 runner/check_site.py STATE_DIR

Errors (exit code 1): a local link or image that points to a missing file or to the account root, leftover
notebook wording, a JSON file that does not parse, a sizer row without its numbers, a script with a syntax error.
Notes only: English pages with Chinese left in them, page sizes.
"""
import glob
import json
import os
import re
import shutil
import subprocess
import sys
from html.parser import HTMLParser

FORBIDDEN = [r"跑格子", r"格子 ?2", r"（當日 \d+ 次）", r"（当日 \d+ 次）", r"Run Cell", r"\(\d+ runs that day\)"]
PUBLIC = [r"(?i)yahoo", r"(?i)yhoo", r"\^(GSPC|IXIC|DJI|RUT|VIX)\b", r"Sharpe", r"四關", r"四关", r"\bCSV\b", r"v6\.1",
          r"照抄用的文字", r"今日可落單", r"今日可落单", r"止蝕", r"止蚀", r"OpenBB", r"FRED", r"Colab", r"Wikipedia", r"AI_NEWS", r"HTF_WIDE_SCAN", r"ANTHROPIC_API_KEY", r"表單", r"Cboe 取不到",
          r"utm_source", r"yptr", r"數據源狀態", r"数据源状态", r"財報與經濟日曆的來源", r"Google Drive"]   # never on a public page
CJK = re.compile(r"[㐀-鿿]")


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.refs, self.sizer, self.text = [], [], []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        for k in ("href", "src"):
            if a.get(k):
                self.refs.append(a[k])
        if "data-entry" in a:
            self.sizer.append(a)
        if tag in ("script", "style"):
            self._skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip:
            self.text.append(data)


def local_target(page, ref):
    ref = ref.split("#")[0].split("?")[0]
    if not ref or re.match(r"^(https?:|mailto:|tel:|data:|javascript:)", ref):
        return None
    if ref.startswith("/"):
        return ref
    return os.path.normpath(os.path.join(os.path.abspath(os.path.dirname(page)), ref))


def newest_runs(site):
    """The newest brief and pre-open folders: notebook wording and sizer data are checked there (older pages are archives)."""
    out = set()
    for kind in ("briefs", "preopen"):
        base = os.path.join(site, kind)
        runs = sorted(r for r in os.listdir(base) if os.path.isdir(os.path.join(base, r))) if os.path.isdir(base) else []
        if runs:
            out.add(os.path.join(base, runs[-1]))
    return out


def check_site(site, errors, notes):
    pages = sorted(glob.glob(os.path.join(site, "**", "*.html"), recursive=True))
    newest = newest_runs(site)
    sizes = []
    for page in pages:
        html = open(page, encoding="utf-8").read()
        rel = os.path.relpath(page, site)
        p = Links()
        p.feed(html)
        for ref in p.refs:
            tgt = local_target(page, ref)
            if tgt is None:
                continue
            if not os.path.isabs(tgt) or tgt == ref.split("#")[0].split("?")[0]:
                errors.append(f"{rel}: link to the account root ({ref}); use a relative link")
            elif not os.path.abspath(tgt).startswith(os.path.abspath(site)):
                errors.append(f"{rel}: link leaves the site folder ({ref})")
            elif not os.path.exists(tgt) and not os.path.exists(os.path.join(tgt, "index.html")):
                errors.append(f"{rel}: link to a missing file ({ref})")
        if os.path.dirname(page) in newest or os.path.basename(page) == "index.html":
            for pat in PUBLIC:
                for m in re.finditer(pat, re.sub(r"<script.*?</script>", "", html, flags=re.S)):
                    errors.append(f"{rel}: public page shows «{m.group(0)}»")
        if os.path.dirname(page) in newest:
            for pat in FORBIDDEN:
                for m in re.finditer(pat, html):
                    errors.append(f"{rel}: leftover notebook wording «{m.group(0)}»")
            sizes.append((len(html.encode("utf-8")), rel))
            for a in p.sizer:
                miss = [k for k in ("data-stop", "data-direction", "data-risk-mult") if k not in a]
                if miss:
                    errors.append(f"{rel}: sizer row {a.get('data-ticker', '?')} lacks {', '.join(miss)}")
                    continue
                try:
                    entry, stop = float(a["data-entry"]), float(a["data-stop"])
                except ValueError:
                    errors.append(f"{rel}: sizer row {a.get('data-ticker', '?')} has a non-numeric price")
                    continue
                if entry <= 0 or stop <= 0 or entry == stop:
                    errors.append(f"{rel}: sizer row {a.get('data-ticker', '?')} has entry {entry} and stop {stop}")
        if os.path.basename(page) == "en.html" or "/en/" in page:
            text = "".join(p.text).replace("繁體", "").replace("简体", "")   # the language switch names itself in each language
            left = CJK.findall(text)
            if left:
                sample = sorted(set(m.group(0) for m in re.finditer(r"[㐀-鿿][㐀-鿿，、：；（）「」]*", text)), key=len)[-8:]
                notes.append(f"{rel}: {len(left)} Chinese characters left, e.g. {' | '.join(sample)}")
    for folder in newest:                                          # the plain-text summaries of the newest runs
        for txt in glob.glob(os.path.join(folder, "*.txt")):
            body = open(txt, encoding="utf-8").read()
            for pat in PUBLIC + FORBIDDEN:
                for m in re.finditer(pat, body):
                    errors.append(f"{os.path.relpath(txt, site)}: text summary shows «{m.group(0)}»")
    for js in glob.glob(os.path.join(site, "**", "*.json"), recursive=True):
        try:
            json.load(open(js, encoding="utf-8"))
        except ValueError as e:
            errors.append(f"{os.path.relpath(js, site)}: not valid JSON ({e})")
    node = shutil.which("node")
    for js in glob.glob(os.path.join(site, "assets", "*.js")):
        if node:
            r = subprocess.run([node, "--check", js], capture_output=True, text=True)
            if r.returncode:
                errors.append(f"{os.path.relpath(js, site)}: syntax error\n{r.stderr.strip()[:400]}")
    for size, rel in sorted(sizes, reverse=True)[:6]:
        notes.append(f"size {size / 1024:7.0f} KB  {rel}")
    return len(pages)


def main():
    state = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("STATE_DIR", "state")
    errors, notes = [], []
    n = 0
    for name in ("site", "site_free"):
        site = os.path.join(state, name)
        if os.path.isdir(site):
            n += check_site(site, errors, notes)
    for js in glob.glob(os.path.join(state, "ledger", "*.json")):
        try:
            json.load(open(js, encoding="utf-8"))
        except ValueError as e:
            errors.append(f"ledger/{os.path.basename(js)}: not valid JSON ({e})")
    print(f"Checked {n} pages.")
    for x in notes:
        print("note:", x)
    for x in errors[:200]:
        print("ERROR:", x)
    if errors:
        print(f"{len(errors)} error(s).")
        sys.exit(1)
    print("No errors.")


if __name__ == "__main__":
    main()
