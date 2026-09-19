"""Keep tests away from the developer's real .env: no real tokens, account keys or public URLs.

Settings read from .env are overridden by environment variables, including
empty ones, so blanking them makes a default app behave like a clean checkout
(no Telegram polling, no private account reads, open local-only API).
"""
from unittest.mock import patch


BLANK_LOCAL_SETTINGS = {name: "" for name in (
    "TELEGRAM_BOT_TOKEN", "WEBAPP_URL", "ALLOWED_ORIGINS", "API_ACCESS_TOKEN",
    "TELEGRAM_ALLOWED_USER_IDS", "OKX_API_KEY", "OKX_SECRET_KEY", "OKX_PASSPHRASE")}


def isolated_environment():
    """A patch.dict to start in setUpModule and stop in tearDownModule."""
    return patch.dict("os.environ", BLANK_LOCAL_SETTINGS)
