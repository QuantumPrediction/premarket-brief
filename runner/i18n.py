"""Translate the v6.3 brief from Traditional Chinese into English and Simplified Chinese.

The v6.3 scripts write Traditional Chinese only. This module reuses the translation method of the
biotech brief v1.2: a hand-translated phrase table for English (at each position the longest phrase
wins), and a character table plus a few mainland terms for Simplified Chinese.
Tables next to this file: i18n_table.json (biotech v1.2) and i18n_v63.json (v6.3 phrases and overrides),
plus a few regular expressions below for sentences where numbers sit between the words.
"""
import html as _html_i18n
import json
import os
import re

_HERE = os.path.dirname(os.path.abspath(__file__))
_EN, _SC = {}, {}


def _load():
    if _EN:
        return
    d = json.load(open(os.path.join(_HERE, "i18n_table.json"), encoding="utf-8"))
    extra = os.path.join(_HERE, "i18n_v63.json")                   # v6.3 phrases and overrides
    if os.path.exists(extra):
        d["en"].update(json.load(open(extra, encoding="utf-8"))["en"])
    _SC["tab"] = str.maketrans(d["sc_chars"], d["sc_to"])
    _SC["terms"] = [tuple(x) for x in d["sc_terms"]]
    m = {k: v for k, v in d["en"].items() if k}
    mh = {}
    for k, v in m.items():                                     # web pages: escape the English; also match the escaped Chinese
        vh = v if '"' in k else _html_i18n.escape(v, quote=False)
        mh[k] = vh
        ke = _html_i18n.escape(k)
        if ke != k and ke not in m:
            mh[ke] = vh
    for nm, mm in (("", m), ("h", mh)):
        root = {}
        for k in mm:
            n = root
            for ch in k:
                n = n.setdefault(ch, {})
            n[""] = mm[k]
        _EN["m" + nm], _EN["t" + nm], _EN["rx" + nm] = mm, root, re.compile("(?=" + _trie_rx(mm) + ")")


def _trie_rx(keys):
    """把所有原文砌成字典樹再轉成正則表達式：同一位置永遠取最長的原文。"""
    root = {}
    for k in keys:
        n = root
        for ch in k:
            n = n.setdefault(ch, {})
        n[""] = 1
    def pat(n):
        kids = sorted(k for k in n if k != "")
        if not kids:
            return ""
        parts, leaf = [], []
        for ch in kids:
            sub = n[ch]
            if len(sub) == 1 and "" in sub:
                leaf.append(ch)
            else:
                parts.append(re.escape(ch) + pat(sub))
        if leaf:
            parts.append(re.escape(leaf[0]) if len(leaf) == 1 else "[" + "".join(re.escape(c) for c in leaf) + "]")
        body = parts[0] if len(parts) == 1 else "(?:" + "|".join(parts) + ")"
        return "(?:" + body + ")?" if "" in n else body
    return pat(root)

_CJK_RX = re.compile(r"[㐀-鿿]")
_NEED_RX = re.compile("[\u3000-\u303f\u30fb\u3400-\u9fff\uff00-\uffef]")     # 英文版不應留下的字（中文字和全形標點）
_LEAD_STRIP = "([“（「【《『）」】》』，。；：、！？｜"
_TRAIL_STRIP = ",.;:)!?]%”）」】》』，。；：、！？｜（"
_EN_WD = {"一": "Mon", "二": "Tue", "三": "Wed", "四": "Thu", "五": "Fri", "六": "Sat", "日": "Sun"}
_EN_MON = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
_EN_QN = {"一": "1", "二": "2", "三": "3", "四": "4"}
_EN_RULES = [
    (re.compile(r"(20\d\d) 年第([一二三四])季"), lambda m: f"Q{_EN_QN[m.group(2)]} {m.group(1)}"),
    (re.compile(r"(20\d\d) 年上半年"), lambda m: f"1H {m.group(1)}"),
    (re.compile(r"(20\d\d) 年下半年"), lambda m: f"2H {m.group(1)}"),
    (re.compile(r"(20\d\d) 年年中"), lambda m: f"mid-{m.group(1)}"),
    (re.compile(r"(20\d\d) 年底前後"), lambda m: f"late {m.group(1)}"),
    (re.compile(r"(20\d\d) 年底"), lambda m: f"end-{m.group(1)}"),
    (re.compile(r"(20\d\d) 年初"), lambda m: f"early {m.group(1)}"),
    (re.compile(r"（([一二三四五六日])）"), lambda m: f" ({_EN_WD[m.group(1)]})"),
    (re.compile(r"(?<![\d.])(1[0-2]|[1-9])月(?!\d)"), lambda m: _EN_MON[int(m.group(1))]),
    (re.compile(r"等 (\d+) 間"), lambda m: f" ({m.group(1)} in all)"),
]
_INLINE_TAG = re.compile(r"</?(?:b|i|a|span|small|strong|em|code)\b[^<>]*>$")

