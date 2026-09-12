"""Transport-only product API. Run uvicorn agent_trading.api:create_app --factory."""

import asyncio
from contextlib import asynccontextmanager
from typing import Annotated
from uuid import UUID

from fastapi import FastAPI, Header, Query, Response
from fastapi.exceptions import RequestValidationError, ResponseValidationError
from fastapi.responses import JSONResponse

from .analysis_api_models import AnalysisReport, AnalysisRequest, HistoryPage
from .analysis_config import AnalysisConfig
from .analysis_repository import RepositoryError
from .analysis_service import AnalysisService, ServiceError


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


def create_app(config=None, service=None):
    analysis_service = service or AnalysisService(config or AnalysisConfig.from_env())

    @asynccontextmanager
    async def lifespan(app):
        await analysis_service.startup()
        yield

    app = FastAPI(title="Market Analysis Copilot", version="0.1", lifespan=lifespan)
    app.state.analysis_service = analysis_service

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
        response.status_code = 200 if result["status"] == "READY" else 503
        return result

    @app.post("/api/v1/analyses", response_model=AnalysisReport, status_code=201)
    async def analyze(body: AnalysisRequest, response: Response,
                      idempotency_key: Annotated[str | None, Header()] = None):
        result = await analysis_service.analyze(body.symbol, idempotency_key=idempotency_key)
        response.status_code = 201 if result.created else 200
        return result.report

    @app.get("/api/v1/analyses", response_model=HistoryPage)
    async def history(limit: Annotated[int, Query(ge=1, le=50)] = 20,
                      offset: Annotated[int, Query(ge=0, le=10000)] = 0):
        return await asyncio.to_thread(analysis_service.repository.history, limit, offset)

    @app.get("/api/v1/analyses/{analysis_id}", response_model=AnalysisReport)
    async def by_id(analysis_id: UUID):
        result = await asyncio.to_thread(analysis_service.repository.get, str(analysis_id))
        if result is None:
            raise ServiceError("ANALYSIS_NOT_FOUND", 404, str(analysis_id))
        return result

    return app
