from decimal import Decimal
from pathlib import Path
import tempfile
import unittest

from agent_trading.data import read_candles


class PrecisionTests(unittest.TestCase):
    def test_json_numeric_tokens_preserve_price_and_volume(self):
        text = ('{"symbol":"TEST-USDT","timeframe":"1m",'
                '"close_time":"2026-01-01T00:01:00Z",'
                '"open":100,"high":102,"low":99,'
                '"close":101.1234567890123456789,'
                '"volume":0.1234567890123456789,"closed":true}')
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "candles.jsonl"
            path.write_text(text, encoding="utf-8")
            result = list(read_candles(path))[0]
        self.assertEqual(result.close, Decimal("101.1234567890123456789"))
        self.assertEqual(result.volume, Decimal("0.1234567890123456789"))
