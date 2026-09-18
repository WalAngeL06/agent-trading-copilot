"""Local user declarations; never an exchange setting or verification."""
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Literal

from pydantic import BaseModel, ConfigDict


class AccountPreferences(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    lira_auto_earn: Literal['ENABLED', 'DISABLED'] | None = None


class AccountPreferenceStore:
    def __init__(self, path):
        self.path = Path(path)
        try:
            self.current = AccountPreferences.model_validate_json(self.path.read_text(encoding='utf-8'))
        except FileNotFoundError:
            self.current = AccountPreferences()
        except (OSError, ValueError):
            raise ValueError('Local account preferences are unreadable or invalid.') from None

    def save(self, preferences):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with NamedTemporaryFile(mode='w', encoding='utf-8', dir=self.path.parent,
                                    prefix='.preferences-', suffix='.tmp', delete=False) as handle:
                temporary = Path(handle.name)
                handle.write(preferences.model_dump_json(indent=2) + '\n')
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        self.current = preferences
        return preferences

    def lira_status(self):
        return {'status': 'UNKNOWN', 'source': None, 'verified': False,
                'api_verification': 'NOT_EXPOSED',
                'user_preference': self.current.lira_auto_earn}
