"""X API v2 with OAuth 1.0a user context: upload one image, then POST /2/tweets (plain text, never a link).

Needs X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET (an app with Read and Write permission).
"""
import os
import re

import requests

from . import PublishError

API = "https://api.x.com/2"
UPLOAD_V1 = "https://upload.twitter.com/1.1/media/upload.json"
TIMEOUT = 60


def oauth_session():
    from requests_oauthlib import OAuth1Session
    keys = [os.environ.get(k, "").strip() for k in ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_SECRET")]
    if not all(keys):
        raise PublishError("the four X_* credentials are not all set")
    return OAuth1Session(keys[0], client_secret=keys[1], resource_owner_key=keys[2], resource_owner_secret=keys[3])


def _json(r, what):
    try:
        body = r.json()
    except ValueError:
        body = {}
    if r.status_code >= 400:
        detail = body.get("detail") or body.get("title") or "; ".join(str(e.get("message", "")) for e in body.get("errors", []) if isinstance(e, dict))
        raise PublishError(f"X {what}: {r.status_code} {detail}".strip())
    return body


def upload_media(path, session):
    """The v2 media endpoint; the older v1.1 endpoint is tried when v2 is not available to the app."""
    try:
        with open(path, "rb") as f:
            r = session.post(f"{API}/media/upload", files={"media": (os.path.basename(path), f, "image/png")},
                             data={"media_category": "tweet_image"}, timeout=TIMEOUT)
        if r.status_code in (403, 404):
            with open(path, "rb") as f:
                r = session.post(UPLOAD_V1, files={"media": f}, timeout=TIMEOUT)
            return str(_json(r, "media upload")["media_id_string"])
        body = _json(r, "media upload")
    except requests.RequestException as e:
        raise PublishError(f"X media upload: {type(e).__name__}") from None
    return str((body.get("data") or body).get("id") or body.get("media_id_string"))


def post_thread(parts, image=None, session=None):
    """The first post carries the image; later parts reply to the part before. Returns {"ids": [...]}."""
    for p in parts:
        if re.search(r"https?://", p, re.I):
            raise PublishError("a link was about to be posted to X; the post was stopped")       # last line of defence after the gate
    session = session or oauth_session()
    media = upload_media(image, session) if image and os.path.exists(image) else None
    ids = []
    for i, text in enumerate(parts):
        payload = {"text": text}
        if i == 0 and media:
            payload["media"] = {"media_ids": [media]}
        if ids:
            payload["reply"] = {"in_reply_to_tweet_id": ids[-1]}
        try:
            r = session.post(f"{API}/tweets", json=payload, timeout=TIMEOUT)
        except requests.RequestException as e:
            raise PublishError(f"X post: {type(e).__name__}") from None
        ids.append(str(_json(r, "post")["data"]["id"]))
    return {"ids": ids}