def _en_side(s, i, step, html):
    """取 i 位置的字元；網頁版遇到行內標籤（<b> 等）就跳過，看標籤另一邊的字。"""
    for _ in range(4):
        if i < 0 or i >= len(s):
            return ""
        c = s[i]
        if not html or c not in "<>":
            return c
        if step < 0 and c == ">":
            j = s.rfind("<", 0, i)
            if j < 0 or not _INLINE_TAG.search(s[j:i + 1]):
                return c
            i = j - 1
        elif step > 0 and c == "<":
            j = s.find(">", i)
            if j < 0 or not _INLINE_TAG.search(s[i:j + 1]):
                return c
            i = j + 1
        else:
            return c
    return ""

def _wordy(c):
    return bool(c) and ((c.isascii() and c.isalnum()) or bool(_CJK_RX.match(c)))

_EN_CTX = {"日": lambda q: "" if re.search(r"(?:day|rank|item|attempt|#) ?\d+\s*$", q) else "days",
           "之上": lambda q: "or higher" if re.search(r"\d\s*$", q) else "above",
           "之下": lambda q: "or lower" if re.search(r"\d\s*$", q) else "below"}
_SC_RULES = [(re.compile(r"(\d+) 注"), r"\1 笔")]

def _en_last(out, html):
    """已輸出文字的最後一個字（網頁版跳過行內標籤）。"""
    t = "".join(out[-6:])
    if html:
        t = re.sub(r"(?:</?(?:b|i|a|span|small|strong|em|code)\b[^<>]*>)+$", "", t)
    return t[-1:] if t else "", t

def _en_put(out, s, j, v, html):
    """加入一段譯文：按已輸出的前一個字和原文的下一個字決定空格。"""
    if not v:
        return
    q, tail = _en_last(out, html)
    n = _en_side(s, j, 1, html)
    if v[0] == " " and (not q or q.isspace() or q in "([“$" or (html and q == ">")):
        v = v.lstrip(" ")
    if v and v[0] in ",.;:)!?%" and out and out[-1][-1:] == " " and out[-1][-2:] != "  " and not out[-1].endswith("\n "):
        out[-1] = out[-1][:-1]
    if v and v[-1] == " " and (not n or n.isspace() or n in ",.;:)!?]%”，。；：、）」】》』！？" or (html and n == "<")):
        v = v.rstrip(" ")
    if not v:
        return
    if (v[0].isalnum() or v[0] in "(“$") and q and ((q.isascii() and q.isalnum()) or _CJK_RX.match(q) or q in ")]%”’×:;,.!?|·▲▼↑↓★"):
        v = " " + v
    elif v[0] in "|·" and q and not q.isspace():
        v = " " + v
    if (v[-1].isalnum() or v[-1] in ").:;,%”|·]") and n and ((n.isascii() and n.isalnum()) or n in "(“$±+−「『《【★"):
        v = v + " "
    out.append(v)

