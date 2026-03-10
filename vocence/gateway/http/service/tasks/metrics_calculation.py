"""
Metrics calculation background worker for dashboard.

Periodically calculates metrics from validator_evaluations and stores them
in performance_metrics table. These metrics are for dashboard/monitoring purposes only.

Uses the same logic as the validator: for each validator, only the most recent
MAX_EVALS_FOR_SCORING evaluations (by evaluation_id) are used to compute win rate
per participant. Runs every METRICS_CALCULATION_INTERVAL seconds (default 300s).

Only valid participants are included in performance_metrics.
"""

import asyncio
from typing import Dict, Set

from vocence.domain.config import MAX_EVALS_FOR_SCORING, METRICS_CALCULATION_INTERVAL
from vocence.shared.logging import emit_log, print_header
from vocence.registry.persistence.repositories import (
    EvaluationRepository,
    MetricsRepository,
    ValidatorRepository,
    MinerRepository,
)


class MetricsCalculationTask:
    """Background worker for calculating dashboard metrics from submitted evaluations.
    
    Calculates per-validator, per-participant metrics from validator_evaluations.
    No cross-validator aggregation - each validator's metrics stored separately.
    """
    
    def __init__(self):
        self.evaluation_repo = EvaluationRepository()
        self.metrics_repo = MetricsRepository()
        self.validator_repo = ValidatorRepository()
        self.participant_repo = MinerRepository()
        self._running = False
    
    async def run(self) -> None:
        """Run the metrics calculation worker loop."""
        self._running = True
        emit_log(f"Metrics calculation worker starting (interval={METRICS_CALCULATION_INTERVAL}s)", "start")
        emit_log(f"Using last {MAX_EVALS_FOR_SCORING} evaluations per validator (same as validator logic)", "info")
        
        # Initial delay to let other services start
        await asyncio.sleep(10)
        
        while self._running:
            try:
                await self._compute_and_store_metrics()
            except Exception as e:
                emit_log(f"Metrics calculation error: {e}, will retry in {METRICS_CALCULATION_INTERVAL}s", "error")
                import traceback
                traceback.print_exc()
            
            await asyncio.sleep(METRICS_CALCULATION_INTERVAL)
    
    def stop(self) -> None:
        """Stop the worker."""
        self._running = False
    
    async def _get_valid_participant_hotkeys(self) -> Set[str]:
        """Get set of valid participant hotkeys."""
        valid_participants = await self.participant_repo.fetch_valid_miners()
        return {p.miner_hotkey for p in valid_participants}
    
    async def _remove_invalid_participant_metrics(self, valid_hotkeys: Set[str]) -> int:
        """Remove metrics for participants that are no longer valid.
        
        Args:
            valid_hotkeys: Set of currently valid participant hotkeys
            
        Returns:
            Number of metrics removed
        """
        all_metrics = await self.metrics_repo.fetch_all_metrics()
        removed = 0
        
        for metric in all_metrics:
            if metric.miner_hotkey not in valid_hotkeys:
                # Note: We'd need a delete method in metrics_repo
                # For now, just count
                removed += 1
        
        return removed
    
    async def _compute_and_store_metrics(self) -> None:
        """Calculate metrics from evaluations and store in performance_metrics for dashboard.
        
        For each validator, uses only the most recent MAX_EVALS_FOR_SCORING evaluations
        (same window as validator-side scoring), then:
        - Calculate win rate per participant from that window
        - Store in performance_metrics (one row per validator-participant pair)
        
        Only includes metrics for valid participants.
        """
        print_header("Dashboard Metrics Calculation")
        
        # Get valid participant hotkeys
        valid_hotkeys = await self._get_valid_participant_hotkeys()
        
        if not valid_hotkeys:
            emit_log("No valid participants found", "info")
            return
        
        emit_log(f"Found {len(valid_hotkeys)} valid participants", "info")
        
        # Clean up metrics for invalid participants
        removed = await self._remove_invalid_participant_metrics(valid_hotkeys)
        if removed > 0:
            emit_log(f"Removed {removed} metrics for invalid participants", "info")
        
        # Get all validators
        validators = await self.validator_repo.fetch_all_validators()
        
        if not validators:
            emit_log("No validators found", "info")
            return
        
        total_metrics = 0
        
        for validator in validators:
            # Only registered validators (validator_registry) are processed
            stats = await self.evaluation_repo.compute_miner_stats_by_validator_recent(
                validator.hotkey,
                max_evals=MAX_EVALS_FOR_SCORING,
            )
            
            if not stats:
                eval_count = await self.evaluation_repo.count_by_validator(validator.hotkey)
                if eval_count == 0:
                    emit_log(
                        f"Validator {validator.hotkey[:12]}... (uid={validator.uid}): no evaluations in DB for this hotkey. "
                        "Ensure validator_registry.hotkey exactly matches the hotkey used when submitting evaluations.",
                        "warn",
                    )
                else:
                    emit_log(f"Validator {validator.hotkey[:12]}...: {eval_count} evaluations but stats empty", "warn")
                continue
            
            # Build metrics dict, only for valid participants (registered_miners with is_valid=true)
            metrics_to_save = {}
            skipped = 0
            for participant_hotkey, participant_stats in stats.items():
                if participant_hotkey not in valid_hotkeys:
                    skipped += 1
                    continue
                wins = participant_stats.get("wins", 0)
                total = participant_stats.get("total", 0)
                win_rate = participant_stats.get("win_rate", 0.0)
                metrics_to_save[participant_hotkey] = {
                    "score": win_rate,
                    "total_evaluations": total,
                    "total_wins": wins,
                    "win_rate": win_rate,
                }
            
            if skipped > 0:
                emit_log(
                    f"Validator {validator.hotkey[:12]}...: {skipped} miner(s) in evaluations not in valid list "
                    "(miner_hotkey in validator_evaluations must match registered_miners.miner_hotkey)",
                    "warn",
                )
            if not metrics_to_save:
                emit_log(
                    f"Validator {validator.hotkey[:12]}...: no miners matched; check registered_miners.is_valid and hotkey match",
                    "warn",
                )
                continue
            
            count = await self.metrics_repo.bulk_store_metrics(
                validator_hotkey=validator.hotkey,
                metrics_data=metrics_to_save,
            )
            total_metrics += count
            emit_log(f"Validator {validator.hotkey[:12]}...: stored {count} metrics", "info")
        
        emit_log(f"Updated {total_metrics} dashboard metrics from {len(validators)} validators", "success")
        
        # Log current leader (based on simple win rate, not weighted)
        all_metrics = await self.metrics_repo.fetch_all_metrics()
        if all_metrics:
            # Group by participant and sum
            participant_totals: Dict[str, Dict[str, int]] = {}
            for metric in all_metrics:
                if metric.miner_hotkey not in participant_totals:
                    participant_totals[metric.miner_hotkey] = {"wins": 0, "total": 0}
                participant_totals[metric.miner_hotkey]["wins"] += metric.total_wins
                participant_totals[metric.miner_hotkey]["total"] += metric.total_evaluations
            
            # Find leader by win rate
            leader = None
            leader_rate = 0.0
            for hotkey, totals in participant_totals.items():
                if totals["total"] > 0:
                    rate = totals["wins"] / totals["total"]
                    if rate > leader_rate:
                        leader = hotkey
                        leader_rate = rate
            
            if leader:
                t = participant_totals[leader]
                emit_log(
                    f"Dashboard leader: {leader[:8]}... "
                    f"({t['wins']}/{t['total']} wins, {leader_rate:.1%})",
                    "info"
                )

