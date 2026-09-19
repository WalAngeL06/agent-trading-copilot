"""Transport-only product API. Run uvicorn agent_trading.api:create_app --factory."""

import asyncio
from contextlib import asynccontextmanager
import logging
from typing import Annotated
from uuid import UUID

from fastapi import FastAPI, Header, Query, Response
from fastapi.exceptions import RequestValidationError, ResponseValidationError
from fastapi.responses import JSONResponse, RedirectResponse

from .analysis_api_models import AnyAnalysisReport, AnalysisRequest, HistoryPage
from .analysis_config import AnalysisConfig
from .analysis_repository import RepositoryError
from .analysis_service import AnalysisService, ServiceError
from .bot_service import BotService
from .config import Config
from .strategy_settings import StrategySettings, StrategyStore
from .demo_config import DemoConfig
from .account_preferences import AccountPreferences, AccountPreferenceStore
from .okx_mcp_runtime import open_atk_mcp
from .access import AccessPolicy, is_public_deployment
from .paper_session import PaperSessionStore


_ERROR_MESSAGES = {
    "INVALID_REQUEST": "The request does not match the product API contract.",
    "INVALID_SYMBOL": "The requested instrument is not enabled.",
    "INVALID_IDEMPOTENCY_KEY": "The idempotency key does not match the product API contract.",
    "IDEMPOTENCY_CONFLICT": "The idempotency key belongs to another request.",
    "ANALYSIS_IN_PROGRESS": "The original analysis is still running.",
    "SERVICE_BUSY": "Another analysis is running. Retry later.",
    "ANALYSIS_NOT_FOUND": "The requested analysis was not found.",
    "PERSISTENCE_UNAVAILABLE": "Product history is unavailable.",
    "ANALYSIS_INTERNAL_ERROR": "The product response could not be completed.",
}


def _error(code, status, analysis_id=None):
    return JSONResponse(status_code=status, content={"error": {
        "code": code, "message": _ERROR_MESSAGES[code], "analysis_id": analysis_id}})


def _iso(value):
    return None if value is None else value.isoformat().replace("+00:00", "Z")


