"""Deterministic synthetic OHLC benchmarks. Offline, no RNG, no network.

Scenarios are built from *percentage* moves at a BTC-like price so that a
percentage reversal threshold means the same thing here as it would on real
15m data. Absolute-step fixtures are misleading: if a single bar's range
already exceeds the threshold, every detector confirms on every bar and the
comparison measures the fixture instead of the algorithm.

These are hand-shaped paths, not market data. They are review aids [H]; no
result here is empirical validation of any rule.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from ...models import Candle

SYMBOL = "BTC-USDT"
TIMEFRAME = "15m"
START = datetime(2026, 1, 1, 0, 15, tzinfo=timezone.utc)
STEP = timedelta(minutes=15)
BASE_PRICE = Decimal("60000")
WICK_PCT = Decimal("0.0006")          # ~36 points at 60k: a normal 15m wick
TICK = Decimal("0.1")


def _q(value):
    return Decimal(value).quantize(TICK)


def _walk(returns, start=BASE_PRICE):
    """Close path from fractional returns, quantised to a realistic tick."""
    price, closes = Decimal(start), []
    for step in returns:
        price = price * (Decimal(1) + Decimal(step))
        closes.append(_q(price))
    return closes


def _candles(closes, overrides=None, wick_pct=WICK_PCT,
             symbol=SYMBOL, timeframe=TIMEFRAME):
    """Build a valid closed-candle series from a close path.

    Upper and lower wicks use slightly different deterministic multipliers so
    adjacent candles at a turning point do not produce byte-identical extremes.
    Exactly equal extremes are a fixture artifact, not a market property, and
    they would silently suppress every strict-comparison detector.
    """
    overrides = overrides or {}
    candles = []
    for index, close in enumerate(closes):
        close = _q(close)
        open_ = _q(closes[index - 1]) if index else close
        span = close * Decimal(wick_pct)
        up = _q(span * (Decimal(1) + Decimal(index % 3) / Decimal(10)))
        down = _q(span * (Decimal(1) + Decimal((index + 2) % 3) / Decimal(10)))
        high = max(open_, close) + up
        low = min(open_, close) - down
        if index in overrides:
            over_high, over_low = overrides[index]
            if over_high is not None:
                high = max(high, _q(over_high))
            if over_low is not None:
                low = min(low, _q(over_low))
        candles.append(Candle(symbol=symbol, timeframe=timeframe,
                              close_time=START + STEP * index, open=open_, high=high,
                              low=low, close=close, volume=Decimal("1")))
    return tuple(candles)


def clean_uptrend():
    """Advance in ~1.5% legs separated by ~0.9% pullbacks.

    A 0.5% threshold should see each pullback; a 1.5% threshold should ignore
    them and report an essentially trending market.
    """
    returns = []
    for _ in range(6):
        returns.extend([Decimal("0.0025")] * 6)
        returns.extend([Decimal("-0.0045")] * 2)
    return _candles(_walk(returns))


def clean_downtrend():
    """Mirror of clean_uptrend."""
    returns = []
    for _ in range(6):
        returns.extend([Decimal("-0.0025")] * 6)
        returns.extend([Decimal("0.0045")] * 2)
    return _candles(_walk(returns))


def v_reversal():
    """One decisive low after a ~7% decline. Every detector should find it."""
    returns = [Decimal("-0.0037")] * 20 + [Decimal("0.0039")] * 20
    return _candles(_walk(returns))


def choppy_range():
    """Directionless oscillation of ~0.9% peak-to-trough, six-bar period.

    Measures over-detection. A 0.5% threshold is inside the noise band; a 1.5%
    threshold is outside it.
    """
    returns = []
    for _ in range(8):
        returns.extend([Decimal("0.0030")] * 3)
        returns.extend([Decimal("-0.0030")] * 3)
    return _candles(_walk(returns))


def false_breakout():
    """Range, then one candle sweeping ~1.4% above the range high and closing back in.

    The sweep print exists only as a wick, so close-only detectors cannot see
    it at all. This is the wick-versus-close discriminator.
    """
    returns = []
    for _ in range(5):
        returns.extend([Decimal("0.0035")] * 2)
        returns.extend([Decimal("-0.0035")] * 2)
    returns.append(Decimal("0.0010"))         # sweep candle, closes back inside
    for _ in range(4):
        returns.extend([Decimal("-0.0035")] * 2)
        returns.extend([Decimal("0.0035")] * 2)
    returns.extend([Decimal("-0.0040")] * 8)  # genuine breakdown afterwards
    closes = _walk(returns)
    sweep = len([r for r in returns[:21]]) - 1
    peak = max(closes[:sweep + 1]) * Decimal("1.014")
    return _candles(closes, overrides={sweep: (peak, None)})


def volatility_reversal():
    """Quiet regime, then a volatility expansion and a sharp reversal.

    A fixed percentage threshold cannot suit both regimes; an ATR-scaled
    threshold is the reason this scenario exists.
    """
    returns = []
    for step in range(24):
        returns.append(Decimal("0.0008") if step % 2 == 0 else Decimal("-0.0005"))
    returns.extend([Decimal("0.0090")] * 12)
    returns.extend([Decimal("-0.0110")] * 12)
    return _candles(_walk(returns))


BENCHMARKS = {
    "clean_uptrend": clean_uptrend,
    "clean_downtrend": clean_downtrend,
    "v_reversal": v_reversal,
    "choppy_range": choppy_range,
    "false_breakout": false_breakout,
    "volatility_reversal": volatility_reversal,
}


def all_benchmarks():
    """Materialise every scenario deterministically."""
    return {name: build() for name, build in BENCHMARKS.items()}


def load_candle_json(path, symbol=SYMBOL, timeframe=TIMEFRAME):
    """Optional: read saved real candles from JSON/JSONL for offline research.

    Accepts the repository's replay row shape. Never used by the test suite; it
    exists so a saved BTC-USDT series can be replayed without network access.
    """
    import json
    from pathlib import Path

    text = Path(path).read_text(encoding="utf-8-sig")
    if text.lstrip().startswith("["):
        rows = json.loads(text, parse_float=Decimal)
    else:
        rows = [json.loads(line, parse_float=Decimal)
                for line in text.splitlines() if line.strip()]
    candles = []
    for row in rows:
        row = dict(row)
        row.setdefault("symbol", symbol)
        row.setdefault("timeframe", timeframe)
        row.setdefault("closed", True)
        candles.append(Candle.from_dict(row))
    return tuple(candles)
