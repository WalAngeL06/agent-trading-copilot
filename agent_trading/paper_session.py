"""Durable PAPER session: the running strategy survives backend restarts.

Only this application writes the file; pickle must never load untrusted
input. A session resumes only for the same symbol and strategy profile, and
anything unreadable or incompatible starts a fresh session instead.
"""

import logging
import os
from pathlib import Path
import pickle
from tempfile import NamedTemporaryFile


SESSION_FORMAT = 1


class PaperSessionStore:
    def __init__(self, path):
        self.path = Path(path)

    def save(self, symbol, profile, brain, stream_as_of):
        payload = {"format": SESSION_FORMAT, "symbol": symbol, "profile": profile,
                   "brain": brain, "stream_as_of": dict(stream_as_of)}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with NamedTemporaryFile(mode="wb", dir=self.path.parent, prefix=".paper-session-",
                                    suffix=".tmp", delete=False) as handle:
                temporary = Path(handle.name)
                pickle.dump(payload, handle, protocol=pickle.HIGHEST_PROTOCOL)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def load(self, symbol, profile):
        """(brain, stream_as_of) for this symbol and profile, or None."""
        try:
            with self.path.open("rb") as handle:
                payload = pickle.load(handle)
        except FileNotFoundError:
            return None
        except Exception:
            logging.warning("Saved PAPER session is unreadable; a fresh session will start")
            return None
        if (not isinstance(payload, dict) or payload.get("format") != SESSION_FORMAT
                or payload.get("symbol") != symbol or payload.get("profile") != profile):
            return None
        return payload["brain"], dict(payload["stream_as_of"])

    def clear(self):
        self.path.unlink(missing_ok=True)