def create_app(config=None, service=None, bot_config=None, bot_service=None,
               mcp_factory=None, demo_config=None, strategy_path="config/strategy.json",
               preferences_path="config/preferences.json",
               session_path="runs/product/paper_session.pickle"):
    analysis_service = service or AnalysisService(config or AnalysisConfig.from_env())
    demo = demo_config or DemoConfig.from_env()
    access = AccessPolicy(demo.api_access_token, demo.telegram_bot_token,
                          demo.telegram_allowed_user_ids)
    if not access.enabled and is_public_deployment(demo.webapp_url, demo.allowed_origins):
        raise ValueError("A public WEBAPP_URL or ALLOWED_ORIGINS requires API_ACCESS_TOKEN or "
                         "TELEGRAM_ALLOWED_USER_IDS; refusing to expose an unprotected API.")
    if bot_service is None:
        runtime_config = analysis_service.config
        bot_service = BotService(
            bot_config or Config(symbol=runtime_config.allowed_symbols[0]),
            mcp_factory=mcp_factory or open_atk_mcp,
            node_path=runtime_config.node_path,
            server_path=runtime_config.server_path,
            mcp_timeout=runtime_config.mcp_timeout_seconds,
            telegram_token=demo.telegram_bot_token,
            webapp_url=demo.webapp_url,
            telegram_allowed_user_ids=demo.telegram_allowed_user_ids,
            session_store=PaperSessionStore(session_path),
        )

    strategy_store = StrategyStore(strategy_path)
    preferences_store = AccountPreferenceStore(preferences_path)
    bot_service.strategy_profile = strategy_store.current.to_profile()
    control_lock = asyncio.Lock()

    @asynccontextmanager
    async def lifespan(app):
        await analysis_service.startup()
        bot_service.startup()
        if bot_service.session_store and bot_service.session_store.was_active():
            bot_service.start()  # The owner left the agent running before this restart.
        try:
            yield
        finally:
            await bot_service.shutdown()

    app = FastAPI(title="Autonomous Trading Agent Analysis API", version="0.2", lifespan=lifespan)
    app.state.analysis_service = analysis_service
    app.state.bot_service = bot_service

    # Registered before CORS so CORS stays outermost: preflights pass and
    # rejections still carry CORS headers the browser can read.
    @app.middleware("http")
    async def require_access(request, call_next):
        if (request.method != "OPTIONS" and request.url.path.startswith("/api/")
                and not access.permits(request.headers.get("authorization"),
                                       request.headers.get("x-telegram-init-data"))):
            return JSONResponse(status_code=401, content={"error": {
                "code": "UNAUTHORIZED",
                "message": "An access key or an allowed Telegram account is required."}})
        return await call_next(request)

    from fastapi.middleware.cors import CORSMiddleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(demo.allowed_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, exc):
        # FastAPI's default detail includes input/body; discard all untrusted echo.
        if request.url.path == '/api/v1/strategy/config':
            return JSONResponse(status_code=422, content={'error': {
                'code': 'INVALID_STRATEGY',
                'message': ' '.join(dict.fromkeys(error['msg'] for error in exc.errors()))}})
        return _error("INVALID_REQUEST", 422)

    @app.exception_handler(ResponseValidationError)
    async def invalid_response(request, exc):
        return _error("ANALYSIS_INTERNAL_ERROR", 500)

    @app.exception_handler(ServiceError)
    async def service_error(request, exc):
        code = exc.code if exc.code in _ERROR_MESSAGES else "ANALYSIS_INTERNAL_ERROR"
        return _error(code, exc.status_code, exc.analysis_id)

    @app.exception_handler(RepositoryError)
    async def repository_error(request, exc):
        return _error("PERSISTENCE_UNAVAILABLE", 503, exc.analysis_id)

    @app.get("/health/live")
    async def live():
        return {"status": "ALIVE"}

    @app.get("/health/ready")
    async def ready(response: Response):
        result = await analysis_service.readiness()
        backend_ready = result["repository"] == "AVAILABLE"
        analysis_market = result["status"] == "READY"
        market_ready = analysis_market or bot_service.market_connected
        if bot_service.market_connected and not analysis_market:
            result["reason_codes"] = [code for code in result["reason_codes"] if code in {
                "PERSISTENCE_UNAVAILABLE", "LAST_ANALYSIS_FAILED",
            }]
        telegram = ("RUNNING" if bot_service.telegram and bot_service.telegram.running
                    else "DISABLED" if not bot_service.telegram else "ERROR")
        result.update(
            backend="READY" if backend_ready else "ERROR",
            market="CONNECTED" if market_ready else "NOT_VALIDATED",
            account=bot_service.private_state["account_auth"],
            telegram=telegram,
            execution_mode="PAPER",
            market_source=bot_service.market_source,
            last_market_update=_iso(bot_service.last_market_update),
            last_private_update=_iso(bot_service.last_private_update),
        )
        result["status"] = ("READY" if backend_ready and market_ready
                            and not result["reason_codes"] else "NOT_READY")

        response.status_code = 200 if result["status"] == "READY" else 503
        return result

    @app.post("/api/v1/analyses", response_model=AnyAnalysisReport, status_code=201)
    async def analyze(body: AnalysisRequest, response: Response,
                      idempotency_key: Annotated[str | None, Header()] = None):
        result = await analysis_service.analyze(body.symbol, idempotency_key=idempotency_key)
        response.status_code = 201 if result.created else 200
        return result.report

    @app.get("/api/v1/analyses", response_model=HistoryPage)
    async def history(limit: Annotated[int, Query(ge=1, le=50)] = 20,
                      offset: Annotated[int, Query(ge=0, le=10000)] = 0):
        return await asyncio.to_thread(analysis_service.repository.history, limit, offset)

    @app.get("/api/v1/analyses/{analysis_id}", response_model=AnyAnalysisReport)
    async def by_id(analysis_id: UUID):
        result = await asyncio.to_thread(analysis_service.repository.get, str(analysis_id))
        if result is None:
            raise ServiceError("ANALYSIS_NOT_FOUND", 404, str(analysis_id))
        return result

    @app.get("/api/v1/bot/status")
    async def bot_status():
        return {
            "bot_status": "running" if bot_service.is_running else "stopped",
            "strategy_state": bot_service.latest_state.get("decision", {}).get("action", "NO_TRADE") if bot_service.latest_state else "UNKNOWN",
            "execution_mode": "PAPER",
            "market_source": bot_service.market_source,
            "market_connected": bot_service.market_connected,
            "market_status": bot_service.market_status,
            "symbol": bot_service.config.symbol,
            "account_auth": bot_service.private_state["account_auth"],
            "auto_earn_status": bot_service.private_state["auto_earn_status"],
            "lira_auto_earn": preferences_store.lira_status(),
            "last_market_update": _iso(bot_service.last_market_update),
            "last_private_update": _iso(bot_service.last_private_update),
            "balance": bot_service.private_state["balance"],
        }

    @app.get("/api/v1/bot/market")
    async def bot_market():
        return bot_service.latest_state.get("market_state", {}) if bot_service.latest_state else {}

    @app.get("/api/v1/bot/activity")
    async def bot_activity():
        activity = bot_service.latest_state.get("execution", {}) if bot_service.latest_state else {}
        return {
            **activity,
            "events": bot_service.ui_events
        }

    @app.get("/api/v1/account/preferences", response_model=AccountPreferences)
    async def account_preferences():
        return preferences_store.current

    @app.put("/api/v1/account/preferences", response_model=AccountPreferences)
    async def save_account_preferences(body: AccountPreferences):
        try:
            return preferences_store.save(body)
        except OSError:
            return JSONResponse(status_code=503, content={"error": {
                "code": "PREFERENCES_WRITE_FAILED", "message": "Local preference could not be saved."}})

    @app.get("/api/v1/strategy/config", response_model=StrategySettings)
    async def strategy_config():
        return strategy_store.current

    @app.put("/api/v1/strategy/config", response_model=StrategySettings)
    async def save_strategy(body: StrategySettings):
        async with control_lock:
            if bot_service.is_running or (bot_service.task and not bot_service.task.done()):
                return JSONResponse(status_code=409, content={"error": {
                    "code": "AGENT_RUNNING",
                    "message": "Stop the agent before modifying the active strategy."}})
            try:
                saved = strategy_store.save(body)
            except OSError:
                return JSONResponse(status_code=503, content={"error": {
                    "code": "CONFIG_WRITE_FAILED", "message": "Strategy could not be saved on disk."}})
            bot_service.strategy_profile = saved.to_profile()
            bot_service.latest_state = {}
            bot_service._add_ui_event("Strategy", "Configuration saved")
            return saved

    @app.post("/api/v1/bot/start")
    async def bot_start():
        async with control_lock:
            started = bot_service.start()
            remember_running(True)
            return {"status": "started" if started else "already running"}

    @app.post("/api/v1/bot/stop")
    async def bot_stop():
        async with control_lock:
            task = bot_service.task
            stopped = bot_service.stop()
            remember_running(False)
            if task:
                await asyncio.gather(task, return_exceptions=True)
            return {"status": "stopped" if stopped else "not running"}

    def remember_running(active):
        if bot_service.session_store is None:
            return
        try:
            bot_service.session_store.mark_active(active)
        except OSError:
            logging.warning("Agent run state could not be saved")

    @app.get("/dashboard", include_in_schema=False)
    async def dashboard():
        # Preserve existing bookmarks and Telegram links with one canonical UI.
        return RedirectResponse(demo.webapp_url)

    return app
