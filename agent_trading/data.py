"""Incremental replay input. Input order is preserved, never silently sorted."""

import json
from decimal import Decimal
from pathlib import Path
from typing import Iterator

from .models import Candle


def read_candles(path: Path) -> Iterator[Candle]:
    with path.open(encoding="utf-8-sig") as source:
        for number, line in enumerate(source, 1):
            if not line.strip():
                continue
            try:
                yield Candle.from_dict(json.loads(line, parse_float=Decimal))
            except ValueError as exc:
                raise ValueError(f"{path}: line {number}: {exc}") from exc
