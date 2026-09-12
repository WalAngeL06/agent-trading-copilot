"""Run from the project directory: py -m agent_trading --config config.example.json."""

import argparse
from pathlib import Path
import sys

from .config import Config
from .data import read_candles
from .engine import ReplayEngine
from .journal import JsonlJournal


def main() -> int:
    parser = argparse.ArgumentParser(description="Trading foundation: offline replay, no orders")
    parser.add_argument("--config", type=Path, default=Path("config.example.json"))
    parser.add_argument("--output", type=Path, help="New output file (must not already exist)")
    args = parser.parse_args()
    try:
        config_path = args.config.resolve()
        config = Config.load(config_path)
        source = config_path.parent / config.data_path
        destination = args.output or config_path.parent / config.output_path
        if not source.is_file():
            raise ValueError(f"input file does not exist: {source}")
        with JsonlJournal(destination) as journal:
            engine = ReplayEngine(config, journal=journal)
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
        print(f"Replay failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
