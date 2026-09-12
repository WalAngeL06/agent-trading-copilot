"""Strict frontend wire schemas. Financial values are strings, never floats."""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .models import utc_time


FinancialString = Annotated[str, Field(pattern=r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$")]
UtcString = Annotated[str, Field(pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$")]
BaselineTimeframeName = Literal["4H", "1H", "15m"]
TimeframeName = Annotated[str, Field(
    pattern=r"^[1-9][0-9]{0,2}(?:m|H|D|W|M)(?:utc)?$", max_length=16)]


class WireModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class AnalysisRequest(WireModel):
    symbol: str = Field(min_length=1, max_length=40)


class Candle(WireModel):
    symbol: str
    timeframe: BaselineTimeframeName
    close_time: UtcString
    open: FinancialString
    high: FinancialString
    low: FinancialString
    close: FinancialString
    volume: FinancialString
    closed: Literal[True]


class CandleV2(Candle):
    timeframe: TimeframeName


class Ticker(WireModel):
    symbol: str
    last: FinancialString
    bid: FinancialString
    ask: FinancialString
    exchange_time: UtcString
    observed_at: UtcString


class BookLevel(WireModel):
    price: FinancialString
    quantity: FinancialString


class OrderbookSummary(WireModel):
    best_bid: BookLevel
    best_ask: BookLevel
    bid_levels: int
    ask_levels: int
    exchange_time: UtcString
    observed_at: UtcString


class Spread(WireModel):
    value: FinancialString
    source: Literal["ORDERBOOK"]
    exchange_time: UtcString
    observed_at: UtcString


class Market(WireModel):
    ticker: Ticker | None
    spread: Spread | None
    orderbook_summary: OrderbookSummary | None


class Freshness(WireModel):
    status: Literal["FRESH", "STALE", "UNKNOWN"]
    checked_at: UtcString | None
    expected_close_time: UtcString
    required_close_time: UtcString
    publication_grace_seconds: int


class Timeframe(WireModel):
    latest_closed_candle: Candle | None
    candle_count: int
    latest_close_time: UtcString | None
    observed_at: UtcString | None
    data_status: Literal["NOT_EVALUATED", "AVAILABLE", "MISSING", "FAILED"]
    freshness: Freshness


class TimeframeV2(Timeframe):
    latest_closed_candle: CandleV2 | None


class Module(WireModel):
    status: Literal["AVAILABLE", "NOT_IMPLEMENTED", "NOT_EVALUATED", "FAILED"]
    reason_codes: list[str]


class Modules(WireModel):
    market_structure: Module
    range: Module
    deviation: Module
    premium_discount: Module
    acceptance: Module
    risk: Module


class Decision(WireModel):
    action: Literal["NO_TRADE"] | None
    reason_codes: list[str]
    order_sent: Literal[False]


class Explanation(WireModel):
    deterministic_summary: str


class Evidence(WireModel):
    evidence_id: str
    kind: Literal["TICKER", "ORDERBOOK", "CLOSED_CANDLES"]
    reference: str
    source_id: str
    decision_input: bool
    close_time: UtcString | None
    observed_at: UtcString


class Filtering(WireModel):
    received_rows: int
    open_rows: int
    future_rows: int
    duplicate_rows: int
    retained_rows: int


class Provenance(WireModel):
    tool: str
    symbol: str | None
    timeframe: str | None
    request_observed_at: UtcString
    response_observed_at: UtcString
    latency_ms: int
    success: bool
    error_code: str | None
    filtering: Filtering | None
    rpc_error_code: int | None
    transport: Literal["MCP"]
    provider: Literal["OKX Agent Trade Kit"]
    site: Literal["tr"]


class Source(WireModel):
    source_id: str
    provenance: Provenance


class ProductError(WireModel):
    code: str
    message: str
    stage: str
    timeframe: BaselineTimeframeName | None


class ProductErrorV2(ProductError):
    timeframe: TimeframeName | None


class TimelineEvent(WireModel):
    schema_version: Literal["analysis-events-v0.1"]
    analysis_id: str
    sequence: int
    type: Literal["REQUEST_RECEIVED", "MCP_CONNECTED", "TICKER_FETCHED", "CANDLES_FETCHED",
                  "ORDERBOOK_FETCHED", "SNAPSHOT_BUILT", "DECISION_EVALUATED",
                  "ANALYSIS_COMPLETED", "ANALYSIS_FAILED"]
    at: UtcString
    data: dict[str, Any]


class AnalysisReport(WireModel):
    schema_version: Literal["analysis-report-v0.1"]
    analysis_id: str
    symbol: str
    site: Literal["tr"]
    status: Literal["RUNNING", "COMPLETED", "FAILED"]
    requested_at: UtcString
    started_at: UtcString
    completed_at: UtcString | None
    decision_as_of: UtcString | None
    market: Market
    timeframes: dict[BaselineTimeframeName, Timeframe]
    modules: Modules
    decision: Decision
    explanation: Explanation
    evidence: list[Evidence]
    sources: list[Source]
    errors: list[ProductError]
    timeline: list[TimelineEvent]


class StrategyContext(WireModel):
    profile_id: Annotated[str, Field(min_length=1, max_length=128)] | None
    required_timeframes: list[TimeframeName] = Field(min_length=1, max_length=16)


class AnalysisReportV2(AnalysisReport):
    schema_version: Literal["analysis-report-v0.2"]
    strategy_context: StrategyContext
    timeframes: dict[TimeframeName, TimeframeV2] = Field(min_length=1, max_length=16)
    errors: list[ProductErrorV2]

    @model_validator(mode="after")
    def consistent_timeframes_and_cutoff(self):
        required = self.strategy_context.required_timeframes
        if len(set(required)) != len(required) or set(required) != set(self.timeframes):
            raise ValueError("Timeframe context and entries must match uniquely")
        cutoff = utc_time(self.decision_as_of) if self.decision_as_of is not None else None
        for tf, frame in self.timeframes.items():
            candle = frame.latest_closed_candle
            if candle is not None:
                if (candle.timeframe != tf or candle.symbol != self.symbol or
                        candle.close_time != frame.latest_close_time):
                    raise ValueError("Candle identity and timeframe metadata must match")
                if cutoff is not None and utc_time(candle.close_time) > cutoff:
                    raise ValueError("Closed inputs cannot exceed the knowledge cutoff")
        for evidence in self.evidence:
            if evidence.decision_input and (
                    cutoff is None or evidence.close_time is None or
                    utc_time(evidence.close_time) > cutoff):
                raise ValueError("Decision evidence must be available at the knowledge cutoff")
        return self


AnyAnalysisReport = Annotated[
    AnalysisReport | AnalysisReportV2, Field(discriminator="schema_version")]


class HistoryPage(WireModel):
    items: list[AnyAnalysisReport]
    limit: int
    offset: int
    total: int
