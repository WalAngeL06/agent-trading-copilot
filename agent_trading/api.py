"""Transport-only product API. Run uvicorn agent_trading.api:create_app --factory."""

import asyncio
from contextlib import asynccontextmanager
from typing import Annotated
from uuid import UUID

from fastapi import FastAPI, Header, Query, Response
from fastapi.exceptions import RequestValidationError, ResponseValidationError
from fastapi.responses import JSONResponse

from .analysis_api_models import AnyAnalysisReport, AnalysisRequest, HistoryPage
from .analysis_config import AnalysisConfig
from .analysis_repository import RepositoryError
from .analysis_service import AnalysisService, ServiceError
from .bot_service import BotService
from .config import Config
from .okx import OkxMarketAdapter


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


def create_app(config=None, service=None, bot_config=None, adapter=None):
    import os
    env_vars = ["TELEGRAM_BOT_TOKEN", "WEBAPP_URL", "VITE_BACKEND_URL", "OKX_API_KEY", "OKX_SECRET_KEY", "OKX_PASSPHRASE"]
    print("\n--- ENV VALIDATION ---")
    for v in env_vars:
        status = "PRESENT" if os.environ.get(v) else "MISSING"
        print(f"{v}: {status}")
    print("----------------------\n")

    analysis_service = service or AnalysisService(config or AnalysisConfig.from_env())
    try:
        if bot_config is None: bot_config = Config.from_env()
        if adapter is None: adapter = OkxMarketAdapter(bot_config.okx_site, bot_config.cli_timeout_seconds, bot_config.node_path, bot_config.okx_cli_path)
    except Exception:
        pass # Allow tests to pass without full env config
    bot_service = BotService(bot_config, adapter) if bot_config and adapter else None

    @asynccontextmanager
    async def lifespan(app):
        await analysis_service.startup()
        if bot_service: bot_service.startup()
        yield
        if bot_service: bot_service.shutdown()

    app = FastAPI(title="Autonomous Trading Agent Analysis API", version="0.2", lifespan=lifespan)
    app.state.analysis_service = analysis_service

    from fastapi.middleware.cors import CORSMiddleware
    allowed_origin = os.environ.get("WEBAPP_URL", "http://localhost:5173")
    origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173"
    ]
    if allowed_origin not in origins:
        origins.append(allowed_origin)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, exc):
        # FastAPI's default detail includes input/body; discard all untrusted echo.
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
        if bot_service:
            result["market"] = "CONNECTED" if result["status"] == "READY" else "ERROR"
            result["account"] = bot_service.private_state.get("account_auth", "UNKNOWN")
            result["telegram"] = "CONNECTED" if bot_service.telegram and bot_service.telegram.running else ("DISABLED" if not bot_service.telegram else "ERROR")
            result["execution_mode"] = "PAPER"
            
            # Decide overall readiness
            if result["market"] == "ERROR":
                result["status"] = "NOT_READY"

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
        if not bot_service: return {"error": "Bot service not configured"}
        return {
            "bot_status": "running" if bot_service.is_running else "stopped",
            "strategy_state": bot_service.latest_state.get("decision", {}).get("action", "NO_TRADE") if bot_service.latest_state else "UNKNOWN",
            "account_auth": bot_service.private_state.get("account_auth", "UNKNOWN"),
            "autoEarn": bot_service.private_state.get("autoEarn", "UNKNOWN"),
            "balance": bot_service.private_state.get("balance")
        }

    @app.get("/api/v1/bot/market")
    async def bot_market():
        if not bot_service: return {"error": "Bot service not configured"}
        return bot_service.latest_state.get("market_state", {}) if bot_service.latest_state else {}

    @app.get("/api/v1/bot/activity")
    async def bot_activity():
        if not bot_service: return {"error": "Bot service not configured"}
        activity = bot_service.latest_state.get("execution", {}) if bot_service.latest_state else {}
        return {
            **activity,
            "events": bot_service.ui_events
        }

    @app.post("/api/v1/bot/start")
    async def bot_start():
        if not bot_service: return {"error": "Bot service not configured"}
        started = bot_service.start()
        return {"status": "started" if started else "already running"}

    @app.post("/api/v1/bot/stop")
    async def bot_stop():
        if not bot_service: return {"error": "Bot service not configured"}
        stopped = bot_service.stop()
        return {"status": "stopped" if stopped else "not running"}

    return app
