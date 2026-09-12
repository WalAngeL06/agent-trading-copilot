"""Bootstrap and optional polling of real closed candles, with shadow intents."""

from datetime import datetime, timezone
import time

from .engine import ReplayEngine
from .okx import OkxMarketAdapter, normalize_candles


def _fetch(engine: ReplayEngine, adapter: OkxMarketAdapter, as_of: datetime):
    candles = []
    for tf in engine.config.timeframes:
        rows = adapter.candles(engine.config.symbol, tf, engine.config.bootstrap_limit + 1)
        history = normalize_candles(rows, engine.config.symbol, tf, as_of)
        if not history:
            raise ValueError("OKX has no closed candles for a required timeframe")
        candles.extend(history[-engine.config.bootstrap_limit:])
    return candles


def run_shadow(engine: ReplayEngine, adapter: OkxMarketAdapter,
               clock=lambda: datetime.now(timezone.utc), sleep=time.sleep) -> dict:
    if engine.config.mode != "shadow":
        raise ValueError("real market polling requires shadow mode")
    try:
        return _run(engine, adapter, clock, sleep)
    except Exception as exc:
        engine.fail(exc, stage="market_data", symbol=engine.config.symbol)
        raise


def _run(engine, adapter, clock, sleep):
    as_of = clock()
    engine.bootstrap(_fetch(engine, adapter, as_of), as_of)
    result = engine.evaluate_snapshot(engine.config.symbol, as_of)
    cycles = 1
    while engine.config.shadow_cycles == 0 or cycles < engine.config.shadow_cycles:
        sleep(engine.config.poll_interval_seconds)
        as_of = clock()
        candles = _fetch(engine, adapter, as_of)
        engine.update_context(candles, as_of)
        result = engine.evaluate_snapshot(engine.config.symbol, as_of)
        cycles += 1
    return result
