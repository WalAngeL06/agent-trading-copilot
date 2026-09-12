"""Operational configuration only; no implicit strategy parameters."""

from dataclasses import dataclass
import json
from pathlib import Path


@dataclass(frozen=True)
class Config:
    mode: str = "replay"
    history_limit: int = 512
    data_path: str = "examples/candles.jsonl"
    output_path: str = "runs/replay.jsonl"

    def __post_init__(self):
        if self.mode != "replay":
            raise ValueError("only replay is implemented; live, shadow and backtest are unavailable")
        if type(self.history_limit) is not int or self.history_limit <= 0:
            raise ValueError("history_limit must be a positive integer")
        for path in (self.data_path, self.output_path):
            if not isinstance(path, str) or not path.strip():
                raise ValueError("data_path and output_path must be nonempty strings")

    @classmethod
    def load(cls, path: Path) -> "Config":
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(payload, dict):
            raise ValueError("configuration must be a JSON object")
        try:
            return cls(**payload)
        except TypeError as exc:
            raise ValueError("unknown configuration field") from exc
