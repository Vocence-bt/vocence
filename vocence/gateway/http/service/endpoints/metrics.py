"""
Metrics endpoints for Vocence Service (Dashboard).

Provides endpoints for retrieving aggregated metrics for dashboard/monitoring.
These metrics are calculated server-side from submitted evaluation metadata.

Note: These metrics are for dashboard display only. Validators calculate
their own metrics from their own S3 buckets for weight setting.
"""

from datetime import datetime
from typing import Dict, Any

from fastapi import APIRouter

from vocence.gateway.http.service.models import AggregatedMetricsResponse
from vocence.registry.persistence.repositories.metrics_repository import MetricsRepository
from vocence.registry.persistence.repositories.evaluation_repository import EvaluationRepository


router = APIRouter()
metrics_repo = MetricsRepository()
evaluation_repo = EvaluationRepository()


@router.get("", response_model=AggregatedMetricsResponse)
async def get_aggregated_metrics() -> AggregatedMetricsResponse:
    """Get aggregated dashboard metrics across all validators.
    
    Metrics are calculated server-side from submitted evaluation metadata.
    This is for dashboard/monitoring purposes only.
    
    This endpoint is public (no authentication required).
    
    Returns:
        Aggregated metrics for all participants (dashboard view)
    """
    metrics = await metrics_repo.compute_aggregated_metrics()
    all_metrics = await metrics_repo.fetch_all_metrics()
    
    # Get unique validator count
    validators = set(m.validator_hotkey for m in all_metrics)
    
    # Find most recent update (filter out None values)
    valid_timestamps = [m.updated_at for m in all_metrics if m.updated_at is not None]
    latest_update = max(valid_timestamps, default=datetime.utcnow())
    
    return AggregatedMetricsResponse(
        metrics=metrics,
        total_validators=len(validators),
        updated_at=latest_update,
    )

