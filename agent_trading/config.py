"""Operational configuration only; no implicit strategy parameters."""

from dataclasses import dataclass
import json
import math
from pathlib import Path
import re

from .market import bar_duration


@dataclass(frozen=True)
class Config:
    mode: str = "replay"
    history_limit: int = 512
    data_path: str = "examples/candles.jsonl"
    output_path: str = "runs/replay.jsonl"
    symbol: str = "BTC-USDT"
    timeframes: tuple[str, ...] = ("4H", "1H", "15m")
    bootstrap_limit: int = 100
    shadow_cycles: int = 1
    poll_interval_seconds: int = 15
    cli_timeout_seconds: int = 30
    okx_site: str = "tr"
    node_path: str | None = None
    okx_cli_path: str | None = None

    def __post_init__(self):
        if self.mode not in ("replay", "shadow"):
            raise ValueError("only replay and shadow are implemented; live and backtest are unavailable")
        if type(self.history_limit) is not int or self.history_limit <= 0:
            raise ValueError("history_limit must be a positive integer")
        for path in (self.data_path, self.output_path):
            if not isinstance(path, str) or not path.strip():
                raise ValueError("data_path and output_path must be nonempty strings")
        if not isinstance(self.symbol, str) or not re.fullmatch(r"[A-Z0-9]+(?:-[A-Z0-9]+)+", self.symbol):
            raise ValueError("symbol must be an OKX instrument identifier")
        if not isinstance(self.timeframes, (list, tuple)) or not self.timeframes:
            raise ValueError("timeframes must be a nonempty list")
        if any(not isinstance(tf, str) for tf in self.timeframes):
            raise ValueError("timeframes must contain strings")
        if len(set(self.timeframes)) != len(self.timeframes):
            raise ValueError("timeframes must be unique")
        for tf in self.timeframes:
            bar_duration(tf)
        object.__setattr__(self, "timeframes", tuple(self.timeframes))
        if type(self.bootstrap_limit) is not int or not 1 <= self.bootstrap_limit <= 299:
            raise ValueError("bootstrap_limit must be between 1 and 299")
        if self.mode == "shadow" and self.history_limit < self.bootstrap_limit:
            raise ValueError("history_limit must retain the requested bootstrap context")
        if type(self.shadow_cycles) is not int or self.shadow_cycles < 0:
            raise ValueError("shadow_cycles must be nonnegative (0 means continuous)")
        if type(self.poll_interval_seconds) not in (int, float) or not math.isfinite(self.poll_interval_seconds) or self.poll_interval_seconds <= 0:
            raise ValueError("poll_interval_seconds must be positive and finite")
        if type(self.cli_timeout_seconds) is not int or self.cli_timeout_seconds <= 0:
            raise ValueError("cli_timeout_seconds must be a positive integer")
        if self.okx_site not in ("tr", "global", "eea"):
            raise ValueError("unsupported OKX site")
        for path in (self.node_path, self.okx_cli_path):
            if path is not None and (not isinstance(path, str) or not path.strip()):
                raise ValueError("optional runtime paths must be nonempty strings")

    @classmethod
    def load(cls, path: Path) -> "Config":
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(payload, dict):
            raise ValueError("configuration must be a JSON object")
        try:
            return cls(**payload)
        except TypeError as exc:
            raise ValueError("unknown configuration field") from exc
