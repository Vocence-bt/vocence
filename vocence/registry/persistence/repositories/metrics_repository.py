"""
Performance Metrics Repository.

Handles per-validator metrics storage. Metrics are calculated server-side
from ValidatorEvaluation data by the metrics aggregation task.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from sqlalchemy import select, delete, func

from vocence.registry.persistence.connection import acquire_session
from vocence.registry.persistence.schema import PerformanceMetrics
from vocence.shared.logging import emit_log


class MetricsRepository:
    """Repository for performance_metrics table.
    
    Stores per-validator metrics calculated from validator_evaluations.
    """
    
    async def store_metrics(
        self,
        miner_hotkey: str,
        validator_hotkey: str,
        score: float,
        total_evaluations: int = 0,
        total_wins: int = 0,
        win_rate: float = 0.0,
    ) -> PerformanceMetrics:
        """Save or update performance metrics.
        
        Args:
            miner_hotkey: Miner's hotkey
            validator_hotkey: Validator's hotkey
            score: Calculated score
            total_evaluations: Total evaluations
            total_wins: Total wins
            win_rate: Win rate percentage
            
        Returns:
            PerformanceMetrics instance
        """
        async with acquire_session() as session:
            query = select(PerformanceMetrics).where(
                PerformanceMetrics.miner_hotkey == miner_hotkey,
                PerformanceMetrics.validator_hotkey == validator_hotkey,
            )
            result = await session.execute(query)
            existing = result.scalar_one_or_none()
            
            if existing:
                existing.score = score
                existing.total_evaluations = total_evaluations
                existing.total_wins = total_wins
                existing.win_rate = win_rate
                existing.updated_at = datetime.now(timezone.utc)
                metrics = existing
            else:
                metrics = PerformanceMetrics(
                    miner_hotkey=miner_hotkey,
                    validator_hotkey=validator_hotkey,
                    score=score,
                    total_evaluations=total_evaluations,
                    total_wins=total_wins,
                    win_rate=win_rate,
                )
                session.add(metrics)
            
            await session.flush()
            return metrics
    
    async def bulk_store_metrics(
        self,
        validator_hotkey: str,
        metrics_data: Dict[str, Dict[str, Any]],
    ) -> int:
        """Batch save metrics for a validator.
        
        Args:
            validator_hotkey: Validator's hotkey
            metrics_data: Dict mapping miner_hotkey to {score, total_evaluations, total_wins, win_rate}
            
        Returns:
            Number of metrics saved
        """
        count = 0
        for miner_hotkey, data in metrics_data.items():
            await self.store_metrics(
                miner_hotkey=miner_hotkey,
                validator_hotkey=validator_hotkey,
                score=data.get("score", 0.0),
                total_evaluations=data.get("total_evaluations", 0),
                total_wins=data.get("total_wins", 0),
                win_rate=data.get("win_rate", 0.0),
            )
            count += 1
        return count
    
    async def fetch_by_validator(
        self,
        validator_hotkey: str,
    ) -> List[PerformanceMetrics]:
        """Get all metrics for a validator."""
        async with acquire_session() as session:
            query = select(PerformanceMetrics).where(
                PerformanceMetrics.validator_hotkey == validator_hotkey
            )
            result = await session.execute(query)
            return list(result.scalars().all())
    
    async def fetch_by_miner(
        self,
        miner_hotkey: str,
    ) -> List[PerformanceMetrics]:
        """Get all metrics for a miner from all validators."""
        async with acquire_session() as session:
            query = select(PerformanceMetrics).where(
                PerformanceMetrics.miner_hotkey == miner_hotkey
            )
            result = await session.execute(query)
            return list(result.scalars().all())
    
    async def fetch_all_metrics(self) -> List[PerformanceMetrics]:
        """Get all performance metrics."""
        async with acquire_session() as session:
            query = select(PerformanceMetrics)
            result = await session.execute(query)
            return list(result.scalars().all())
    
    async def compute_aggregated_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Get aggregated metrics across all validators.
        
        Returns:
            Dict mapping miner_hotkey to aggregated stats
        """
        async with acquire_session() as session:
            query = (
                select(
                    PerformanceMetrics.miner_hotkey,
                    func.avg(PerformanceMetrics.score).label("avg_score"),
                    func.sum(PerformanceMetrics.total_evaluations).label("total_evaluations"),
                    func.sum(PerformanceMetrics.total_wins).label("total_wins"),
                    func.count(PerformanceMetrics.validator_hotkey).label("validator_count"),
                )
                .group_by(PerformanceMetrics.miner_hotkey)
            )
            result = await session.execute(query)
            rows = result.all()
            
            aggregated = {}
            for row in rows:
                total_evaluations = row.total_evaluations or 0
                total_wins = row.total_wins or 0
                aggregated[row.miner_hotkey] = {
                    "avg_score": float(row.avg_score or 0),
                    "total_evaluations": total_evaluations,
                    "total_wins": total_wins,
                    "win_rate": total_wins / total_evaluations if total_evaluations > 0 else 0.0,
                    "validator_count": row.validator_count,
                }
            
            return aggregated

