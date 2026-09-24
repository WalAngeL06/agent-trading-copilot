"""[U-DD-DEVIATION-001] Profile and command-line knobs for the DD deviation models."""
import argparse
import unittest
from decimal import Decimal as D

from agent_trading.strategy_v1 import StrategyProfile
from agent_trading.strategy_v1.config import BREAK_EVEN_TRIGGERS, ENTRY_MODELS

OLD_GATE = dict(direction='LONG_ONLY', direction_gate='BIAS_LONG_PERMISSION')


class DdProfileTests(unittest.TestCase):
    def test_the_entry_models_are_named_and_kept_as_a_tuple(self):
        self.assertEqual(ENTRY_MODELS, ('CHOCH_FVG', 'HTF_FVG_REVERSAL'))
        profile = StrategyProfile(entry_models=['HTF_FVG_REVERSAL', 'CHOCH_FVG'])
        self.assertEqual(profile.entry_models, ('HTF_FVG_REVERSAL', 'CHOCH_FVG'))

    def test_unknown_duplicate_or_empty_entry_models_are_rejected(self):
        for models in ((), ('MODEL_3',), ('CHOCH_FVG', 'CHOCH_FVG')):
            with self.subTest(models=models), self.assertRaises(ValueError):
                StrategyProfile(entry_models=models)

    def test_model_two_follows_the_gate_unless_set(self):
        self.assertTrue(StrategyProfile(model2_requires_htf_fvg=None)
                        .effective_model2_requires_htf_fvg)
        self.assertFalse(StrategyProfile(model2_requires_htf_fvg=None, **OLD_GATE)
                         .effective_model2_requires_htf_fvg)
        self.assertFalse(StrategyProfile(model2_requires_htf_fvg=False)
                         .effective_model2_requires_htf_fvg)

    def test_the_old_gate_cannot_require_an_htf_fvg(self):
        with self.assertRaises(ValueError):
            StrategyProfile(model2_requires_htf_fvg=True, **OLD_GATE)
        with self.assertRaises(ValueError):
            StrategyProfile(model2_requires_htf_fvg=1)

    def test_the_eq_scale_out_is_a_share_of_the_original_quantity(self):
        profile = StrategyProfile(eq_scale_out_fraction=D('0.30'), runner_fraction=D('0.20'))
        self.assertEqual(profile.eq_scale_out_fraction, D('0.30'))
        for bad in (D('0'), D('1.5'), D('NaN'), 0.3):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                StrategyProfile(eq_scale_out_fraction=bad)

    def test_the_eq_slice_counts_against_the_non_runner_allocation(self):
        with self.assertRaises(ValueError):
            StrategyProfile(eq_scale_out_fraction=D('0.30'), runner_fraction=D('0.20'),
                            partial_take_profits=({'r_multiple': '1', 'close_fraction': '0.60'},))

    def test_the_break_even_trigger_is_validated(self):
        self.assertEqual(BREAK_EVEN_TRIGGERS, ('RANGE_EQ', 'R_MULTIPLE'))
        with self.assertRaises(ValueError):
            StrategyProfile(break_even_trigger='TWO_R')

    def test_the_run_config_shows_the_dd_knobs(self):
        data = StrategyProfile(entry_models=ENTRY_MODELS, model2_requires_htf_fvg=None,
                               eq_scale_out_fraction=D('0.30'), runner_fraction=D('0.20'),
                               break_even_trigger='RANGE_EQ').as_dict()
        self.assertEqual(data['entry_models'], ['CHOCH_FVG', 'HTF_FVG_REVERSAL'])
        self.assertIs(data['model2_requires_htf_fvg'], True)
        self.assertEqual(data['eq_scale_out_fraction'], '0.30')
        self.assertEqual(data['break_even_trigger'], 'RANGE_EQ')


class DdDefaultTests(unittest.TestCase):
    def test_the_dd_models_are_the_default(self):
        profile = StrategyProfile()
        self.assertEqual(profile.entry_models, ENTRY_MODELS)
        self.assertIsNone(profile.model2_requires_htf_fvg)
        self.assertTrue(profile.effective_model2_requires_htf_fvg)
        self.assertEqual(profile.eq_scale_out_fraction, D('0.30'))
        self.assertEqual(profile.break_even_trigger, 'RANGE_EQ')
        self.assertFalse(profile.secondary_fvg_support_enabled)
        self.assertEqual(profile.runner_fraction, D('0.20'))


class DdFlagTests(unittest.TestCase):
    def profile(self, *flags):
        from agent_trading.backtest.cli import add_profile_arguments, profile_from_args
        parser = argparse.ArgumentParser()
        add_profile_arguments(parser)
        return profile_from_args(parser.parse_args(list(flags)))

    def test_every_dd_knob_has_a_flag(self):
        profile = self.profile('--entry-models', 'CHOCH_FVG', '--model2-htf-fvg', 'auto',
                               '--eq-scale-out', '0.25', '--break-even-trigger', 'RANGE_EQ',
                               '--runner-fraction', '0.20', '--no-secondary-fvg')
        self.assertEqual(profile.entry_models, ('CHOCH_FVG',))
        self.assertIsNone(profile.model2_requires_htf_fvg)
        self.assertEqual(profile.eq_scale_out_fraction, D('0.25'))
        self.assertEqual(profile.break_even_trigger, 'RANGE_EQ')
        self.assertFalse(profile.secondary_fvg_support_enabled)

    def test_the_legacy_behaviour_is_selectable(self):
        profile = self.profile('--entry-models', 'HTF_FVG_REVERSAL', '--model2-htf-fvg', 'false',
                               '--eq-scale-out', 'none', '--break-even-trigger', 'R_MULTIPLE',
                               '--secondary-fvg')
        self.assertIsNone(profile.eq_scale_out_fraction)
        self.assertIs(profile.model2_requires_htf_fvg, False)
        self.assertTrue(profile.secondary_fvg_support_enabled)


if __name__ == '__main__':
    unittest.main()
