"""
FastAPI application for Vocence Service.

Provides centralized service for validators to:
- Get list of valid participants
- Submit evaluation metadata
- Submit metrics
- Manage blocked entities
"""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from vocence import __version__
from vocence.shared.logging import emit_log, print_header
from vocence.registry.persistence.connection import establish_connection, terminate_connection
from vocence.gateway.http.service.endpoints.participants import router as participants_router
from vocence.gateway.http.service.endpoints.evaluations import router as evaluations_router
from vocence.gateway.http.service.endpoints.metrics import router as metrics_router
from vocence.gateway.http.service.endpoints.blocklist import router as blocklist_router
from vocence.gateway.http.service.endpoints.status import router as status_router
from vocence.gateway.http.service.tasks import (
    ParticipantValidationTask,
    MetricsCalculationTask,
)


# Global task references
_background_workers: list[asyncio.Task] = []


@asynccontextmanager
async def application_lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager.
    
    Initializes database and starts background workers on startup.
    Cleans up resources on shutdown.
    """
    print_header("Vocence Service Starting")
    
    # Initialize database
    await establish_connection()
    emit_log("Database initialized", "success")
    
    # Create tables if needed
    from vocence.registry.persistence.connection import initialize_schema
    await initialize_schema()
    
    # Start background workers
    validation_worker = ParticipantValidationTask()
    metrics_worker = MetricsCalculationTask()
    
    _background_workers.append(asyncio.create_task(validation_worker.run()))
    _background_workers.append(asyncio.create_task(metrics_worker.run()))
    emit_log("Background workers started (validation, metrics)", "success")
    
    yield
    
    # Cleanup
    emit_log("Shutting down...", "info")
    
    # Cancel background workers
    for worker in _background_workers:
        worker.cancel()
        try:
            await worker
        except asyncio.CancelledError:
            pass
    
    # Close database
    await terminate_connection()
    emit_log("Shutdown complete", "success")


# Create FastAPI application
app = FastAPI(
    title="Vocence Service",
    description="Centralized service for Vocence voice intelligence subnet validators",
    version=__version__,
    lifespan=application_lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(status_router, tags=["Status"])
app.include_router(participants_router, prefix="/participants", tags=["Participants"])
app.include_router(evaluations_router, prefix="/evaluations", tags=["Evaluations"])
app.include_router(metrics_router, prefix="/metrics", tags=["Metrics"])
app.include_router(blocklist_router, prefix="/blocklist", tags=["Blocklist"])


def run_service() -> None:
    """Entry point for running the service."""
    import uvicorn
    from vocence.domain.config import SERVICE_HOST, SERVICE_PORT, SERVICE_RELOAD

    uvicorn.run(
        "vocence.gateway.http.service.app:app",
        host=SERVICE_HOST,
        port=SERVICE_PORT,
        reload=SERVICE_RELOAD,
    )


if __name__ == "__main__":
    run_service()

