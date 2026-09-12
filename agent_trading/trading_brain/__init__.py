"""Opt-in causal PAPER strategy; no exchange client or production pipeline change."""
from .models import (BrainConfig, SwingHigh, SwingLow, ValidHigh, ValidLow, RangeState,
                     ManipulationEvent, FVG, TradeCandidate, PaperTrade, BrainEvent)
from .structure import StructureEngine
from .range import RangeEngine
from .manipulation import ManipulationEngine
from .gaps import GapEngine
from .paper import RiskPolicy, PaperBroker
from .runtime import TradingBrain, replay
