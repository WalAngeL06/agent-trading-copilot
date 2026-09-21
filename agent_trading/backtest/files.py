"""Atomic artifact writes: a reader sees the old file or the new one, never half."""
import os
from pathlib import Path


def write_atomic(path, text):
    """Write LF text next to `path` as `<name>.tmp`, then move it into place.

    The `.tmp` suffix is never picked up by the dataset loader, and the same
    bytes come out on Windows and on the VPS.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    try:
        with temporary.open('w', encoding='utf-8', newline='\n') as handle:
            handle.write(text)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()
    return path
