"""Read-only official Agent Trade Kit CLI adapter; no order operations."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

from .market import bar_duration
from .models import Candle


def _symbol(symbol: str):
    if not isinstance(symbol, str) or not re.fullmatch(r"[A-Z0-9]+(?:-[A-Z0-9]+)+", symbol):
        raise ValueError("invalid OKX instrument identifier")


class OkxMarketAdapter:
    def __init__(self, site="tr", timeout=30, node_path=None, cli_path=None):
        if site not in ("tr", "global", "eea"):
            raise ValueError("unsupported OKX site")
        self.site = site
        self.timeout = timeout
        self.node_path = node_path or shutil.which("node")
        self.cli_path = cli_path or self._installed_cli()
        if not self.node_path or not self.cli_path:
            raise RuntimeError("Node or official OKX CLI not found; configure runtime paths")

    @staticmethod
    def _installed_cli():
        binary = shutil.which("okx")
        if binary:
            candidates = [Path(binary).resolve(),
                          Path(binary).parent / "node_modules/@okx_ai/okx-trade-cli/dist/index.js",
                          Path(binary).parent.parent / "lib/node_modules/@okx_ai/okx-trade-cli/dist/index.js"]
        else:
            candidates = []
        if os.environ.get("APPDATA"):
            candidates.append(Path(os.environ["APPDATA"]) / "npm/node_modules/@okx_ai/okx-trade-cli/dist/index.js")
        for path in candidates:
            if path.is_file() and path.suffix in (".js", ".mjs"):
                return str(path)
        return None

    def _read(self, operation: str, symbol: str, options=()):
        if operation not in ("ticker", "candles", "orderbook"):
            raise ValueError("only allowlisted public market reads are available")
        _symbol(symbol)
        allowed = {"ticker": set(), "candles": {"--bar", "--limit", "--after"},
                   "orderbook": {"--sz"}}[operation]
        if len(options) % 2 or any(options[i] not in allowed for i in range(0, len(options), 2)):
            raise ValueError("unsupported public market option")
        if any(not isinstance(options[i], str) or options[i].startswith("-")
               for i in range(1, len(options), 2)):
            raise ValueError("invalid public market option value")
        try:
            result = subprocess.run(
                [self.node_path, self.cli_path, "market", operation, symbol, *options, "--json"],
                capture_output=True, text=True, encoding="utf-8", timeout=self.timeout,
                shell=False, env=dict(os.environ, OKX_SITE=self.site),
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RuntimeError(f"OKX public {operation} could not complete") from exc
        if result.returncode != 0:
            raise RuntimeError(f"OKX public {operation} failed (exit {result.returncode}); raw output suppressed")
        try:
            data = json.loads(result.stdout, parse_float=Decimal)
        except ValueError as exc:
            raise RuntimeError(f"OKX public {operation} returned invalid JSON") from exc
        if not isinstance(data, list):
            raise RuntimeError(f"OKX public {operation} returned an unexpected data shape")
        return data

    def ticker(self, symbol: str):
        return self._read("ticker", symbol)

    def candles(self, symbol: str, timeframe: str, limit: int, after: int | None = None):
        bar_duration(timeframe)
        if type(limit) is not int or not 1 <= limit <= 300:
            raise ValueError("candle request limit must be between 1 and 300")
        options = ("--bar", timeframe, "--limit", str(limit))
        if after is not None:
            if type(after) is not int or after < 0:
                raise ValueError("after must be a nonnegative millisecond timestamp")
            options += ("--after", str(after))
        return self._read("candles", symbol, options)

    def orderbook(self, symbol: str, depth: int = 5):
        if type(depth) is not int or not 1 <= depth <= 400:
            raise ValueError("order book depth must be between 1 and 400")
        return self._read("orderbook", symbol, ("--sz", str(depth)))


def _decimal(value) -> Decimal:
    if type(value) not in (str, int, Decimal):
        raise ValueError("OKX numeric values must be strings, integers or Decimals; floats are unsafe")
    return Decimal(value)


def normalize_candles(rows: list, symbol: str, timeframe: str,
                      as_of: datetime) -> tuple[Candle, ...]:
    _symbol(symbol)
    duration = bar_duration(timeframe)
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("normalization as_of must include a timezone")
    if not isinstance(rows, list):
        raise ValueError("OKX candles must be an array")
    unique = {}
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    for row in rows:
        try:
            if not isinstance(row, (list, tuple)) or len(row) != 9:
                raise ValueError("OKX candle must have nine fields")
            if type(row[8]) not in (str, int) or str(row[8]) not in ("0", "1"):
                raise ValueError("invalid OKX candle confirmation flag")
            if str(row[8]) == "0":
                continue
            stamp = _decimal(row[0])
            if not stamp.is_finite() or stamp < 0 or stamp != stamp.to_integral_value():
                raise ValueError("invalid OKX candle opening timestamp")
            close_time = epoch + timedelta(milliseconds=int(stamp)) + duration
            if close_time > as_of:
                continue
            candle = Candle(symbol, timeframe, close_time,
                            *(_decimal(value) for value in row[1:6]))
            if close_time in unique and unique[close_time] != candle:
                raise ValueError("conflicting duplicate OKX candle")
            unique[close_time] = candle
        except (InvalidOperation, OverflowError, TypeError) as exc:
            raise ValueError("invalid OKX candle payload") from exc
    return tuple(unique[stamp] for stamp in sorted(unique))