def _en_sub(s, html):
    """逐段換成英文。同一處有幾種切法時，取段數最少、又不留下中文字的一種（動態規劃）。"""
    h = "h" if html else ""
    root, rx = _EN["t" + h], _EN["rx" + h]
    ms = {}
    for mo in rx.finditer(s):
        i = mo.start()
        n, j, ends = root, i, []
        while j < len(s) and s[j] in n:
            n = n[s[j]]
            j += 1
            if "" in n:
                ends.append((j, n[""]))
        if ends:
            ms[i] = ends
    if not ms:
        return s
    pts = sorted(set(ms) | {j for e in ms.values() for j, _ in e} | {mo.start() for mo in _NEED_RX.finditer(s)} | {len(s)})
    best = {len(s): (0, None)}
    for k in range(len(pts) - 2, -1, -1):
        i = pts[k]
        b = (best[pts[k + 1]][0] + (5 if _NEED_RX.match(s[i]) else 0), None)
        for j, v in ms.get(i, ()):
            c = 1 - 0.001 * (j - i) + best[j][0]                 # 同樣段數時取較長的原文
            if c < b[0]:
                b = (c, (j, v))
        best[i] = b
    nxt = {pts[x]: pts[x + 1] for x in range(len(pts) - 1)}
    pos = pts[0]
    out = [s[:pos]]
    while pos < len(s):
        ch = best[pos][1]
        if ch:
            j, v = ch
            key = s[pos:j]
            if key in _EN_CTX:
                v = _EN_CTX[key](_en_last(out, html)[1])
            elif re.fullmatch(r"\d+ 日", key) and re.search(r"(?:day|rank|item|attempt|#)\s*$", _en_last(out, html)[1]):
                v = key[:-2]                                  # 「第 9 日」→ day 9
            _en_put(out, s, j, v, html)
        else:
            j = nxt[pos]
            out.append(s[pos:j])
        pos = j
    return "".join(out)



def translate(s, lang, html=False):
    """Traditional Chinese text -> lang ("tc" returns it unchanged). html=True for a whole web page."""
    if lang == "tc" or not isinstance(s, str) or not s:
        return s
    _load()
    if lang == "sc":
        t = s.translate(_SC["tab"])
        for a, b in _SC["terms"]:
            t = t.replace(a, b)
        for rx, b in _SC_RULES:
            t = rx.sub(b, t)
        return t.replace("「", "“").replace("」", "”").replace("『", "‘").replace("』", "’")
    if html is True:                                         # web page: leave <style> and <script> alone
        parts = re.split(r"(<style[^>]*>.*?</style>|<script[^>]*>.*?</script>)", s, flags=re.S)
        return "".join(p if p.startswith(("<style", "<script")) else translate(p, lang, "body") for p in parts)
    for rx, fn in _V63_PRE + _EN_RULES:
        s = rx.sub(fn, s)
    s = _en_sub(s, html == "body")
    for rx, fn in _V63_POST:
        s = rx.sub(fn, s)
    return s


_NUM = r"([\d,]+(?:\.\d+)?)"
_V63_PRE = [                                                     # Chinese -> English before the phrase table
    (re.compile(r"開在 " + _NUM + r" 至 " + _NUM + r"(?= 之間)"), r"Opens between \1 and \2"),
    (re.compile(r"開在 " + _NUM + r"(?= 之下：)"), r"Opens below \1"),
    (re.compile(r"開在 " + _NUM + r"(?= 之上：)"), r"Opens above \1"),
    (re.compile(r"（第 (\d+)）"), r" (#\1)"),
    (re.compile(r" (\d+) 則(?=、|$|<|\s)"), r" \1"),
]
_V63_POST = [                                                    # English clean-up after the phrase table
    (re.compile(r"\bbetween " + _NUM + r" to " + _NUM), r"between \1 and \2"),
    (re.compile(r"(?<![\d.,])\b1 (name|day|item|session|stock|share|unit|record)s\b"), r"1 \1"),
    (re.compile(r"(?<=[\d%]) (?=[:;](?:\s|$))"), ""),
    (re.compile(r"\( (?=[\d−-])"), "("),                               # "( 1.3%" -> "(1.3%"                 # "between 1 and 2 : still" -> "between 1 and 2: still"
]


def translate_obj(x, lang):
    """Translate every string inside a JSON-like object."""
    if isinstance(x, str):
        out = translate(x, lang)
        return out.strip() if x == x.strip() else out
    if isinstance(x, list):
        return [translate_obj(v, lang) for v in x]
    if isinstance(x, dict):
        return {k: translate_obj(v, lang) for k, v in x.items()}
    return x


def leftovers(s):
    """Chinese text the English table did not cover (used to check the table)."""
    return _NEED_RX.findall(s)
