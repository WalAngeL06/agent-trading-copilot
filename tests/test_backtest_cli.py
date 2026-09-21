"""Strategy and cost flags shared by the backtest and the sweep command lines."""
import argparse
from decimal import Decimal as D
import unittest

from agent_trading.backtest.__main__ import build_config, build_parser
from agent_trading.strategy_v1 import StrategyProfile


def backtest_profile(*flags):
    return build_config(build_parser().parse_args(['--data', '.', '--output', '.', *flags])).profile


class BacktestDefaultsTests(unittest.TestCase):
    def test_the_default_command_line_profile_is_the_default_strategy_profile(self):
        self.assertEqual(backtest_profile(), StrategyProfile())


class SharedFlagTests(unittest.TestCase):
    def parse(self, *flags):
        from agent_trading.backtest.cli import add_cost_arguments, add_profile_arguments
        parser = argparse.ArgumentParser()
        add_profile_arguments(parser)
        add_cost_arguments(parser)
        return parser.parse_args(list(flags))

    def test_any_command_line_builds_the_same_profile_from_the_same_flags(self):
        from agent_trading.backtest.cli import profile_from_args
        flags = ('--direction', 'SHORT_ONLY', '--partial-tp', '1.0:0.20', '--stop-buffer', '7',
                 '--boundary-proximity', '9', '--entry-level', 'FVG_LOW', '--no-trailing')
        self.assertEqual(profile_from_args(self.parse(*flags)), backtest_profile(*flags))

    def test_absolute_price_flags_default_to_the_btc_values_but_stay_detectable(self):
        from agent_trading.backtest.cli import explicit_absolute_flags, profile_from_args
        args = self.parse()
        self.assertIsNone(args.boundary_proximity)
        self.assertIsNone(args.stop_buffer)
        profile = profile_from_args(args)
        self.assertEqual((profile.boundary_proximity, profile.stop_buffer), (D('500'), D('100')))
        self.assertEqual(explicit_absolute_flags(args), ())

    def test_every_explicit_absolute_price_flag_is_reported(self):
        from agent_trading.backtest.cli import explicit_absolute_flags
        args = self.parse('--stop-buffer', '1', '--trailing-buffer', '2',
                          '--htf-zone-tolerance', '3', '--slippage', '0.5')
        self.assertEqual(explicit_absolute_flags(args),
                         ('--stop-buffer', '--trailing-buffer', '--htf-zone-tolerance',
                          '--slippage'))
        self.assertEqual(explicit_absolute_flags(self.parse('--slippage', '0')), ())

    def test_costs_come_from_the_shared_flags(self):
        from agent_trading.backtest.cli import costs_from_args
        costs = costs_from_args(self.parse('--fee-rate', '0.001'))
        self.assertEqual((costs.fee_rate, costs.slippage), (D('0.001'), D('0')))


if __name__ == '__main__':
    unittest.main()
