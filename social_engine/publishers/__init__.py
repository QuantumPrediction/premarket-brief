"""One module per platform. Each takes a requests-like `session` so tests can run without a network."""


class PublishError(RuntimeError):
    """A platform refused or failed; the message is safe to log and to send to the alerts chat (no secrets)."""
