"""One JSON event per line, one file per run; never overwrite past evidence."""

import json
from pathlib import Path

from .models import to_jsonable


class JsonlJournal:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._file = path.open("x", encoding="utf-8")

    def write(self, event: dict) -> None:
        self._file.write(json.dumps(to_jsonable(event), ensure_ascii=False,
                                    sort_keys=True, allow_nan=False) + "\n")
        self._file.flush()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self._file.close()
