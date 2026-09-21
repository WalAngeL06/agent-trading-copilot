"""OKX spot listing rows reduced to typed facts [U-MULTI-PAIR-001].

`market_get_instruments` and `market_get_tickers` return the raw OKX rows. Only
what a universe selection needs survives: the pair, its base and quote, its
state, when it was listed, and 24h activity in the quote currency.
"""
from datetime import datetime, timezone
from decimal import Decimal as D
import unittest

from agent_trading.market_observations import (SpotInstrument, SpotVolume,
                                               normalize_spot_instruments,
                                               normalize_spot_tickers)


def instrument(inst_id="ETH-USDT", base="ETH", quote="USDT", state="live",
               list_time="1548133413000", inst_type="SPOT"):
    return {"instType": inst_type, "instId": inst_id, "baseCcy": base, "quoteCcy": quote,
            "state": state, "listTime": list_time, "tickSz": "0.01", "lotSz": "0.000001"}


def ticker(inst_id="ETH-USDT", last="2500.12345678901234", vol_ccy="123456789.123456789",
           inst_type="SPOT"):
    return {"instType": inst_type, "instId": inst_id, "last": last, "vol24h": "5000",
            "volCcy24h": vol_ccy, "ts": "1767262500000"}


class SpotInstrumentTests(unittest.TestCase):
    def test_a_spot_listing_keeps_pair_base_quote_state_and_listing_time(self):
        records = normalize_spot_instruments([instrument(), instrument("BTC-USDT", "BTC")])
        self.assertEqual(records[0], SpotInstrument(
            "ETH-USDT", "ETH", "USDT", "live",
            datetime(2019, 1, 22, 5, 3, 33, tzinfo=timezone.utc)))
        self.assertEqual([r.symbol for r in records], ["ETH-USDT", "BTC-USDT"])

    def test_an_empty_listing_time_is_unknown_not_invented(self):
        record, = normalize_spot_instruments([instrument(list_time="")])
        self.assertIsNone(record.list_time)

    def test_malformed_listings_are_rejected(self):
        cases = {'not spot': [instrument(inst_type="SWAP")],
                 'bad id': [instrument(inst_id="--help", base="--help")],
                 'base/quote mismatch': [instrument(base="BTC")],
                 'duplicate': [instrument(), instrument()],
                 'empty listing': [],
                 'missing field': [{"instType": "SPOT", "instId": "ETH-USDT"}]}
        for label, rows in cases.items():
            with self.subTest(label), self.assertRaises((ValueError, KeyError)):
                normalize_spot_instruments(rows)


class SpotVolumeTests(unittest.TestCase):
    def test_volume_and_last_price_stay_exact_decimals(self):
        record, = normalize_spot_tickers([ticker()])
        self.assertEqual(record, SpotVolume("ETH-USDT", D("2500.12345678901234"),
                                            D("123456789.123456789")))

    def test_a_missing_last_price_is_unknown(self):
        record, = normalize_spot_tickers([ticker(last="")])
        self.assertIsNone(record.last)

    def test_the_ticker_time_is_not_a_reason_to_reject_the_listing(self):
        row = ticker()
        row["ts"] = "9999999999999"                     # a fast clock on the venue side
        self.assertEqual(len(normalize_spot_tickers([row])), 1)

    def test_malformed_volumes_are_rejected(self):
        cases = {'float': [ticker(vol_ccy=1.5)], 'negative': [ticker(vol_ccy="-1")],
                 'nan': [ticker(vol_ccy="NaN")], 'not spot': [ticker(inst_type="SWAP")],
                 'duplicate': [ticker(), ticker()], 'empty listing': []}
        for label, rows in cases.items():
            with self.subTest(label), self.assertRaises((ValueError, ArithmeticError)):
                normalize_spot_tickers(rows)


if __name__ == '__main__':
    unittest.main()
