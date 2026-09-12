"""Explicit owner-local private read command. Prints private snapshots, never credentials."""

import argparse
import asyncio
import json
from pathlib import Path

from .okx_private import failed_read
from .okx_private_config import load_private_config
from .okx_private_runtime import read_private_snapshots


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read OKX TR account and flexible Earn; no exchange writes")
    parser.add_argument("--env-file", default=str(Path.cwd() / ".env"))
    parser.add_argument("--node-path")
    parser.add_argument("--server-path")
    parser.add_argument("--timeout", type=float, default=30)
    args = parser.parse_args(argv)
    try:
        result = asyncio.run(read_private_snapshots(load_private_config(args.env_file),
            node_path=args.node_path, server_path=args.server_path, timeout=args.timeout))
    except Exception as exc:
        result = failed_read(exc)
    print(json.dumps(result.to_dict(), separators=(",", ":")))
    return 0 if result.status == "CONNECTED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
