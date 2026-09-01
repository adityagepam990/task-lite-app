"""FastAPI application factory, middleware and error handling.

Run it with either:

    uvicorn app.main:app --reload
    python -m app.main            # reads host/port from config.toml
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import __version__
from app.config import get_settings
from app.database import SessionLocal, create_all
from app.errors import AppError
from app.realtime import manager
from app.routers import boards, columns, stats, tasks, ws
from app.schemas.common import ErrorBody, ErrorResponse
from app.seed import seed_if_empty

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s %(name)s: %(message)s",
)
logger = logging.getLogger("tasklite")

settings = get_settings()

API_PREFIX = "/api"


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Create tables and seed starter content before serving requests."""
    create_all()
    logger.info("database ready at %s", settings.database.url)

    if settings.seed.enabled:
        with SessionLocal() as db:
            if seed_if_empty(db):
                logger.info("first run: starter boards created")

    yield
    # Nothing to tear down: SQLite connections are closed per request and the
    # WebSocket registry dies with the process.


def _error_response(
    status_code: int,
    code: str,
    message: str,
    details: Any | None = None,
) -> JSONResponse:
    """Build a response in the shared error envelope."""
    body = ErrorResponse(error=ErrorBody(code=code, message=message, details=details))
    return JSONResponse(status_code=status_code, content=body.model_dump(mode="json"))


def create_app() -> FastAPI:
    """Build and configure the application."""
    app = FastAPI(
        title=settings.app.name,
        version=__version__,
        description=(
            "Local-first personal Kanban API.\n\n"
            "Every response uses the same envelope: `{success, data, error}`. "
            "Successful calls populate `data`; failures populate `error` with a "
            "stable `code` you can branch on."
        ),
        lifespan=lifespan,
        # Envelope-aware default so the generated docs show the real error shape.
        responses={
            400: {"model": ErrorResponse, "description": "Invalid request"},
            404: {"model": ErrorResponse, "description": "Not found"},
            409: {"model": ErrorResponse, "description": "Conflict"},
            422: {"model": ErrorResponse, "description": "Validation failed"},
        },
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors.allow_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- error handling ---------------------------------------------------
    # Four handlers, one envelope. Anything that reaches a client as an error
    # goes through exactly one of these.

    @app.exception_handler(AppError)
    async def handle_app_error(_request: Request, exc: AppError) -> JSONResponse:
        """Expected business-rule failures (404 / 409 / 422)."""
        return _error_response(exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Pydantic rejected the request body or query params.

        The per-field errors are flattened to ``{"field": "reason"}``, which is
        what the frontend's form code wants; FastAPI's raw list is harder to use
        and leaks internal locator tuples.
        """
        fields: dict[str, str] = {}
        for error in exc.errors():
            # loc looks like ("body", "title") -- drop the source segment.
            location = [str(part) for part in error["loc"][1:]] or [str(error["loc"][0])]
            fields[".".join(location)] = error["msg"]

        return _error_response(
            422,
            "validation_error",
            "The request contains invalid values.",
            {"fields": fields},
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(
        _request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        """404s from unmatched routes, 405s from wrong methods, and similar."""
        codes = {404: "not_found", 405: "method_not_allowed"}
        return _error_response(
            exc.status_code,
            codes.get(exc.status_code, "http_error"),
            str(exc.detail),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(_request: Request, exc: Exception) -> JSONResponse:
        """Anything unplanned.

        The exception text is only echoed back when debug is on, so a production
        run cannot leak a stack trace or a file path to a client.
        """
        logger.exception("unhandled error")
        return _error_response(
            500,
            "internal_error",
            str(exc) if settings.app.debug else "An unexpected error occurred.",
        )

    # --- routes -----------------------------------------------------------

    @app.get("/api/health", tags=["meta"], summary="Liveness and diagnostics")
    async def health() -> dict[str, Any]:
        """Report that the API is up, plus a couple of useful diagnostics.

        Deliberately outside the envelope: a health check is read by humans and
        uptime tools, not by the typed client.
        """
        return {
            "status": "ok",
            "version": __version__,
            "database": settings.database.url,
            "websocket_clients": manager.connection_count,
        }

    app.include_router(boards.router, prefix=API_PREFIX)
    app.include_router(columns.router, prefix=API_PREFIX)
    app.include_router(tasks.router, prefix=API_PREFIX)
    app.include_router(stats.router, prefix=API_PREFIX)
    # No prefix: the socket lives at /ws, not /api/ws.
    app.include_router(ws.router)

    return app


app = create_app()


def main() -> None:
    """Run the development server using host/port from configuration."""
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.server.host,
        port=settings.server.port,
        reload=True,
    )


if __name__ == "__main__":
    main()
