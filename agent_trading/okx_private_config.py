"""Owner-local API-key authentication; never inspect CLI/desktop credential stores."""

from dataclasses import dataclass, field
import os
from pathlib import Path
import re


AUTH_ENV_FIELDS = ("OKX_API_KEY", "OKX_SECRET_KEY", "OKX_PASSPHRASE")


@dataclass(frozen=True)
class PrivateConfig:
    api_key: str = field(default="", repr=False)
    secret_key: str = field(default="", repr=False)
    passphrase: str = field(default="", repr=False)
    error_code: str | None = None

    @property
    def ready(self):
        return self.error_code is None and all((self.api_key, self.secret_key, self.passphrase))

    @property
    def status(self):
        return "ERROR" if self.error_code else "CONFIGURED" if self.ready else "AUTH_MISSING"


def load_private_config(env_file=None, *, env=None) -> PrivateConfig:
    """Strict literal KEY=VALUE file, then environment overrides (even empty values).

    No shell expansion, token lookup, OAuth login, or writes. CONFIGURED is local
    configuration only, never evidence of CONNECTED. Unknown dotenv names are
    ignored rather than forwarded to the MCP child.
    """
    values = {}
    if env_file is not None:
        try:
            path = Path(env_file)
            text = path.read_text(encoding="utf-8-sig")
        except FileNotFoundError:
            text = ""
        except (OSError, UnicodeError, TypeError, ValueError):
            return PrivateConfig(error_code="ENV_UNREADABLE")
        try:
            seen = set()
            for line in text.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                name, separator, value = line.partition("=")
                name, value = name.strip(), value.strip()
                if not separator or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) or name in seen:
                    raise ValueError
                seen.add(name)
                if value.startswith(("'", '"')):
                    if len(value) < 2 or value[-1] != value[0]:
                        raise ValueError
                    value = value[1:-1]
                if name in AUTH_ENV_FIELDS:
                    values[name] = value
        except ValueError:
            return PrivateConfig(error_code="CONFIG_INVALID")
    source = os.environ if env is None else env
    try:
        for name in AUTH_ENV_FIELDS:
            if name in source:
                values[name] = source[name]
        credentials = tuple(values.get(name, "").strip() for name in AUTH_ENV_FIELDS)
        if any(any(ord(char) < 32 or ord(char) == 127 for char in value) for value in credentials):
            return PrivateConfig(error_code="CONFIG_INVALID")
        return PrivateConfig(*credentials)
    except (TypeError, AttributeError):
        return PrivateConfig(error_code="CONFIG_INVALID")
