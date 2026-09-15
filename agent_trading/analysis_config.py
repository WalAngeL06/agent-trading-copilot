"""Operator-owned analysis requirements/settings; no strategy or live switches."""

from dataclasses import dataclass
import math
import os
from pathlib import Path
import re

from .market import bar_duration


BASELINE_TIMEFRAMES = ("4H", "1H", "15m")


@dataclass(frozen=True)
class AnalysisConfig:
    db_path: Path = Path("runs/product/analyses.sqlite3")
    audit_dir: Path = Path("runs/analyses")
    allowed_symbols: tuple[str, ...] = ("BTC-USDT",)
    required_timeframes: tuple[str, ...] = BASELINE_TIMEFRAMES
    history_limit: int = 100
    publication_grace_seconds: int = 60
    observation_max_age_seconds: int = 60
    mcp_timeout_seconds: float = 20
    analysis_timeout_seconds: float = 60
    ready_ttl_seconds: float = 60
    sqlite_timeout_seconds: float = 1
    node_path: str | None = None
    server_path: str | None = None

    def __post_init__(self):
        for name in ("db_path", "audit_dir"):
            value = getattr(self, name)
            if not isinstance(value, (str, Path)) or not str(value).strip():
                raise ValueError("Product paths must be nonempty")
            object.__setattr__(self, name, Path(value))
        symbols = self.allowed_symbols
        if (not isinstance(symbols, (tuple, list)) or not 1 <= len(symbols) <= 5 or
                any(not isinstance(s, str) or len(s) > 40 or
                    not re.fullmatch(r"[A-Z0-9]+(?:-[A-Z0-9]+)+", s) for s in symbols) or
                len(set(symbols)) != len(symbols)):
            raise ValueError("A small explicit instrument allowlist is required")
        object.__setattr__(self, "allowed_symbols", tuple(symbols))
        frames = self.required_timeframes
        if (not isinstance(frames, (tuple, list)) or not 1 <= len(frames) <= 16 or
                any(not isinstance(tf, str) for tf in frames) or len(set(frames)) != len(frames)):
            raise ValueError("Required timeframes must be a bounded unique collection")
        for tf in frames:
            bar_duration(tf)
        object.__setattr__(self, "required_timeframes", tuple(frames))
        for name, low, high in (("history_limit", 1, 299), ("publication_grace_seconds", 0, 300),
                                ("observation_max_age_seconds", 1, 300)):
            value = getattr(self, name)
            if type(value) is not int or not low <= value <= high:
                raise ValueError("Operational integer setting is outside bounds")
        for name, upper in (("mcp_timeout_seconds", 60), ("analysis_timeout_seconds", 300),
                            ("ready_ttl_seconds", 300), ("sqlite_timeout_seconds", 5)):
            value = getattr(self, name)
            if type(value) not in (int, float) or not math.isfinite(value) or not 0 < value <= upper:
                raise ValueError("Operational timeout must be positive, finite and bounded")
        for name in ("node_path", "server_path"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError("Operator runtime paths must be nonempty")

    @classmethod
    def from_env(cls):
        fields = {}
        for field, env in (("db_path", "ANALYSIS_DB_PATH"), ("audit_dir", "ANALYSIS_AUDIT_DIR"),
                           ("node_path", "ANALYSIS_NODE_PATH"), ("server_path", "ANALYSIS_ATK_SERVER_PATH")):
            if env in os.environ:
                fields[field] = os.environ[env]
        for field in ("history_limit", "publication_grace_seconds", "observation_max_age_seconds"):
            env = "ANALYSIS_" + field.upper()
            if env in os.environ:
                fields[field] = int(os.environ[env])
        for field in ("mcp_timeout_seconds", "analysis_timeout_seconds", "ready_ttl_seconds",
                      "sqlite_timeout_seconds"):
            env = "ANALYSIS_" + field.upper()
            if env in os.environ:
                fields[field] = float(os.environ[env])
        if "ANALYSIS_ALLOWED_SYMBOLS" in os.environ:
            fields["allowed_symbols"] = tuple(os.environ["ANALYSIS_ALLOWED_SYMBOLS"].split(","))
        if "ANALYSIS_REQUIRED_TIMEFRAMES" in os.environ:
            fields["required_timeframes"] = tuple(
                tf.strip() for tf in os.environ["ANALYSIS_REQUIRED_TIMEFRAMES"].split(","))
        return cls(**fields)
