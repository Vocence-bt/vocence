"""
Evaluations endpoints for Vocence Service.

Provides endpoints for submitting evaluation metadata.
"""

from typing import Annotated, List

from fastapi import APIRouter, Depends, HTTPException

from vocence.gateway.http.service.auth.signature import verify_validator_signature
from vocence.gateway.http.service.models import (
    EvaluationSubmission,
    EvaluationResponse,
    LiveEvaluationStartedRequest,
)
from vocence.registry.persistence.repositories.evaluation_repository import EvaluationRepository
from vocence.shared.logging import emit_log


router = APIRouter()
evaluation_repo = EvaluationRepository()

MAX_BATCH_SIZE = 100  # Maximum evaluations allowed per batch request


@router.post("/live")
async def live_evaluation_started(
    body: LiveEvaluationStartedRequest,
    hotkey: Annotated[str, Depends(verify_validator_signature)],
) -> dict:
    """Notify that an evaluation has started (prompt generated, miners about to be evaluated).

    Used by the dashboard validation status bar to show "pending". When the same
    validator submits results via POST /evaluations or POST /evaluations/batch
    for this evaluation_id, the pending row is removed.
    """
    await evaluation_repo.add_live_pending(
        validator_hotkey=hotkey,
        evaluation_id=body.evaluation_id,
        prompt_summary=body.prompt_summary,
        miner_hotkeys=body.miner_hotkeys or None,
    )
    emit_log(
        f"Live evaluation pending: validator={hotkey[:12]}..., eval_id={body.evaluation_id}, miners={len(body.miner_hotkeys or [])}",
        "info",
    )
    return {"ok": True}


@router.post("", response_model=EvaluationResponse)
async def submit_evaluation(
    evaluation: EvaluationSubmission,
    hotkey: Annotated[str, Depends(verify_validator_signature)],
) -> EvaluationResponse:
    """Submit evaluation metadata.
    
    Validators call this endpoint after evaluating a sample to store
    the metadata and result in the centralized database.
    
    Args:
        evaluation: Evaluation submission data
        
    Requires validator signature authentication.
    
    Returns:
        Created evaluation record
    """
    result = await evaluation_repo.store_evaluation(
        validator_hotkey=hotkey,
        evaluation_id=evaluation.evaluation_id,
        miner_hotkey=evaluation.participant_hotkey,
        s3_bucket=evaluation.s3_bucket,
        s3_prefix=evaluation.s3_prefix,
        wins=evaluation.wins,
        prompt=evaluation.prompt,
        confidence=evaluation.confidence,
        reasoning=evaluation.reasoning,
        original_audio_url=evaluation.original_audio_url,
        generated_audio_url=evaluation.generated_audio_url,
    )
    await evaluation_repo.delete_live_pending(hotkey, evaluation.evaluation_id)

    return EvaluationResponse(
        id=result.id,
        evaluation_id=result.evaluation_id,
        participant_hotkey=result.miner_hotkey,
        prompt=result.prompt,
        s3_bucket=result.s3_bucket,
        s3_prefix=result.s3_prefix,
        wins=result.wins,
        confidence=result.confidence,
        reasoning=result.reasoning,
        original_audio_url=result.original_audio_url,
        generated_audio_url=result.generated_audio_url,
        evaluated_at=result.evaluated_at,
    )


@router.post("/batch", response_model=List[EvaluationResponse])
async def submit_evaluations_batch(
    evaluations: List[EvaluationSubmission],
    hotkey: Annotated[str, Depends(verify_validator_signature)],
) -> List[EvaluationResponse]:
    """Submit multiple evaluations in batch.
    
    Validators can use this endpoint to submit multiple evaluations at once.
    Limited to 100 evaluations per request.
    
    Args:
        evaluations: List of evaluation submissions (max 100)
        
    Requires validator signature authentication.
    
    Returns:
        List of created evaluation records
        
    Raises:
        HTTPException: If batch size exceeds limit
    """
    if len(evaluations) > MAX_BATCH_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"Batch size exceeds limit of {MAX_BATCH_SIZE} evaluations",
        )
    
    results = []
    seen_eval_ids = set()
    for evaluation in evaluations:
        result = await evaluation_repo.store_evaluation(
            validator_hotkey=hotkey,
            evaluation_id=evaluation.evaluation_id,
            miner_hotkey=evaluation.participant_hotkey,
            s3_bucket=evaluation.s3_bucket,
            s3_prefix=evaluation.s3_prefix,
            wins=evaluation.wins,
            prompt=evaluation.prompt,
            confidence=evaluation.confidence,
            reasoning=evaluation.reasoning,
            original_audio_url=evaluation.original_audio_url,
            generated_audio_url=evaluation.generated_audio_url,
        )
        seen_eval_ids.add(evaluation.evaluation_id)
        results.append(EvaluationResponse(
            id=result.id,
            evaluation_id=result.evaluation_id,
            participant_hotkey=result.miner_hotkey,
            prompt=result.prompt,
            s3_bucket=result.s3_bucket,
            s3_prefix=result.s3_prefix,
            wins=result.wins,
            confidence=result.confidence,
            reasoning=result.reasoning,
            original_audio_url=result.original_audio_url,
            generated_audio_url=result.generated_audio_url,
            evaluated_at=result.evaluated_at,
        ))
    for eval_id in seen_eval_ids:
        await evaluation_repo.delete_live_pending(hotkey, eval_id)

    return results

