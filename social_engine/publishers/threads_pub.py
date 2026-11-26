"""Meta Threads API (graph.threads.net): single posts, image carousels and reply chains.

Needs THREADS_USER_ID and THREADS_ACCESS_TOKEN (a long-lived token; see refresh_threads_token.py).
Threads fetches images itself, so every image must already be public on the website: verify_assets() waits for that.
"""
import os
import time

import requests

from . import PublishError

BASE = "https://graph.threads.net/v1.0"
TIMEOUT = 40


def _creds():
    uid, tok = os.environ.get("THREADS_USER_ID", "").strip(), os.environ.get("THREADS_ACCESS_TOKEN", "").strip()
    if not uid or not tok:
        raise PublishError("THREADS_USER_ID or THREADS_ACCESS_TOKEN is not set")
    return uid, tok


def _req(method, path, params, session=None):
    try:
        r = (session or requests).request(method, f"{BASE}/{path}", params=params if method == "GET" else None,
                                          data=params if method != "GET" else None, timeout=TIMEOUT)
        body = r.json()
    except (requests.RequestException, ValueError) as e:
        raise PublishError(f"Threads {path.split('/')[-1]}: {type(e).__name__}") from None     # the token is in the request: never echo it
    if r.status_code >= 400 or "error" in body:
        err = body.get("error", {})
        raise PublishError(f"Threads {path.split('/')[-1]}: {r.status_code} {err.get('message', '')} (code {err.get('code')})")
    return body


def verify_assets(urls, tries=6, wait=15, session=None, sleep=time.sleep):
    """HEAD every image address until all answer 200 (GitHub Pages needs a moment after a deployment)."""
    pending = list(urls)
    for attempt in range(tries):
        still = []
        for u in pending:
            try:
                ok = (session or requests).head(u, timeout=20, allow_redirects=True).status_code == 200
            except requests.RequestException:
                ok = False
            if not ok:
                still.append(u)
        pending = still
        if not pending:
            return True
        if attempt < tries - 1:
            sleep(wait)
    raise PublishError("images are not public yet: " + ", ".join(pending))


def wait_finished(container_id, token, tries=20, wait=3, session=None, sleep=time.sleep):
    for _ in range(tries):
        st = _req("GET", container_id, {"fields": "status,error_message", "access_token": token}, session)
        if st.get("status") == "FINISHED":
            return
        if st.get("status") in ("ERROR", "EXPIRED"):
            raise PublishError(f"Threads container {st.get('status')}: {st.get('error_message', '')}")
        sleep(wait)
    raise PublishError("Threads container was not ready in time")


def _publish(uid, token, creation_id, session, sleep):
    wait_finished(creation_id, token, session=session, sleep=sleep)
    return _req("POST", f"{uid}/threads_publish", {"creation_id": creation_id, "access_token": token}, session)["id"]


def post(text, image_urls=(), reply_to=None, session=None, sleep=time.sleep):
    """One post: text only, one image, or a carousel of 2-20 images. Returns the published post id."""
    uid, token = _creds()
    urls = list(image_urls)
    common = {"access_token": token, **({"reply_to_id": reply_to} if reply_to else {})}
    if len(urls) >= 2:
        children = []
        for u in urls:
            children.append(_req("POST", f"{uid}/threads", {"media_type": "IMAGE", "image_url": u, "is_carousel_item": "true", "access_token": token}, session)["id"])
        for c in children:
            wait_finished(c, token, session=session, sleep=sleep)
        parent = _req("POST", f"{uid}/threads", {"media_type": "CAROUSEL", "children": ",".join(children), "text": text, **common}, session)["id"]
    elif urls:
        parent = _req("POST", f"{uid}/threads", {"media_type": "IMAGE", "image_url": urls[0], "text": text, **common}, session)["id"]
    else:
        parent = _req("POST", f"{uid}/threads", {"media_type": "TEXT", "text": text, **common}, session)["id"]
    return _publish(uid, token, parent, session, sleep)


def post_thread(parts, image_urls=(), session=None, sleep=time.sleep, verify=True):
    """The first part carries the images; later parts are replies to the part before. Returns {"ids": [...]}."""
    if image_urls and verify:
        verify_assets(image_urls, session=session, sleep=sleep)
    ids = []
    for i, text in enumerate(parts):
        ids.append(post(text, image_urls if i == 0 else (), reply_to=ids[-1] if ids else None, session=session, sleep=sleep))
    return {"ids": ids}
