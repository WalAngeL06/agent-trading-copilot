"""Run from the project directory: py -m agent_trading --config config.example.json."""

import argparse
from pathlib import Path
import sys

from .config import Config
from .data import read_candles
from .engine import ReplayEngine
from .journal import JsonlJournal
from .okx import OkxMarketAdapter
from .shadow import run_shadow


def main() -> int:
    parser = argparse.ArgumentParser(description="Trading foundation: replay or OKX shadow, no orders")
    parser.add_argument("--config", type=Path, default=Path("config.example.json"))
    parser.add_argument("--output", type=Path, help="New output file (must not already exist)")
    args = parser.parse_args()
    try:
        config_path = args.config.resolve()
        config = Config.load(config_path)
        source = config_path.parent / config.data_path
        destination = args.output or config_path.parent / config.output_path
        if config.mode == "replay" and not source.is_file():
            raise ValueError(f"input file does not exist: {source}")
        with JsonlJournal(destination) as journal:
            engine = ReplayEngine(config, journal=journal)
            if config.mode == "shadow":
                try:
                    adapter = OkxMarketAdapter(config.okx_site, config.cli_timeout_seconds,
                                               config.node_path, config.okx_cli_path)
                    result = run_shadow(engine, adapter)
                except (ValueError, OSError, RuntimeError) as exc:
                    engine.fail(exc, stage="market_data")
                    raise
                print(f"Shadow complete: {config.symbol}, {result['market_state']['counts']}, "
                      f"{result['decision']['action']}, {result['execution']['action']}, "
                      f"0 orders. Log: {destination}")
                return 0
            count = 0
            iterator = iter(read_candles(source))
            while True:
                try:
                    candle = next(iterator)
                except StopIteration:
                    break
                except (ValueError, OSError) as exc:
                    journal.write({"schema_version": 1, "event": "ERROR",
                                   "stage": "data", "error_type": type(exc).__name__,
                                   "message": str(exc)})
                    raise
                engine.process(candle)
                count += 1
            if count == 0:
                journal.write({"schema_version": 1, "event": "ERROR",
                               "stage": "data", "message": "input contains no candles"})
                raise ValueError("input contains no candles")
        print(f"Replay complete: {count} candles, {count} NO_TRADE, 0 orders. Log: {destination}")
        return 0
    except (ValueError, OSError, RuntimeError) as exc:
        print(f"Run failed: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Run stopped by user; 0 orders.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
