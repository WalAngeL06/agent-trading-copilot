"""Causal support adapter; conservative wick-touch freshness is [H]-RISK-ZONE-001."""
from dataclasses import replace
from .risk_models import SupportingZone
from .risk import positive_decimal
from ..models import Candle


class SupportingZoneBook:
    def __init__(self, symbol, timeframe):
        self.symbol, self.timeframe = symbol, timeframe
        self.zones = ()

    def process(self, candle):
        if (not isinstance(candle, Candle) or candle.closed is not True
                or candle.symbol != self.symbol or candle.timeframe != self.timeframe):
            raise ValueError('support requires a closed candle for this stream')
        self.zones = tuple(replace(zone, fresh=False) if zone.fresh
                           and candle.close_time > zone.validated_at
                           and ((candle.low <= zone.upper and candle.high >= zone.lower)
                                or (zone.direction == 'LONG' and candle.low < zone.invalidation_level)
                                or (zone.direction == 'SHORT' and candle.high > zone.invalidation_level)) else zone
                           for zone in self.zones)

    def publish(self, gap, zone_id):
        if (gap.direction not in ('LONG', 'SHORT')
                or not all(positive_decimal(x) for x in (gap.lower, gap.upper)) or gap.lower >= gap.upper):
            raise ValueError('support requires a validated directional gap')
        zone = SupportingZone(zone_id, gap.kind, gap.direction, gap.lower, gap.upper,
                              gap.lower if gap.direction == 'LONG' else gap.upper,
                              gap.observed_at, self.symbol, self.timeframe,
                              source_ids=gap.source_ids + ('[H]-RISK-ZONE-001',))
        self.zones += (zone,)
        return zone
