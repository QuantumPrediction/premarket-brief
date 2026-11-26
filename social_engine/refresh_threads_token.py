"""Keeps the 60-day Threads token alive (run monthly by .github/workflows/threads_token_refresh.yml).

    python -m social_engine.refresh_threads_token

With GH_SECRETS_PAT (a fine-grained token with "Secrets: read and write" on this repository) the refreshed token is
written back to the THREADS_ACCESS_TOKEN secret. Without it nothing is refreshed (a refreshed token that cannot be
stored helps nobody); instead the private Telegram chat is told when the stored token has 10 days or less left.
The expiry date is kept in state/social/threads_token.json. The token itself is never printed or stored there.
"""
import base64
import datetime as dt
import json
import os
import sys

import requests

from . import config
from .publishers import telegram_pub

REFRESH_URL = "https://graph.threads.net/refresh_access_token"
WARN_DAYS = 10


def meta_path(state=None):
    return os.path.join(state or config.state_dir(), "social", "threads_token.json")


def load_meta(state=None):
    try:
        with open(meta_path(state), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_meta(meta, state=None):
    os.makedirs(os.path.dirname(meta_path(state)), exist_ok=True)
    with open(meta_path(state), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=1)


def refresh(token, session=None):
    """Returns (new token, seconds until it expires). Raises RuntimeError with a message that holds no secret."""
    try:
        r = (session or requests).get(REFRESH_URL, params={"grant_type": "th_refresh_token", "access_token": token}, timeout=40)
        body = r.json()
    except (requests.RequestException, ValueError) as e:
        raise RuntimeError(f"Threads refresh: {type(e).__name__}") from None
    if r.status_code >= 400 or "access_token" not in body:
        raise RuntimeError(f"Threads refresh: {r.status_code} {body.get('error', {}).get('message', '')}")
    return body["access_token"], int(body.get("expires_in", 60 * 86400))


def put_secret(repo, name, value, pat, session=None):
    """Write a repository Actions secret (sealed with the repository's public key, as GitHub requires)."""
    from nacl import encoding, public
    s = session or requests
    head = {"Authorization": f"Bearer {pat}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    api = f"https://api.github.com/repos/{repo}/actions/secrets"
    key = s.get(f"{api}/public-key", headers=head, timeout=40)
    if key.status_code >= 400:
        raise RuntimeError(f"GitHub public key: {key.status_code}")
    k = key.json()
    sealed = public.SealedBox(public.PublicKey(k["key"].encode("utf-8"), encoding.Base64Encoder())).encrypt(value.encode("utf-8"))
    r = s.put(f"{api}/{name}", headers=head, timeout=40, json={"encrypted_value": base64.b64encode(sealed).decode("utf-8"), "key_id": k["key_id"]})
    if r.status_code not in (201, 204):
        raise RuntimeError(f"GitHub secret update: {r.status_code}")


def main(session=None, today=None):
    today = today or dt.date.today()
    token = os.environ.get("THREADS_ACCESS_TOKEN", "").strip()
    if not token:
        print("THREADS_ACCESS_TOKEN is not set; nothing to refresh.")
        return 0
    meta = load_meta()
    pat, repo = os.environ.get("GH_SECRETS_PAT", "").strip(), os.environ.get("GITHUB_REPOSITORY", "").strip()
    if pat and repo:
        try:
            new, seconds = refresh(token, session)
            put_secret(repo, "THREADS_ACCESS_TOKEN", new, pat, session)
        except Exception as e:                                           # noqa: BLE001
            msg = f"Threads token refresh failed: {e}. Refresh it by hand before {meta.get('expires_on', 'it expires')} (see social_engine/README.md)."
            print(msg)
            telegram_pub.alert("⚠️ " + msg)
            return 1
        meta = {"expires_on": str(today + dt.timedelta(seconds=seconds)), "refreshed_on": str(today)}
        save_meta(meta)
        print(f"Threads token refreshed and stored; it now expires on {meta['expires_on']}.")
        return 0
    exp = None if "--reset" in sys.argv else meta.get("expires_on")      # --reset: the secret was just renewed by hand
    if not exp:                                                          # first run without a way to store a token: start the clock
        meta = {"expires_on": str(today + dt.timedelta(days=60)), "assumed_from": str(today)}
        save_meta(meta)
        print(f"No GH_SECRETS_PAT: the token is not refreshed automatically. Assuming it was issued today; expiry noted as {meta['expires_on']}.")
        return 0
    left = (dt.date.fromisoformat(exp) - today).days
    print(f"No GH_SECRETS_PAT: the Threads token has about {left} day(s) left (noted expiry {exp}).")
    if left <= WARN_DAYS:
        telegram_pub.alert(f"⚠️ The Threads token expires in about {left} day(s) ({exp}). Refresh it and update the THREADS_ACCESS_TOKEN "
                           "secret, then run the Threads token refresh workflow with 'token renewed' ticked, or add GH_SECRETS_PAT to automate this.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
