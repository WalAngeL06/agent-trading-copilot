"""Environment-only product/demo settings; secret values are never represented."""

from dataclasses import dataclass, field
import os
from pathlib import Path
import re
from urllib.parse import urlsplit


DEMO_ENV_FIELDS = ("TELEGRAM_BOT_TOKEN", "WEBAPP_URL", "ALLOWED_ORIGINS",
                   "API_ACCESS_TOKEN", "TELEGRAM_ALLOWED_USER_IDS")
MIN_ACCESS_TOKEN_LENGTH = 24
LOCAL_FRONTEND_ORIGINS = ("http://localhost:5173", "http://127.0.0.1:5173")


def _file_values(path):
    try:
        text = Path(path).read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        return {}
    except (OSError, UnicodeError, TypeError, ValueError):
        raise ValueError("demo environment file is unreadable") from None
    values, seen = {}, set()
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        name, separator, value = line.partition("=")
        name, value = name.strip(), value.strip()
        if not separator or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) or name in seen:
            raise ValueError("demo environment file is invalid")
        seen.add(name)
        if value.startswith(("'", '"')):
            if len(value) < 2 or value[-1] != value[0]:
                raise ValueError("demo environment file is invalid")
            value = value[1:-1]
        if name in DEMO_ENV_FIELDS:
            values[name] = value
    return values


def _url(value, default):
    value = value.strip() if isinstance(value, str) else ""
    value = value or default
    parsed = urlsplit(value)
    if parsed.scheme not in ("http", "https") or not parsed.netloc or parsed.username or parsed.password:
        raise ValueError("product URL must be an HTTP(S) URL without credentials")
    return value


def _access_token(value):
    value = value.strip()
    if value and (len(value) < MIN_ACCESS_TOKEN_LENGTH
                  or any(ord(char) <= 32 or ord(char) == 127 for char in value)):
        raise ValueError(f"API_ACCESS_TOKEN must be at least {MIN_ACCESS_TOKEN_LENGTH} "
                         "printable characters without spaces")
    return value


def _user_ids(value):
    ids = []
    for item in value.split(",") if value.strip() else ():
        item = item.strip()
        if not re.fullmatch(r"[1-9][0-9]{0,15}", item):
            raise ValueError("TELEGRAM_ALLOWED_USER_IDS must be comma-separated Telegram user IDs")
        ids.append(int(item))
    return tuple(dict.fromkeys(ids))


def _origin(value):
    parsed = urlsplit(value)
    if (parsed.scheme not in ("http", "https") or not parsed.netloc or parsed.username
            or parsed.password or parsed.path not in ("", "/") or parsed.query or parsed.fragment):
        raise ValueError("allowed origins must be bare HTTP(S) origins")
    return f"{parsed.scheme}://{parsed.netloc}"


@dataclass(frozen=True)
class DemoConfig:
    telegram_bot_token: str = field(default="", repr=False)
    webapp_url: str = "http://127.0.0.1:5173"
    allowed_origins: tuple[str, ...] = LOCAL_FRONTEND_ORIGINS
    api_access_token: str = field(default="", repr=False)
    telegram_allowed_user_ids: tuple[int, ...] = ()

    @classmethod
    def from_env(cls, env_file=".env", *, env=None):
        values = _file_values(env_file)
        source = os.environ if env is None else env
        for name in DEMO_ENV_FIELDS:
            if name in source:
                values[name] = source[name]
        token = values.get("TELEGRAM_BOT_TOKEN", "").strip()
        if any(ord(char) < 32 or ord(char) == 127 for char in token):
            raise ValueError("Telegram token is invalid")
        webapp_url = _url(values.get("WEBAPP_URL", ""), "http://127.0.0.1:5173")
        origins = list(LOCAL_FRONTEND_ORIGINS)
        configured = values.get("ALLOWED_ORIGINS", "")
        if configured.strip():
            for item in configured.split(","):
                origin = _origin(item.strip())
                if origin not in origins:
                    origins.append(origin)
        return cls(token, webapp_url, tuple(origins),
                   _access_token(values.get("API_ACCESS_TOKEN", "")),
                   _user_ids(values.get("TELEGRAM_ALLOWED_USER_IDS", "")))
