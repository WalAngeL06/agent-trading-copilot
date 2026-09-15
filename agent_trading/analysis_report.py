"""Product wire report and deterministic wording; no strategy or HTTP policy."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal, localcontext

from .analysis_config import BASELINE_TIMEFRAMES
from .market import bar_duration
from .market_observations import observation_time
from .models import to_jsonable


REPORT_VERSION = "analysis-report-v0.2"
EVENT_VERSION = "analysis-events-v0.1"


def interval_floor(stamp: datetime, timeframe: str) -> datetime:
    stamp = observation_time(stamp)
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    duration = bar_duration(timeframe)
    return epoch + ((stamp - epoch) // duration) * duration


def series_freshness(latest, timeframe, cutoff, grace):
    expected = interval_floor(cutoff, timeframe)
    required = interval_floor(cutoff - timedelta(seconds=grace), timeframe)
    return to_jsonable({
        "status": "UNKNOWN" if latest is None else ("FRESH" if latest >= required else "STALE"),
        "checked_at": cutoff, "expected_close_time": expected,
        "required_close_time": required, "publication_grace_seconds": grace,
    })


def exact_spread(bid: Decimal, ask: Decimal) -> Decimal:
    # Enough significant places for exact subtraction, even for long JSON tokens.
    precision = max(bid.adjusted(), ask.adjusted()) - min(
        bid.as_tuple().exponent, ask.as_tuple().exponent) + 2
    with localcontext() as context:
        context.prec = max(28, precision)
        return ask - bid


def new_report(analysis_id: str, symbol: str, now: datetime, grace: int,
               required_timeframes: tuple[str, ...] = BASELINE_TIMEFRAMES) -> dict:
    now = observation_time(now)
    timeframes = {}
    for tf in required_timeframes:
        freshness = series_freshness(None, tf, now, grace)
        freshness["checked_at"] = None
        timeframes[tf] = {
            "latest_closed_candle": None, "candle_count": 0, "latest_close_time": None,
            "observed_at": None, "data_status": "NOT_EVALUATED", "freshness": freshness,
        }
    modules = {name: {"status": "NOT_IMPLEMENTED",
                      "reason_codes": ["ALGORITHMIC_DEFINITION_PENDING"]}
               for name in ("market_structure", "range", "deviation", "premium_discount")}
    modules.update({name: {"status": "NOT_EVALUATED", "reason_codes": ["ANALYSIS_RUNNING"]}
                    for name in ("acceptance", "risk")})
    return to_jsonable({
        "schema_version": REPORT_VERSION, "analysis_id": analysis_id,
        "symbol": symbol, "site": "tr", "status": "RUNNING",
        "requested_at": now, "started_at": now, "completed_at": None,
        "decision_as_of": None, "market": {"ticker": None, "spread": None, "orderbook_summary": None},
        "strategy_context": {"profile_id": None, "required_timeframes": list(required_timeframes)},
        "timeframes": timeframes, "modules": modules,
        "decision": {"action": None, "reason_codes": [], "order_sent": False},
        "explanation": {"deterministic_summary": "Analysis is running; no decision has been evaluated."},
        "evidence": [], "sources": [], "errors": [], "timeline": [],
    })


def deterministic_summary(report: dict) -> str:
    if report["status"] == "FAILED":
        errors = report["errors"]
        if not errors:
            return "Analysis failed; no trading decision was produced."
        error = errors[0]
        tf = error.get("timeframe")
        if error["code"] == "STALE_TIMEFRAME":
            return f"Required {tf} closed-candle data is stale. No trading decision was produced."
        if error["code"] == "MISSING_TIMEFRAME":
            return f"Required {tf} closed-candle data is missing. No trading decision was produced."
        return f"Analysis failed: {error['message']} No trading decision was produced."
    if report["status"] == "COMPLETED":
        if (report["decision"]["action"] == "NO_TRADE" and
                "STRATEGY_NOT_CONFIGURED" in report["decision"]["reason_codes"]):
            return ("No trading strategy is currently configured. Market data was retrieved "
                    "successfully and the deterministic decision pipeline returned NO_TRADE.")
        return "The deterministic analysis completed. Review its structured decision and limitations."
    return "Analysis is running; no decision has been evaluated."
