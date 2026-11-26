"""Telegram Bot API (HTML mode): the public channel post, the private Xiaohongshu pack, and alerts.

Needs TELEGRAM_BOT_TOKEN, plus TELEGRAM_PUBLIC_CHAT_ID and / or TELEGRAM_DRAFTS_CHAT_ID. The bot must be an admin of both chats.
"""
import html
import json
import os
import re

import requests

from .. import config
from . import PublishError

API = "https://api.telegram.org/bot{token}/{method}"
TIMEOUT = 40


def _call(method, data=None, files=None, session=None):
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise PublishError("TELEGRAM_BOT_TOKEN is not set")
    try:
        r = (session or requests).post(API.format(token=token, method=method), data=data, files=files, timeout=TIMEOUT)
        body = r.json()
    except (requests.RequestException, ValueError) as e:
        raise PublishError(f"Telegram {method}: {type(e).__name__}") from None       # never the exception text: it holds the token in the URL
    if not body.get("ok"):
        raise PublishError(f"Telegram {method}: {body.get('error_code')} {body.get('description')}")
    return body["result"]


def plain_len(text):
    return len(html.unescape(re.sub(r"<[^>]*>", "", text)))


def split_text(text, limit=None):
    """Telegram HTML cut at blank lines, never inside a paragraph, each piece within the message limit."""
    limit = limit or config.TELEGRAM_TEXT_MAX
    out, cur = [], ""
    for para in text.split("\n\n"):
        nxt = (cur + "\n\n" + para) if cur else para
        if plain_len(nxt) > limit and cur:
            out.append(cur)
            cur = para
        else:
            cur = nxt
    return out + ([cur] if cur else [])


def button(label, url):
    return json.dumps({"inline_keyboard": [[{"text": label, "url": url}]]}, ensure_ascii=False)


def send_message(chat_id, text, markup=None, session=None, silent=False):
    ids = []
    parts = split_text(text)
    for i, part in enumerate(parts):
        data = {"chat_id": chat_id, "text": part, "parse_mode": "HTML", "disable_web_page_preview": "true", "disable_notification": "true" if silent else "false"}
        if markup and i == len(parts) - 1:
            data["reply_markup"] = markup
        ids.append(_call("sendMessage", data, session=session)["message_id"])
    return ids


def send_photo(chat_id, path, caption="", markup=None, session=None):
    """Photo with its caption and button. A caption over Telegram's 1,024 characters goes out as a follow-up message (the button moves with it)."""
    fits = plain_len(caption) <= config.TELEGRAM_CAPTION_MAX
    data = {"chat_id": chat_id}
    if caption and fits:
        data.update(caption=caption, parse_mode="HTML")
    if markup and (fits or not caption):
        data["reply_markup"] = markup
    with open(path, "rb") as f:
        ids = [_call("sendPhoto", data, files={"photo": (os.path.basename(path), f, "image/png")}, session=session)["message_id"]]
    if caption and not fits:
        ids += send_message(chat_id, caption, markup, session)
    return ids


def send_media_group(chat_id, paths, session=None):
    media = [{"type": "photo", "media": f"attach://p{i}"} for i in range(len(paths))]
    handles = [open(p, "rb") for p in paths]
    try:
        files = {f"p{i}": (os.path.basename(p), h, "image/png") for i, (p, h) in enumerate(zip(paths, handles))}
        got = _call("sendMediaGroup", {"chat_id": chat_id, "media": json.dumps(media)}, files=files, session=session)
    finally:
        for h in handles:
            h.close()
    return [m["message_id"] for m in got]


# ---------- what the orchestrator calls ----------
def post_public(text, image=None, lang="tc", session=None):
    """The public channel: wide card + caption + the button that opens the web brief."""
    chat = os.environ.get("TELEGRAM_PUBLIC_CHAT_ID", "").strip()
    if not chat:
        raise PublishError("TELEGRAM_PUBLIC_CHAT_ID is not set")
    label = {"tc": "開啟完整盤前簡報", "sc": "打开完整盘前简报", "en": "Open the full pre-market brief"}[lang]
    markup = button(label, config.site_url(lang))
    ids = send_photo(chat, image, text, markup, session) if image and os.path.exists(image) else send_message(chat, text, markup, session)
    return {"message_ids": ids}


def post_xhs_pack(xhs, images, brief_date, session=None):
    """The private drafts chat: the four Simplified Chinese slides, then one message to copy into Xiaohongshu."""
    chat = os.environ.get("TELEGRAM_DRAFTS_CHAT_ID", "").strip()
    if not chat:
        raise PublishError("TELEGRAM_DRAFTS_CHAT_ID is not set")
    ids = send_media_group(chat, images, session) if len(images) >= 2 else ([send_photo(chat, images[0], session=session)[0]] if images else [])
    esc = lambda x: html.escape(str(x), quote=False)      # noqa: E731
    tags = " ".join("#" + t for t in xhs["hashtags"])
    text = (f"<b>小红书草稿｜{esc(brief_date)}</b>（长按下面三段即可复制）\n\n<b>标题</b>\n<code>{esc(xhs['title'])}</code>\n\n"
            f"<b>正文</b>\n<code>{esc(xhs['body'])}</code>\n\n<b>话题</b>\n<code>{esc(tags)}</code>")
    ids += send_message(chat, text, session=session)
    return {"message_ids": ids}


def alert(text, session=None):
    """A note to the private drafts chat (run summary, compliance failure, API error). Never raises: alerts must not break a run."""
    chat = os.environ.get("TELEGRAM_DRAFTS_CHAT_ID", "").strip()
    if not chat or not os.environ.get("TELEGRAM_BOT_TOKEN", "").strip():
        return False
    try:
        send_message(chat, html.escape(text, quote=False)[:3900], session=session, silent=True)
        return True
    except PublishError as e:
        print(f"Alert not delivered: {e}", flush=True)
        return False
