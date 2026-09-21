"""Which OKX TR pairs a multi-pair sweep tests [U-MULTI-PAIR-001].

Guide section 3, step 1: illiquid instruments are filtered out and the model is
run on major, liquid pairs. The selection is pure and reproducible: the same
listing always yields the same ranked universe, and the written document says
exactly how it was chosen and what that choice cannot see.
"""
from datetime import datetime, timezone
from decimal import Decimal as D
import json
from pathlib import Path
import tempfile
import unittest

from agent_trading.backtest.universe import (STABLE_BASES, read_universe, select_universe,
                                             write_universe)
from agent_trading.market_observations import SpotInstrument, SpotVolume

AS_OF = datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc)
LISTED = datetime(2021, 1, 1, tzinfo=timezone.utc)


def listing(*rows):
    """rows: (symbol, state, quote volume or None for a missing ticker)."""
    instruments, volumes = [], []
    for symbol, state, volume in rows:
        base, quote = symbol.split('-')
        instruments.append(SpotInstrument(symbol, base, quote, state, LISTED))
        if volume is not None:
            volumes.append(SpotVolume(symbol, D('1.5'), D(volume)))
    return tuple(instruments), tuple(volumes)


def select(rows, **kwargs):
    settings = dict(quote='USDT', top=30, as_of=AS_OF)
    settings.update(kwargs)
    return select_universe(*listing(*rows), **settings)


class SelectionTests(unittest.TestCase):
    def test_only_live_pairs_in_the_quote_currency_are_candidates(self):
        universe = select([('ETH-USDT', 'live', '500'), ('BTC-USDT', 'live', '900'),
                           ('SOL-TRY', 'live', '10000'), ('XRP-USDT', 'suspend', '800')])
        self.assertEqual(universe.symbols, ('BTC-USDT', 'ETH-USDT'))
        self.assertEqual(universe.counts['instruments'], 4)
        self.assertEqual(universe.counts['live'], 3)
        self.assertEqual(universe.counts['quote_matches'], 2)

    def test_stablecoin_and_fiat_bases_are_excluded(self):
        universe = select([('USDC-USDT', 'live', '99999'), ('EUR-USDT', 'live', '5000'),
                           ('ETH-USDT', 'live', '500')])
        self.assertEqual(universe.symbols, ('ETH-USDT',))
        self.assertEqual(universe.counts['excluded'], 2)
        self.assertIn('USDC', STABLE_BASES)

    def test_a_custom_exclusion_list_replaces_the_default(self):
        universe = select([('USDC-USDT', 'live', '99999'), ('ETH-USDT', 'live', '500')],
                          exclude_bases=())
        self.assertEqual(universe.symbols, ('USDC-USDT', 'ETH-USDT'))

    def test_pairs_without_a_ticker_are_counted_not_guessed(self):
        universe = select([('ETH-USDT', 'live', '500'), ('NEW-USDT', 'live', None)])
        self.assertEqual(universe.symbols, ('ETH-USDT',))
        self.assertEqual(universe.counts['missing_ticker'], 1)

    def test_ranking_is_by_quote_volume_then_symbol(self):
        universe = select([('BBB-USDT', 'live', '100'), ('AAA-USDT', 'live', '100'),
                           ('CCC-USDT', 'live', '100.5')])
        self.assertEqual(universe.symbols, ('CCC-USDT', 'AAA-USDT', 'BBB-USDT'))
        self.assertEqual(universe.members[0].quote_volume_24h, D('100.5'))

    def test_top_caps_the_selection_and_fewer_candidates_are_fine(self):
        rows = [('AAA-USDT', 'live', '3'), ('BBB-USDT', 'live', '2'), ('CCC-USDT', 'live', '1')]
        self.assertEqual(select(rows, top=2).symbols, ('AAA-USDT', 'BBB-USDT'))
        wide = select(rows, top=10)
        self.assertEqual(len(wide.members), 3)
        self.assertEqual((wide.counts['candidates'], wide.counts['selected']), (3, 3))

    def test_invalid_arguments_are_rejected(self):
        rows = [('ETH-USDT', 'live', '500')]
        for kwargs in ({'top': 0}, {'top': True}, {'quote': 'usdt'},
                       {'as_of': datetime(2026, 9, 21)}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                select(rows, **kwargs)


class DocumentTests(unittest.TestCase):
    def setUp(self):
        self.universe = select([('ETH-USDT', 'live', '123456789.123456789'),
                                ('BTC-USDT', 'live', '987654321.5')], top=2)

    def test_the_document_states_how_it_was_chosen_and_its_bias(self):
        document = self.universe.as_dict()
        self.assertEqual((document['quote'], document['top'], document['site']),
                         ('USDT', 2, 'tr'))
        self.assertEqual(document['ranking'], 'quote_volume_24h')
        self.assertEqual(document['as_of'], '2026-09-21T12:00:00+00:00')
        for tag in ('SELECTED_BY_CURRENT_24H_VOLUME', 'SURVIVORSHIP_BIAS',
                    'DELISTED_PAIRS_ABSENT'):
            self.assertIn(tag, document['limitations'])
        self.assertEqual(document['members'][0]['quote_volume_24h'], '987654321.5')

    def test_the_written_document_round_trips_exactly(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'universe.json'
            write_universe(self.universe, path)
            raw = path.read_bytes()
            self.assertNotIn(b'\r\n', raw)
            self.assertTrue(raw.endswith(b'\n'))
            json.loads(raw)
            self.assertEqual(read_universe(path), self.universe)
            self.assertEqual([p.name for p in Path(directory).iterdir()], ['universe.json'])


if __name__ == '__main__':
    unittest.main()
