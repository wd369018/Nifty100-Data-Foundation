"""Nifty100 FastAPI application (Sprint 6, Day 38).

Run:
    uvicorn src.api.main:app --port 8000
"""

import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from src.api.routers import (
    companies,
    documents,
    health,
    peers,
    portfolio,
    screener,
    sectors,
    valuation,
)

logger = logging.getLogger("uvicorn.access")


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    app = FastAPI(
        title="Nifty100 Data Foundation API",
        description="REST API for the Nifty 100 analytics platform (Sprint 6).",
        version="0.6.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        """Log method, path and response time for every request."""
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "%s %s -> %s (%.1f ms)",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        return response

    app.include_router(health.router, prefix="/api/v1")
    app.include_router(companies.router, prefix="/api/v1")
    app.include_router(screener.router, prefix="/api/v1")
    app.include_router(sectors.router, prefix="/api/v1")
    app.include_router(peers.router, prefix="/api/v1")
    app.include_router(valuation.router, prefix="/api/v1")
    app.include_router(portfolio.router, prefix="/api/v1")
    app.include_router(documents.router, prefix="/api/v1")

    # Pre-warm the feature-frame cache at startup so the heaviest
    # computation happens once, before any request is served.
    from src.api import cached_feature_frame

    cached_feature_frame()

    @app.get("/")
    def root():
        """Service index — points at the API docs."""
        return {
            "service": "Nifty100 Data Foundation API",
            "docs": "/docs",
            "openapi": "/openapi.json",
        }

    return app


app = create_app()
