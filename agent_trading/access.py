"""Owner-only API access: a bearer access key or an allowlisted Telegram Mini App user."""

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
from urllib.parse import parse_qsl, urlsplit


INIT_DATA_MAX_AGE = timedelta(hours=24)
INIT_DATA_CLOCK_SKEW = timedelta(minutes=5)
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def telegram_user_id(init_data, bot_token, *, now=None):
    """User id from Mini App initData signed with this bot's token, else None.

    Telegram signs every received field except `hash` (sorted `key=value`
    lines) with HMAC-SHA-256 keyed by HMAC-SHA-256("WebAppData", bot token).
    See https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
    """
    if not init_data or not bot_token:
        return None
    try:
        pairs = parse_qsl(init_data, keep_blank_values=True, strict_parsing=True)
    except ValueError:
        return None
    fields = dict(pairs)
    if len(fields) != len(pairs):
        return None
    received = fields.pop("hash", "")
    check = "\n".join(f"{key}={fields[key]}" for key in sorted(fields))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    if not received or not hmac.compare_digest(expected.encode(), received.encode()):
        return None
    try:
        signed_at = datetime.fromtimestamp(int(fields["auth_date"]), timezone.utc)
        user_id = json.loads(fields["user"])["id"]
    except (KeyError, TypeError, ValueError, OverflowError, OSError):
        return None
    now = now or datetime.now(timezone.utc)
    if type(user_id) is not int or not now - INIT_DATA_MAX_AGE <= signed_at <= now + INIT_DATA_CLOCK_SKEW:
        return None
    return user_id


class AccessPolicy:
    """Without a key or Telegram allowlist the API stays open (local development)."""

    def __init__(self, access_token="", telegram_bot_token="", telegram_user_ids=()):
        self._token = access_token.encode()
        self._bot_token = telegram_bot_token
        self._user_ids = frozenset(telegram_user_ids)

    @property
    def enabled(self):
        return bool(self._token) or bool(self._bot_token and self._user_ids)

    def permits(self, authorization, init_data):
        if not self.enabled:
            return True
        if self._token and authorization:
            scheme, _, credential = authorization.partition(" ")
            if scheme.lower() == "bearer" and hmac.compare_digest(credential.strip().encode(), self._token):
                return True
        if self._bot_token and self._user_ids and init_data:
            return telegram_user_id(init_data, self._bot_token) in self._user_ids
        return False


def is_public_deployment(webapp_url, allowed_origins):
    """True when the WebApp or an allowed browser origin is reachable beyond this machine."""
    return any((urlsplit(url).hostname or "") not in _LOCAL_HOSTS
               for url in (webapp_url, *allowed_origins))
